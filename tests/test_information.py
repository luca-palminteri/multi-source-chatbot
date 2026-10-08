"""Run the real compiled graph with deterministic models and seeded graph data."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from test_retrieval import Fixture
from assistant.contracts import DocumentEvidence, Passage

HAS_RUNTIME = all(importlib.util.find_spec(name) is not None
                  for name in ("langgraph", "langchain_core", "pydantic"))
if HAS_RUNTIME:
    from assistant.information import InformationPipeline, RetrievalPlan


class Documents:
    def __init__(self, evidence=()):
        self.evidence, self.calls = evidence, []

    def search(self, query, **kwargs):
        self.calls.append(query)
        return self.evidence


class Model:
    def __init__(self, plan, answer):
        self.plan, self.answer, self.calls = plan, answer, []

    def with_structured_output(self, schema):
        return SimpleNamespace(invoke=lambda messages: self.plan)

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.answer)


def query(entity_id="svc-vpn", steps=None):
    return {"entity_id": entity_id, "entity_type": "service", "name": "VPN",
            "steps": steps if steps is not None else [{"edge": "OWNS", "direction": "in"}]}


@unittest.skipUnless(HAS_RUNTIME, "Install project dependencies to run LangGraph checks")
class InformationTests(Fixture):
    def pipeline(self, queries=None, evidence=(), answer="No relevant evidence is available."):
        plan = {"document_query": "VPN access", "graph_queries": queries or [query()]}
        self.documents = Documents(evidence)
        self.model = Model(plan, answer)
        return InformationPipeline(self.documents, self.graph, self.model)

    def test_combined_evidence_tool_and_trace(self):
        passage = Passage("chunk-vpn", "doc-vpn", "pol-vpn", "VPN policy",
                          "data/documents/vpn.md", 1, "2026-10-01", 0, 26,
                          "VPN needs manager approval.")
        pipeline = self.pipeline(evidence=(DocumentEvidence(passage, 0.9),),
                                 answer="IT handles VPN [G1]. Manager approval is required [D1].")
        before = self.database.read_bytes()
        result = pipeline.as_tool().invoke({"question": "Who handles VPN and what is required?"})
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(self.documents.calls, ["VPN access"])
        self.assertEqual(result["sources"]["D1"]["passage"]["document_id"], "doc-vpn")
        self.assertEqual(result["sources"]["G1"]["entities"][-1]["id"], "team-it")
        self.assertEqual([item["event"] for item in result["trace"]],
                         ["planning", "document_retrieval", "graph_retrieval", "synthesis"])
        prompt = json.loads(self.model.calls[0][1][1])
        self.assertEqual(prompt["sources"], json.loads(json.dumps(result["sources"])))
        json.dumps(result)

    def test_missing_information_and_context(self):
        pipeline = self.pipeline(queries=[query("svc-missing", [])])
        result = pipeline.invoke("What is its policy?", "We were discussing an unknown service.")
        self.assertEqual(result["sources"], {})
        self.assertEqual(result["trace"][2]["missing_entity_ids"], ["svc-missing"])
        self.assertIn("No relevant evidence", result["answer"])
        self.assertEqual(len(self.documents.calls), 1)
        self.assertIn("unknown service", self.model.calls[0][1][1])

    def test_model_can_search_without_guessing_id(self):
        result = self.pipeline(queries=[query("")]).invoke("Which team owns VPN?")
        self.assertEqual(result["sources"]["G1"]["entities"][-1]["id"], "team-it")

    def test_invalid_plan_rejected_before_reads(self):
        pipeline = self.pipeline()
        self.model.plan["graph_queries"][0]["steps"][0]["edge"] = "DELETE"
        with self.assertRaises(ValueError):
            pipeline.invoke("Delete everything")
        self.assertEqual(self.documents.calls, [])
        self.assertEqual(self.model.calls, [])

    def test_query_bounds_and_unknown_fields(self):
        for queries in ([query()] * 9, [query(steps=[{"edge": "OWNS", "direction": "in"}] * 4)], []):
            with self.assertRaises(ValueError):
                RetrievalPlan.model_validate({"document_query": "VPN", "graph_queries": queries})
        with self.assertRaises(ValueError):
            RetrievalPlan.model_validate({"document_query": "VPN", "graph_queries": [query()], "sql": "DELETE"})

    def test_unknown_citation_and_empty_answer_rejected(self):
        for answer in ("Fact [D99]", ""):
            with self.assertRaises(ValueError):
                self.pipeline(answer=answer).invoke("VPN?")

    def test_conflicting_sources_preserved_for_synthesis(self):
        passages = tuple(DocumentEvidence(
            Passage(f"chunk-{i}", f"doc-{i}", "pol-vpn", "VPN policy",
                    "data/documents/vpn.md", i, "2026-10-01", 0, len(text), text), 0.9)
            for i, text in enumerate(("Approval is required.", "Approval is optional."), 1))
        pipeline = self.pipeline(evidence=passages,
                                 answer="The sources conflict about approval [D1] [D2].")
        result = pipeline.invoke("Is VPN approval required?")
        supplied = json.loads(self.model.calls[0][1][1])["sources"]
        self.assertEqual(supplied["D1"]["passage"]["text"], "Approval is required.")
        self.assertEqual(supplied["D2"]["passage"]["text"], "Approval is optional.")
        self.assertIn("conflict", result["answer"])

    def test_repeated_invocations_have_separate_traces(self):
        pipeline = self.pipeline()
        first = pipeline.invoke("VPN?")
        second = pipeline.invoke("VPN again?")
        self.assertEqual(len(first["trace"]), 4)
        self.assertEqual(len(second["trace"]), 4)
        with self.assertRaises(ValueError):
            pipeline.invoke("   ")


if __name__ == "__main__":
    unittest.main()
