# Multi-source internal assistant

Steps 1 through 6 have source implementations: scope, synthetic data, configuration,
SQLite setup, document ingestion/search, typed graph traversal, and a centralized
LangGraph informational pipeline with grounded synthesis and trace output, and a
separate MCP action server, and model-driven orchestration with MCP discovery and
conversation memory, and a passive interactive terminal chat. Step 7 adds an
evidence-based live evaluation runner and reproducible demo instructions.
A clean Windows Python 3.12 environment installed from `uv.lock` passes
53 automated tests, subprocess MCP checks, and all 17 live Gemini scenarios in
one complete run using the stronger final-answer and action-result assertions.

Step 8 adds the pinned upstream Agent Chat UI and a local LangGraph server, with
shared orchestration, visible tool activity, server-owned conversation history,
and safeguards against replaying uncertain actions. See [browser setup](docs/web-chat.md).

- [Scope and architecture](docs/architecture.md)
- [Data and action contracts](docs/contracts.md)
- [Representative requests](docs/examples.md)
- [Implementation plan](plans/README.md)
- [Verification, requirement evidence, reset workflow, and presenter demo](docs/demo.md)

Validate the dataset without credentials or dependencies (Python 3.10+):

```powershell
python scripts/validate_demo.py
```

Install the locked application and runtime dependencies (Python 3.10+). If this
workspace already contains an MSYS `.venv`, first set
`$env:UV_PROJECT_ENVIRONMENT = ".venv-win"`; use `.venv-win` in later commands.

```powershell
python -m pip install uv==0.12.23
uv sync --locked --extra runtime --python 3.12
Copy-Item .env.example .env
```

Set your own `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey) in `.env` for chat, ingestion, and document search.
After changing embedding providers or models, rerun ingestion to rebuild the index.
Seeding and graph retrieval do not require credentials. On MSYS Python, the
virtual environment executable is `.venv\bin\python.exe`; the locked setup uses
standard Windows Python and `.venv\Scripts\python.exe` as shown here.

```powershell
.venv\Scripts\python -m assistant.cli seed
.venv\Scripts\python -m assistant.cli graph emp-001 --step MEMBER_OF:out --step OWNS:out
.venv\Scripts\python -m assistant.cli graph svc-vpn --step OWNS:in
.venv\Scripts\python -m assistant.cli ingest
.venv\Scripts\python -m assistant.cli search "What does VPN access require?"
.venv\Scripts\python -m assistant.cli ask "Which team handles VPN access, and what does the access policy require?" --trace
.venv\Scripts\python -m unittest discover -s tests -v
```

The installed `assistant` command exposes the same commands. Run from the project
root or pass `--root <project-directory>` before the subcommand. The `runtime`
dependency extra adds the MCP adapter for agent orchestration.

- [Retrieval setup, contracts, and validation status](docs/retrieval.md)
- [Informational pipeline, tool contract, and validation limits](docs/information.md)
- [Action MCP startup, retry behavior, and client smoke check](docs/actions.md)
- [Agent orchestration, invocation, and validation status](docs/agent.md)
- [Terminal chat and the complete startup sequence](docs/chat.md)
- [Browser chat, Windows setup, and execution safeguards](docs/web-chat.md)

After the locked installation, configuring `.env`, seeding, and
ingesting, start `uv run --locked --extra runtime python -m assistant.cli chat`. It launches the MCP server
automatically. Use `/new` for a fresh conversation and `/exit` to quit.

Live Gemini calls and MCP actions have been verified against synthetic demo data.
The unit suite uses deterministic models; `scripts/evaluate_demo.py` exercises real
model calls and isolated MCP writes. `uv.lock` pins dependencies across supported
Python/platform combinations; CI installs with `uv sync --locked --extra runtime`.
To deliberately refresh dependencies, run `uv lock --upgrade`, sync, and rerun checks.
The latest verified run is saved in `runtime/evaluation-locked-final.json`.
The evaluator writes to `runtime/evaluation.json` by default; use `--output`
to preserve earlier reports.

GitHub Actions runs demo data validation, the unit suite, and subprocess MCP checks
on every push and pull request, and can also be started manually from the Actions
tab. CI covers Python 3.10 and 3.12 on Linux and Python 3.12 on Windows, installs
the `runtime` extra, and requires no API credentials. Live Gemini evaluation stays
an explicit local command.

After installing/configuring the runtime, run `python scripts/check_mcp.py` for
real subprocess protocol checks and `python scripts/evaluate_demo.py` for the
live model/retrieval/action evaluation. The latter creates disposable demo state
and captures evidence in `runtime/evaluation.json`; it does not reset your chat
database. See [the demo guide](docs/demo.md) for expected behavior and limits.
