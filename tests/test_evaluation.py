"""Ensure evaluation rejects plausible answers without observable evidence."""
import json
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
        result = {"ok": True, "answer": "Policy [D1], owner [G1]",
                  "trace": [{"event": "tool_selected", "name": "lookup_information"}]}
        lookup = {"answer": "Policy [D1], owner [G1]", "sources": {"D1": {}, "G1": {}},
                  "trace": [{"event": event} for event in
                            ("planning", "document_retrieval", "graph_retrieval", "synthesis")]}
        self.assertEqual(check_turn(result, [lookup], [], [], combined=True), [])
        lookup["answer"] = "Policy [D1]"
        self.assertTrue(check_turn(result, [lookup], [], [], combined=True))

    def test_final_answer_must_preserve_supported_citations(self):
        lookup = {"answer": "Policy [D1], owner [G1]", "sources": {"D1": {}, "G1": {}},
                  "trace": [{"event": event} for event in
                            ("planning", "document_retrieval", "graph_retrieval", "synthesis")]}
        result = {"ok": True, "answer": "Policy and owner",
                  "trace": [{"event": "tool_selected", "name": "lookup_information"}]}
        errors = check_turn(result, [lookup], [], [], combined=True)
        self.assertIn("Final answer is missing a supported D citation", errors)
        self.assertIn("Final answer is missing a supported G citation", errors)
        result["answer"] = "Policy [D99], owner [G1]"
        self.assertIn("Final answer cites an unavailable source",
                      check_turn(result, [lookup], [], [], combined=True))
        result["answer"] = "Policy and owner [D99, G1]"
        self.assertIn("Final answer cites an unavailable source",
                      check_turn(result, [lookup], [], [], combined=True))
        result["answer"] = "Policy and owner [D1, G1]"
        lookup["answer"] = "Policy and owner [D1, G1]"
        self.assertEqual(check_turn(result, [lookup], [], [], combined=True), [])

    def test_action_requires_successful_matching_result(self):
        action = "create_service_request"
        result = {"ok": True, "answer": "Created", "trace": [
            {"event": "tool_selected", "name": action, "id": "call-1"},
            {"event": "tool_result", "name": action, "id": "call-1",
             "status": "success", "result": None}]}
        outcome = result["trace"][1]
        for payload in ({"ok": False, "error": {"code": "FORBIDDEN"}},
                        {"ok": True}, {"ok": True, "request": {}}, "invalid JSON"):
            outcome["result"] = json.dumps(payload)
            self.assertTrue(check_turn(result, [], [], [], action=action, require_information=False))
        payload = {"ok": True, "request": {"id": "req-1"}}
        for content in (payload, json.dumps(payload),
                        [{"type": "text", "text": json.dumps(payload)}]):
            outcome["result"] = content
            self.assertEqual(check_turn(result, [], [], [], action=action,
                                        require_information=False), [])
        outcome["status"] = "error"
        self.assertTrue(check_turn(result, [], [], [], action=action, require_information=False))
        outcome["status"] = "success"
        outcome["id"] = "another-call"
        self.assertIn("Selected action call has no matching MCP result",
                      check_turn(result, [], [], [], action=action, require_information=False))
        outcome["id"] = "call-1"
        result["trace"].append({"event": "tool_selected", "name": "unexpected_action", "id": "extra"})
        self.assertIn("Unexpected additional action selected",
                      check_turn(result, [], [], [], action=action, require_information=False))

    def test_each_action_call_needs_a_result(self):
        action = "create_service_request"
        result = {"ok": True, "trace": [
            {"event": "tool_selected", "name": action, "id": "one"},
            {"event": "tool_selected", "name": action, "id": "two"},
            {"event": "tool_result", "name": action, "id": "one", "status": "success",
             "result": {"ok": True, "request": {"id": "req-1"}}}]}
        self.assertTrue(check_turn(result, [], [], [], action=action, require_information=False))

    def test_expected_answer_content_is_checked(self):
        result = {"ok": True, "answer": "Manager approval is required; enable MFA.", "trace": []}
        patterns = (r"manager.{0,30}approval", r"MFA|multi.factor")
        self.assertEqual(check_turn(result, [], [], [], require_information=False,
                                    answer_patterns=patterns), [])
        result["answer"] = "VPN access is available."
        self.assertEqual(len(check_turn(result, [], [], [], require_information=False,
                                       answer_patterns=patterns)), 2)

    def test_stale_record_is_rejected(self):
        result = {"ok": True, "trace": [{"event": "tool_selected", "name": "lookup_information"}]}
        lookup = {"sources": {"G1": {"entities": [{"id": "req-1", "attributes": {"version": 1}}]}},
                  "trace": [{"event": event} for event in
                            ("planning", "document_retrieval", "graph_retrieval", "synthesis")]}
        self.assertTrue(check_turn(result, [lookup], [], [], expected_record={"id": "req-1", "version": 2}))
