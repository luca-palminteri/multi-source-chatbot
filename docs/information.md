# Centralized informational pipeline (step 3)

`assistant.information.InformationPipeline` compiles a LangGraph flow:
`START -> plan -> retrieve -> synthesize -> END`.

State carries the question, relevant conversation context, validated retrieval
plan, document evidence, graph evidence, source map, final answer, and trace.
The model plans retrieval without keyword intent routing. Every valid request
searches documents and queries the graph, including questions with missing facts.
Graph planning accepts only typed entity searches and allowlisted directed edges;
there is no generated SQL or mutation interface. Limits are eight queries, three
hops per query, twenty starting entities per search, and one hundred returned
paths. Trace output reports truncation and missing entity IDs.

The synthesis prompt treats retrieved text and context as untrusted data. It
requires relevant evidence, inline `[D1]` / `[G1]` citations, explicit missing
information, and disclosure of conflicting sources. Source entries retain full
document provenance or graph entities and relationships. Individual and comma-separated
grouped citation markers are parsed; every referenced ID must exist. Unknown IDs
and empty model responses fail explicitly. Citation relevance and factual
entailment remain model responsibilities; deterministic checks do not prove them.
Retrieval or provider failures propagate rather than becoming empty evidence.

`create_information_pipeline(settings)` constructs the configured providers and
retrievers. `pipeline.invoke(question, context="")` returns a JSON-serializable
object with `answer`, `sources`, and `trace`. Trace events cover planning,
document retrieval, graph retrieval, and synthesis. Traces are returned per call;
they are not automatically persisted or sent to a telemetry service.

`pipeline.as_tool()` exposes the `lookup_information` LangChain tool. This is the
single application information tool intended for the step 5 agent. Setup/debug
retrieval commands remain available to developers, but should not be registered
as separate agent tools. The graph contains no MCP client or action tool.

After installing dependencies, configuring `.env`, seeding, and ingesting:

```powershell
.venv\Scripts\python -m assistant.cli ask "Which team handles VPN access, and what does the access policy require?" --trace
.venv\Scripts\python -m assistant.cli ask "What is the policy for satellite internet?" --trace
.venv\Scripts\python -m unittest discover -s tests -v
```

On MSYS Python, use `.venv\bin\python.exe` instead. Tests exercise the compiled
graph with a deterministic model and seeded read-only SQLite retrieval, without
API credentials. They are skipped when orchestration dependencies are missing.
Live synthesis and runtime checks still require dependency installation and a
configured provider; fake-model checks do not establish live answer quality.
