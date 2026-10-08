# Data and action contracts

All data are fictional. IDs are stable strings with type prefixes (`emp-`,
`team-`, `svc-`, `pol-`, `req-`, `doc-`). IDs are unique within the dataset.
Timestamps use UTC ISO 8601; dates use ISO 8601. Seed timestamps are fixed.

## SQLite target schema

| Entity/table | Fields |
| --- | --- |
| teams | id PK, name |
| employees | id PK, name, email UNIQUE, team_id FK teams |
| services | id PK, name, owner_team_id FK teams |
| policies | id PK, title |
| policy_services | policy_id FK policies, service_id FK services; composite PK |
| service_requests | id PK, service_id FK services, submitter_id FK employees, assigned_team_id FK teams, summary, description, status, created_at, updated_at, version positive integer |
| documents | id PK, title, path UNIQUE, policy_id FK policies, version positive integer, effective_date |

Enable SQLite foreign keys. Seed `policy_services` from policy `service_ids`.
Create requests with UUID-based `req-` IDs, UTC timestamps, status `open`,
version 1, and assignment from the service's current owning team.
Reject blank summaries/descriptions; summary length 1–120, description 1–2000.
Statuses: `open`, `in_progress`, `resolved`, `cancelled`.
Allowed transitions: open → in_progress/cancelled; in_progress → resolved/cancelled.
Resolved and cancelled are terminal. Request assignments are persisted facts.

Graph edges are derived from foreign keys and join rows:

| Source → target | Edge type |
| --- | --- |
| employee → team | MEMBER_OF |
| team → service | OWNS |
| policy → service | APPLIES_TO |
| request → employee | SUBMITTED_BY |
| request → team | ASSIGNED_TO |
| request → service | REQUESTS |

Traverse forward/reverse edges explicitly and return the supporting path, e.g.
`emp-001 -MEMBER_OF-> team-product -OWNS-> svc-software`.
Document chunks retain document_id, policy_id, title, relative source path,
version, effective_date, chunk_id, text, and passage offsets. Retrieved document
evidence includes similarity score; graph evidence includes typed entity IDs,
edges, source tables/record IDs, and request version where relevant. Empty evidence
is an explicit empty result, never a fabricated answer.

## MCP tool contracts

Both tools expose object schemas with `additionalProperties: false`. Identity
comes from trusted session configuration, never from model-provided employee IDs.
For this demo only the configured employee's requests can be modified. Server
validation, authorization, and writes occur in one transaction.

`create_service_request` required input:

```json
{"service_id":"svc-vpn","summary":"VPN for remote work","description":"Need VPN access for remote work starting October 12."}
```

Resolve a service against graph evidence. Ask for service or a concrete issue if
missing/ambiguous; the model may summarize a supplied issue without asking for a
literal title. Do not invent dates, device IDs, software names, or approval.
Persist one request and return it after commit.

`update_service_request_status` required input:

```json
{"request_id":"req-001","status":"in_progress","expected_version":1}
```

Ask which request and target status if unspecified. Obtain expected_version from
a current informational read. Atomically update only when the stored version
matches and the transition is valid; increment version and updated_at. A conflict
requires a fresh read and reassessment, not a blind retry. Request IDs supplied
explicitly still require an ownership check on the server.

Success structured result for either action:

```json
{"ok":true,"request":{"id":"req-001","service_id":"svc-vpn","submitter_id":"emp-001","assigned_team_id":"team-it","summary":"VPN for remote work","description":"Need VPN access for remote work starting October 12.","status":"in_progress","created_at":"2026-10-01T09:00:00Z","updated_at":"2026-10-07T12:00:00Z","version":2}}
```

Failure result: `{"ok":false,"error":{"code":"VERSION_CONFLICT","message":"Request changed; retrieve its current state."}}`.
Other codes: VALIDATION_ERROR, NOT_FOUND, FORBIDDEN, INVALID_TRANSITION, STORAGE_ERROR.
Expose failures as MCP tool errors (`isError: true`) with the structured error.
No failed operation writes state. Do not claim success without a committed result.
Transport uncertainty during create must not trigger automatic retries; read back
the employee's requests and clarify before risking a duplicate. Idempotency keys
can be added later if retries are needed.
