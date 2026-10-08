from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from assistant.storage import seed_database
from assistant.actions.store import commit_action
from assistant.retrieval.graph import GraphRetriever


class ActionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = SimpleNamespace(sqlite_path=Path(self.temp.name) / "actions.sqlite3", demo_employee_id="emp-001")
        seed_database(self.settings.sqlite_path, ROOT / "data/seed.json")

    def create(self):
        result = commit_action(self.settings, SimpleNamespace(service_id="svc-vpn", summary="VPN", description="Remote access"), True)
        self.assertTrue(result["ok"], result)
        return result["request"]

    def update(self, record, status, version):
        return commit_action(self.settings, SimpleNamespace(request_id=record["id"], status=status, expected_version=version), False)

    def test_creation_persists_and_graph_observes_it(self):
        record = self.create()
        self.assertEqual(record["assigned_team_id"], "team-it")
        self.assertEqual(record["version"], 1)
        path = GraphRetriever(self.settings.sqlite_path).traverse(record["id"], []).paths[0]
        self.assertEqual(path.entities[0].attributes, record)

    def test_lifecycle_conflict_and_noop(self):
        record = self.create()
        self.assertEqual(self.update(record, "resolved", 1)["error"]["code"], "INVALID_TRANSITION")
        updated = self.update(record, "in_progress", 1)["request"]
        self.assertEqual(updated["version"], 2)
        self.assertEqual(self.update(record, "in_progress", 1)["error"]["code"], "VERSION_CONFLICT")
        self.assertEqual(self.update(record, "in_progress", 2)["request"], updated)
        self.assertTrue(self.update(record, "resolved", 2)["ok"])
        self.assertEqual(self.update(record, "open", 3)["error"]["code"], "INVALID_TRANSITION")

    def test_ownership_and_unknown_ids(self):
        record = self.create()
        self.settings.demo_employee_id = "emp-002"
        self.assertEqual(self.update(record, "cancelled", 1)["error"]["code"], "FORBIDDEN")
        self.settings.demo_employee_id = "missing"
        self.assertEqual(self.update(record, "cancelled", 1)["error"]["code"], "FORBIDDEN")
        self.settings.demo_employee_id = "emp-001"
        self.assertEqual(self.update({"id": "req-missing"}, "cancelled", 1)["error"]["code"], "NOT_FOUND")

    def test_concurrent_updates_have_one_winner(self):
        record = self.create()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda status: self.update(record, status, 1), ["in_progress", "cancelled"]))
        self.assertEqual(sum(r["ok"] for r in results), 1)
        self.assertEqual(next(r for r in results if not r["ok"])["error"]["code"], "VERSION_CONFLICT")

    def test_assignment_validates_service_relationship_and_ownership(self):
        record = self.create()
        def assign(team, version=1):
            return commit_action(self.settings, SimpleNamespace(request_id=record["id"], team_id=team,
                                                               expected_version=version), False)
        self.assertEqual(assign("team-product")["error"]["code"], "INVALID_ASSIGNMENT")
        self.assertEqual(assign("team-missing")["error"]["code"], "INVALID_ASSIGNMENT")
        self.assertEqual(assign("team-it")["request"], record)
        self.assertEqual(assign("team-it", 2)["error"]["code"], "VERSION_CONFLICT")
        self.settings.demo_employee_id = "emp-002"
        self.assertEqual(assign("team-it")["error"]["code"], "FORBIDDEN")
        self.settings.demo_employee_id = "emp-001"
        self.update(record, "cancelled", 1)
        self.assertEqual(assign("team-it", 2)["error"]["code"], "INVALID_TRANSITION")

    def test_invalid_storage_write_rolls_back(self):
        import sqlite3
        from contextlib import closing
        result = commit_action(self.settings, SimpleNamespace(service_id="svc-vpn", summary="", description="issue"), True)
        self.assertEqual(result["error"]["code"], "STORAGE_ERROR")
        with closing(sqlite3.connect(self.settings.sqlite_path)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM service_requests").fetchone()[0], 6)


if __name__ == "__main__":
    unittest.main()
