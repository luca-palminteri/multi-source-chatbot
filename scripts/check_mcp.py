"""Real subprocess MCP smoke check using an isolated seeded database."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from assistant.storage import seed_database
from assistant.retrieval.graph import GraphRetriever


def snapshot(database):
    with sqlite3.connect(database) as connection:
        return list(connection.iterdump())


async def check():
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "actions.sqlite3"
        seed_database(database, ROOT / "data/seed.json")
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "assistant.actions.server", "--root", str(ROOT)],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "SQLITE_PATH": str(database),
                 "DEMO_EMPLOYEE_ID": "emp-001", "MCP_TRANSPORT": "stdio"})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                assert {t.name for t in tools} == {"create_service_request", "update_service_request_status", "assign_service_request"}
                assert all(t.inputSchema["additionalProperties"] is False for t in tools)

                async def call(name, args, code=None):
                    before = snapshot(database)
                    result = await session.call_tool(name, args)
                    data = result.structuredContent
                    assert data is not None
                    assert result.isError == (code is not None), result
                    if code:
                        assert data["error"]["code"] == code, data
                        assert snapshot(database) == before, "Failed action changed records"
                    else:
                        assert data["ok"], data
                    return data

                create = {"service_id": "svc-vpn", "summary": "VPN smoke check", "description": "Need remote access."}
                for invalid in [{**create, "submitter_id": "emp-002"}, {**create, "description": " "}, {**create, "summary": 12}, {}]:
                    await call("create_service_request", invalid, "VALIDATION_ERROR")
                await call("create_service_request", {**create, "service_id": "svc-missing"}, "NOT_FOUND")
                await call("update_service_request_status", {
                    "request_id": "req-nonexistent", "status": "in_progress", "expected_version": 1}, "NOT_FOUND")
                request = (await call("create_service_request", create))["request"]
                update = {"request_id": request["id"], "status": "in_progress", "expected_version": 1}
                await call("update_service_request_status", {**update, "status": "resolved"}, "INVALID_TRANSITION")
                await call("update_service_request_status", {**update, "expected_version": True}, "VALIDATION_ERROR")
                updated = (await call("update_service_request_status", update))["request"]
                assert updated["version"] == 2
                await call("update_service_request_status", update, "VERSION_CONFLICT")
                assert GraphRetriever(database).traverse(request["id"], []).paths[0].entities[0].attributes == updated
        # Reconnect to a fresh process to verify durable state and a safe no-op.
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("update_service_request_status", {**update, "expected_version": 2})
                assert not result.isError
                assert result.structuredContent["request"] == updated
                from langchain_mcp_adapters.tools import load_mcp_tools
                discovered = await load_mcp_tools(session)
                assignment = next(tool for tool in discovered if tool.name == "assign_service_request")
                await assignment.ainvoke({"request_id": request["id"], "team_id": "team-it", "expected_version": 2})
                invalid = await session.call_tool("assign_service_request", {"request_id": request["id"], "team_id": "team-product", "expected_version": 2})
                assert invalid.isError and invalid.structuredContent["error"]["code"] == "INVALID_ASSIGNMENT"
        print("MCP discovery, validation, mutations, restart persistence, and graph visibility passed.")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(check(), timeout=60))
