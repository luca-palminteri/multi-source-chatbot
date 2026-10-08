# Step 1: Define scope and demo data

## Implementation status

Step 1 deliverables are implemented. See [scope and architecture](../../docs/architecture.md),
[data/action contracts](../../docs/contracts.md), [example requests](../../docs/examples.md),
[seed dataset](../../data/seed.json), and [configuration template](../../.env.example).
Run `python scripts/validate_demo.py` from the repository root to validate the sources.
Source validation passes. Model and embedding defaults, retrieval, the chatbot
runtime, and MCP actions are implemented in later steps. Current verification
and remaining acceptance work are recorded in [the demo guide](../../docs/demo.md).

## Outcome

A bounded use case, agreed architecture, and small reproducible dataset that demonstrate every mandatory requirement.

## Prerequisites

Read [INSTRUCTIONS.md](../../INSTRUCTIONS.md). Use the confirmed internal knowledge assistant scope, Python with LangGraph/LangChain, terminal UI, and synthetic data. Select model access before implementing provider-dependent code.

## Tasks

- Describe the intended user and the questions and actions the assistant supports.
- Select a tool-calling model and embedding approach; document configuration variables without storing secrets.
- Select the orchestration framework, local storage, graph representation, and passive UI.
- Define entity IDs, relationships, document metadata, and action input/output contracts.
- Create synthetic employees, teams, services, policies, and service requests. Include membership, service ownership, policy applicability, submitter, and assignment relationships.
- Seed approximately 5 policy/service documents, 3 teams, 6 employees, 4 services, and 6 service requests. Include VPN access, software installation, and equipment support scenarios.
- Define create_service_request and update_service_request_status as the initial actions. Use a known demo employee identity and define which details require clarification.
- Include facts split across documents and graph relationships so combining both sources has a clear purpose.
- Choose the authoritative store for mutable facts. Ensure graph retrieval reflects updates, rather than maintaining an unsynchronized duplicate.
- Write representative informational, action, mixed, ambiguous, and unsupported requests with expected behavior.
- Document component boundaries and a proposed directory layout for application code, data, MCP server, UI, and checks.

## Deliverables

Scope notes, architecture diagram, data schema, seed files, example requests, and configuration template.

## Completion criteria

- At least one example requires document evidence and graph relationships together.
- At least two useful actions are defined with required inputs and observable persisted results.
- Model access is selected and the confirmed Python/LangGraph/LangChain stack is configured.
- The demo can use synthetic data if external sources are unavailable.

## Next step

[Build retrieval](../step-02/plan-step.md).
