"""Local Agent Server boundary. Routing remains entirely model selected."""
import asyncio
from contextlib import asynccontextmanager, closing
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from urllib.parse import parse_qs

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph_sdk.runtime import ServerRuntime
from langgraph.constants import TAG_NOSTREAM
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse, Response
from starlette.exceptions import HTTPException
from . import chat_service

from .agent import build_graph, connect_action_tools
from .config import Settings
from .information import InformationInput, InformationPipeline, create_information_pipeline
from .providers import chat_provider
from .debug import log_failure
from .messages import message_text

STOPPED = "Execution stopped. An action may have committed. Start a new conversation and retrieve current records before retrying."
TURN_TIMEOUT = 120


def allowed_origin(origin):
    return origin in {"http://localhost:3000", "http://127.0.0.1:3000", os.environ.get("CHAT_UI_ORIGIN")}


class ExecutionLedger:
    """Fail closed across cancellation, worker retries, and process restarts."""

    def __init__(self, path):
        self.path = Path(path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("CREATE TABLE IF NOT EXISTS executions (thread TEXT PRIMARY KEY, pending INTEGER NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY)")
        return connection

    def submission(self, message_id):
        with closing(self._connect()) as connection, connection:
            try:
                connection.execute("INSERT INTO submissions VALUES (?)", (message_id,))
            except sqlite3.IntegrityError:
                raise ValueError("Message already submitted; retrieve history instead of resending") from None

    def begin(self, thread, run_id=None):
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT pending FROM executions WHERE thread=?", (thread,)).fetchone()
            if row and row[0]:
                raise ValueError(STOPPED)
            if run_id:
                try:
                    connection.execute("INSERT INTO attempts VALUES (?)", (run_id,))
                except sqlite3.IntegrityError:
                    raise ValueError(STOPPED) from None
            connection.execute("INSERT INTO executions VALUES (?, 1) ON CONFLICT(thread) DO UPDATE SET pending=1", (thread,))

    def finish(self, thread):
        with closing(self._connect()) as connection, connection:
            connection.execute("UPDATE executions SET pending=0 WHERE thread=?", (thread,))


def ledger(settings):
    return ExecutionLedger(settings.sqlite_path.with_suffix(".web-executions.sqlite3"))


def validate_submission(body):
    """Validate executable input before the server applies message reducers."""
    allowed = {"assistant_id", "input", "config", "stream_mode", "stream_subgraphs",
               "stream_resumable", "on_disconnect", "multitask_strategy", "metadata",
               "if_not_exists", "on_completion"}
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValueError("Only new message runs are supported; replay, commands and checkpoints are disabled")
    if body.get("assistant_id") != "assistant":
        raise ValueError("Use the server-configured assistant")
    value = body.get("input")
    if not isinstance(value, dict) or set(value) != {"messages"}:
        raise ValueError("Submit only new messages")
    messages = value["messages"]
    if not isinstance(messages, list) or len(messages) != 1 or not isinstance(messages[0], dict):
        raise ValueError("Submit exactly one new user message")
    message = messages[0]
    if set(message) - {"id", "type", "role", "content"}:
        raise ValueError("Unsupported message fields")
    if message.get("type", message.get("role")) not in {"human", "user"} or (
            "role" in message and message["role"] not in {"human", "user"}):
        raise ValueError("Only user messages are accepted")
    content = message.get("content")
    if isinstance(content, list):
        if not content or any(not isinstance(block, dict) or set(block) != {"type", "text"}
                              or block["type"] != "text" or not isinstance(block["text"], str)
                              for block in content):
            raise ValueError("Only text messages are supported")
        content = "".join(block["text"] for block in content)
    if not isinstance(content, str) or not content.strip() or len(content) > 4000:
        raise ValueError("Message must contain 1 to 4000 characters")
    message_id = message.setdefault("id", str(uuid4()))
    if not isinstance(message_id, str) or not message_id or len(message_id) > 128:
        raise ValueError("Invalid message ID")
    if body.get("config") not in (None, {}, {"recursion_limit": 24}):
        raise ValueError("Execution configuration is server controlled")
    if body.get("multitask_strategy", "reject") != "reject":
        raise ValueError("Concurrent runs on one thread are rejected")
    if body.get("on_disconnect", "continue") != "continue":
        raise ValueError("Disconnect continues the existing run; use explicit cancellation to stop")
    body.update(config={"recursion_limit": 24}, multitask_strategy="reject", on_disconnect="continue")
    return message_id


class ExecutionBoundary:
    def __init__(self, app):
        self.app = app

    async def reject(self, scope, receive, send, detail, status=400):
        origin = dict(scope["headers"]).get(b"origin", b"").decode()
        headers = {"Vary": "Origin"}
        if allowed_origin(origin):
            headers["Access-Control-Allow-Origin"] = origin
        await JSONResponse({"detail": detail}, status, headers=headers)(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope["path"].rstrip("/"), scope["method"]
        query = parse_qs(scope.get("query_string", b"").decode())
        if path.startswith("/chat/"):
            origin = dict(scope["headers"]).get(b"origin", b"").decode()
            if method == "OPTIONS":
                headers = {"Vary": "Origin"}
                if allowed_origin(origin):
                    headers.update({"Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, X-Api-Key, X-Auth-Scheme"})
                return await Response(status_code=204, headers=headers)(scope, receive, send)
            try:
                raw = bytearray()
                if method == "POST":
                    while True:
                        event = await receive()
                        if event["type"] == "http.disconnect":
                            return
                        raw.extend(event.get("body", b""))
                        if len(raw) > 2000:
                            raise ValueError("Request too large")
                        if not event.get("more_body"):
                            break
                result = await chat_service.operation(path, method, query, json.loads(raw) if raw else None)
                response = JSONResponse(result)
            except (ValueError, TypeError) as exc:
                response = JSONResponse({"detail": str(exc)}, 400)
            except HTTPException as exc:
                response = JSONResponse({"detail": exc.detail}, exc.status_code)
            except Exception as exc:
                log_failure("Chat operation", exc)
                response = JSONResponse({"detail": "Chat operation failed. Retry after checking the server."}, 503)
            origin = dict(scope["headers"]).get(b"origin", b"").decode()
            if allowed_origin(origin):
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Vary"] = "Origin"
            return await response(scope, receive, send)
        native_thread = re.match(r"/threads/([^/]+)(?:/|$)", path)
        if native_thread and native_thread[1] != "search":
            from uuid import UUID
            try:
                native_id = str(UUID(native_thread[1]))
            except ValueError:
                return await self.reject(scope, receive, send, "Invalid thread ID")
            store = await asyncio.to_thread(chat_service.catalog)
            row = await asyncio.to_thread(store.get, native_id)
            if row and row["lifecycle"] != "live":
                return await self.reject(scope, receive, send, "Conversation permanently deleted")
        if path.endswith("/cancel") and "rollback" in query.get("action", []):
            return await self.reject(scope, receive, send, "Cancellation cannot roll back actions")
        run = re.fullmatch(r"/threads/([^/]+)/runs(?:/(stream|wait))?", path)
        creating = path == "/threads" and method == "POST"
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            # No alternate execution APIs, state edits, rollback, or mutable assistant configs.
            safe = (method == "POST" and (path in {"/threads", "/threads/search", "/assistants/search"}
                    or re.fullmatch(r"/threads/[^/]+/history", path)
                    or re.fullmatch(r"/threads/[^/]+/runs/[^/]+/cancel", path)))
            if not (safe or (run and method == "POST")):
                return await self.reject(scope, receive, send, "Execution replay and state changes are disabled")
        if not ((run and method == "POST") or creating):
            if path == "/threads/search" and method == "POST":
                store = await asyncio.to_thread(chat_service.catalog)
                tombstones = set(await asyncio.to_thread(store.tombstones))
                if tombstones:
                    start = None
                    chunks = bytearray()

                    async def filtered_send(event):
                        nonlocal start
                        if event["type"] == "http.response.start":
                            start = event
                        elif event["type"] == "http.response.body":
                            chunks.extend(event.get("body", b""))
                            if not event.get("more_body"):
                                payload = bytes(chunks)
                                if start["status"] == 200:
                                    rows = json.loads(payload)
                                    payload = json.dumps([row for row in rows if row["thread_id"] not in tombstones]).encode()
                                start["headers"] = [(key, value) for key, value in start["headers"] if key != b"content-length"]
                                start["headers"].append((b"content-length", str(len(payload)).encode()))
                                await send(start)
                                await send({"type": "http.response.body", "body": payload})
                        else:
                            await send(event)

                    return await self.app(scope, receive, filtered_send)
            return await self.app(scope, receive, send)
        raw = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            raw.extend(event.get("body", b""))
            if len(raw) > 32000:
                return await self.reject(scope, receive, send, "Request too large")
            if not event.get("more_body"):
                break
        try:
            body = json.loads(raw)
            if creating:
                if not isinstance(body, dict) or set(body) - {"thread_id", "metadata", "if_exists"}:
                    raise ValueError("Threads must start empty; injected state and supersteps are disabled")
                if body.get("thread_id"):
                    from uuid import UUID
                    body["thread_id"] = str(UUID(body["thread_id"]))
            else:
                message_id = validate_submission(body)
                settings = await asyncio.to_thread(lambda: Settings.load(Path(__file__).resolve().parents[2]))
                await asyncio.to_thread(ledger(settings).submission, message_id)
        except (ValueError, TypeError):
            return await self.reject(scope, receive, send, "Invalid or repeated submission; send one new user text message without replay options")
        payload = json.dumps(body).encode()
        delivered = False

        async def replacement_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": payload, "more_body": False}
            return await receive()

        scope = dict(scope)
        scope["headers"] = [(key, value) for key, value in scope["headers"] if key != b"content-length"]
        scope["headers"].append((b"content-length", str(len(payload)).encode()))
        identifier = body.get("thread_id") if creating else run[1]
        if identifier:
            from uuid import UUID
            identifier = str(UUID(identifier))
            admission_guard = chat_service.guards[identifier]
            if run and admission_guard.locked():
                return await self.reject(scope, receive, send, "Conversation is busy; retry when the current operation finishes", 409)
            await admission_guard.acquire()
            admitted = False

            async def admission_send(event):
                nonlocal admitted
                if event["type"] == "http.response.start" and not admitted:
                    admitted = True
                    admission_guard.release()
                    if run and event["status"] < 400:
                        chat_service.synchronize_after_run(identifier)
                await send(event)

            try:
                store = await asyncio.to_thread(chat_service.catalog)
                row = await asyncio.to_thread(store.get, identifier)
                if row and row["lifecycle"] != "live":
                    return await self.reject(scope, receive, admission_send, "Conversation permanently deleted")
                try:
                    await self.app(scope, replacement_receive, admission_send)
                finally:
                    try:
                        await chat_service.sync(identifier)
                    except Exception as exc:
                        log_failure("Chat catalog synchronization", exc)
            finally:
                if not admitted:
                    admission_guard.release()
        else:
            await self.app(scope, replacement_receive, send)


@asynccontextmanager
async def lifespan(app):
    store = await asyncio.to_thread(chat_service.catalog)
    await chat_service.reconcile(store)
    yield
    for task in list(chat_service.sync_tasks):
        task.cancel()
    if chat_service.sync_tasks:
        await asyncio.gather(*chat_service.sync_tasks, return_exceptions=True)


app = Starlette(middleware=[Middleware(ExecutionBoundary)], lifespan=lifespan)


class SchemaModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "schema-only"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, *args, **kwargs):
        raise RuntimeError("Schema model cannot execute")


def browser_action_tool(tool):
    """Preserve discovered schemas and JSON text for upstream's tool renderer."""
    async def invoke(**arguments):
        result = await tool.ainvoke(arguments)
        if isinstance(result, list) and all(isinstance(block, dict) and
                block.get("type") == "text" and isinstance(block.get("text"), str)
                for block in result):
            return "\n".join(block["text"] for block in result)
        return result

    return StructuredTool.from_function(coroutine=invoke, name=tool.name,
                                       description=tool.description, args_schema=tool.args_schema)


@asynccontextmanager
async def graph(config: RunnableConfig, runtime: ServerRuntime):
    settings = await asyncio.to_thread(lambda: Settings.load(Path(__file__).resolve().parents[2]))
    executing = runtime.execution_runtime is not None
    thread = config.get("configurable", {}).get("thread_id")
    execution = ledger(settings)
    if executing:
        if not thread:
            raise ValueError("A server thread is required")
        store = await asyncio.to_thread(chat_service.catalog)
        row = await asyncio.to_thread(store.get, str(thread))
        if row and row["lifecycle"] != "live":
            raise ValueError("Conversation permanently deleted")
        await asyncio.to_thread(store.set_model, str(thread), getattr(settings, "chat_model", None))
        await asyncio.to_thread(execution.begin, str(thread), config.get("configurable", {}).get("run_id"))

    completed = False

    async def before(state):
        return {}

    async def after(state):
        nonlocal completed
        last = state["messages"][-1]
        if not last.tool_calls:
            if not message_text(last).strip():
                raise ValueError("Agent returned no answer")
            completed = True
        return {}

    try:
        async with asyncio.timeout(TURN_TIMEOUT):
            async with connect_action_tools(settings) as tools:
                if executing:
                    model = await asyncio.to_thread(chat_provider, settings)
                    pipeline = await asyncio.to_thread(create_information_pipeline, settings)
                    if isinstance(pipeline, InformationPipeline):
                        pipeline.planner = pipeline.planner.with_config(tags=[TAG_NOSTREAM])
                        pipeline.model = pipeline.model.with_config(tags=[TAG_NOSTREAM])
                    information = pipeline.as_tool()
                else:
                    model = SchemaModel()
                    information = StructuredTool.from_function(
                        func=lambda question, context="": None, name="lookup_information",
                        description="Read-only centralized document and graph lookup", args_schema=InformationInput)
                workflow = build_graph(model, information, [browser_action_tool(tool) for tool in tools], settings.demo_employee_id,
                                       pre_model_hook=before, post_model_hook=after)
                yield workflow
        if executing and completed:
            await asyncio.to_thread(execution.finish, str(thread))
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log_failure("Web execution", exc)
        # Suppress provider URLs, credentials, and raw MCP errors in the error stream.
        raise RuntimeError(STOPPED) from None
