# Step 4: Implement the action MCP server

## Implementation status

Server, typed schemas, transactional mutations, and real-client smoke check are
implemented. See [startup and validation](../../docs/actions.md). Storage tests
pass locally. Real subprocess MCP checks pass discovery, validation, mutations,
restart persistence, and graph visibility in the clean locked Windows Python 3.12
environment. Agent integration is implemented in step 5.

## Outcome

A separate MCP server that exposes the supported mutations with valid schemas and persistent results.

## Prerequisites

Step 1 action contracts and step 2 application data/store interfaces.

## Tasks

- Choose a local MCP transport and use an MCP SDK to implement the protocol.
- Run the server as a separate process from the informational pipeline.
- Expose create_service_request and update_service_request_status. Creation requires a known requester, service, and description; status updates require a request ID and valid target status.
- Define a small status lifecycle such as open, in_progress, resolved, and cancelled. Persist request IDs and timestamps in SQLite; return the created or updated record.
- Provide informative tool descriptions, typed input schemas, and structured success/error outputs.
- Validate IDs, required fields, valid state transitions, and use-case constraints inside the server.
- Persist changes transactionally and return the affected record identifiers and resulting state.
- Make repeated identical requests safe where practical; define retry behavior so a transport failure does not cause unintended duplicate work.
- Ensure successful mutations are reflected in subsequent graph retrieval.
- Keep mutation implementations owned by the server; the agent must not call a parallel direct-write API.
- Document server startup and verify tool discovery and invocation through a real MCP client.

## Deliverables

Runnable MCP server, action tools, schemas, persistent action store, and MCP client smoke check.

## Completion criteria

- The client discovers each tool with its input schema.
- Valid MCP calls update the expected record and return verifiable results.
- Invalid inputs return useful errors without partial mutations.
- A later informational query observes the new state.
- The informational graph contains no MCP action execution path.

## Next step

[Connect the agent](../step-05/plan-step.md).
