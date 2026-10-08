# Step 6: Connect the passive chat interface

## Outcome

A usable conversation interface that delegates decisions to the agent.

## Prerequisites

Step 5 agent entry point and the confirmed UI choice.

## Tasks

- Implement the selected Python terminal chat loop with LangGraph/LangChain behind a single agent entry point.
- Forward user messages and conversation/session identifiers to the agent.
- Display answers, source references, clarification requests, and action outcomes.
- Support a fresh conversation and a clean exit.
- Display useful connection/model errors without exposing credentials.
- Keep retrieval, action selection, and intent classification out of UI code.
- Document a single clear startup sequence for the MCP server and chat application.

## Deliverables

Runnable passive chat interface and startup instructions.

## Completion criteria

- A user can ask a question, follow up, request an action, and inspect its outcome in one conversation.
- Clarification answers resume the conversation with the necessary context.
- The UI forwards all requests to the same agent entry point.
- No custom frontend is needed to demonstrate the solution.

## Next step

[Verify and prepare the demo](../step-07/plan-step.md).
