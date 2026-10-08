# Step 2: Build document and graph retrieval

## Outcome

Two read-only retrieval components with consistent, traceable results.

## Prerequisites

Step 1 data schema, seed dataset, and technology choices.

## Tasks

- Create the project environment, dependency configuration, and local configuration loader.
- Implement repeatable data seeding and document ingestion.
- Split documents into useful passages, retain document IDs and source references, and generate embeddings for the document index.
- Build an explicit graph with typed entities and relationships over the synthetic internal data. A relational table alone does not demonstrate graph traversal; implement meaningful relationship queries, such as employee to team to owned service.
- Implement document search returning passages, source identifiers, and relevance information.
- Implement graph queries returning entities, relationships, and stable IDs, including at least one multi-hop example.
- Keep both retrieval interfaces read-only; data seeding is a setup operation rather than an agent action.
- Define how action updates become visible to subsequent graph queries.
- Handle empty results and missing entities explicitly.

## Deliverables

Ingestion command, reproducible seed command, document retriever, graph retriever, and shared evidence result contracts.

## Completion criteria

- A known question retrieves its supporting document passage.
- A relationship question returns the expected connected entities.
- Re-running ingestion does not accidentally duplicate the dataset.
- Retrieved evidence has enough provenance for the final answer to cite its source.
- Retrieval does not mutate application records.

## Implementation status

Source implementation is available in `src/assistant/` with setup/retrieval CLI,
evidence contracts, and tests. Retrieval checks pass as part of the 53-test suite
installed from `uv.lock` in a clean Windows Python 3.12 environment. Historical
live runs verified Google embeddings and document/graph retrieval. A new complete
run passed all 17 live scenarios with stronger assertions using locked dependencies.
See [retrieval setup and validation](../../docs/retrieval.md).

## Next steps

[Build the informational pipeline](../step-03/plan-step.md) and [implement the MCP server](../step-04/plan-step.md).
