# Terminal chat

Run these commands from the project root with Python 3.10 or newer:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[runtime]"
Copy-Item .env.example .env
```

If `.env` already exists, keep it. Set your own `GOOGLE_API_KEY` in `.env`, then:

```powershell
.venv\Scripts\python -m assistant.cli seed
.venv\Scripts\python -m assistant.cli ingest
.venv\Scripts\python -m assistant.cli chat
```

On MSYS Python use `.venv\bin\python.exe` in place of
`.venv\Scripts\python`. The installed `assistant chat` command is equivalent.
For a different project location use `assistant --root <directory> chat`.

The chat application automatically launches the separate stdio MCP action server
and discovers its tools. No second terminal or manually started server is needed.
Keep `MCP_TRANSPORT=stdio`; the child server uses the same Python environment and
project root. Startup failures print setup guidance without raw exception text.

Type a question, follow-up, or explicitly requested action at `You:`. Clarifying
answers use the same conversation and agent entry point. Each response displays
the agent's answer followed by tool results, including returned source references
and action outcomes. A completed agent turn does not imply an action succeeded:
inspect the tool's `ok`/error result. Source labels belong to their individual tool
result; repeated `D1` labels across lookups may refer to different evidence.

- `/new` closes the connection and starts a fresh conversation with newly
  discovered tools and a new session ID. It discards chat memory; committed
  request changes remain in the database.
- `/exit`, Ctrl+C, or end-of-input closes chat. `/help` lists the commands.
- Empty input is ignored; messages are limited to 4000 characters.

An execution failure stops further messages in that conversation. Use `/new`
and ask for current request state before retrying an action: a timed-out or
interrupted mutation may already have committed. Chat never automatically retries
actions. Memory is in-process and is lost on exit.

The UI performs no retrieval, intent classification, or action selection. All
application messages pass to `AgentSession.ask`, which supplies the conversation
ID to LangGraph. Deterministic tests cover forwarding, clarification context,
reset/cleanup, source and outcome display, input bounds, and sanitized failures.
Live model/MCP interaction still requires installed dependencies, credentials,
and the step 7 demo checks.

## Diagnosing a failed or slow turn

Run `python -m assistant.cli chat --debug` to show MCP discovery, tool selection,
retrieval planning, query embedding, synthesis, step timings, and a waiting message
every ten seconds. Failures include the exception type, numeric HTTP status when
available, and stack locations. Diagnostics omit prompts, tool arguments, API
keys, raw exception messages, and source code lines. The terminal displays the
failure type even without debug mode. A `TimeoutError` can mean the 120-second
turn limit was reached; status 429 indicates rate limiting, 401/403 an access
problem, and 404 an unavailable model or endpoint. These are clues, not a
confirmed diagnosis. Stop and inspect the failing stage before retrying actions.

Gemini chat defaults to `CHAT_THINKING_LEVEL=low` for Gemini 3 models,
`CHAT_REQUEST_TIMEOUT=45` seconds per request, and `CHAT_MAX_RETRIES=0`.
Override these in `.env` if needed. The overall turn limit remains 120 seconds.
Capability questions and greetings are answered directly by the model; questions
about actual policies and records still require document and graph retrieval.

Chat defaults to `gemini-3.5-flash-lite`, a model designed for low latency.
Change `CHAT_MODEL` in `.env` to override it. Embedding settings are independent.

`CHAT_REQUESTS_PER_MINUTE=10` paces chat calls across the agent, planner, and
synthesizer within one process. This prevents bursts during multi-step questions;
set it to match your project quota. Other processes share the Google project quota
but have separate local limiters. HTTP 429 failures now show a rate/quota message
and a retry delay when Google supplies one.
