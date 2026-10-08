# Step 5: Connect autonomous agent orchestration

## Outcome

A model-driven agent that chooses the informational pipeline or MCP action tools and can sequence them for mixed requests.

## Prerequisites

Step 3 informational tool and step 4 runnable MCP server.

## Tasks

- Discover MCP tools at startup and convert their advertised schemas into model-callable tools using the selected framework integration.
- Register the informational pipeline alongside the discovered action tools.
- Write agent instructions requiring evidence retrieval for application questions and MCP execution for actions.
- Use the framework's generic tool execution loop. Do not implement keyword matching, a hand-authored intent classifier, or branches mapping user wording to routes.
- Preserve conversation context so follow-up references can resolve to known records.
- Ask for missing action arguments instead of inventing IDs or silently choosing an ambiguous target.
- Support mixed requests by gathering needed information before executing an explicitly requested action.
- Report action success only after receiving a successful tool result; surface failed executions accurately.
- Define bounded execution and failure handling for unavailable tools or services.
- Record selected tool names and results for architectural verification.
- Add assign_service_request as an extensibility example and verify it is discovered after reconnect/restart without editing routing code. Validate the assigned team's relationship to the requested service on the server.

## Deliverables

Agent entry point, MCP discovery integration, system instructions, conversation state, and execution traces.

## Completion criteria

- Informational paraphrases invoke the centralized informational tool.
- Action paraphrases invoke the appropriate MCP tool.
- A mixed request produces the required retrieval and action sequence.
- Ambiguous action targets result in a clarifying response without mutation.
- A newly advertised MCP tool is usable without changes to intent selection logic.

## Next step

[Connect the interface](../step-06/plan-step.md).
