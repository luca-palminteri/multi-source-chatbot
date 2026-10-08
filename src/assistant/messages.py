"""Extract answer text from string or Gemini content-block responses."""


def message_text(message):
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block if isinstance(block, str) else block.get("text", "")
                       for block in content
                       if isinstance(block, str) or (isinstance(block, dict)
                           and block.get("type") == "text" and not block.get("thought")))
    return ""
