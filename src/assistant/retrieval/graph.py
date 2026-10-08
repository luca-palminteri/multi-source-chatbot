from contextlib import closing
from pathlib import Path

from ..contracts import Entity, Relationship, GraphPath, GraphResult
from ..storage import read_connection

TABLE_TYPES = {"employees": "employee", "teams": "team", "services": "service",
               "policies": "policy", "service_requests": "request"}
EDGE_TYPES = {"MEMBER_OF", "OWNS", "APPLIES_TO", "SUBMITTED_BY", "ASSIGNED_TO", "REQUESTS"}


class GraphRetriever:
    def __init__(self, database: Path):
        self.database = database

    def _snapshot(self):
        entities, edges = {}, []
        with closing(read_connection(self.database)) as connection:
            # One consistent snapshot; rebuild on every query to see committed actions.
            connection.execute("BEGIN")
            for table, kind in TABLE_TYPES.items():
                for row in connection.execute(f"SELECT * FROM {table} ORDER BY id"):
                    attrs = dict(row)
                    entities[row["id"]] = Entity(row["id"], kind, attrs, table, row["id"])
                    links = {"employees": [("team_id", "MEMBER_OF")],
                             "service_requests": [("submitter_id", "SUBMITTED_BY"),
                                                  ("assigned_team_id", "ASSIGNED_TO"),
                                                  ("service_id", "REQUESTS")]}.get(table, [])
                    for column, edge_type in links:
                        edges.append(Relationship(row["id"], row[column], edge_type, table, (row["id"],)))
                    if table == "services":
                        edges.append(Relationship(row["owner_team_id"], row["id"], "OWNS", table, (row["id"],)))
            for row in connection.execute("SELECT * FROM policy_services ORDER BY policy_id, service_id"):
                edges.append(Relationship(row["policy_id"], row["service_id"], "APPLIES_TO",
                                          "policy_services", (row["policy_id"], row["service_id"])))
        return entities, edges

    def find_entities(self, *, entity_type=None, name=None):
        if entity_type is not None and entity_type not in TABLE_TYPES.values():
            raise ValueError("Unknown entity type")
        entities, _ = self._snapshot()
        return tuple(entity for entity in entities.values()
                     if (entity_type is None or entity.type == entity_type)
                     and (name is None or name.casefold() in str(entity.attributes.get("name", entity.attributes.get("title", entity.attributes.get("summary", "")))).casefold()))

    def traverse(self, start_id: str, steps: list[tuple[str, str]]):
        """Each step is (edge type, 'out' or 'in'); edges retain native direction."""
        for edge_type, direction in steps:
            if edge_type not in EDGE_TYPES or direction not in {"out", "in"}:
                raise ValueError("Unknown edge type or direction")
        entities, edges = self._snapshot()
        if start_id not in entities:
            return GraphResult(missing_entity_ids=(start_id,))
        adjacency = {}
        for edge in edges:
            adjacency.setdefault((edge.source_id, edge.type, "out"), []).append((edge.target_id, edge))
            adjacency.setdefault((edge.target_id, edge.type, "in"), []).append((edge.source_id, edge))
        paths = [GraphPath((entities[start_id],), ())]
        for edge_type, direction in steps:
            paths = [GraphPath(path.entities + (entities[target],), path.relationships + (edge,))
                     for path in paths
                     for target, edge in adjacency.get((path.entities[-1].id, edge_type, direction), [])]
        return GraphResult(paths=tuple(paths))
