"""Evidence checks for live evaluation; never routes or executes user requests."""
import json
import re

from .citations import citation_ids


def _action_result(content):
    """Decode adapter text blocks as well as direct structured MCP results."""
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (ValueError, TypeError):
            return None
    if isinstance(content, dict):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                result = _action_result(block.get("text"))
                if result is not None:
                    return result
    return None


def check_turn(result, lookups, before, after, *, action=None, combined=False,
               expected_record=None, require_information=True, answer_patterns=(),
               citation_types=()):
    failures = []
    selected = [event["name"] for event in result["trace"]
                if event["event"] == "tool_selected"]
    if not result["ok"]:
        failures.append("Agent execution failed")
    if action is None:
        if before != after:
            failures.append("Read-only or invalid request changed persisted records")
        if any(name != "lookup_information" for name in selected):
            failures.append("Unexpected action selected")
    elif action not in selected:
        failures.append(f"Expected MCP tool was not selected: {action}")
    else:
        if any(name not in {"lookup_information", action} for name in selected):
            failures.append("Unexpected additional action selected")
        calls = [event for event in result["trace"]
                 if event["event"] == "tool_selected" and event["name"] == action]
        outcomes = [event for event in result["trace"]
                    if event["event"] == "tool_result" and event["name"] == action]
        if not outcomes:
            failures.append("Selected action has no MCP result")
        for call in calls:
            matching = [event for event in outcomes if event.get("id") == call.get("id")]
            if not matching:
                failures.append("Selected action call has no matching MCP result")
            for event in matching:
                payload = _action_result(event.get("result"))
                if (event.get("status") != "success" or not payload or
                        payload.get("ok") is not True or
                        not isinstance(payload.get("request"), dict) or
                        not payload["request"].get("id")):
                    failures.append("MCP action did not return a successful persisted request")
    if require_information or combined or expected_record:
        if "lookup_information" not in selected or not lookups:
            failures.append("No centralized information lookup observed")
    for lookup in lookups:
        events = [item["event"] for item in lookup["trace"]]
        if events != ["planning", "document_retrieval", "graph_retrieval", "synthesis"]:
            failures.append("Incomplete centralized retrieval trace")
    if combined:
        if not any({"D", "G"} <= {key[0] for key in
                   citation_ids(item["answer"]) & item["sources"].keys()}
                   for item in lookups):
            failures.append("Combined answer does not cite both evidence sources")
    answer = result.get("answer", "")
    sources = {key for lookup in lookups for key in lookup["sources"]}
    citations = citation_ids(answer)
    if citations - sources:
        failures.append("Final answer cites an unavailable source")
    for kind in set(citation_types) | ({"D", "G"} if combined else set()):
        if not any(key.startswith(kind) for key in citations & sources):
            failures.append(f"Final answer is missing a supported {kind} citation")
    for pattern in answer_patterns:
        if not re.search(pattern, answer, flags=re.IGNORECASE):
            failures.append(f"Final answer is missing expected content: {pattern}")
    if expected_record:
        entities = [entity for item in lookups for key, source in item["sources"].items()
                    if key.startswith("G") for entity in source["entities"]]
        if not any(entity["id"] == expected_record["id"] and
                   entity["attributes"] == expected_record for entity in entities):
            failures.append("Information lookup did not retrieve current persisted request")
    return failures
