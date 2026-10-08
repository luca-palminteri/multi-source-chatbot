from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    sqlite_path: Path
    vector_index_path: Path
    embedding_provider: str
    embedding_model: str
    chat_provider: str
    chat_model: str
    demo_employee_id: str
    mcp_transport: str
    chat_thinking_level: str = "low"
    chat_request_timeout: float = 45
    chat_max_retries: int = 0
    chat_requests_per_minute: float = 10

    @classmethod
    def load(cls, root: Path | str = "."):
        from dotenv import dotenv_values

        root = Path(root).resolve()
        values = {**dotenv_values(root / ".env"), **os.environ}

        def path(name, default):
            return (root / values.get(name, default)).resolve()

        return cls(root, path("SQLITE_PATH", "runtime/assistant.sqlite3"),
                   path("VECTOR_INDEX_PATH", "runtime/vector_index"),
                   values.get("EMBEDDING_PROVIDER", "google"),
                   values.get("EMBEDDING_MODEL", "gemini-embedding-001"),
                   values.get("CHAT_PROVIDER", "google"),
                   values.get("CHAT_MODEL", "gemini-3.5-flash-lite"),
                   values.get("DEMO_EMPLOYEE_ID", "emp-001"),
                   values.get("MCP_TRANSPORT", "stdio"),
                   values.get("CHAT_THINKING_LEVEL", "low"),
                   float(values.get("CHAT_REQUEST_TIMEOUT", "45")),
                   int(values.get("CHAT_MAX_RETRIES", "0")),
                   float(values.get("CHAT_REQUESTS_PER_MINUTE", "10")))
