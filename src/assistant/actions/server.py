"""Separate stdio MCP process; no dependency on the informational pipeline."""
import argparse
import asyncio
import json
from typing import Annotated, Literal

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from ..config import Settings
from .store import commit_action, error


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CreateRequest(Input):
    service_id: Annotated[str, StringConstraints(pattern=r"^svc-[A-Za-z0-9_-]+$")]
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class UpdateStatus(Input):
    request_id: Annotated[str, StringConstraints(pattern=r"^req-[A-Za-z0-9_-]+$")]
    status: Literal["open", "in_progress", "resolved", "cancelled"]
    expected_version: int = Field(ge=1)


class AssignRequest(Input):
    request_id: Annotated[str, StringConstraints(pattern=r"^req-[A-Za-z0-9_-]+$")]
    team_id: Annotated[str, StringConstraints(pattern=r"^team-[A-Za-z0-9_-]+$")]
    expected_version: int = Field(ge=1)


TOOLS = {
    "assign_service_request": (AssignRequest, "Assign the configured employee's active request to its service's owning team. Requires known request/team IDs and expected_version from a fresh informational read. On conflict retrieve current state; never blindly retry."),
    "create_service_request": (CreateRequest, "Create a service request for the configured employee. Requires a known service and concrete summary/description. Assigned to the service owner, initially open. Never blindly retry after transport uncertainty; first retrieve the employee's requests."),
    "update_service_request_status": (UpdateStatus, "Update the configured employee's request using expected_version from a fresh informational read. Allowed: open to in_progress/cancelled; in_progress to resolved/cancelled. Terminal states cannot change. On conflict retrieve current state and reassess; do not blindly retry."),
}

def _execute(settings, name, arguments):
    """Internal server implementation, not an agent-facing direct-write API."""
    if name not in TOOLS:
        return error("VALIDATION_ERROR", "Unknown action tool.")
    try:
        value = TOOLS[name][0].model_validate(arguments)
    except ValidationError as exc:
        message = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return error("VALIDATION_ERROR", message)
    return commit_action(settings, value, isinstance(value, CreateRequest))


def build_server(settings):
    server = Server("internal-assistant-actions")

    @server.list_tools()
    async def list_tools():
        return [types.Tool(name=name, description=description, inputSchema=model.model_json_schema())
                for name, (model, description) in TOOLS.items()]

    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        result = await asyncio.to_thread(_execute, settings, name, arguments)
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result))],
                                    structuredContent=result, isError=not result["ok"])

    return server


async def run(settings):
    if settings.mcp_transport != "stdio":
        raise ValueError("Only MCP_TRANSPORT=stdio is supported.")
    server = build_server(settings)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    asyncio.run(run(Settings.load(args.root)))


if __name__ == "__main__":
    main()
