"""Passive terminal interface: all application messages go to AgentSession.ask."""
import asyncio
import json
import logging
import time
from contextlib import suppress

from .debug import logger, log_failure


def render_turn(result, write):
    write(f"Assistant: {result['answer']}")
    for event in result.get("trace", []):
        if event.get("event") == "execution_failed":
            code = event.get("status_code")
            write(f"Failure type: {event.get('error_type', 'unknown')}"
                  + (f"; HTTP status: {code}" if code is not None else ""))
        if event.get("event") == "tool_result":
            # Display advertised results without selecting tools or interpreting intent.
            content = event.get("result", "")
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (ValueError, TypeError):
                    pass
            formatted = json.dumps(content, indent=2, ensure_ascii=False) if not isinstance(content, str) else content
            write(f"Tool result ({event.get('name', 'tool')}, {event.get('status', 'unknown')}):\n{formatted}")


def connection_error(exc):
    """Never echo exception text: provider/transport exceptions can contain secrets."""
    if isinstance(exc, ImportError):
        return 'Chat dependencies are missing. Install with: python -m pip install -e ".[runtime]"'
    if isinstance(exc, FileNotFoundError):
        return "Chat data or executable is missing. Check the project root, then run seed and ingest."
    if isinstance(exc, ValueError):
        return "Chat configuration is invalid. Check GOOGLE_API_KEY, provider settings, MCP_TRANSPORT=stdio, and the ingested index."
    if isinstance(exc, TimeoutError):
        return "Chat connection timed out. Check the MCP server and model connection."
    return "Chat connection failed. Check dependencies, model credentials, data setup, and MCP configuration."


async def run_chat(settings, *, connector=None, read=None, write=print):
    if connector is None:
        from .agent import connect_agent
        connector = connect_agent
    if read is None:
        async def read(prompt):
            return await asyncio.to_thread(input, prompt)

    write("Terminal chat. /new starts a fresh conversation; /exit quits. Sources and tool outcomes appear below each answer.")
    try:
        while True:
            async with connector(settings) as session:
                write(f"Conversation: {session.config['configurable']['thread_id']}")
                stopped = False
                while True:
                    message = await read("You: ")
                    command = message.strip()
                    if command == "/exit":
                        return 0
                    if command == "/new":
                        write("Starting a fresh conversation; previous context is discarded.")
                        break
                    if not command:
                        continue
                    if command == "/help":
                        write("/new: fresh conversation. /exit: quit. Messages may contain up to 4000 characters.")
                        continue
                    if len(message) > 4000:
                        write("Message must contain 1 to 4000 characters.")
                        continue
                    if stopped:
                        write("This conversation stopped after an execution failure. Use /new and retrieve current records before retrying an action.")
                        continue
                    async def heartbeat():
                        started = time.monotonic()
                        while True:
                            await asyncio.sleep(10)
                            logger.debug("Still waiting for agent response (%.0fs)", time.monotonic() - started)

                    monitor = asyncio.create_task(heartbeat()) if logger.isEnabledFor(logging.DEBUG) else None
                    try:
                        result = await session.ask(message)
                    finally:
                        if monitor is not None:
                            monitor.cancel()
                            with suppress(asyncio.CancelledError):
                                await monitor
                    render_turn(result, write)
                    stopped = not result.get("ok", False)
    except EOFError:
        return 0
    except Exception as exc:
        log_failure("Chat connection", exc)
        write(connection_error(exc))
        return 1


def start_chat(settings):
    try:
        return asyncio.run(run_chat(settings))
    except KeyboardInterrupt:
        print("\nChat closed. If interrupted during an action, retrieve current records before retrying.")
        return 0
