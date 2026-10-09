# Browser chat

Step 8 uses the upstream LangChain Agent Chat UI, pinned at
`28cfb43a62b7179ed4065dd761e16ece8c29d983`, with pnpm 10.5.1. The backend is
LangGraph CLI 0.4.33 / API 0.15.3 / in-memory runtime 0.35.3, locked in `uv.lock`.
The CLI remains available; both entrypoints use `build_graph` and the same prompts
and dynamically discovered action tools.

## Windows setup

Run from the repository root with standard Windows Python 3.12, Node.js 22 or
newer, and uv 0.12.23. Python 3.10 remains supported for the terminal application;
the server extra is marked for Python 3.12+. The verified local environment uses
Python 3.12.15 and Node.js 25.9.0.

```powershell
python -m pip install uv==0.12.23
$env:UV_PROJECT_ENVIRONMENT = ".venv-web"
uv sync --locked --extra web --python 3.12
Copy-Item .env.example .env  # only for a fresh checkout
```

Set `GOOGLE_API_KEY` in the backend `.env`. Keep credentials out of UI variables.
Choose unused paths for disposable demo state in the backend `.env`, then seed
and ingest it. The LangGraph CLI loads that file with precedence over existing
shell variables, so set these values in the file itself:

```dotenv
SQLITE_PATH=runtime/browser-demo/assistant.sqlite3
VECTOR_INDEX_PATH=runtime/browser-demo/vector_index
LANGSMITH_TRACING=false
```

```powershell
.venv-web/Scripts/python.exe -m assistant.cli seed
.venv-web/Scripts/python.exe -m assistant.cli ingest
```

Install the vendored UI without changing its upstream lockfile:

```powershell
Push-Location ui/agent-chat-ui
Copy-Item .env.local.example .env.local
npm.cmd exec --yes --package=pnpm@10.5.1 -- pnpm install --frozen-lockfile
npm.cmd exec --yes --package=pnpm@10.5.1 -- pnpm build
Pop-Location
```

## Start in two terminals

Backend terminal, from the repository root, with the same database/index paths
used for setup:

```powershell
$env:PYTHONUTF8 = "1"
.venv-web/Scripts/langgraph.exe dev --host 127.0.0.1 --no-browser --no-reload --allow-blocking
```

`--allow-blocking` is required by this pinned MCP client's Windows stdio startup:
it synchronously checks the interpreter with `shutil.which` / `os.access`.
Application database/provider setup runs in worker threads. This override is a
local development limitation; it is not a production deployment recommendation.

UI terminal:

```powershell
Set-Location ui/agent-chat-ui
node node_modules/next/dist/bin/next start --hostname 127.0.0.1
```

Open <http://localhost:3000>. The example UI environment connects directly to
<http://localhost:2024> and graph ID `assistant`. The pinned server's default
CORS permits this connection. No UI API key is needed. Although the upstream
[local development guide](https://docs.langchain.com/langsmith/local-dev-testing)
lists a LangSmith key as a prerequisite, this pinned server starts and serves
runs without one. Tracing was disabled during verification. A LangSmith key is
only needed here if you opt into that service; Google credentials are still
required for real model calls and ingestion.

Use the seven-turn [presenter conversation](demo.md#presenter-conversation),
including create/read/update/read/assignment. Leave “Hide Tool Calls” off to
inspect lookup evidence, citation markers, and MCP results. Refresh to retrieve
history, or use “New thread” for an independent conversation. The application
accepts text messages only, with a 4000-character limit.

## Appearance

Use the appearance icon in the chat header to choose **Light**, **Dark**, or
**System**. The icon menu is also available on mobile and on the connection form.
A fresh visit defaults to System and follows later OS appearance changes. Your
choice persists for this browser origin in local storage (`agent-chat-appearance`).
Code blocks keep their dark syntax-highlighting palette in either appearance.

To verify appearance against the running UI without backend credentials or model
calls, run:

```powershell
$env:WEB_BROWSER_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe"
node scripts/check_web_appearance.cjs
```

Set `WEB_UI_URL` if the UI uses a different address. Optionally set `WEB_SETUP_URL`
to a UI started without public API URL/assistant ID settings to also check the
connection form. The check supplies a disposable deterministic HTTP stream and
checks desktop/mobile appearance, System updates, persistence, initial paint,
conversation rendering, and history. Screenshots and a report are saved under
ignored `runtime/appearance-verification/`.

## Execution and history limits

The server owns thread IDs and checkpoint persistence. Each UI turn submits only
one new human message. No frontend logic classifies intent. Internal retrieval
model streams are hidden; native orchestration AI/tool messages remain visible.
Each run opens a stdio MCP process, discovers schemas, and closes the connection
on completion, failure, or cancellation. Schema/history inspection also closes
its MCP connection and makes no provider calls.

The HTTP boundary rejects system/assistant/tool inputs, checkpoint branching,
commands, state edits, mutable assistant configuration, threadless runs, and
alternate execution APIs. The UI's edit/regenerate/branch controls are disabled;
the patch is recorded in `ui/agent-chat-ui/UPSTREAM.md`.

Runs have a 120-second execution limit and recursion limit 24. Same-thread
concurrency is rejected. A separate local SQLite ledger records submissions and
execution attempts before tools execute, rejecting reused message IDs and worker
retries. An incomplete/failed/cancelled run leaves its thread blocked, including
after restart. Start a new thread and read current records before another action.
A disconnect continues the existing run; reconnect reads its history rather than
submitting again. Cancellation cannot roll back a committed action, and rollback
requests are rejected. This does not deduplicate a deliberate new request with a
new message ID in a new thread.

The dev server stores in-memory history and pickles it under `.langgraph_api/`.
This is local development persistence, with no production durability guarantee.
The safety ledger lives next to the configured action database with suffix
`.web-executions.sqlite3`. Do not delete it to recover a failed conversation.
To reset the demo, use new database/index paths and new threads. Stop both
terminals with Ctrl+C; no separate MCP service needs manual startup.

## Verification and troubleshooting

```powershell
.venv-web/Scripts/python.exe -m unittest discover -s tests -v
.venv-web/Scripts/python.exe scripts/validate_demo.py
.venv-web/Scripts/python.exe scripts/check_mcp.py
.venv-web/Scripts/python.exe scripts/check_web.py
```

`check_web.py` starts a real disposable Agent Server with deterministic models,
real MCP subprocesses and a seeded database. It verifies discovery, streams/tool
IDs, continuity/isolation, concurrency, cancellation, uncertain action outcomes,
reconnect, and replay rejection. It requires no credentials. Reports and server
logs are saved under ignored `runtime/web-smoke/`.

For a real-model browser check against already running disposable services:

```powershell
$env:WEB_BROWSER_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe"
node scripts/check_web_browser.cjs
.venv-web/Scripts/python.exe scripts/check_web_records.py --database runtime/browser-demo/assistant.sqlite3
```

Alternatively install Playwright Chromium in the UI package and omit that
variable. This check makes paid model calls and performs synthetic actions,
then checks missing details and an invalid ID in a new thread. The records check
compares the three successful MCP results and versions to the selected database.
Evidence is saved in ignored `runtime/web-verification/`.

If the UI cannot connect, check `/ok` on port 2024 and the UI environment's API
URL/assistant ID, then restart the UI after changing public variables. If port
2024 is occupied, the CLI can select another port; stop the earlier server or
update/rebuild the UI's API URL. If setup reports an MSYS interpreter, use the
dedicated `.venv-web` environment. `PYTHONUTF8=1` avoids Windows console encoding
errors. A missing vector index requires ingestion with the same configured paths.
After quota/timeouts, start a new thread and verify record state before retrying.

Chat history supports cursor pagination, literal substring search across titles and
visible user/assistant messages, Rename, Export Markdown, Export JSON, and Delete.
Use the row's actions button or the current chat header. Rename accepts a trimmed
1–100 character title and works during a run. Search is case-insensitive, debounced,
and includes older conversations beyond the first page; tool results and messages
with the UI's `do-not-render-` prefix are excluded from search.

Exports download a persisted native checkpoint snapshot in UTF-8 with a sanitized
title-based filename. Markdown includes visible messages and citation text. The
versioned JSON record also includes native tool calls/results and public run IDs,
statuses, and timestamps. JSON is a record, not an executable replay/import format.
Export and deletion are unavailable while a run is pending or running. Delete
permanently removes native history, checkpoints, and runs; it does not undo service
request actions or remove the independent execution/submission/attempt ledger.

Presentation settings live beside `SQLITE_PATH` in `.chat-catalog.sqlite3`, with
separate default/manual titles, model, timestamps, an FTS5 trigram text index, and
lifecycle tombstones. Native LangGraph state remains the message authority.
Accepted and completed/cancelled/failed runs synchronize the catalog. Startup
and opening history reconcile all paginated native threads and retry pending
deletions, including tombstones whose native persistence flush was interrupted.
Keep the catalog and execution ledger when backing up or moving the
local demo: deletion tombstones prevent reuse of old conversation IDs.

The narrow `/chat/history`, `/chat/{id}/settings`, `/chat/{id}/title`,
`/chat/{id}/export`, and `/chat/{id}/delete` endpoints use the pinned local
Agent Server's in-process storage operations. The per-thread lifecycle guard is
shared with HTTP run admission. Generic state edits and native deletion remain
blocked. This integration targets the single-process local in-memory server;
another runtime requires verifying its native operations and guard semantics.

Run `.venv-web/Scripts/python.exe scripts/check_web.py --browser` to check the
controls against disposable native state and deterministic models without paid
provider calls. It starts an isolated UI build and tests desktop/mobile keyboard
menus, rename/error/reload behavior, search, Unicode downloads, and deletion
selection. Browser evidence is in `runtime/chat-actions-browser/`; server checks
are in `runtime/web-smoke/`. Chrome is the default browser on Windows; set
`WEB_BROWSER_PATH` to override it.
Set `CHAT_UI_ORIGIN` on the backend when serving the UI on a different local
origin; the standard localhost/127.0.0.1 port 3000 origins are already allowed.
