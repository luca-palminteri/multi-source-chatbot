import json
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from assistant.agent import AgentSession
from assistant.chat import run_chat


class ChatTests(unittest.IsolatedAsyncioTestCase):
    async def run_script(self, messages, *, failing=False):
        sessions, closed, output, inputs = [], [], [], []

        class Workflow:
            async def astream(self, request, config, **kwargs):
                inputs.append((request["messages"][0][1], config["configurable"]["thread_id"]))
                if failing:
                    raise ConnectionError("credential-secret")
                yield {"tools": {"messages": [SimpleNamespace(
                    type="tool", name="advertised_tool", tool_call_id="1", status="success",
                    content=json.dumps({"sources": {"D1": {"path": "policy.md"}},
                                        "ok": False, "error": "VERSION_CONFLICT"}))]}}
                yield {"agent": {"messages": [SimpleNamespace(
                    type="ai", tool_calls=[], content="Which request do you mean? [D1]")]}}

        @asynccontextmanager
        async def connector(settings):
            session = AgentSession(Workflow(), ["advertised_tool"])
            sessions.append(session)
            try:
                yield session
            finally:
                closed.append(session)

        iterator = iter(messages)
        async def read(prompt):
            try:
                return next(iterator)
            except StopIteration:
                raise EOFError

        code = await run_chat(None, connector=connector, read=read, write=output.append)
        return code, sessions, closed, output, inputs

    async def test_followup_clarification_action_and_fresh_conversation(self):
        messages = ["Who owns VPN?", "Create a request", "The VPN request", "/new", "Hello", "/exit"]
        code, sessions, closed, output, inputs = await self.run_script(messages)
        self.assertEqual(code, 0)
        self.assertEqual([text for text, _ in inputs], [messages[0], messages[1], messages[2], "Hello"])
        self.assertEqual(len({thread for _, thread in inputs[:3]}), 1)
        self.assertNotEqual(inputs[0][1], inputs[3][1])
        self.assertEqual(closed, sessions)
        display = "\n".join(output)
        for expected in ("Which request", "D1", "policy.md", "VERSION_CONFLICT", '"ok": false'):
            self.assertIn(expected, display)

    async def test_invalid_input_and_eof(self):
        code, sessions, closed, output, inputs = await self.run_script([" ", "x" * 4001, "/help", "hello"])
        self.assertEqual(code, 0)
        self.assertEqual([text for text, _ in inputs], ["hello"])
        self.assertEqual(closed, sessions)

    async def test_failure_blocks_further_messages_and_hides_exception(self):
        code, _, _, output, inputs = await self.run_script(["Act", "Retry", "/exit"], failing=True)
        self.assertEqual(code, 0)
        self.assertEqual(len(inputs), 1)
        self.assertNotIn("credential-secret", "\n".join(output))
        self.assertIn("may have committed", "\n".join(output))

    async def test_connection_error_is_sanitized(self):
        @asynccontextmanager
        async def connector(settings):
            raise ConnectionError("credential-secret")
            yield
        output = []
        self.assertEqual(await run_chat(None, connector=connector, write=output.append), 1)
        self.assertNotIn("credential-secret", "\n".join(output))
        self.assertIn("connection failed", output[-1])
