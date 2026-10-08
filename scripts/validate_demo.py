"""Read-only validation of step 1 sources; no dependencies or API calls."""
import json
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate():
    data = json.loads((ROOT / "data/seed.json").read_text(encoding="utf-8"))
    if data["schema_version"] != 1:
        raise ValueError("Unsupported seed schema")
    counts = {"teams": 3, "employees": 6, "services": 4, "policies": 5,
              "documents": 5, "service_requests": 6}
    tables = {}
    all_ids = set()
    for table, count in counts.items():
        rows = data[table]
        if len(rows) != count:
            raise ValueError(f"Unexpected {table} count")
        tables[table] = {row["id"]: row for row in rows}
        for row in rows:
            if row["id"] in all_ids:
                raise ValueError(f"Duplicate ID: {row['id']}")
            all_ids.add(row["id"])

    def reference(value, table):
        if value not in tables[table]:
            raise ValueError(f"Missing {table} reference: {value}")

    emails = [row["email"] for row in data["employees"]]
    if len(set(emails)) != len(emails):
        raise ValueError("Duplicate employee email")
    for row in data["employees"]:
        reference(row["team_id"], "teams")
    reference("emp-001", "employees")
    for row in data["services"]:
        reference(row["owner_team_id"], "teams")
    for row in data["policies"]:
        if not row["service_ids"] or len(set(row["service_ids"])) != len(row["service_ids"]):
            raise ValueError("Empty or duplicate policy applicability")
        for service_id in row["service_ids"]:
            reference(service_id, "services")
    paths = set()
    for row in data["documents"]:
        reference(row["policy_id"], "policies")
        path = (ROOT / row["path"]).resolve()
        if not path.is_relative_to(ROOT / "data/documents") or path in paths:
            raise ValueError("Invalid or duplicate document path")
        paths.add(path)
        if not path.read_text(encoding="utf-8").strip():
            raise ValueError("Empty policy document")
        date.fromisoformat(row["effective_date"])
        if type(row["version"]) is not int or row["version"] < 1:
            raise ValueError("Invalid document version")
    for row in data["service_requests"]:
        reference(row["service_id"], "services")
        reference(row["submitter_id"], "employees")
        reference(row["assigned_team_id"], "teams")
        if row["status"] not in {"open", "in_progress", "resolved", "cancelled"}:
            raise ValueError("Invalid request status")
        for field, limit in (("summary", 120), ("description", 2000)):
            if not row[field].strip() or len(row[field]) > limit:
                raise ValueError(f"Invalid request {field}")
        if type(row["version"]) is not int or row["version"] < 1:
            raise ValueError("Invalid request version")
        timestamps = [datetime.fromisoformat(row[field].replace("Z", "+00:00"))
                      for field in ("created_at", "updated_at")]
        if any(value.utcoffset() is None or value.utcoffset().total_seconds() != 0
               for value in timestamps) or timestamps[1] < timestamps[0]:
            raise ValueError("Invalid UTC request timestamps")
    # Verify the two evidence scenarios, beyond simple foreign-key validity.
    alex_team = tables["employees"]["emp-001"]["team_id"]
    if tables["services"]["svc-software"]["owner_team_id"] != alex_team:
        raise ValueError("Missing employee-to-team-to-service demo path")
    if "svc-vpn" not in tables["policies"]["pol-vpn"]["service_ids"]:
        raise ValueError("Missing VPN policy relationship")
    print("Demo sources valid: 3 teams, 6 employees, 4 services, 5 policies/documents, 6 requests.")


if __name__ == "__main__":
    validate()
