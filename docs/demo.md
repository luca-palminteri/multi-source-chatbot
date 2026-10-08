# Reproducible verification and demo

Run commands from the project root using Python 3.10+. On standard Windows use
`.venv\Scripts\python.exe`; this workspace's MSYS environment uses
`.venv\bin\python.exe`. On Linux/macOS use `.venv/bin/python`.

## Clean setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[runtime]"
Copy-Item .env.example .env
```

Configure `GOOGLE_API_KEY` in `.env`, then run:

```powershell
.venv\Scripts\python scripts/validate_demo.py
.venv\Scripts\python -m assistant.cli seed
.venv\Scripts\python -m assistant.cli ingest
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python scripts/check_mcp.py
.venv\Scripts\python scripts/evaluate_demo.py --output runtime/evaluation.json
.venv\Scripts\python -m assistant.cli chat
```

The evaluation uses real configured models, real embeddings, the persisted vector
index, SQLite graph traversal, and the separately launched stdio MCP server. It
seeds and ingests disposable state on every run, leaving your interactive database
unchanged. It makes paid provider calls. Exit code 0 means every automated check
passed; failure or unavailable dependencies/credentials returns 1 and writes a
report. An incomplete report never counts as successful live validation.

`runtime/evaluation.json` captures discovery, each prompt, selected tools and
arguments, returned results, full informational sources and pipeline traces, and
database snapshots before/after each turn. This is synthetic demo evidence, but
may contain sensitive text if adapted to real data; keep it in ignored `runtime/`.
Review factual relevance and missing-information wording manually: citations alone
do not prove that each claim is supported. The automated runner checks both source
types for combined questions and exact graph attributes for updated records.

`seed` preserves existing records. For a fresh interactive demo, choose new paths
in `.env`, such as `SQLITE_PATH=runtime/demo-02.sqlite3` and
`VECTOR_INDEX_PATH=runtime/demo-02-index`, then seed and ingest again. This resets
the demo without deleting earlier records. Evaluation always resets independently.

## Presenter conversation

Enter these messages in one chat session:

1. `What does the VPN access policy require?`
2. `Which team handles VPN access, and what does the policy require?`
3. `Create a VPN access request for me. Summary: Demo remote access. Description: Need VPN for remote work starting October 12.`
4. `Show the request you just created, including its status and version.`
5. `Set that request to in_progress.`
6. `What is its current status and version?`
7. `Assign that request to its owning team IT Operations (team-it).`

The last action demonstrates a tool added only to the MCP server's advertised
registry/schema. `connect_agent` discovers it through MCP; neither agent routing
nor UI code contains a branch for assignment. Assignment to the current owner is
a valid no-op, so demonstrate discovery and the actual MCP result rather than
claiming a changed team. `scripts/check_mcp.py` independently verifies discovery,
schema validation, invalid IDs, missing arguments, invalid transitions, optimistic
version conflicts, process restart persistence, and graph visibility.

Also try the runner's paraphrases and mixed request. Start a fresh conversation
with `/new` before `Create a service request for me.`; it should ask for details.
`Set request req-nonexistent to in_progress.` and `Reopen my resolved request req-005.`
must leave records unchanged. These requests may be declined before an action is
selected; the protocol smoke check additionally exercises actual server failures.

## Requirement-to-evidence map

| Mandatory requirement in INSTRUCTIONS.md | Observable evidence |
| --- | --- |
| Document RAG | Policy cases: document sources with passage provenance and retrieval trace |
| Structured knowledge graph | Graph cases: employee/team/service paths; current request attributes |
| Centralized informational orchestration | All informational cases: planning, document retrieval, graph retrieval, synthesis |
| Combined RAG + KG | Combined cases cite D and G sources; manually inspect relevance |
| Autonomous selection; no keyword/intent router | Real model-selected traces for original/paraphrased and mixed prompts; `agent.py` tools passed to LangGraph |
| Separate action MCP server as only runtime writer | Create/update/extension MCP results paired with SQLite snapshots; subprocess protocol smoke check |
| Strict action separation and correct schemas | Read-only snapshot comparisons; `check_mcp.py` strict schema/error checks |
| Tool extensibility without routing changes | Discovered `assign_service_request`, selected extension call; server-only registry definition |
| Passive ready-made UI | Terminal transcript and `test_chat.py` forwarding/context/failure checks |
| Modular architecture | [Architecture diagram](architecture.md), separate retrieval/information/agent/actions/chat modules |

## Limitations and verification status

The fixed employee identity is a demo convention. There is no production
authentication, authorization layer, durable chat history, or provisioning action.
SQLite-derived typed relationships satisfy the small graph use case; a dedicated
graph database and exposing this assistant as an external MCP server are optional.
Versions guard concurrent mutations; do not blindly retry uncertain action results.
Dependency version ranges are configured, but no verified dependency lock exists.

Verified on 2026-10-08 using standard Windows Python 3.12 in `.venv-win`:
49 automated tests passed without skips, and the real subprocess MCP smoke check
passed discovery, validation, mutations, restart persistence, and graph visibility.
Seventeen live Gemini scenarios passed across the recorded verification runs,
including capabilities, document/graph questions and paraphrases, missing evidence,
clarification, invalid requests, and a create/read/update/read/assignment/mixed loop.
`runtime/evaluation.json` records the passing cases and identifies their source runs.

Live testing exposed and corrected request bursts causing HTTP 429, MCP subprocess
configuration losing the selected database/identity, Windows SQLite cleanup leaks,
and a model reusing an earlier turn's request version. MCP now receives explicit
configuration, and the agent is instructed to retrieve a fresh version in the current
turn before updates/assignments. A subprocess regression test checks isolation.
Two test-created interactive records from the earlier configuration bug were backed
up in `runtime/test-record-cleanup-backup.json` and removed by exact record match.
Later action tests used disposable databases.

Gemini latency varies; the tested action run included a turn lasting about 90 seconds.
Chat calls use shared pacing of 10 requests per minute, a 45-second request timeout,
and the existing 120-second turn limit. These defaults reduce bursts and bound waits;
they do not guarantee availability or replace the Google project's quota limits.
Use `chat --debug` for sanitized timing and exception details. Run
`scripts/evaluate_demo.py --debug` for the full suite, or add `--actions-only` to
repeat the isolated action loop. Reports are checkpointed after each case.

The actual terminal program was also verified with capability and missing-policy
questions, a combined VPN question, `/new`, and `/exit`. The Python subprocess
returned exit code 0. `runtime/chat-verified.log` contains the transcript and
`runtime/terminal-verification.json` records the checks. Repeat this read-only
terminal check with `python scripts/verify_chat.py` in the configured environment.
