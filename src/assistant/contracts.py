from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Passage:
    chunk_id: str
    document_id: str
    policy_id: str
    title: str
    source_path: str
    version: int
    effective_date: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class DocumentEvidence:
    passage: Passage
    score: float


@dataclass(frozen=True)
class Entity:
    id: str
    type: str
    attributes: dict[str, Any]
    source_table: str
    record_id: str


@dataclass(frozen=True)
class Relationship:
    source_id: str
    target_id: str
    type: str
    source_table: str
    record_ids: tuple[str, ...]


@dataclass(frozen=True)
class GraphPath:
    entities: tuple[Entity, ...]
    relationships: tuple[Relationship, ...]


@dataclass(frozen=True)
class GraphResult:
    paths: tuple[GraphPath, ...] = ()
    missing_entity_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceResult:
    documents: tuple[DocumentEvidence, ...] = ()
    graph: GraphResult = field(default_factory=GraphResult)
