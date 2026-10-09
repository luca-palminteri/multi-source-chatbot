"""Pinned local Agent Server integration; never calls its public HTTP boundary."""
import asyncio
from copy import deepcopy
from collections import defaultdict
from pathlib import Path
from uuid import UUID

from starlette.exceptions import HTTPException

from .chat_catalog import ChatCatalog, export_chat
from .config import Settings

guards = defaultdict(asyncio.Lock)
reconcile_guard = asyncio.Lock()
sync_tasks = set()


def catalog():
    settings = Settings.load(Path(__file__).resolve().parents[2])
    return ChatCatalog(settings.sqlite_path.with_suffix(".chat-catalog.sqlite3"))


def native():
    # These are the same extension operations used by langgraph-api==0.15.3.
    from langgraph_runtime.database import connect
    from langgraph_runtime.ops import Threads, Runs
    return connect, Threads, Runs


async def get_thread(identifier):
    connect, Threads, _ = native()
    async with connect() as conn:
        return deepcopy(await anext(await Threads.get(conn, UUID(identifier))))


async def active(identifier):
    connect, _, Runs = native()
    async with connect() as conn:
        for status in ("pending", "running"):
            if [r async for r in await Runs.search(conn, UUID(identifier), status=status, limit=1)]:
                return True
    return False


async def remove(identifier, store):
    connect, Threads, _ = native()
    try:
        async with connect() as conn:
            iterator = await Threads.delete(conn, UUID(identifier))
            async for _ in iterator:
                pass
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    await asyncio.to_thread(store.lifecycle, identifier, "deleted")


async def reconcile(store):
    async with reconcile_guard:
        # Also sweep completed tombstones: an abrupt process exit can precede the
        # in-memory runtime's periodic native-store flush after a successful delete.
        for identifier in await asyncio.to_thread(store.tombstones):
            async with guards[identifier]:
                if not await active(identifier):
                    await remove(identifier, store)
        connect, Threads, _ = native()
        offset = 0
        while offset is not None:
            async with connect() as conn:
                iterator, offset = await Threads.search(conn, metadata=None, values=None, status=None,
                    limit=100, offset=offset, sort_by="thread_id", sort_order="ASC")
                threads = [t async for t in iterator]
            for thread in threads:
                await asyncio.to_thread(store.sync, thread)


async def sync(identifier):
    try:
        store = await asyncio.to_thread(catalog)
        await asyncio.to_thread(store.sync, await get_thread(identifier))
    except HTTPException as exc:
        if exc.status_code != 404:
            raise


def synchronize_after_run(identifier):
    async def finish():
        try:
            await asyncio.sleep(0.2)
            await sync(identifier)  # Includes accepted input and partial persisted output.
            for _ in range(650):
                if not await active(identifier):
                    await sync(identifier)
                    return
                await asyncio.sleep(0.2)
        except Exception as exc:
            from .debug import log_failure
            log_failure("Chat catalog synchronization", exc)
    task = asyncio.create_task(finish())
    sync_tasks.add(task)
    task.add_done_callback(sync_tasks.discard)


async def operation(path, method, query, body):
    store = await asyncio.to_thread(catalog)
    if path == "/chat/history" and method == "GET":
        search = query.get("q", [""])[0]
        cursor = query.get("cursor", [None])[0]
        limit = int(query.get("limit", ["30"])[0])
        if len(search) > 200 or not 1 <= limit <= 100 or (cursor and len(cursor) > 256):
            raise ValueError("Invalid or oversized history query")
        await reconcile(store)
        return await asyncio.to_thread(store.search, search, cursor, limit)
    parts = path.split("/")
    if len(parts) != 4 or parts[1] != "chat":
        raise HTTPException(404, "Unknown chat operation")
    identifier, action = parts[2:]
    identifier = str(UUID(identifier))
    if action == "title" and method == "POST":
        # Title updates do not participate in execution admission and can complete
        # even while a synchronous /runs/wait request holds the lifecycle guard.
        if not isinstance(body, dict) or set(body) != {"title"}:
            raise ValueError("Provide only the title field")
        row = await asyncio.to_thread(store.get, identifier)
        if row and row["lifecycle"] != "live":
            raise HTTPException(410, "Conversation permanently deleted")
        await asyncio.to_thread(store.sync, await get_thread(identifier))
        await asyncio.to_thread(store.rename, identifier, body["title"])
        return {"title": body["title"].strip()}
    lock = guards[identifier]
    if action in {"delete", "export"} and lock.locked():
        raise HTTPException(409, "A run is active; wait for it to finish")
    async with lock:
        row = await asyncio.to_thread(store.get, identifier)
        if row and row["lifecycle"] != "live":
            if action == "delete" and method == "POST":
                await remove(identifier, store)
                return {"deleted": True}
            raise HTTPException(410, "Conversation permanently deleted")
        thread = await get_thread(identifier)
        await asyncio.to_thread(store.sync, thread)
        row = await asyncio.to_thread(store.get, identifier)
        if action == "settings" and method == "GET":
            return {"title": row["manual_title"] or row["default_title"], "status": thread["status"]}
        if action in {"delete", "export"} and await active(identifier):
            raise HTTPException(409, "A run is active; wait for it to finish")
        if action == "export" and method == "GET":
            connect, Threads, Runs = native()
            from langgraph_api.state import state_snapshot_to_thread_state
            async with connect() as conn:
                state = state_snapshot_to_thread_state(await Threads.State.get(conn,
                    config={"configurable": {"thread_id": identifier}}))
                runs = []
                offset = 0
                while True:
                    page = [r async for r in await Runs.search(conn, UUID(identifier), limit=100, offset=offset)]
                    runs.extend({k: str(r[k]) for k in ("run_id", "status", "created_at", "updated_at") if k in r} for r in page)
                    if len(page) < 100:
                        break
                    offset += 100
            format = query.get("format", ["markdown"])[0]
            result = export_chat(row, state["values"].get("messages", []), format)
            if format == "json":
                import json
                data = json.loads(result["content"])
                data["runs"] = runs
                result["content"] = json.dumps(data, ensure_ascii=False, indent=2)
            return result
        if action == "delete" and method == "POST":
            await asyncio.to_thread(store.lifecycle, identifier, "pending")
            try:
                await remove(identifier, store)
            except Exception:
                raise HTTPException(503, "Deletion pending. Retry to finish removing history.") from None
            return {"deleted": True}
    raise HTTPException(404, "Unknown chat operation")
