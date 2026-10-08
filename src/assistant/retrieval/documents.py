from contextlib import closing
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Protocol

import numpy as np

from ..debug import stage
from ..contracts import Passage, DocumentEvidence
from ..storage import read_connection
from .chunking import split_document


class Embeddings(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def _normalize(vectors, count):
    matrix = np.asarray(vectors, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != count or matrix.shape[1] == 0 or not np.isfinite(matrix).all():
        raise ValueError("Invalid embedding shape or values")
    norms = np.linalg.norm(matrix, axis=1)
    if np.any(norms == 0):
        raise ValueError("Embedding vectors must be nonzero")
    return matrix / norms[:, None]


def ingest(database: Path, root: Path, index: Path, embeddings: Embeddings,
           provider: str, model: str, *, chunk_size=900, overlap=120):
    passages = []
    root = root.resolve()
    with closing(read_connection(database)) as connection:
        documents = [dict(row) for row in connection.execute("SELECT * FROM documents ORDER BY id")]
    for document in documents:
        path = (root / document["path"]).resolve()
        if not path.is_relative_to((root / "data/documents").resolve()):
            raise ValueError("Document source escapes data/documents")
        passages.extend(split_document(path.read_text(encoding="utf-8"), document, chunk_size, overlap))
    if not passages:
        raise ValueError("No document passages to ingest")
    metadata = {"schema_version": 1, "provider": provider, "model": model,
                "passages": [asdict(passage) for passage in passages]}
    encoded = json.dumps(metadata, sort_keys=True, ensure_ascii=False)
    fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    target = index / "index.npz"
    if target.exists():
        with np.load(target, allow_pickle=False) as previous:
            if str(previous["fingerprint"]) == fingerprint:
                return len(passages)
    matrix = _normalize(embeddings.embed_documents([passage.text for passage in passages]), len(passages))
    # One atomic artifact keeps metadata and vectors in the same generation.
    index.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=index, suffix=".npz", delete=False) as stream:
            temporary = Path(stream.name)
            np.savez_compressed(stream, vectors=matrix, metadata=encoded, fingerprint=fingerprint)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return len(passages)


class DocumentRetriever:
    def __init__(self, index: Path, embeddings: Embeddings, provider: str, model: str):
        self.embeddings = embeddings
        with np.load(index / "index.npz", allow_pickle=False) as artifact:
            metadata = json.loads(str(artifact["metadata"]))
            self.matrix = artifact["vectors"].copy()
        if metadata["schema_version"] != 1 or (metadata["provider"], metadata["model"]) != (provider, model):
            raise ValueError("Index provider/model mismatch; rerun ingestion")
        self.passages = tuple(Passage(**row) for row in metadata["passages"])
        self.matrix = _normalize(self.matrix, len(self.passages))

    def search(self, query: str, *, top_k=4, min_score=0.0):
        if top_k < 1 or not -1 <= min_score <= 1:
            raise ValueError("Invalid retrieval limits")
        if not query.strip():
            return ()
        with stage("Query embedding (Google)"):
            query_vector = _normalize([self.embeddings.embed_query(query)], 1)[0]
        if query_vector.shape[0] != self.matrix.shape[1]:
            raise ValueError("Query embedding dimension does not match index")
        scores = self.matrix @ query_vector
        order = np.argsort(-scores, kind="stable")[:top_k]
        return tuple(DocumentEvidence(self.passages[int(i)], float(np.clip(scores[i], -1, 1)))
                     for i in order if scores[i] >= min_score)
