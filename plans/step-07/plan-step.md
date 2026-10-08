# Step 7: Verify requirements and prepare the demo

## Implementation status

Evaluation runner, evidence assertions/tests, requirement mapping, and presenter
instructions are implemented. See [the demo guide](../../docs/demo.md).
Local validation: 26 tests passed, 13 dependency-related skips; seed validation
passed. Live MCP/model checks and clean setup validation remain pending because
dependency installation is blocked by network access. Step 7 is not yet complete.

## Outcome

A reproducible demonstration with evidence that the architecture meets the challenge requirements.

## Prerequisites

Steps 1–6 complete.

## Tasks

- Build a small integration evaluation set covering document questions, graph questions, combined questions, actions, mixed requests, missing information, and failures.
- Check actual tool traces and persisted records, rather than judging only the wording of the answer.
- Verify informational requests do not mutate records and always enter the centralized graph.
- Verify action requests execute through the MCP client/server boundary.
- Verify both evidence sources contribute to the combined-question example.
- Verify missing arguments and unknown IDs do not produce accidental writes.
- Verify an action update is visible to later informational retrieval.
- Repeat representative requests with paraphrased wording to check model-driven selection.
- Demonstrate adding an MCP tool without changing routing logic.
- Document setup, configuration, seed/reset commands, component boundaries, known limitations, and example conversations.
- Run the documented workflow from a clean local setup and capture representative traces for the demo.

## Deliverables

Targeted integration checks, evaluation examples/results, project README, architecture diagram, and demo script.

## Completion criteria

- Every mandatory item in INSTRUCTIONS.md maps to a working example and observable evidence.
- Document retrieval, graph retrieval, and MCP calls are real integrations rather than mocked demo responses.
- Setup commands and environment variables are documented without committed secrets.
- The final demo includes a policy question, "Which team handles VPN access, and what does the policy require?", service request creation, a follow-up showing the new request, a status update, and discovery of assign_service_request without routing edits.
- Optional features are clearly identified and do not delay completion of the required scope.
