"""Run real models, retrieval, and subprocess MCP against disposable demo state."""
import argparse
import asyncio
from dataclasses import replace
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from assistant.evaluation import check_turn


def snapshot(database):
    with closing(sqlite3.connect(database)) as connection:
        return list(connection.iterdump())


def requests(database):
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        return {row["id"]: dict(row) for row in connection.execute("SELECT * FROM service_requests")}


async def evaluate(report, output=None, actions_only=False):
    from assistant.agent import connect_agent
    from assistant.config import Settings
    from assistant.information import create_information_pipeline
    from assistant.providers import embedding_provider
    from assistant.retrieval.documents import ingest
    from assistant.storage import seed_database
    from langchain_core.tools import StructuredTool

    settings = Settings.load(ROOT)
    report["configuration"] = {"chat_model": settings.chat_model,
                               "embedding_model": settings.embedding_model}
    with tempfile.TemporaryDirectory(prefix="assistant-eval-") as directory:
        settings = replace(settings, sqlite_path=Path(directory) / "demo.sqlite3",
                           vector_index_path=Path(directory) / "index",
                           demo_employee_id="emp-001")
        seed_database(settings.sqlite_path, ROOT / "data/seed.json")
        ingest(settings.sqlite_path, ROOT, settings.vector_index_path,
               embedding_provider(settings), settings.embedding_provider, settings.embedding_model)
        pipeline = create_information_pipeline(settings)
        lookups = []

        def record_lookup(question, context=""):
            result = pipeline.invoke(question, context)
            lookups.append(result)
            return result

        original_tool = pipeline.as_tool()
        class RecordingPipeline:
            def as_tool(self):
                return StructuredTool.from_function(func=record_lookup, name=original_tool.name,
                    description=original_tool.description, args_schema=original_tool.args_schema)

        # The child MCP process must use the same disposable database as retrieval.
        overrides = {"SQLITE_PATH": str(settings.sqlite_path), "DEMO_EMPLOYEE_ID": "emp-001"}
        previous = {name: os.environ.get(name) for name in overrides}
        os.environ.update(overrides)
        try:
            async with connect_agent(settings, pipeline=RecordingPipeline()) as session:
                report["discovery"] = list(session.tool_names)
                if "assign_service_request" not in session.tool_names:
                    raise ValueError("Extension tool was not discovered")

                async def turn(label, prompt, *, action=None, combined=False,
                               expected_record=None, fresh=True, require_information=True):
                    if fresh:
                        # Same discovered workflow, separate conversation checkpoint.
                        from assistant.agent import AgentSession
                        current = AgentSession(session.workflow, session.tool_names)
                    else:
                        current = session
                    lookups.clear()
                    before = snapshot(settings.sqlite_path)
                    print(f"{label}: START", flush=True)
                    started = time.monotonic()
                    result = await current.ask(prompt)
                    after = snapshot(settings.sqlite_path)
                    failures = check_turn(result, lookups, before, after, action=action,
                                          combined=combined, expected_record=expected_record,
                                          require_information=require_information)
                    item = {"case": label, "prompt": prompt, "passed": not failures,
                            "elapsed_seconds": round(time.monotonic() - started, 1),
                            "failures": failures, "response": result, "lookups": list(lookups),
                            "database_before": before, "database_after": after}
                    report["cases"].append(item)
                    print(f"{label}: {'PASS' if not failures else 'FAIL'}", flush=True)
                    if failures:
                        print("  " + "; ".join(failures), flush=True)
                    if output:
                        output.parent.mkdir(parents=True, exist_ok=True)
                        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
                    return item

                if not actions_only:
                    await turn("capabilities", "Hey, what can I ask?", require_information=False)
                    for label, prompt in [
                        ("policy", "What does the VPN access policy require?"),
                        ("policy_paraphrase", "What prerequisites must I satisfy for remote VPN access?"),
                        ("graph", "Which services does Alex Rivera's team own?"),
                        ("graph_paraphrase", "What services are owned by Product Engineering?"),
                        ("missing_information", "What is our lunar travel reimbursement policy?"),
                        ("missing_arguments", "Create a service request for me."),
                        ("unknown_id", "Set request req-nonexistent to in_progress."),
                        ("invalid_transition", "Reopen my resolved request req-005.")]:
                        await turn(label, prompt, require_information=label != "missing_arguments")
                    await turn("combined", "Which team handles VPN access, and what does the policy require?",
                               combined=True, fresh=False)
                    await turn("combined_paraphrase", "Who owns the VPN service and what prerequisites apply?",
                               combined=True)
                initial = requests(settings.sqlite_path)
                created = await turn("create", 'Create a VPN access request for me. Summary: "Demo remote access". '
                                     'Description: "Need VPN for remote work starting October 12."',
                                     action="create_service_request", fresh=False, require_information=False)
                new = [row for key, row in requests(settings.sqlite_path).items() if key not in initial]
                if len(new) != 1 or new[0]["service_id"] != "svc-vpn" or new[0]["submitter_id"] != "emp-001":
                    created["failures"].append("Expected exactly one persisted VPN request for emp-001")
                    created["passed"] = False
                else:
                    record = new[0]
                    await turn("followup", "Show the request you just created, including its status and version.",
                               expected_record=record, fresh=False)
                    updated = await turn("update", f'Set {record["id"]} to in_progress.',
                                         action="update_service_request_status", fresh=False)
                    record = requests(settings.sqlite_path)[record["id"]]
                    if record["status"] != "in_progress" or record["version"] != 2:
                        updated["failures"].append("Persisted status/version did not update")
                        updated["passed"] = False
                    await turn("update_visible", f'What is the current status/version of {record["id"]}?',
                               expected_record=record)
                    await turn("extension", f'Assign {record["id"]} to its owning team IT Operations (team-it).',
                               action="assign_service_request")
                initial = requests(settings.sqlite_path)
                mixed = await turn("mixed", 'Check the VPN prerequisites and owning team, then create a VPN request. '
                                   'Summary: "Mixed demo". Description: "Need VPN for remote work."',
                                   action="create_service_request", combined=True)
                names = [e["name"] for e in mixed["response"]["trace"] if e["event"] == "tool_selected"]
                if ("lookup_information" not in names or "create_service_request" not in names or
                    names.index("lookup_information") > names.index("create_service_request") or
                    len(set(requests(settings.sqlite_path)) - set(initial)) != 1):
                    mixed["failures"].append("Mixed request did not retrieve before one persisted creation")
                    mixed["passed"] = False
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/evaluation.json")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--actions-only", action="store_true", help="Run create/follow-up/update/assignment/mixed loop only")
    args = parser.parse_args()
    from assistant.debug import configure
    configure(args.debug)
    report = {"kind": "live_integration", "cases": [], "passed": False}
    try:
        asyncio.run(evaluate(report, args.output, args.actions_only))
        report["passed"] = bool(report["cases"]) and all(case["passed"] for case in report["cases"])
    except Exception as exc:
        # Keep credential-bearing provider exception messages out of reports.
        report["blocked_by"] = type(exc).__name__
        print(f"Evaluation could not complete ({type(exc).__name__}); check dependencies and provider configuration.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Evidence report: {args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
