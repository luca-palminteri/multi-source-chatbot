"""Launch a real local server with deterministic models and disposable MCP state."""
import json
from contextlib import closing
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx

from assistant.storage import seed_database

ROOT = Path(__file__).resolve().parents[1]


def main():
    evidence = ROOT / "runtime/web-smoke"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "report.json").write_text(json.dumps({"passed": False, "status": "running"}), encoding="utf-8")
    checks = {}
    with tempfile.TemporaryDirectory(prefix="web-smoke-", dir=evidence) as directory:
        work = Path(directory)
        database = work / "assistant.sqlite3"
        seed_database(database, ROOT / "data/seed.json")
        fixture = work / "fixture.py"
        fixture.write_text(
            "import sys\n" + f"sys.path.insert(0, {str(ROOT / 'tests')!r})\n" +
            "from web_fixture import Model, Pipeline\nimport assistant.web as web\n"
            "web.chat_provider = lambda settings: Model()\n"
            "web.create_information_pipeline = lambda settings: Pipeline()\n"
            "graph = web.graph\napp = web.app\n", encoding="utf-8")
        config = work / "langgraph.json"
        config.write_text(json.dumps({"dependencies": [str(ROOT)], "graphs": {"assistant": "fixture:graph"},
                                      "http": {"app": "fixture:app"}}), encoding="utf-8")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        environment = {**os.environ, "PYTHONUTF8": "1", "LANGSMITH_TRACING": "false",
                       "SQLITE_PATH": str(database), "VECTOR_INDEX_PATH": str(work / "index"),
                       "LANGGRAPH_API_DIR": str(work / "history")}
        if "--browser" in sys.argv:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                ui_port = sock.getsockname()[1]
            ui_url = f"http://127.0.0.1:{ui_port}"
            environment["CHAT_UI_ORIGIN"] = ui_url
        with (evidence / "server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, "-c", "from langgraph_cli.cli import cli; cli()",
                "dev", "--config", str(config), "--host", "127.0.0.1", "--port", str(port),
                "--no-browser", "--no-reload", "--allow-blocking"], cwd=work, env=environment,
                stdout=log, stderr=subprocess.STDOUT)
            try:
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=30) as client:
                    deadline = time.monotonic() + 30
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError("Server failed; inspect runtime/web-smoke/server.log")
                        try:
                            if client.get("/ok").status_code == 200:
                                break
                        except httpx.ConnectError:
                            pass
                        if time.monotonic() > deadline:
                            raise TimeoutError("Server startup timed out")
                        time.sleep(0.2)

                    def thread():
                        response = client.post("/threads", json={})
                        response.raise_for_status()
                        return response.json()["thread_id"]

                    def body(text):
                        return {"assistant_id": "assistant", "input": {"messages": [
                            {"type": "human", "content": text, "id": str(uuid4())}]}}

                    def turn(identifier, text):
                        response = client.post(f"/threads/{identifier}/runs/wait", json=body(text))
                        response.raise_for_status()
                        return response.json()

                    assistants = client.post("/assistants/search", json={}).json()
                    checks["discovery"] = assistants[0]["graph_id"] == "assistant"
                    aid = assistants[0]["assistant_id"]
                    checks["schema"] = client.get(f"/assistants/{aid}/schemas").status_code == 200
                    identifier = thread()
                    submission = body("create-test")
                    submission.update(stream_mode=["values", "messages-tuple"], stream_resumable=True)
                    events = []
                    with client.stream("POST", f"/threads/{identifier}/runs/stream", json=submission) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if line.startswith("data: "):
                                events.append(json.loads(line[6:]))
                    (evidence / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
                    state = client.get(f"/threads/{identifier}/state").json()["values"]
                    calls = [call for message in state["messages"] for call in message.get("tool_calls", [])]
                    results = [message for message in state["messages"] if message["type"] == "tool"]
                    checks["native_tool_ids"] = len(calls) == 1 and len(results) == 1 and calls[0]["id"] == results[0]["tool_call_id"]
                    checks["streamed_messages"] = bool(events) and any(isinstance(e, dict) and "messages" in e for e in events)
                    checks["duplicate_rejected"] = client.post(f"/threads/{identifier}/runs/wait", json=submission).status_code == 400
                    followup = turn(identifier, "followup")
                    checks["continuity"] = "create-test" in str(followup["messages"][-1]["content"])
                    independent = turn(thread(), "fresh")
                    checks["isolation"] = "create-test" not in str(independent)
                    lookup = turn(thread(), "lookup-test")
                    checks["evidence_visible"] = "[D1]" in str(lookup) and "[G1]" in str(lookup)
                    for option in ("checkpoint", "command"):
                        invalid = body("create-test")
                        invalid[option] = {}
                        checks[f"{option}_blocked"] = client.post(f"/threads/{identifier}/runs/wait", json=invalid).status_code == 400
                    checks["state_edit_blocked"] = client.post(f"/threads/{identifier}/state", json={"values": {}}).status_code == 400
                    checks["thread_state_injection_blocked"] = client.post("/threads", json={"supersteps": []}).status_code == 400
                    rejection = client.post(f"/threads/{identifier}/runs/wait", json=invalid, headers={"Origin": "http://localhost:3000"})
                    checks["browser_can_read_rejection"] = rejection.headers.get("access-control-allow-origin") == "http://localhost:3000"
                    failed = thread()
                    error = turn(failed, "fail-test")
                    blocked = turn(failed, "create-test")
                    checks["sanitized_error"] = "__error__" in error and "private-provider" not in str(error)
                    checks["failed_thread_blocked"] = "__error__" in blocked
                    uncertain = thread()
                    checks["uncertain_action_error"] = "__error__" in turn(uncertain, "uncertain-test")
                    checks["uncertain_action_blocked"] = "__error__" in turn(uncertain, "create-test")
                    disconnected = thread()
                    payload = body("create-test")
                    payload.update(stream_mode=["values"], stream_resumable=True)
                    with client.stream("POST", f"/threads/{disconnected}/runs/stream", json=payload) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if line.startswith("data: "):
                                metadata = json.loads(line[6:])
                                if isinstance(metadata, dict) and "run_id" in metadata:
                                    disconnected_run = metadata["run_id"]
                                    break
                    for _ in range(100):
                        status = client.get(f"/threads/{disconnected}/runs/{disconnected_run}").json()["status"]
                        if status not in {"pending", "running"}:
                            break
                        time.sleep(0.1)
                    checks["disconnect_continues_same_run"] = status == "success"
                    history = client.get(f"/threads/{disconnected}/state").json()["values"]["messages"]
                    checks["reconnect_has_one_tool_result"] = len([m for m in history if m["type"] == "tool"]) == 1
                    slow = thread()
                    run = client.post(f"/threads/{slow}/runs", json=body("slow-test")).json()
                    # Wait for the factory to mark execution pending before cancelling.
                    guard = database.with_suffix(".web-executions.sqlite3")
                    for _ in range(100):
                        with closing(sqlite3.connect(guard)) as connection:
                            started = connection.execute("SELECT pending FROM executions WHERE thread=?", (slow,)).fetchone()
                        if started:
                            break
                        time.sleep(0.05)
                    checks["concurrency_rejected"] = client.post(f"/threads/{slow}/runs", json=body("create-test")).status_code == 409
                    checks["rollback_blocked"] = client.post(f"/threads/{slow}/runs/{run['run_id']}/cancel?action=rollback").status_code == 400
                    client.post(f"/threads/{slow}/runs/{run['run_id']}/cancel?wait=true&action=interrupt").raise_for_status()
                    checks["cancelled_thread_blocked"] = "__error__" in turn(slow, "create-test")
                    with closing(sqlite3.connect(database)) as connection:
                        count = connection.execute("SELECT COUNT(*) FROM service_requests WHERE summary='API smoke request'").fetchone()[0]
                    checks["no_duplicate_mutations"] = count == 3
                    # Step 11: native listing/state/history and narrow chat controls.
                    checks["native_history"] = bool(client.post(f"/threads/{identifier}/history", json={"limit": 2}).json())
                    renamed = "Unicode café / 聊天"
                    checks["rename"] = client.post(f"/chat/{identifier}/title", json={"title": renamed}).status_code == 200
                    checks["rename_validation"] = all(client.post(f"/chat/{identifier}/title", json=payload).status_code == 400
                        for payload in ({"title": " "}, {"title": "x" * 101}, {"title": "valid", "model": "injected"}))
                    checks["rename_does_not_edit_state"] = client.get(f"/threads/{identifier}/state").json()["values"] == followup
                    exported = client.get(f"/chat/{identifier}/export?format=json")
                    exported.raise_for_status()
                    transcript = json.loads(exported.json()["content"])
                    checks["json_export"] = transcript["version"] == 1 and transcript["title"] == renamed and any(m["type"] == "tool" for m in transcript["messages"])
                    checks["safe_export_filename"] = "/" not in exported.json()["filename"]
                    failure_export = client.get(f"/chat/{uncertain}/export?format=json")
                    failure_export.raise_for_status()
                    checks["failed_chat_export"] = any(m["type"] == "tool" for m in json.loads(failure_export.json()["content"])["messages"])
                    markdown = client.get(f"/chat/{identifier}/export?format=markdown").json()["content"]
                    checks["markdown_export"] = renamed in markdown and "create-test" in markdown
                    checks["literal_search"] = any(t["thread_id"] == identifier for t in client.get("/chat/history", params={"q": "CAFÉ"}).json()["threads"])
                    checks["message_search"] = any(t["thread_id"] == identifier for t in client.get("/chat/history", params={"q": "create-test"}).json()["threads"])
                    for _ in range(105):
                        thread()
                    found, cursor = [], None
                    while True:
                        page = client.get("/chat/history", params={"limit": 17, **({"cursor": cursor} if cursor else {})})
                        page.raise_for_status()
                        found.extend(t["thread_id"] for t in page.json()["threads"])
                        cursor = page.json()["cursor"]
                        if not cursor:
                            break
                    checks["pagination_beyond_100"] = len(found) > 100 and len(found) == len(set(found)) and identifier in found
                    running = thread()
                    run_response = client.post(f"/threads/{running}/runs", json=body("slow-test"))
                    run_response.raise_for_status()
                    checks["active_delete_rejected"] = client.post(f"/chat/{running}/delete", json={}).status_code == 409
                    checks["active_export_rejected"] = client.get(f"/chat/{running}/export").status_code == 409
                    checks["active_rename_allowed"] = client.post(f"/chat/{running}/title", json={"title": "Active chat"}).status_code == 200
                    from concurrent.futures import ThreadPoolExecutor
                    race = thread()
                    with ThreadPoolExecutor(2) as pool:
                        deletion = pool.submit(client.post, f"/chat/{race}/delete", json={})
                        admission = pool.submit(client.post, f"/threads/{race}/runs", json=body("slow-test"))
                        ds, rs = deletion.result().status_code, admission.result().status_code
                    checks["delete_admission_race"] = (ds == 200 and rs in {400, 409}) or (ds == 409 and rs == 200)
                    checks["blocked_history_delete"] = client.post(f"/chat/{slow}/delete", json={}).status_code == 200
                    checks["native_delete"] = client.post(f"/chat/{identifier}/delete", json={}).status_code == 200
                    checks["idempotent_delete"] = client.post(f"/chat/{identifier}/delete", json={}).status_code == 200
                    checks["deleted_state_blocked"] = client.get(f"/threads/{identifier}/state").status_code == 400
                    checks["deleted_export_blocked"] = client.get(f"/chat/{identifier}/export").status_code == 410
                    checks["old_id_recreation_blocked"] = client.post("/threads", json={"thread_id": identifier.upper()}).status_code == 400
                    checks["old_id_run_blocked"] = client.post(f"/threads/{identifier}/runs", json=body("fresh")).status_code == 400
                    checks["deleted_search_removed"] = not client.get("/chat/history", params={"q": renamed}).json()["threads"]
                    from assistant.chat_catalog import ChatCatalog
                    catalog = ChatCatalog(database.with_suffix(".chat-catalog.sqlite3"))
                    recovery = thread()
                    catalog.lifecycle(recovery, "pending")  # Simulates interruption before native delete.
                    native_rows = client.post("/threads/search", json={"ids": [recovery]}).json()
                    checks["native_search_excludes_tombstones"] = not native_rows
                    client.get("/chat/history").raise_for_status()
                    checks["interrupted_delete_recovered"] = catalog.get(recovery)["lifecycle"] == "deleted" and client.get(f"/threads/{recovery}").status_code == 400
                    with closing(sqlite3.connect(guard)) as connection:
                        checks["deletion_retains_safety_ledger"] = bool(connection.execute("SELECT * FROM executions WHERE thread=?", (identifier,)).fetchone())
                    with closing(sqlite3.connect(database)) as connection:
                        checks["deletion_retains_business_records"] = connection.execute("SELECT COUNT(*) FROM service_requests WHERE summary='API smoke request'").fetchone()[0] == 3
                    # Restart the same disposable native store and catalog.
                    for _ in range(100):
                        if client.get(f"/threads/{running}").json()["status"] != "busy":
                            break
                        time.sleep(0.1)
                    time.sleep(10.5)  # Pinned native runtime flushes every 10 seconds.
                    process.terminate()
                    process.wait(timeout=10)
                    process = subprocess.Popen([sys.executable, "-c", "from langgraph_cli.cli import cli; cli()",
                        "dev", "--config", str(config), "--host", "127.0.0.1", "--port", str(port),
                        "--no-browser", "--no-reload", "--allow-blocking"], cwd=work, env=environment,
                        stdout=log, stderr=subprocess.STDOUT)
                    deadline = time.monotonic() + 30
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError("Restart failed; inspect server.log")
                        try:
                            if client.get("/ok").status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        if time.monotonic() > deadline:
                            raise TimeoutError("Restart timed out")
                        time.sleep(0.2)
                    checks["title_survives_server_restart"] = client.get(f"/chat/{running}/settings").json().get("title") == "Active chat"
                    checks["message_search_survives_restart"] = any(t["thread_id"] == running for t in client.get("/chat/history", params={"q": "slow-test"}).json()["threads"])
                    checks["tombstone_survives_restart"] = client.post("/threads", json={"thread_id": identifier}).status_code == 400
                    if "--browser" in sys.argv:
                        api_url = f"http://127.0.0.1:{port}"
                        ui_env = {**os.environ, "NEXT_PUBLIC_API_URL": api_url, "NEXT_PUBLIC_ASSISTANT_ID": "assistant",
                                  "WEB_CHECK_DIST_DIR": ".next-chat-actions-check", "WEB_UI_URL": ui_url}
                        ui_config = ROOT / "ui/agent-chat-ui/tsconfig.json"
                        saved_ui_config = ui_config.read_bytes()
                        with (evidence / "ui.log").open("w", encoding="utf-8") as ui_log:
                            ui = subprocess.Popen(["node", "node_modules/next/dist/bin/next", "dev", "--hostname", "127.0.0.1",
                                "--port", str(ui_port)], cwd=ROOT / "ui/agent-chat-ui", env=ui_env, stdout=ui_log, stderr=subprocess.STDOUT)
                            try:
                                deadline = time.monotonic() + 60
                                while time.monotonic() < deadline:
                                    if ui.poll() is not None:
                                        raise RuntimeError("UI startup failed; inspect runtime/web-smoke/ui.log")
                                    try:
                                        if httpx.get(ui_url, timeout=10).status_code == 200:
                                            break
                                    except httpx.HTTPError:
                                        pass
                                    time.sleep(0.2)
                                result = subprocess.run(["node", str(ROOT / "scripts/check_chat_actions_browser.cjs"), api_url],
                                    cwd=ROOT, env=ui_env, timeout=180)
                                checks["chat_actions_browser"] = result.returncode == 0
                            finally:
                                try:
                                    ui.terminate()
                                    ui.wait(timeout=10)
                                finally:
                                    ui_config.write_bytes(saved_ui_config)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    report = {"passed": all(checks.values()), "checks": checks}
    (evidence / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
