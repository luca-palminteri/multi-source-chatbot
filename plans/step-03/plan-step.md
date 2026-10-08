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
See [pipeline documentation](../../docs/information.md). Pipeline and retrieval
tests pass as part of the 53-test suite in a clean locked Windows Python 3.12
environment. Historical live combined-answer and missing-information cases are
recorded in `runtime/evaluation.json`. A new complete live run with the stronger
final-answer checks passed all 17 scenarios in `runtime/evaluation-locked-final.json`.
See [verification status](../../docs/demo.md).

## Next step

Agent integration is implemented in [step 5](../step-05/plan-step.md).
