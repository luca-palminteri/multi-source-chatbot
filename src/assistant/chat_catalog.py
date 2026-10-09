"""Durable presentation settings. Native checkpoints remain authoritative."""
import base64
from contextlib import closing
from datetime import datetime, timezone
import json
import re
import sqlite3


def visible(messages):
    messages = [m.model_dump(mode="json") if hasattr(m, "model_dump") else m for m in messages]
    return [m for m in messages if not str(m.get("id", "")).startswith("do-not-render-")]


def text(message):
    content = message.get("content", "")
    return content if isinstance(content, str) else "\n".join(
        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


def title(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 100:
        raise ValueError("Title must contain 1 to 100 characters")
    return value.strip()


class ChatCatalog:
    def __init__(self, path):
        self.path = path

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.create_function("casefold", 1, lambda s: s.casefold())
        conn.execute("""CREATE TABLE IF NOT EXISTS chats (
            thread_id TEXT PRIMARY KEY, default_title TEXT NOT NULL DEFAULT 'New chat',
            manual_title TEXT, updated_at TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT '',
            model TEXT, status TEXT NOT NULL DEFAULT 'idle', lifecycle TEXT NOT NULL DEFAULT 'live',
            search_text TEXT NOT NULL DEFAULT '')""")
        conn.execute("CREATE INDEX IF NOT EXISTS chats_order ON chats(lifecycle, updated_at DESC, thread_id DESC)")
        indexed = conn.execute("SELECT 1 FROM sqlite_master WHERE name='chat_search'").fetchone()
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chat_search USING fts5(thread_id UNINDEXED, text, tokenize='trigram case_sensitive 1')")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS chats_search_insert AFTER INSERT ON chats BEGIN
            INSERT INTO chat_search SELECT NEW.thread_id,
            casefold(COALESCE(NEW.manual_title,NEW.default_title)) || char(10) || NEW.search_text
            WHERE NEW.lifecycle='live'; END""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS chats_search_update AFTER UPDATE ON chats BEGIN
            DELETE FROM chat_search WHERE thread_id=OLD.thread_id;
            INSERT INTO chat_search SELECT NEW.thread_id,
            casefold(COALESCE(NEW.manual_title,NEW.default_title)) || char(10) || NEW.search_text
            WHERE NEW.lifecycle='live'; END""")
        if not indexed:
            conn.execute("""INSERT INTO chat_search SELECT thread_id,
                casefold(COALESCE(manual_title,default_title)) || char(10) || search_text
                FROM chats WHERE lifecycle='live'""")
        conn.commit()
        return conn

    def get(self, identifier):
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT * FROM chats WHERE thread_id=?", (identifier,)).fetchone()
            return dict(row) if row else None

    def sync(self, thread):
        messages = visible((thread.get("values") or {}).get("messages", []))
        first = next((text(m).strip() for m in messages if m.get("type") == "human"), "New chat")
        searchable = "\n".join(text(m) for m in messages if m.get("type") in {"human", "ai"})
        identifier = str(thread["thread_id"])
        with closing(self.connect()) as conn, conn:
            conn.execute("""INSERT INTO chats(thread_id, default_title, updated_at, created_at, status, search_text)
                VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(thread_id) DO UPDATE SET
                default_title=excluded.default_title, updated_at=MAX(chats.updated_at, excluded.updated_at),
                status=excluded.status, search_text=excluded.search_text WHERE chats.lifecycle='live'""",
                (identifier, first[:100] or "New chat", self.timestamp(thread["updated_at"]), self.timestamp(thread["created_at"]),
                 thread["status"], searchable.casefold()))

    @staticmethod
    def timestamp(value):
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()

    def rename(self, identifier, value):
        value = title(value)
        with closing(self.connect()) as conn, conn:
            changed = conn.execute("UPDATE chats SET manual_title=?, updated_at=? WHERE thread_id=? AND lifecycle='live'",
                         (value, datetime.now(timezone.utc).isoformat(), identifier))
            if not changed.rowcount:
                raise ValueError("Conversation unavailable or permanently deleted")

    def set_model(self, identifier, model):
        with closing(self.connect()) as conn, conn:
            conn.execute("INSERT OR IGNORE INTO chats(thread_id) VALUES (?)", (identifier,))
            conn.execute("UPDATE chats SET model=? WHERE thread_id=? AND lifecycle='live'", (model, identifier))

    def lifecycle(self, identifier, state):
        with closing(self.connect()) as conn, conn:
            conn.execute("INSERT OR IGNORE INTO chats(thread_id) VALUES (?)", (identifier,))
            conn.execute("""UPDATE chats SET lifecycle=?, default_title='', manual_title=NULL,
                search_text='', model=NULL, created_at='', updated_at='', status='deleted' WHERE thread_id=?""",
                         (state, identifier))

    def pending(self):
        with closing(self.connect()) as conn:
            return [r[0] for r in conn.execute("SELECT thread_id FROM chats WHERE lifecycle='pending'")]

    def tombstones(self):
        with closing(self.connect()) as conn:
            return [r[0] for r in conn.execute("SELECT thread_id FROM chats WHERE lifecycle!='live'")]

    def search(self, query="", cursor=None, limit=30):
        if len(query) > 200 or not 1 <= limit <= 100:
            raise ValueError("Search is limited to 200 characters and 100 results per page")
        params = [query.casefold(), query.casefold()]
        where = "lifecycle='live' AND (instr(casefold(COALESCE(manual_title,default_title)),?)>0 OR instr(search_text,?)>0)"
        if len(query) >= 3 and "\x00" not in query:
            where += " AND thread_id IN (SELECT thread_id FROM chat_search WHERE chat_search MATCH ?)"
            params.append('"' + query.casefold().replace('"', '""') + '"')
        if cursor:
            try:
                if len(cursor) > 256:
                    raise ValueError()
                stamp, identifier = json.loads(base64.urlsafe_b64decode(cursor))
                if not isinstance(stamp, str) or not isinstance(identifier, str):
                    raise ValueError()
            except Exception:
                raise ValueError("Invalid history cursor") from None
            where += " AND (updated_at < ? OR (updated_at = ? AND thread_id < ?))"
            params += [stamp, stamp, identifier]
        with closing(self.connect()) as conn:
            rows = conn.execute(f"SELECT * FROM chats WHERE {where} ORDER BY updated_at DESC, thread_id DESC LIMIT ?",
                                [*params, limit + 1]).fetchall()
        results = []
        for row in rows[:limit]:
            body = row["search_text"]
            position = max(0, body.find(query.casefold()) - 40)
            results.append({"thread_id": row["thread_id"], "title": row["manual_title"] or row["default_title"],
                            "updated_at": row["updated_at"], "status": row["status"],
                            "snippet": body[position:position + 160] if query else ""})
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = base64.urlsafe_b64encode(json.dumps([last["updated_at"], last["thread_id"]]).encode()).decode()
        return {"threads": results, "cursor": next_cursor}


def export_chat(row, messages, format):
    name = row["manual_title"] or row["default_title"]
    messages = visible(messages)
    data = {"version": 1, "record_only": True, "title": name, "thread_id": row["thread_id"],
            "exported_at": datetime.now(timezone.utc).isoformat(), "model": row["model"],
            "status": row["status"], "messages": [
                {"role": {"human": "user", "ai": "assistant", "tool": "tool"}[m["type"]],
                 **{k: m[k] for k in ("id", "type", "content", "tool_calls", "tool_call_id", "name") if k in m}}
                for m in messages if m.get("type") in {"human", "ai", "tool"}]}
    if format == "json":
        content = json.dumps(data, ensure_ascii=False, indent=2)
    elif format == "markdown":
        content = f"# {name}\n\nThread: {row['thread_id']}\n\nExported: {data['exported_at']}\n\n"
        if row["model"]:
            content += f"Model: {row['model']}\n\n"
        content += "\n\n".join(f"## {'User' if m['type'] == 'human' else 'Assistant'}\n\n{text(m)}"
                                for m in messages if m.get("type") in {"human", "ai"})
    else:
        raise ValueError("Export format must be markdown or json")
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")[:80] or "chat"
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", filename, re.I):
        filename = "chat-" + filename
    return {"content": content, "filename": filename + (".json" if format == "json" else ".md")}
