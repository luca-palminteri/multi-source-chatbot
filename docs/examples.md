# Representative requests and expected behavior

These are acceptance scenarios for later steps, not implemented routing rules.

| Kind | Request | Expected behavior/evidence |
| --- | --- | --- |
| Informational, combined | Which team handles VPN access, and what does the access policy require? | Informational graph: team-it OWNS svc-vpn; pol-vpn APPLIES_TO svc-vpn; cite doc-vpn for manager approval, managed device, MFA. |
| Informational, multi-hop | Which services does my team own? | emp-001 MEMBER_OF team-product OWNS svc-software; cite relationship path. |
| Informational, document | Can I install software without a license? | Cite doc-software: approved catalog and valid license required. |
| Informational, state | What's the status of my VPN request req-001? | Read SQLite request: open, assigned team-it, version 1 in fresh seed. |
| Action | Create a VPN request for remote work starting October 12. | Model chooses MCP create; service svc-vpn, identity emp-001, supplied issue summarized; persisted open request assigned team-it. |
| Action, paraphrase | Move req-001 into work underway. | Retrieve version; model maps to in_progress; MCP update; version 2 persisted. |
| Mixed | Check what I need for VPN access, then create a request for remote work next week. | Informational graph for requirements then MCP create with supplied issue; never claim access or approvals granted. |
| Ambiguous | Create a request for me. | Clarify service and issue; no write yet. |
| Ambiguous | Close my request. | Clarify request ID and whether resolved or cancelled; no guessed mutation. |
| Unsupported | Install Photoshop on my laptop now. | Explain only service requests are supported; ask whether to create one and gather software details. |
| Missing evidence | What is the parental leave policy? | Informational graph returns no relevant evidence; state unavailable. |
| Unauthorized | Cancel req-003. | Server rejects: submitted by emp-003, not demo emp-001. |
| Invalid transition | Reopen req-005. | Reject terminal resolved transition, preserve state. |
| Freshness | Start req-001, then tell me its status. | MCP update followed by fresh informational graph read returns in_progress and version 2. |

Policy documents explain requirements, not live request status. Future checks must
verify actual tool traces and persisted state, including the absence of writes
for ambiguous/unsupported requests.
