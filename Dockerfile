# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS ui-build
WORKDIR /app/ui/agent-chat-ui
RUN npm install --global pnpm@10.5.1
COPY ui/agent-chat-ui/package.json ui/agent-chat-ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY ui/agent-chat-ui/ ./
ARG NEXT_PUBLIC_API_URL=http://localhost:20240
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_ASSISTANT_ID=assistant \
    NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install --yes --no-install-recommends bash util-linux libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ui-build /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN pip install --no-cache-dir uv==0.12.23 \
    && uv sync --locked --extra web --no-dev --python /usr/local/bin/python
COPY data/ ./data/
COPY langgraph.json ./
# Compose supplies the environment. Avoid LangGraph loading a host .env and
# overriding container paths; the configuration still expects this file.
RUN touch .env
COPY --from=ui-build /app/ui/agent-chat-ui/ ./ui/agent-chat-ui/
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd --create-home --uid 10001 assistant \
    && mkdir -p runtime .langgraph_api ui/agent-chat-ui/.next/cache \
    && chown -R assistant:assistant runtime .langgraph_api ui/agent-chat-ui/.next/cache
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    NEXT_TELEMETRY_DISABLED=1 \
    LANGSMITH_TRACING=false
USER assistant
EXPOSE 3000 2024
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
