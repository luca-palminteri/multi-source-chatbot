from ..contracts import Passage


def split_document(text: str, document: dict, chunk_size=900, overlap=120):
    """Prefer paragraph/word boundaries; offsets index the original Unicode text."""
    if chunk_size < 1 or not 0 <= overlap < chunk_size:
        raise ValueError("Invalid chunk size or overlap")
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind("\n\n", start + chunk_size // 2, end)
            if boundary < 0:
                boundary = text.rfind(" ", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary
        if text[start:end].strip():
            yield Passage(f"{document['id']}:v{document['version']}:{start}-{end}",
                          document["id"], document["policy_id"], document["title"],
                          document["path"], document["version"], document["effective_date"],
                          start, end, text[start:end])
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
