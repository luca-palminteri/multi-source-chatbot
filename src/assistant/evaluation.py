"""Evidence checks for live evaluation; never routes or executes user requests."""
import re


def check_turn(result, lookups, before, after, *, action=None, combined=False,
               expected_record=None, require_information=True):
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
    elif not any(event["event"] == "tool_result" and event["name"] == action
                 for event in result["trace"]):
        failures.append("Selected action has no MCP result")
    if require_information or combined or expected_record:
        if "lookup_information" not in selected or not lookups:
            failures.append("No centralized information lookup observed")
    for lookup in lookups:
        events = [item["event"] for item in lookup["trace"]]
        if events != ["planning", "document_retrieval", "graph_retrieval", "synthesis"]:
            failures.append("Incomplete centralized retrieval trace")
    if combined:
        if not any(re.search(r"\[D\d+\]", item["answer"]) and
                   re.search(r"\[G\d+\]", item["answer"]) and
                   any(key.startswith("D") for key in item["sources"]) and
                   any(key.startswith("G") for key in item["sources"])
                   for item in lookups):
            failures.append("Combined answer does not cite both evidence sources")
    if expected_record:
        entities = [entity for item in lookups for key, source in item["sources"].items()
                    if key.startswith("G") for entity in source["entities"]]
        if not any(entity["id"] == expected_record["id"] and
                   entity["attributes"] == expected_record for entity in entities):
            failures.append("Information lookup did not retrieve current persisted request")
    return failures
