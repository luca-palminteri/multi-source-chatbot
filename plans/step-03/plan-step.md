# Step 3: Build the centralized informational pipeline

## Outcome

One callable informational pipeline that gathers document and graph evidence and synthesizes grounded answers.

## Prerequisites

Step 2 retrievers and evidence contracts.

## Tasks

- Define pipeline state: user question, relevant conversation context, document evidence, graph evidence, and final answer.
- Implement the centralized graph using the selected orchestration framework.
- For the initial demo, gather both document and graph evidence for every informational request; this makes coverage explicit and avoids intent heuristics within retrieval.
- Allow graph query planning to use the model or a bounded read-only query interface. Validate any generated queries before execution.
- Synthesize an answer that distinguishes supported facts from unavailable information and cites the retrieved sources.
- Handle irrelevant, empty, or conflicting evidence without inventing facts.
- Expose the complete pipeline as a clearly described informational tool for the top-level agent.
- Record retrieval and synthesis trace events for later verification.
- Keep MCP clients, action tools, and mutation code outside this pipeline.

## Deliverables

Centralized informational graph, informational tool contract, answer grounding instructions, and trace output.

## Completion criteria

- A combined question uses both document and graph evidence in its answer.
- A missing-information question explains what evidence is unavailable.
- Every application information lookup exposed to the agent runs through this pipeline.
- No action tool can be invoked from the informational graph.

## Implementation status

Source implemented in `src/assistant/information.py`, with the `ask` CLI command,
`lookup_information` tool, grounding instructions, and per-call trace output.
See [pipeline documentation](../../docs/information.md). Compilation and the nine
available seed/graph/chunk checks pass. Eight pipeline tests and five vector
tests require unavailable dependencies and are skipped in this environment;
network restrictions blocked installation. Live combined-answer and missing-fact
acceptance checks remain pending, so completion is not yet verified.

## Next step

Connect this tool to the agent in [step 5](../step-05/plan-step.md), once step 4 is ready.
