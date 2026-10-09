#!/usr/bin/env bash
set -Eeuo pipefail

# One-off Compose commands (setup and CLI chat) use the same image and volumes.
if (( $# > 0 )); then
    exec "$@"
fi

backend_pid=""
ui_pid=""
bootstrap_pid=""
cleanup() {
    trap '' TERM INT
    # Each service gets a process group, including its MCP subprocesses.
    if [[ -n "$bootstrap_pid" ]]; then
        kill -TERM -- "-$bootstrap_pid" 2>/dev/null || true
    fi
    if [[ -n "$backend_pid" ]]; then
        kill -TERM -- "-$backend_pid" 2>/dev/null || true
    fi
    if [[ -n "$ui_pid" ]]; then
        kill -TERM -- "-$ui_pid" 2>/dev/null || true
    fi
    wait "$backend_pid" "$ui_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

# Complete initialization before accepting requests. One-off CLI commands above
# bypass this so maintenance does not implicitly perform embedding API calls.
setsid python -m assistant.bootstrap &
bootstrap_pid=$!
if wait "$bootstrap_pid"; then
    bootstrap_pid=""
else
    status=$?
    echo "Startup initialization failed. Check GOOGLE_API_KEY and embedding settings, then restart the container." >&2
    exit "$status"
fi

setsid langgraph dev --host 0.0.0.0 --port 2024 --no-browser --no-reload --allow-blocking &
backend_pid=$!
setsid node /app/ui/agent-chat-ui/node_modules/next/dist/bin/next start \
    /app/ui/agent-chat-ui --hostname 0.0.0.0 --port 3000 &
ui_pid=$!

# Stop the other service if either exits, and preserve the failure status.
set +e
wait -n "$backend_pid" "$ui_pid"
status=$?
set -e
exit "$status"
