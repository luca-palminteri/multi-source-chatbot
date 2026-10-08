# Run the backend and UI in one container

This image runs the LangGraph CLI HTTP server on port 2024 and the built Next.js
UI on port 3000. Compose exposes the backend on host port 20240 to avoid common
Windows/WSL port reservations. Both use the existing agent; MCP actions still launch as stdio
subprocesses. The terminal CLI is available in the same image.

Use Docker Desktop with Linux containers. Run these commands from the repository
root. For a fresh checkout, copy `.env.example` to `.env` and set `GOOGLE_API_KEY`.
An existing `.env` can be reused; Compose overrides database/index paths to use
the container's persistent runtime volume. Credentials are supplied at runtime
and excluded from the image build.

```powershell
# Fresh checkout only:
Copy-Item .env.example .env
# Set GOOGLE_API_KEY in .env before ingestion.
docker compose build
docker compose run --rm chatbot python -m assistant.cli seed
docker compose run --rm chatbot python -m assistant.cli ingest
docker compose up -d
```

Ingestion calls the configured embedding provider. Setup uses new container
state, independent of any existing host database/index. Seeding preserves
existing records. Repeat ingestion after changing the embedding model/provider
or source documents.

Open <http://localhost:3000>. Check the backend at <http://localhost:20240/ok>.
The ports are bound to the local host. The browser connects directly to port
20240; `localhost` is resolved by the browser, not inside the container.

```powershell
docker compose ps
docker compose logs -f chatbot
# Start a separate interactive terminal conversation with the same data:
docker compose exec chatbot python -m assistant.cli chat
# Rebuild the document index while the services are stopped:
docker compose stop
docker compose run --rm chatbot python -m assistant.cli ingest
docker compose up -d
# Stop and remove the container, retaining its data:
docker compose down
```

Named volumes retain the action database, execution ledger, vector index, and
LangGraph history across container replacement. `docker compose down --volumes`
deletes that state; use it only for an intentional full reset, then seed and
ingest again. Terminal conversations have their own history.

The startup wrapper stops both services if either exits and forwards shutdown
to their process groups. Compose supplies an init process to reap children, as
described in Docker's [multiple-process container guide](https://docs.docker.com/engine/containers/multi-service_container/).
The health check verifies both HTTP endpoints. After editing backend environment
settings, recreate the container with `docker compose up -d --force-recreate`.

`NEXT_PUBLIC_API_URL` is compiled into the UI. To change the browser-visible
backend URL, set `DOCKER_PUBLIC_API_URL` in `.env`, rebuild, and recreate the
container. To change the host backend port, set `DOCKER_API_PORT` and a matching
`DOCKER_PUBLIC_API_URL` in `.env`, then rebuild and recreate the container.
The backend still listens on port 2024 inside the container.

This packages the existing local/demo LangGraph development server, including
its development persistence and lack of authentication. See the
[browser execution limits](web-chat.md#execution-and-history-limits) before
choosing a production deployment architecture.
