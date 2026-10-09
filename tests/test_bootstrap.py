"""First-start and restart behavior without external model calls."""
from contextlib import closing, redirect_stdout
from dataclasses import replace
import io
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from assistant.bootstrap import initialize
from assistant.config import Settings
from assistant.retrieval.documents import DocumentRetriever


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(ROOT / "data", self.root / "data")
        self.settings = replace(Settings.load(ROOT), root=self.root,
                                sqlite_path=self.root / "runtime/assistant.sqlite3",
                                vector_index_path=self.root / "runtime/vector_index")
        self.embeddings = Mock()
        self.embeddings.embed_documents.side_effect = lambda texts: [[1., 2.] for _ in texts]
        provider = patch("assistant.bootstrap.embedding_provider", return_value=self.embeddings)
        provider.start()
        self.addCleanup(provider.stop)

    def initialize(self, settings=None):
        with redirect_stdout(io.StringIO()):
            initialize(settings or self.settings)

    def test_fresh_start_creates_usable_database_and_index(self):
        self.initialize()
        with closing(sqlite3.connect(self.settings.sqlite_path)) as connection:
            self.assertGreater(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 0)
        retriever = DocumentRetriever(self.settings.vector_index_path, self.embeddings,
                                      self.settings.embedding_provider, self.settings.embedding_model)
        self.assertGreater(len(retriever.passages), 0)
        self.embeddings.embed_documents.assert_called_once()

    def test_restart_reuses_index_and_preserves_action_state(self):
        self.initialize()
        artifact = self.settings.vector_index_path / "index.npz"
        before = artifact.read_bytes()
        with closing(sqlite3.connect(self.settings.sqlite_path)) as connection:
            with connection:
                connection.execute("UPDATE service_requests SET status='in_progress', version=2 WHERE id='req-001'")
        self.initialize()
        self.embeddings.embed_documents.assert_called_once()
        self.assertEqual(artifact.read_bytes(), before)
        with closing(sqlite3.connect(self.settings.sqlite_path)) as connection:
            self.assertEqual(connection.execute("SELECT status, version FROM service_requests WHERE id='req-001'").fetchone(),
                             ("in_progress", 2))

    def test_changed_embedding_model_refreshes_index(self):
        self.initialize()
        changed = replace(self.settings, embedding_model="different-model")
        self.initialize(changed)
        self.assertEqual(self.embeddings.embed_documents.call_count, 2)
        DocumentRetriever(changed.vector_index_path, self.embeddings,
                          changed.embedding_provider, changed.embedding_model)

    def test_failed_initial_ingestion_can_be_retried(self):
        self.embeddings.embed_documents.side_effect = RuntimeError("Embedding service unavailable")
        with self.assertRaises(RuntimeError):
            self.initialize()
        self.assertFalse((self.settings.vector_index_path / "index.npz").exists())
        self.embeddings.embed_documents.side_effect = lambda texts: [[1., 2.] for _ in texts]
        self.initialize()
        self.assertTrue((self.settings.vector_index_path / "index.npz").exists())


if __name__ == "__main__":
    unittest.main()
