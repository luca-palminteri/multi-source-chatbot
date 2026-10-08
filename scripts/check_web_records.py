"""Compare the saved browser tool results to an explicitly selected demo database."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("runtime/web-verification/browser-report.json"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    state = None
    for turn in report["turns"][:7]:
        for line in turn["stream"].splitlines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                if isinstance(event, dict) and "messages" in event:
                    state = event
    if not state:
        raise ValueError("Browser evidence has no conversation state")
    calls = {call["id"]: call for message in state["messages"] for call in message.get("tool_calls", [])}
    actions = []
    for message in state["messages"]:
        if message["type"] != "tool" or calls[message["tool_call_id"]]["name"] == "lookup_information":
            continue
        content = message["content"]
        if isinstance(content, list):
            content = "".join(block["text"] for block in content if block.get("type") == "text")
        actions.append({"call": calls[message["tool_call_id"]], "result": json.loads(content)})
    created = actions[0]["result"]["request"]
    # Read-only URI: a mistaken path must not create a new empty database.
    with closing(sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute("SELECT * FROM service_requests WHERE summary=?", (created["summary"],))]
    checks = {
        "browser_checks_passed": report["passed"],
        "one_created_request": len(rows) == 1 and rows[0]["id"] == created["id"],
        "three_successful_mcp_actions": len(actions) == 3 and all(action["result"]["ok"] for action in actions),
        "expected_action_sequence": [action["call"]["name"] for action in actions] == [
            "create_service_request", "update_service_request_status", "assign_service_request"],
        "fresh_versions": len(actions) == 3 and actions[1]["call"]["args"]["expected_version"] == 1
            and actions[2]["call"]["args"]["expected_version"] == 2,
        "current_status_and_version": len(rows) == 1 and rows[0]["status"] == "in_progress" and rows[0]["version"] == 2,
        "database_matches_final_mcp_result": len(rows) == 1 and rows[0] == actions[-1]["result"]["request"],
    }
    result = {"passed": all(checks.values()), "checks": checks, "database": str(args.database), "records": rows, "actions": actions}
    args.report.with_name("database-verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "checks": checks}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
