import json
from pathlib import Path
import tempfile
import unittest

from assistant.chat_catalog import ChatCatalog, export_chat, title


class ChatCatalogTests(unittest.TestCase):
    def test_reconciliation_persistence_literal_search_and_pagination(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.sqlite3"
            catalog = ChatCatalog(path)
            for i in range(120):
                catalog.sync({"thread_id": str(i), "updated_at": "2026-10-09T00:00:00+00:00",
                    "created_at": "2026-10-08T00:00:00+00:00", "status": "idle",
                    "values": {"messages": [
                        {"type": "human", "content": "Default"},
                        {"type": "ai", "content": "Café\n100% _literal_ OR \"quoted\" [D1]"},
                        {"type": "tool", "content": "secret tool payload"},
                        {"type": "ai", "id": "do-not-render-planner", "content": "hidden retrieval"}]}})
            catalog.rename("0", "  Straße 聊天  ")
            restarted = ChatCatalog(path)
            self.assertEqual(restarted.search("STRASSE")["threads"][0]["title"], "Straße 聊天")
            for query in ("CAFÉ", "100%", "_literal_", "OR", '"quoted"', "[D1]"):
                self.assertEqual(len(restarted.search(query, limit=100)["threads"]), 100, query)
            for query in ("secret tool", "hidden retrieval", "Default OR secret", "%notawildcard%"):
                self.assertEqual(restarted.search(query)["threads"], [])
            found, cursor = [], None
            while True:
                page = restarted.search(cursor=cursor, limit=17)
                found += [t["thread_id"] for t in page["threads"]]
                cursor = page["cursor"]
                if cursor is None:
                    break
            self.assertEqual(len(found), 120)
            self.assertEqual(len(set(found)), 120)
            catalog.lifecycle("0", "pending")
            self.assertEqual(restarted.search("STRASSE")["threads"], [])
            self.assertEqual(restarted.get("0")["search_text"], "")
            self.assertEqual(restarted.pending(), ["0"])
            catalog.lifecycle("0", "deleted")
            with self.assertRaises(ValueError):
                restarted.search(cursor="broken")
            with self.assertRaises(ValueError):
                restarted.search("x" * 201)

    def test_title_bounds_and_export_hidden_policy(self):
        for value in (None, "", "  ", "x" * 101):
            with self.assertRaises(ValueError):
                title(value)
        self.assertEqual(title(" chat "), "chat")
        row = {"manual_title": "CON", "default_title": "Original", "thread_id": "thread",
               "model": "known-model", "status": "error"}
        messages = [
            {"type": "human", "id": "user", "content": [{"type": "text", "text": "你好\nline two"}]},
            {"type": "ai", "content": "Evidence [D1]", "tool_calls": [{"id": "call", "name": "lookup", "args": {}}]},
            {"type": "tool", "tool_call_id": "call", "content": "native tool result"},
            {"type": "ai", "id": "do-not-render-internal", "content": "hidden"},
            {"type": "system", "content": "private configuration"}]
        output = export_chat(row, messages, "json")
        data = json.loads(output["content"])
        self.assertEqual(len(data["messages"]), 3)
        self.assertEqual(data["messages"][-1]["tool_call_id"], "call")
        self.assertEqual(output["filename"], "chat-CON.json")
        markdown = export_chat(row, messages, "markdown")["content"]
        self.assertIn("你好\nline two", markdown)
        self.assertIn("Evidence [D1]", markdown)
        self.assertIn("known-model", markdown)
        self.assertNotIn("native tool result", markdown)
        self.assertNotIn("hidden", markdown)
        self.assertNotIn("private configuration", output["content"])

    def test_sync_keeps_manual_title_and_tombstones(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = ChatCatalog(Path(directory) / "catalog.sqlite3")
            thread = {"thread_id": "t", "updated_at": "2026-10-09T12:00:00+00:00",
                      "created_at": "2026-10-09T12:00:00+00:00", "status": "busy",
                      "values": {"messages": [{"type": "human", "content": "First user"}]}}
            catalog.sync(thread)
            catalog.rename("t", "Override")
            thread["status"] = "error"
            thread["updated_at"] = "2026-10-10T12:00:00+00:00"
            catalog.sync(thread)
            self.assertEqual(catalog.search()["threads"][0]["title"], "Override")
            self.assertEqual(catalog.get("t")["status"], "error")
            catalog.lifecycle("t", "deleted")
            catalog.sync(thread)
            self.assertEqual(catalog.search()["threads"], [])
            self.assertEqual(catalog.get("t")["lifecycle"], "deleted")
