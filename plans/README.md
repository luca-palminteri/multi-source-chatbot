# Implementation plan

Build a chatbot that answers questions through a centralized RAG + knowledge graph pipeline and performs actions exclusively through a separate MCP server.

Source of requirements: [INSTRUCTIONS.md](../INSTRUCTIONS.md).

## Confirmed scope

- Internal knowledge assistant for policies, teams, and service requests.
- Python with LangGraph/LangChain and a passive terminal chat interface.
- Synthetic demo documents and structured data.
- Model provider and embedding provider will be selected in step 1; keep their configuration replaceable.

Initial actions: create a service request and update its status. Initial entities: employees, teams, services, policies, and service requests. Relationships include membership, service ownership, policy applicability, request submitter, and request assignment.

Use a local document vector index and SQLite for persistent records. Represent and query explicit graph relationships over the structured data, with request state read from the authoritative store. A dedicated graph database is optional for this small demo.

Example combined question: "Which team handles VPN access, and what does the access policy require?" Example mixed request: "Check what I need for VPN access, then create a request for me." Seed a known demo employee identity; clarify missing action details.

## Steps

1. [Define scope and demo data](step-01/plan-step.md)
2. [Build document and graph retrieval](step-02/plan-step.md)
3. [Build the centralized informational pipeline](step-03/plan-step.md)
4. [Implement the action MCP server](step-04/plan-step.md)
5. [Connect autonomous agent orchestration](step-05/plan-step.md)
6. [Connect the passive chat interface](step-06/plan-step.md)
7. [Verify requirements and prepare the demo](step-07/plan-step.md)

Steps 3 and 4 both depend on step 2's data contracts; step 5 joins them. Keep actions outside the informational pipeline. Model-selected tool calls determine intent; do not implement keyword or manually classified intent routing. Ordinary input validation and protocol dispatch do not replace model intent selection.

## Overall acceptance criteria

- Informational requests always enter the centralized informational pipeline.
- Demonstrate answers supported by document passages and graph relationships.
- All user-requested mutations execute through MCP tools.
- The model selects tools autonomously, including for paraphrased and mixed requests.
- New MCP tools can be discovered without editing intent-routing code.
- The interface forwards messages and displays responses without selecting routes.
- A fresh checkout can be configured, seeded, and run using documented commands.
