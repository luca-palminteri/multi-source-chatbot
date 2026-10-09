Vendored from https://github.com/langchain-ai/agent-chat-ui
Revision: 28cfb43a62b7179ed4065dd761e16ece8c29d983
Package manager: pnpm 10.5.1. Original pnpm-lock.yaml and MIT LICENSE retained.

Local safety patch: shared.tsx hides branch/edit/regenerate controls; thread/index.tsx
submits only the new human message, never fabricated tool responses or artifact context,
and explicitly clears the SDK's implicit checkpoint for new turns, with reject
concurrency. Text input is limited to 4000 characters and unsupported
file upload controls are hidden. These changes do not select tools or route intent.
Stream.tsx disables automatic SDK request retries; reconnect joins or reads an
existing run rather than repeating a mutation submission.
The backend rejects checkpoint replay, state edits, alternate execution endpoints,
non-user input and duplicate message IDs. A cancellation cannot undo a committed action.

Local appearance patch (step 9): theme-provider.tsx mounts next-themes above the
existing providers, using the dark class, System by default, and the browser
storage key agent-chat-appearance. The root HTML suppresses the expected theme
attribute hydration difference; the appearance control waits for browser state.
A tooltip icon opens a styled Light / Dark / System menu with icons and a selected
checkmark. Arrow keys, Home/End, Escape, focus return, and outside dismissal are
supported. The control is available in both chat headers and the connection form,
including mobile. Chat/history, tool and interrupt results, markdown, icons,
artifact controls, focus rings, and shared buttons use theme tokens or paired
status colors. Sonner inherits the provider's theme. Code blocks retain the
upstream dark Prism palette in both appearances; their copy hover stays readable.
No backend or message-submission behavior changes.

Local chat actions patch (step 11): Thread.tsx uses the application's paginated
catalog endpoints. History has debounced literal search, snippets, loading/error/
empty states, and Load more. chat-actions.tsx supplies keyboard/mobile menus,
validated rename and permanent-delete dialogs, and UTF-8 Markdown/JSON downloads.
The header displays the persisted title and the same actions; Stream.tsx refreshes
history when run loading changes. Export/delete controls are disabled during runs.
All new surfaces use existing theme tokens. The backend retains replay safeguards
and deletion tombstones while cascading native history deletion. JSON downloads
are transcript records, not executable replay/import data. next.config.mjs accepts
WEB_CHECK_DIST_DIR for isolated disposable browser verification builds.
