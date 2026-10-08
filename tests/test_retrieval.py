"""Contract checks with synthetic embeddings; no API credentials or calls."""
from contextlib import closing
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from assistant.storage import seed_database, read_connection
from assistant.retrieval.graph import GraphRetriever
from assistant.retrieval.chunking import split_document

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
if HAS_NUMPY:
    from assistant.retrieval.documents import ingest, DocumentRetriever


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "assistant.sqlite3"
        self.index = Path(self.temp.name) / "index"
        seed_database(self.database, ROOT / "data/seed.json")
        self.graph = GraphRetriever(self.database)


class GraphTests(Fixture):
    def test_employee_team_owned_service_path(self):
        result = self.graph.traverse("emp-001", [("MEMBER_OF", "out"), ("OWNS", "out")])
        self.assertEqual(len(result.paths), 1)
        self.assertEqual([e.id for e in result.paths[0].entities],
                         ["emp-001", "team-product", "svc-software"])
        self.assertEqual([e.type for e in result.paths[0].relationships], ["MEMBER_OF", "OWNS"])
        self.assertEqual(result.paths[0].relationships[0].record_ids, ("emp-001",))
        json.dumps(asdict(result))

    def test_vpn_owner_reverse_traversal(self):
        path = self.graph.traverse("svc-vpn", [("OWNS", "in")]).paths[0]
        self.assertEqual(path.entities[-1].id, "team-it")
        self.assertEqual(path.relationships[0].source_id, "team-it")

    def test_policy_applicability(self):
        path = self.graph.traverse("pol-vpn", [("APPLIES_TO", "out")]).paths[0]
        self.assertEqual(path.entities[-1].id, "svc-vpn")
        self.assertEqual(path.relationships[0].record_ids, ("pol-vpn", "svc-vpn"))

    def test_missing_and_empty(self):
        missing = self.graph.traverse("emp-missing", [])
        self.assertEqual(missing.missing_entity_ids, ("emp-missing",))
        self.assertEqual(missing.paths, ())
        self.assertEqual(self.graph.traverse("emp-001", [("OWNS", "out")]).paths, ())

    def test_committed_state_visible_and_reseed_preserves_updates(self):
        with closing(sqlite3.connect(self.database)) as connection:
            with connection:
                connection.execute("UPDATE service_requests SET status='in_progress', version=2 WHERE id='req-001'")
                connection.execute("INSERT INTO service_requests SELECT 'req-new',service_id,submitter_id,assigned_team_id,summary,description,status,created_at,updated_at,version FROM service_requests WHERE id='req-001'")
        seed_database(self.database, ROOT / "data/seed.json")
        result = self.graph.traverse("req-001", [])
        self.assertEqual(result.paths[0].entities[0].attributes["version"], 2)
        self.assertEqual(result.paths[0].entities[0].attributes["status"], "in_progress")
        self.assertEqual(len(self.graph.find_entities(entity_type="request")), 7)

    def test_readonly_and_no_retrieval_mutations(self):
        before = self.database.read_bytes()
        self.graph.traverse("emp-001", [("SUBMITTED_BY", "in")])
        self.graph.find_entities(entity_type="service", name="vpn")
        self.assertEqual(before, self.database.read_bytes())
        with closing(read_connection(self.database)) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM teams")

    def test_foreign_keys_and_idempotency(self):
        seed_database(self.database, ROOT / "data/seed.json")
        self.assertEqual(len(self.graph.find_entities(entity_type="request")), 6)
        with closing(read_connection(self.database)) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_invalid_traversal(self):
        with self.assertRaises(ValueError):
            self.graph.traverse("emp-001", [("MEMBER_OF", "sideways")])


class ChunkTests(unittest.TestCase):
    def test_offsets_cover_source_and_are_repeatable(self):
        document = json.loads((ROOT / "data/seed.json").read_text())["documents"][0]
        text = (ROOT / document["path"]).read_text(encoding="utf-8")
        chunks = list(split_document(text, document, chunk_size=100, overlap=20))
        self.assertEqual(chunks, list(split_document(text, document, 100, 20)))
        covered = set()
        for chunk in chunks:
            self.assertEqual(chunk.text, text[chunk.start:chunk.end])
            self.assertLessEqual(len(chunk.text), 100)
            covered.update(range(chunk.start, chunk.end))
        self.assertEqual(covered, set(range(len(text))))


class SyntheticEmbeddings:
    """Test vectors only; this is never a selectable runtime provider."""
    calls = 0
    terms = ("vpn", "software", "equipment", "account", "request")

    def vector(self, text):
        return [float(text.casefold().count(term)) for term in self.terms] + [0.01]

    def embed_documents(self, texts):
        self.calls += 1
        return [self.vector(text) for text in texts]

    def embed_query(self, text):
        return self.vector(text)


@unittest.skipUnless(HAS_NUMPY, "Install project dependencies to run vector index checks")
class DocumentTests(Fixture):
    def setUp(self):
        super().setUp()
        self.embeddings = SyntheticEmbeddings()
        ingest(self.database, ROOT, self.index, self.embeddings, "test", "synthetic")
        self.retriever = DocumentRetriever(self.index, self.embeddings, "test", "synthetic")

    def test_known_question_and_provenance(self):
        evidence = self.retriever.search("What does VPN access require?", top_k=1)[0]
        self.assertEqual(evidence.passage.document_id, "doc-vpn")
        self.assertIn("manager approval", evidence.passage.text)
        self.assertIn("MFA", evidence.passage.text)
        self.assertGreater(evidence.score, 0)
        source = (ROOT / evidence.passage.source_path).read_text(encoding="utf-8")
        self.assertEqual(source[evidence.passage.start:evidence.passage.end], evidence.passage.text)

    def test_reingest_skips_embedding_and_does_not_duplicate(self):
        before = (self.index / "index.npz").read_bytes()
        count = ingest(self.database, ROOT, self.index, self.embeddings, "test", "synthetic")
        self.assertEqual(count, len(self.retriever.passages))
        self.assertEqual(self.embeddings.calls, 1)
        self.assertEqual(before, (self.index / "index.npz").read_bytes())

    def test_empty_threshold_and_model_mismatch(self):
        self.assertEqual(self.retriever.search("  "), ())
        self.assertEqual(self.retriever.search("unrelated", min_score=0.99), ())
        with self.assertRaises(ValueError):
            DocumentRetriever(self.index, self.embeddings, "test", "changed")

    def test_failed_ingestion_preserves_previous_index(self):
        before = (self.index / "index.npz").read_bytes()
        class Broken(SyntheticEmbeddings):
            def embed_documents(self, texts):
                return [[0.0] for _ in texts]
        with self.assertRaises(ValueError):
            ingest(self.database, ROOT, self.index, Broken(), "test", "changed")
        self.assertEqual(before, (self.index / "index.npz").read_bytes())

    def test_search_does_not_mutate_artifacts(self):
        before = (self.database.read_bytes(), (self.index / "index.npz").read_bytes())
        self.retriever.search("VPN")
        self.assertEqual(before, (self.database.read_bytes(), (self.index / "index.npz").read_bytes()))


if __name__ == "__main__":
    unittest.main()
