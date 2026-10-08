# Step 5 agent orchestration

Install `pip install -e ".[runtime]"`, seed and ingest the data, and set credentials
as described in the README. Run a single agent turn:

```powershell
python -m assistant.cli agent "Who handles VPN access and what approvals are required?" --trace
python scripts/check_mcp.py
python -m unittest discover -s tests -v
```

`assistant.agent.connect_agent(settings)` is an async context manager. Within it,
call `await session.ask(message)` repeatedly to preserve conversation history,
including tool results and known IDs. Memory is private to that session and lost
on process exit. Use `assistant chat` for repeated turns; see [terminal startup](chat.md).

Every connection starts a separate stdio MCP server and discovers advertised tools
using the LangChain MCP adapter. Those tools and the centralized informational tool
are registered with LangGraph's generic ReAct loop. No user wording is matched to
routes. System instructions require evidence retrieval, clarification for missing
arguments or ambiguous targets, fresh versions before mutations, and truthful
reporting. These are model instructions, not guarantees of model behavior.

Initialization and discovery each have a 20-second timeout. A turn has a 120-second
timeout and a 24-step graph limit. Unexpected execution failures stop that session;
reconnect and retrieve current records before retrying because a mutation may have
committed before a transport failure. Server business errors remain tool results.
The turn's `ok` indicates completion, not action success. Inspect tool results for
action success. Traces record discovery, selected names/arguments, results, and
failures in memory; `--trace` prints the current turn. Traces contain application data.

`assign_service_request` uses optimistic versions and permits only the service's
owning team for active requests belonging to the configured employee. Its schema
is discovered without selection-code changes. The MCP smoke script reconnects,
loads it through the adapter, invokes it, and checks rejection of an unrelated team.

Validation: all 53 automated tests and subprocess MCP checks passed in a clean
Windows Python 3.12 environment installed from `uv.lock` on 2026-10-08.
All 17 live scenarios passed in one complete run with the stronger evaluation
assertions, including paraphrases, mixed requests, clarification, and discovered
assignment. Evidence is in `runtime/evaluation-locked-final.json`. Session tests cover trace preservation,
failure/timeout bounds, and stable conversation identifiers; they do not prove
live model selection. See [the demo guide](demo.md) for evidence and limits.
