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
