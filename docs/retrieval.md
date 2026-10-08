# Step 2 retrieval

## Setup and configuration

Install the project with `python -m pip install -e .` in a virtual environment.
Copy `.env.example` to `.env` and set an API key for document embeddings.
`Settings.load(root)` reads `.env`; process environment variables take precedence.
Relative SQLite and index paths resolve against the supplied project root.
Provider factories are lazy and accept the configured Google Gemini models. Additional
providers can implement the embedding interface without changing retrieval.

`assistant seed` creates the schema with foreign keys and inserts missing records
from `data/seed.json` transactionally. Existing entities and requests are preserved,
including updated versions/statuses and new runtime requests. Seed does not reconcile
changed existing seed definitions; use an explicit migration for those changes.
Setup commands are not agent tools.

## Document evidence

`assistant ingest` reads registered documents from SQLite and their source files.
Passages prefer paragraph and word boundaries, default to 900 characters with
120-character overlap, and retain exact Unicode character offsets (start inclusive,
end exclusive). Stable chunk IDs include document ID, version, and offsets.
Evidence contains document/policy IDs, title, source path, version, effective date,
text, and cosine similarity score. Scores are relevance measures, not probabilities.

The index is a NumPy `.npz` artifact containing a normalized embedding matrix and
JSON metadata. A content/configuration fingerprint skips unchanged ingestion and
its embedding calls. Changes rebuild the full small corpus. An atomic replacement
keeps vectors and metadata together, avoiding duplicate chunks and partial index
updates. Failed embedding calls preserve the previous artifact. Run ingestion
after source edits; change the document version for published policy revisions.

Search uses the same embedding provider/model and rejects a mismatched index.
Blank queries and scores below the requested threshold return an empty tuple.
Nonblank semantic searches can return weak matches; consumers should assess the
scores rather than assume every top result answers the question. Missing index,
invalid vectors, or dimension mismatches raise errors instead of returning invented
evidence. A retriever instance holds its loaded index snapshot; recreate it after
re-ingestion to load the new artifact.

## Graph evidence

`GraphRetriever.traverse(start_id, steps)` explicitly walks typed adjacency edges.
Each step is `(relationship_type, direction)`, where direction is `out` or `in`.
For example, `[("MEMBER_OF", "out"), ("OWNS", "out")]` from `emp-001` returns
Alex Rivera, Product Engineering, and Software installation with their connecting
edges. Reverse `OWNS` from `svc-vpn` returns IT Operations.

Paths contain typed entities, native-direction edges, SQLite table names, source
record IDs, and complete entity attributes, including request status/version.
A zero-step traversal retrieves an entity. Missing IDs are reported separately
from valid entities having no matching paths. `find_entities` supports optional
type and name filters for entity resolution; it does not classify chatbot intent.
`EvidenceResult` combines document and graph evidence for step 3.

Every graph call opens a read-only, query-only SQLite connection and reads the
entities and relationship rows in one transaction. It builds adjacency in memory,
then traverses it. A later call sees committed request creations and updates from
the future MCP server; no request state is embedded or cached across graph calls.
Document retrieval and graph retrieval never write application records.

## Validation status

On 2026-10-08, all 49 automated checks passed in the Windows Python 3.12
`.venv-win` environment, including vector-index checks for ingestion, provenance,
model mismatch, failed-ingestion preservation, and mutation-free search. Live
Google query embeddings and document/graph retrieval passed the recorded demo
scenarios in `runtime/evaluation.json`. A resolved dependency lock is still pending.
