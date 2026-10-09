# Step 11: Chat actions

## Status and scope

Implemented. Add manual renaming, history search, Markdown/JSON export, and permanent
conversation deletion. These are explicit application controls; domain actions
requested through conversation continue to run exclusively through MCP.

This step can begin independently of step 10. Share a thread-settings service
with model selection so names, lifecycle status, and model choice do not acquire
conflicting storage contracts. Match step 9's theme tokens for all new controls.

## Current implementation and storage decision

History currently fetches at most 100 threads, labels them with the first message,
and provides only open-thread controls. The backend blocks PATCH and DELETE
requests. LangGraph owns conversation messages/checkpoints; the separate
execution ledger protects against replay and uncertain action outcomes.

Use LangGraph as the authority for messages. Introduce a small durable SQLite
chat catalog beside the configured application database for title, timestamps,
model selection, search text, and lifecycle/tombstone state. This catalog is
presentation/settings storage, not a replacement for the execution ledger.
Use narrow application endpoints for metadata/search/deletion rather than
allowing arbitrary thread/state edits through the existing boundary.

First verify the pinned server's thread listing, state/history, delete, pagination,
and extension APIs in a disposable instance. Choose a server-side integration
that reaches the native thread store without a publicly exposed boundary bypass
or fragile self-HTTP recursion. If that integration is unavailable, resolve it
before implementing permanent deletion; hiding a chat is not a substitute.

## 1. Shared history/catalog foundation

- Add cursor pagination and a stable updated-time ordering, replacing the
  current fixed 100-thread assumption. Empty/loading/error states must be clear.
- Create/backfill catalog entries from paginated native threads without provider
  calls. Synchronize after accepted messages and run completion, cancellation,
  or failure; reconcile after restart so partial runs are represented correctly.
- Use the first user message as a bounded default title. Store manual title
  overrides separately so synchronization never overwrites a renamed chat.
- Add a per-row actions menu, usable by keyboard and on mobile. Refresh list
  state after operations and keep the selected thread consistent.

## 2. Renaming

- Provide Rename from the history menu and current chat header. Open a small
  editable dialog, enforce a trimmed 1-100 character title on client and server,
  and provide Save/Cancel with explicit error feedback.
- Persist only the title field through a narrow validated endpoint; never edit
  messages, execution state, or model choice as part of renaming.
- Update the header and history immediately after success. Renaming must survive
  refresh/restart and must not call an LLM or MCP tool.

Acceptance: custom titles persist, empty/oversized values are rejected, and
renaming cannot mutate checkpoints or interfere with an active run.

## 3. History search

- Add a search input above the history list with a short debounce. Search both
  titles and human/visible-assistant message text, case-insensitively, across
  all chats rather than only the loaded page. Exclude tool payloads and internal
  hidden retrieval messages from the initial search scope.
- Use the chat catalog's text index with bounded queries and pagination; define
  straightforward literal phrase/substring behavior without exposing raw SQL
  or search-language operators. Show matching snippets and a clear no-results
  state. Clearing search restores the normal list.
- Cancel/ignore stale requests so rapid typing cannot replace newer results.
  Exclude deletion tombstones and remove deleted content from the index.

Acceptance: find renamed and older chats, including those beyond the first 100,
and find message-text matches after restart. Search makes no model calls and
selecting a result opens the original conversation.

## 4. Export

- Add Export Markdown and Export JSON to the chat menu. Fetch a stable snapshot
  of persisted messages for the selected thread, not just currently rendered
  or buffered stream content. In the first version, disable export during an
  active run to avoid presenting an incomplete stream as a complete transcript.
- Markdown contains title, thread ID, export time, selected model when known,
  visible user/assistant messages, and citations. JSON is versioned and contains
  message IDs/roles/content, native tool calls/results, and relevant public
  thread/run metadata. Apply existing hidden-message policy; omit credentials,
  internal runnable configuration, and safety-ledger data.
- Download locally using a sanitized title-based filename and UTF-8. Explain
  that exported JSON is a record, not an executable replay/import format.
  Preserve citation text without inventing unavailable source contents.

Acceptance: correct Markdown/JSON exports for reopened and failed chats,
Unicode and multiline messages, citations, and tool results. Export has no
effect on execution or stored conversation state.

## 5. Permanent deletion

- Provide Delete in the actions menu with confirmation that names the chat and
  explains that deleting history does not undo service-request actions.
- Implement a dedicated backend operation that atomically acquires a per-thread
  lifecycle/deletion guard before checking active runs. Reject deletion during
  an active run; disable the UI option too. Run admission and deletion must
  share this guard to close the check-then-delete race.
- Mark deletion pending, remove the native conversation/history/checkpoints via
  the verified server API, and remove title/search/exportable content. Retain a
  minimal tombstone and execution/submission/attempt ledger entries so old thread
  IDs cannot be recreated or used to bypass blocked/uncertain execution rules.
  Make interrupted deletion recoverable and repeated delete requests idempotent.
- Allow removing failed conversation history while retaining its safety state.
  Leave business records and the independent action ledger intact. Enforce
  tombstone checks on all thread-creation/run-admission paths, including explicit
  reuse of an old ID.
- After success, remove the history row. If it was selected, clear its URL/state
  and display a fresh chat. Treat an already deleted thread gracefully.

Acceptance: deleted history cannot be reopened, searched, exported, or recreated
under the same ID; business records and replay safeguards remain effective.
Failures show actionable feedback instead of claiming successful deletion.

## Verification and delivery order

Implement catalog/pagination, rename, search, export, then deletion. Use
disposable databases and native server state for deletion verification.

- Test title validation/persistence, catalog reconciliation, literal search,
  pagination beyond 100 threads, Unicode exports, hidden-message filtering,
  sanitized filenames, and deleted-thread handling.
- Extend Agent Server checks for rename endpoint validation, active-run deletion,
  simultaneous deletion/run submission, interrupted-delete recovery, repeated
  deletion, blocked-thread deletion, and old-ID recreation/replay rejection.
- Verify existing safety checks still pass. Browser-check desktop/mobile menus,
  search, downloads, dialogs, reload behavior, and selection after deletion.
- Update `docs/web-chat.md` and `UPSTREAM.md`. No production hosting or
  multi-user identity system is included in these three local-demo enhancements.

Main files: new chat catalog/service module, `src/assistant/web.py`,
`ui/agent-chat-ui/src/providers/Thread.tsx`, `src/components/thread/history/`,
thread header/actions/export components, and disposable server/browser checks.

## Delivery evidence

Implemented in `chat_catalog.py`, `chat_service.py`, the execution boundary, and
shared UI actions/history controls. The pinned local runtime uses native
`Threads.search`, `Threads.State.get`, `Threads.delete`, and `Runs.search`;
deletion cascades native checkpoints/runs without exposing a bypass endpoint.
The durable catalog has an FTS5 trigram index, separate manual titles, shared
model settings, and deletion tombstones. Startup/history reconciliation sweeps
both pending and completed tombstones to recover an interrupted native flush.

Verification: 65 Python tests passed; disposable Agent Server checks cover
pagination beyond 100, rename validation and active-run renaming, stable exports,
literal search, run/deletion races, interrupted/idempotent deletion, retained
business/ledger data, old-ID rejection, and restart persistence. Desktop/mobile
browser checks pass for keyboard menus, dialogs and error feedback, rename/reload,
search/no-results/clear, Unicode downloads, and selection after deletion.
TypeScript passes; ESLint has no errors and four existing warnings.
