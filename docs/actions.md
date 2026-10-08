# Action MCP server

The standalone server uses stdio and the official MCP Python SDK's supported
1.x API (`mcp>=1.28,<2`). See the [SDK documentation](https://py.sdk.modelcontextprotocol.io/v1/).
It exposes only `create_service_request` and `update_service_request_status`.
Input schemas are generated from strict Pydantic models and reject extra fields.
Results include JSON text and `structuredContent`; failures set `isError: true`.

Install dependencies and seed before starting, from the project root:

```powershell
python -m pip install -e .
python -m assistant.cli seed
python -m assistant.actions.server --root .
```

The installed `assistant-actions --root .` command is equivalent. An MCP client
launches this command as a separate process and communicates over stdin/stdout.
Use the same Python environment as the application. Logs go to stderr; stdout
is reserved for protocol messages. `MCP_TRANSPORT` must be `stdio`.
`SQLITE_PATH` selects the shared authoritative database; `DEMO_EMPLOYEE_ID`
selects the trusted requester. This local demo does not implement remote login.

The informational graph remains read-only and imports no action code. Only the
MCP server invokes its private mutation implementation. Every action uses
`BEGIN IMMEDIATE`, checks requester/ownership and references in that transaction,
and returns the resulting record after commit. Failed operations roll back.
Creation assigns the service owner, uses a UUID request ID and UTC timestamps,
and starts at version 1. Status changes enforce the lifecycle and increment
version. A current-version update to the same status is a no-op.

An identical update retried with its old version returns `VERSION_CONFLICT`;
retrieve current state and reassess. Creation intentionally has no deduplication:
two identical issues can be legitimate separate requests. After an uncertain
create response, retrieve the employee's requests and clarify before retrying.
Do not automatically retry creation. No agent direct-write API is provided.

Verify without model credentials, against a temporary database:

```powershell
python scripts/check_mcp.py
python -m unittest discover -s tests -v
```

The smoke check uses the SDK client, starts real server subprocesses, discovers
schemas, checks invalid input, invokes both mutations, verifies graph visibility,
and reconnects to test persistence. This protocol check passed on 2026-10-08
in the Windows Python 3.12 environment, along with the live model-selected action
loop. `connect_agent` explicitly passes its configured database and employee
identity to the child server; a subprocess regression test verifies this isolation.
