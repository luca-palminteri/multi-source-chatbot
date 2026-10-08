"""Ensure evaluation rejects plausible answers without observable evidence."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from assistant.evaluation import check_turn


class EvaluationTests(unittest.TestCase):
    def test_answer_alone_cannot_pass(self):
        result = {"ok": True, "answer": "Created successfully", "trace": []}
        self.assertTrue(check_turn(result, [], [], [], action="create_service_request"))

    def test_readonly_write_and_unexpected_action_fail(self):
        result = {"ok": True, "trace": [{"event": "tool_selected", "name": "create_service_request"}]}
        errors = check_turn(result, [], ["before"], ["after"])
        self.assertEqual(len(errors), 3)

    def test_combined_requires_sources_citations_and_complete_trace(self):
        result = {"ok": True, "trace": [{"event": "tool_selected", "name": "lookup_information"}]}
        lookup = {"answer": "Policy [D1], owner [G1]", "sources": {"D1": {}, "G1": {}},
                  "trace": [{"event": event} for event in
                            ("planning", "document_retrieval", "graph_retrieval", "synthesis")]}
        self.assertEqual(check_turn(result, [lookup], [], [], combined=True), [])
        lookup["answer"] = "Policy [D1]"
        self.assertTrue(check_turn(result, [lookup], [], [], combined=True))

    def test_stale_record_is_rejected(self):
        result = {"ok": True, "trace": [{"event": "tool_selected", "name": "lookup_information"}]}
        lookup = {"sources": {"G1": {"entities": [{"id": "req-1", "attributes": {"version": 1}}]}},
                  "trace": [{"event": event} for event in
                            ("planning", "document_retrieval", "graph_retrieval", "synthesis")]}
        self.assertTrue(check_turn(result, [lookup], [], [], expected_record={"id": "req-1", "version": 2}))
