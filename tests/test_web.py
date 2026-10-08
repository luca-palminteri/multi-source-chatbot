"""Boundary and lifecycle regressions; the optional server extra is required."""
import asyncio
from contextlib import asynccontextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys
import unittest
from unittest.mock import patch

AVAILABLE = sys.version_info >= (3, 12) and importlib.util.find_spec("langgraph_cli") is not None


@unittest.skipUnless(AVAILABLE, "Install the web extra")
class WebBoundaryTests(unittest.TestCase):
    def body(self):
        return {"assistant_id": "assistant", "input": {"messages": [
            {"type": "human", "content": [{"type": "text", "text": "Hello"}], "id": "new"}]}}

    def test_validation_prevents_authority_injection_and_replay(self):
        from assistant.web import validate_submission
        for role in ("system", "ai", "assistant", "tool", "remove"):
            body = self.body()
            body["input"]["messages"][0]["type"] = role
            with self.subTest(role=role), self.assertRaises(ValueError):
                validate_submission(body)
        for key, value in (("checkpoint", {}), ("command", {"resume": True}),
                           ("config", {"configurable": {"employee_id": "emp-002"}}),
                           ("multitask_strategy", "enqueue"), ("on_disconnect", "cancel")):
            body = self.body()
            body[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_submission(body)
        for text in ("", "   ", "a" * 4001):
            body = self.body()
            body["input"]["messages"][0]["content"] = text
            with self.assertRaises(ValueError):
                validate_submission(body)
        body = self.body()
        validate_submission(body)
        self.assertEqual(body["config"], {"recursion_limit": 24})
        self.assertEqual(body["multitask_strategy"], "reject")

    def test_ledger_survives_restart_and_rejects_duplicate_runs(self):
        from assistant.web import ExecutionLedger
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            first = ExecutionLedger(path)
            first.submission("message")
            first.begin("thread", "run")
            restarted = ExecutionLedger(path)
            with self.assertRaises(ValueError):
                restarted.submission("message")
            with self.assertRaises(ValueError):
                restarted.begin("thread", "other-run")
            restarted.begin("independent-thread", "independent-run")
            first.finish("thread")
            with self.assertRaises(ValueError):
                restarted.begin("thread", "run")
            restarted.begin("thread", "new-run")


@unittest.skipUnless(AVAILABLE, "Install the web extra")
class WebLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_internal_planning_and_synthesis_are_hidden_from_message_stream(self):
        import json
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        from langchain_core.runnables import RunnableLambda
        from assistant.information import InformationPipeline
        from assistant.web import graph, SchemaModel
        from web_fixture import Model

        class InformationModel(SchemaModel):
            def with_structured_output(self, schema):
                return self | RunnableLambda(lambda message: schema.model_validate_json(message.content))

            def _generate(self, messages, **kwargs):
                if "Plan read-only" in messages[0].content:
                    content = json.dumps({"document_query": "VPN", "graph_queries": [
                        {"entity_id": "", "entity_type": "service", "name": "VPN", "steps": []}]})
                else:
                    content = "The available evidence does not establish an answer."
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

        @asynccontextmanager
        async def connection(settings):
            yield []

        documents = SimpleNamespace(search=lambda *args, **kwargs: [])
        retrieval = SimpleNamespace(find_entities=lambda **kwargs: [])
        pipeline = InformationPipeline(documents, retrieval, InformationModel())
        with tempfile.TemporaryDirectory() as directory:
            settings = SimpleNamespace(sqlite_path=Path(directory) / "db.sqlite3", demo_employee_id="emp-001")
            with patch("assistant.web.Settings.load", return_value=settings), \
                 patch("assistant.web.connect_action_tools", connection), \
                 patch("assistant.web.chat_provider", return_value=Model()), \
                 patch("assistant.web.create_information_pipeline", return_value=pipeline):
                config = {"configurable": {"thread_id": "stream", "run_id": "stream"}}
                async with graph(config, SimpleNamespace(execution_runtime=True)) as workflow:
                    events = [event async for event in workflow.astream(
                        {"messages": [("human", "lookup-test")]}, config, stream_mode="messages", subgraphs=True)]
        nodes = {metadata["langgraph_node"] for _, (_, metadata) in events}
        self.assertIn("agent", nodes)
        self.assertNotIn("plan", nodes)
        self.assertNotIn("synthesize", nodes)

    async def test_mcp_json_text_is_preserved_for_upstream_rendering(self):
        from langchain_core.tools import StructuredTool
        from assistant.web import browser_action_tool

        async def action(value: str):
            return [{"type": "text", "text": '{"ok":true,"request":{"id":"req-test"}}'}]

        discovered = StructuredTool.from_function(coroutine=action, name="new_action", description="Discovered schema")
        adapted = browser_action_tool(discovered)
        self.assertEqual(adapted.args_schema.model_json_schema(), discovered.args_schema.model_json_schema())
        self.assertEqual(await adapted.ainvoke({"value": "test"}), '{"ok":true,"request":{"id":"req-test"}}')

    async def test_http_rejection_has_cors_and_blocks_injected_thread_state(self):
        import httpx
        from assistant.web import app
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/threads", json={"supersteps": [{"updates": []}]},
                                         headers={"Origin": "http://localhost:3000"})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:3000")
            response = await client.post("/threads/t/runs/r/cancel?action=%72ollback")
            self.assertEqual(response.status_code, 400)

    async def test_real_mcp_process_exits_after_completion_cancellation_and_init_failure(self):
        import mcp.client.stdio as stdio
        from assistant.agent import connect_action_tools
        from assistant.config import Settings
        from assistant.storage import seed_database
        processes = []
        original = stdio._create_platform_compatible_process

        async def spawn(**kwargs):
            process = await original(**kwargs)
            processes.append(process)
            return process

        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "db.sqlite3"
            seed_database(database, root / "data/seed.json")
            settings = Settings(root, database, Path(directory) / "index", "google", "unused",
                                "google", "unused", "emp-001", "stdio")
            with patch.object(stdio, "_create_platform_compatible_process", spawn):
                async with connect_action_tools(settings) as tools:
                    self.assertIn("create_service_request", [tool.name for tool in tools])
                with self.assertRaises(BaseException):
                    async with connect_action_tools(settings):
                        raise asyncio.CancelledError()
                with patch("mcp.ClientSession.initialize", side_effect=RuntimeError("init failed")):
                    with self.assertRaises(Exception):
                        async with connect_action_tools(settings):
                            self.fail("Initialization should fail")
        self.assertEqual(len(processes), 3)
        self.assertTrue(all(process.returncode is not None for process in processes))

    async def test_factory_closes_resources_and_keeps_failed_thread_blocked(self):
        from assistant.web import graph, ExecutionLedger
        closed = []

        @asynccontextmanager
        async def connection(settings):
            try:
                yield []
            finally:
                closed.append(True)

        with tempfile.TemporaryDirectory() as directory:
            settings = SimpleNamespace(sqlite_path=Path(directory) / "db.sqlite3", demo_employee_id="emp-001")
            runtime = SimpleNamespace(execution_runtime=True)
            pipeline = SimpleNamespace(as_tool=lambda: object())
            with patch("assistant.web.Settings.load", return_value=settings), \
                 patch("assistant.web.connect_action_tools", connection), \
                 patch("assistant.web.chat_provider", return_value=object()), \
                 patch("assistant.web.create_information_pipeline", return_value=pipeline), \
                 patch("assistant.web.build_graph", return_value=object()):
                for failure in (RuntimeError("secret"), asyncio.CancelledError()):
                    config = {"configurable": {"thread_id": str(len(closed)), "run_id": str(len(closed))}}
                    with self.assertRaises(type(failure)):
                        async with graph(config, runtime):
                            raise failure
                    with self.assertRaises(ValueError):
                        ExecutionLedger(settings.sqlite_path.with_suffix(".web-executions.sqlite3")).begin(config["configurable"]["thread_id"])
                self.assertEqual(len(closed), 2)
                with patch("assistant.web.TURN_TIMEOUT", 0.01):
                    with self.assertRaises(RuntimeError):
                        async with graph({"configurable": {"thread_id": "timeout", "run_id": "timeout"}}, runtime):
                            await asyncio.sleep(1)
                self.assertEqual(len(closed), 3)
                with self.assertRaises(ValueError):
                    ExecutionLedger(settings.sqlite_path.with_suffix(".web-executions.sqlite3")).begin("timeout")

    async def test_schema_inspection_closes_mcp_without_providers(self):
        from assistant.web import graph
        closed = []

        @asynccontextmanager
        async def connection(settings):
            try:
                yield []
            finally:
                closed.append(True)

        runtime = SimpleNamespace(execution_runtime=None)
        with patch("assistant.web.connect_action_tools", connection), \
             patch("assistant.web.chat_provider", side_effect=AssertionError("No paid calls")), \
             patch("assistant.web.create_information_pipeline", side_effect=AssertionError("No paid calls")):
            async with graph({}, runtime) as workflow:
                self.assertIn("messages", workflow.get_input_jsonschema()["properties"])
        self.assertEqual(closed, [True])
