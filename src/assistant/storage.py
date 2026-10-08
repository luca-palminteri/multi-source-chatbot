"""Setup writes are separate from read-only retrieval connections."""
import json
from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS employees (id TEXT PRIMARY KEY, name TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE, team_id TEXT NOT NULL REFERENCES teams(id));
CREATE TABLE IF NOT EXISTS services (id TEXT PRIMARY KEY, name TEXT NOT NULL,
 owner_team_id TEXT NOT NULL REFERENCES teams(id));
CREATE TABLE IF NOT EXISTS policies (id TEXT PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policy_services (policy_id TEXT REFERENCES policies(id),
 service_id TEXT REFERENCES services(id), PRIMARY KEY(policy_id, service_id));
CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, title TEXT NOT NULL,
 path TEXT NOT NULL UNIQUE, policy_id TEXT NOT NULL REFERENCES policies(id),
 version INTEGER NOT NULL CHECK(version > 0), effective_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS service_requests (id TEXT PRIMARY KEY,
 service_id TEXT NOT NULL REFERENCES services(id),
 submitter_id TEXT NOT NULL REFERENCES employees(id),
 assigned_team_id TEXT NOT NULL REFERENCES teams(id),
 summary TEXT NOT NULL CHECK(length(trim(summary)) BETWEEN 1 AND 120),
 description TEXT NOT NULL CHECK(length(trim(description)) BETWEEN 1 AND 2000),
 status TEXT NOT NULL CHECK(status IN ('open','in_progress','resolved','cancelled')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version > 0));
"""


def read_connection(path: Path):
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA query_only=ON")
    return connection


def seed_database(path: Path, seed_path: Path):
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    if data["schema_version"] != 1:
        raise ValueError("Unsupported seed schema")
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(SCHEMA)
        with connection:
            for table in ("teams", "employees", "services", "policies", "documents", "service_requests"):
                for original in data[table]:
                    row = {key: value for key, value in original.items() if key != "service_ids"}
                    columns = tuple(row)
                    # Preserve existing records, especially live request state.
                    connection.execute(
                        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) ON CONFLICT(id) DO NOTHING",
                        tuple(row.values()))
            for policy in data["policies"]:
                for service_id in policy["service_ids"]:
                    connection.execute("INSERT INTO policy_services VALUES (?,?) ON CONFLICT DO NOTHING",
                                       (policy["id"], service_id))
    finally:
        connection.close()
