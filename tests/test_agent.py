from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from assistant.agent import AgentSession


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_failure_keeps_partial_trace_and_blocks_retry(self):
        class Workflow:
            async def astream(self, *args, **kwargs):
                yield {"agent": {"messages": [SimpleNamespace(type="ai", tool_calls=[
                    {"name": "new_action", "args": {}, "id": "call-1"}])]}}
                raise ConnectionError("transport lost")
        session = AgentSession(Workflow(), ["new_action"])
        result = await session.ask("Perform action")
        self.assertFalse(result["ok"])
        self.assertEqual(result["trace"][0]["name"], "new_action")
        self.assertEqual(result["trace"][-1]["error_type"], "ConnectionError")
        self.assertFalse((await session.ask("Try again"))["ok"])

    async def test_provider_read_timeout_is_reported_as_timeout(self):
        class ReadTimeout(Exception):
            pass
        class Workflow:
            async def astream(self, *args, **kwargs):
                raise ReadTimeout("secret request URL")
                yield {}
        result = await AgentSession(Workflow(), []).ask("Hello")
        self.assertFalse(result["ok"])
        self.assertIn("timed out", result["answer"])
        self.assertEqual(result["trace"][-1]["error_type"], "ReadTimeout")
        self.assertNotIn("secret", result["answer"])

    async def test_timeout_is_bounded(self):
        import asyncio
        class Workflow:
            async def astream(self, *args, **kwargs):
                await asyncio.sleep(1)
                yield {}
        session = AgentSession(Workflow(), [], timeout=0.01)
        self.assertFalse((await session.ask("Hello"))["ok"])

    async def test_context_config_and_tool_results_are_preserved(self):
        class Workflow:
            configs = []
            async def astream(self, inputs, config, **kwargs):
                self.configs.append(config)
                yield {"tools": {"messages": [SimpleNamespace(type="tool", name="new_action",
                    tool_call_id="1", status="error", content='{"ok":false}')]}}
                yield {"agent": {"messages": [SimpleNamespace(type="ai", content="Action failed", tool_calls=[])]}}
        workflow = Workflow()
        session = AgentSession(workflow, ["new_action"])
        first = await session.ask("Perform action")
        await session.ask("What happened to it?")
        self.assertEqual(workflow.configs[0], workflow.configs[1])
        self.assertEqual(first["trace"][0]["status"], "error")
        self.assertEqual(first["answer"], "Action failed")


class MCPConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_child_uses_explicit_database_and_employee(self):
        import importlib.util
        if not all(importlib.util.find_spec(name) for name in ("mcp", "langchain_mcp_adapters", "langgraph")):
            self.skipTest("Install runtime dependencies for subprocess MCP checks")
        from contextlib import closing
        import sqlite3
        import tempfile
        from unittest.mock import patch
        from assistant.agent import connect_agent
        from assistant.config import Settings
        from assistant.storage import seed_database

        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "isolated.sqlite3"
            seed_database(database, root / "data/seed.json")
            settings = Settings(root, database, Path(directory) / "index", "google", "unused",
                                "google", "unused", "emp-002", "stdio")
            pipeline = SimpleNamespace(as_tool=lambda: object())
            with patch("assistant.agent.build_agent", side_effect=lambda model, info, tools, identity: tools):
                async with connect_agent(settings, model=object(), pipeline=pipeline) as tools:
                    tool = next(tool for tool in tools if tool.name == "create_service_request")
                    await tool.ainvoke({"service_id": "svc-vpn", "summary": "Isolated child test",
                                       "description": "Synthetic configuration test"})
            with closing(sqlite3.connect(database)) as connection:
                rows = connection.execute("SELECT submitter_id FROM service_requests WHERE summary=?",
                                          ("Isolated child test",)).fetchall()
            self.assertEqual(rows, [("emp-002",)])
