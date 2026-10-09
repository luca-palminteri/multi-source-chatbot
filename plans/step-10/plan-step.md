# Step 10: Providers with free tiers and model selection

## Status and scope

Planned. Implement provider support first, then expose a curated model selector
in the browser. Preserve model-selected routing, the centralized informational
pipeline, and application-owned MCP execution. Provider keys remain on the server.

Initial scope: retain Google/Gemini and add Groq as a hosted provider with a free
tier. Add local Ollama support in the same provider phase, with availability
conditional on a running local service and an installed, qualified model.
Ollama local inference avoids hosted inference charges but requires suitable
hardware; it does not make the current Google embedding pipeline local.

## Current implementation

- `config.py` exposes one configured chat provider/model and separate embedding
  settings. `providers.py` currently implements only Google chat and embeddings.
- The selected chat model is used for orchestration, structured retrieval
  planning, and answer synthesis. Models must support tool calls, streaming, and
  the existing `RetrievalPlan` structured-output contract.
- `web.py` rejects arbitrary run configuration and constructs providers per run.
  Schema inspection uses a non-executing model and must remain credential-free.
- UI selection cannot be implemented by changing the assistant ID: this server
  intentionally permits only its configured `assistant` graph.

## 1. Build and qualify the provider layer

1. Add provider adapters through the appropriate LangChain integrations, using
   lazy imports and optional dependencies where practical. Resolve and lock
   compatible versions. Keep the CLI's configured default provider/model working.
2. Add server configuration for `GROQ_API_KEY`, Ollama's server-controlled base
   URL, allowed local models, and provider-specific timeout/rate limits. Keep
   existing Google options specific to Google. Never accept an API key or
   arbitrary provider URL from a chat request.
3. Introduce a curated server-side model catalog with stable selection IDs,
   provider, actual model ID, display name, capabilities, and configuration
   availability. Start with a small set of qualified models; confirm their
   current IDs and free-tier eligibility during implementation. Do not expose
   every model returned by a provider as automatically compatible.
4. Qualify each candidate against tool binding/calls, streamed tool arguments,
   structured retrieval planning, tool-result continuation, and grounded answers.
   Use the same selected provider/model for orchestration, planning, and
   synthesis. Exclude candidates that cannot satisfy these contracts.
5. Keep embedding configuration and the existing vector index unchanged when
   switching chat models. Update limiter identities to include provider/model
   and the quota scope; share limits across orchestration, planning, and synthesis
   and across models when the account's quota is shared.
6. Preserve zero automatic mutation/run retries. Return clear sanitized errors
   for missing keys, unavailable local services/models, and quota exhaustion.
   Do not silently fall back to another model or replay a failed action turn.
   Include limiter waiting in the existing execution-time budget.

Acceptance: each enabled provider passes deterministic adapter checks and a
small real-provider qualification using disposable records before its models
are selectable. Account-specific eligibility is documented rather than assumed.

## 2. Add a controlled API contract

1. Expose a read-only model catalog endpoint containing public IDs, labels,
   capabilities, availability, and the configured default. Catalog reads make
   no inference calls and expose no secrets. An explicit local availability
   check may query the configured Ollama service without running a model.
2. Add exactly one allowlisted selection field to the run contract, for example
   `config.configurable.chat_model_id`. Validate the ID and resolve it against
   the server catalog before provider construction and execution admission.
   Preserve server-controlled recursion limits and reject every unrelated
   configurable field. Verify how the pinned Agent Server forwards this field.
3. For the first version, fix selection per thread after its first accepted turn.
   Store the chosen catalog ID durably in server-owned thread settings, using
   the configured default for older threads. Enforce the rule on the backend
   under concurrent requests, not only in the UI. Record the actual provider
   and model ID on run metadata for later export and diagnosis.
4. Reject unavailable, disabled, or removed model choices without silently
   changing an existing conversation's model. Offer starting a new conversation.
   A failed/blocked thread remains blocked regardless of the selected provider.

Acceptance: direct API requests cannot inject credentials, arbitrary model URLs,
tool configuration, checkpoint replay, or alternate execution settings. Invalid
selection requests do not unnecessarily consume submission IDs or block threads.

## 3. Add model selection to the UI

1. Add a provider-grouped model dropdown near the chat header/composer. Load its
   choices from the backend catalog; show unavailable choices with a short reason.
2. Remember the preferred choice for new chats in browser storage. Resolve it
   against the current catalog before sending. Use the server default when no
   preference has been chosen.
3. Allow changing models before the first turn. Once a thread starts, show its
   stored model with a clear explanation that switching requires a new chat.
   Reopening history restores that thread's selection.
4. Display useful quota/unavailability messages, distinguishing free-tier
   eligibility from actual remaining quota. Do not promise unlimited free use
   or that a billing-enabled account will avoid charges.

## Verification and documentation

- Test default/legacy configuration, adapter-specific options, missing keys,
  unknown catalog IDs, credential redaction, and provider-aware rate limiting.
- Test that all three model roles receive the selected model while embeddings
  remain unchanged. Test CLI behavior and credential-free schema inspection.
- Extend the existing disposable Agent Server checks for valid/invalid selection,
  concurrent first turns, persisted model settings, and all existing replay,
  cancellation, and action-ledger protections.
- Browser-check selection, reload/history restoration, unavailable choices, and
  a complete information/action sequence per qualified provider. Run a UI build
  and the relevant Python checks. Document setup and catalog maintenance in
  `docs/web-chat.md`, `.env.example`, and `UPSTREAM.md`.

## Sources and implementation checkpoints

Provider terms and models change. These official sources were checked while
planning on 2026-10-09; recheck them when selecting exact models.

- [Google pricing](https://ai.google.dev/gemini-api/docs/pricing): free-tier
  availability is model-dependent.
- [Groq rate limits](https://console.groq.com/docs/rate-limits): a free plan is
  available with model/account limits.
- [Groq tool use](https://console.groq.com/docs/tool-use/overview): provider tool
  calling support still requires qualification against this application.
- [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling): use
  an installed model that supports the required tool behavior.

Main files: `src/assistant/config.py`, `providers.py`, `web.py`,
`information.py` if adapter compatibility requires it, new model catalog/thread
settings modules, `pyproject.toml`, `uv.lock`, `.env.example`, and the UI stream,
thread, and new model-selector components.
