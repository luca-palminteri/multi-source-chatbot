"""Private transactional storage implementation of the MCP server."""
from contextlib import closing
from datetime import datetime, timezone
import logging
import sqlite3
from uuid import uuid4

TRANSITIONS = {"open": {"in_progress", "cancelled"},
               "in_progress": {"resolved", "cancelled"}, "resolved": set(), "cancelled": set()}


class ActionError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def error(code, message):
    return {"ok": False, "error": {"code": code, "message": message}}


def _mutate(connection, employee_id, value, creating):
    if not connection.execute("SELECT 1 FROM employees WHERE id=?", (employee_id,)).fetchone():
        raise ActionError("FORBIDDEN", "Configured requester is not a known employee.")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if creating:
        service = connection.execute("SELECT * FROM services WHERE id=?", (value.service_id,)).fetchone()
        if service is None:
            raise ActionError("NOT_FOUND", "Service does not exist; retrieve a known service ID.")
        request_id = "req-" + str(uuid4())
        connection.execute("INSERT INTO service_requests VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (request_id, value.service_id, employee_id, service["owner_team_id"],
                            value.summary, value.description, "open", now, now, 1))
    else:
        request_id = value.request_id
        row = connection.execute("SELECT * FROM service_requests WHERE id=?", (request_id,)).fetchone()
        if row is None:
            raise ActionError("NOT_FOUND", "Request does not exist.")
        if row["submitter_id"] != employee_id:
            raise ActionError("FORBIDDEN", "Only the configured employee's requests can be modified.")
        if row["version"] != value.expected_version:
            raise ActionError("VERSION_CONFLICT", "Request changed; retrieve its current state.")
        # Repeating a target with the current version is a harmless no-op.
        if hasattr(value, "team_id"):
            service = connection.execute("SELECT owner_team_id FROM services WHERE id=?", (row["service_id"],)).fetchone()
            if service is None or service["owner_team_id"] != value.team_id:
                raise ActionError("INVALID_ASSIGNMENT", "Assigned team must own the requested service.")
            if row["status"] in {"resolved", "cancelled"}:
                raise ActionError("INVALID_TRANSITION", "Terminal requests cannot be assigned.")
            if row["assigned_team_id"] != value.team_id:
                connection.execute("UPDATE service_requests SET assigned_team_id=?, updated_at=?, version=version+1 WHERE id=? AND version=?",
                                   (value.team_id, now, request_id, value.expected_version))
        elif row["status"] != value.status:
            if value.status not in TRANSITIONS[row["status"]]:
                raise ActionError("INVALID_TRANSITION", f"Cannot change {row['status']} to {value.status}.")
            connection.execute("UPDATE service_requests SET status=?, updated_at=?, version=version+1 WHERE id=? AND version=?",
                               (value.status, now, request_id, value.expected_version))
    return dict(connection.execute("SELECT * FROM service_requests WHERE id=?", (request_id,)).fetchone())



def commit_action(settings, value, creating):
    try:
        with closing(sqlite3.connect(settings.sqlite_path.as_uri() + "?mode=rw", uri=True, timeout=10)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                record = _mutate(connection, settings.demo_employee_id, value, creating)
            return {"ok": True, "request": record}
    except ActionError as exc:
        return error(exc.code, exc.message)
    except sqlite3.Error:
        logging.exception("Action storage failure")
        return error("STORAGE_ERROR", "Storage unavailable; check server logs and seed the database before use.")
