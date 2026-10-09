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
# Set GOOGLE_API_KEY in .env before startup.
docker compose build
docker compose up -d
```

Startup automatically seeds the database and prepares the document index before
starting either HTTP service. Existing records are preserved. The index is reused
without embedding API calls when sources and embedding settings are unchanged;
changed sources or embedding provider/model trigger ingestion automatically.
Initial ingestion calls the configured embedding provider and requires
`GOOGLE_API_KEY`. Setup uses container state, independent of the host database/index.
The first startup takes longer; follow progress with `docker compose logs -f chatbot`.
If initialization fails, the container exits without starting the HTTP services.
Fix the settings and rerun `docker compose up -d --force-recreate`.

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
deletes that state; use it only for an intentional full reset. The next startup
initializes it again. Terminal conversations have their own history.

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

## Use the prebuilt GHCR image

After CI passes, the container job publishes
`ghcr.io/luca-palminteri/multi-source-chatbot` from the default branch and `v*`
version tags. Pull requests and other branches build without publishing.
`latest` tracks the default branch; a tag such as `v1.2.3` produces `1.2.3`.
Every published build also gets a `sha-<full-commit-sha>` tag. The workflow uses
the built-in `GITHUB_TOKEN` with `packages: write`; no registry secret is needed.

For the first publication, GitHub defaults the package to private. To allow
anonymous pulls, change the package visibility to public in its GitHub package
settings. For private pulls, log in to `ghcr.io` with a classic personal access
token with `read:packages` and access to the package, as described in
[GitHub's registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

With `.env` configured as above, run from the repository root:

```powershell
$env:CHATBOT_IMAGE = "ghcr.io/luca-palminteri/multi-source-chatbot:latest"
docker compose up -d --pull always --no-build
```

Use a version or commit tag instead of `latest` to select a specific build.
Every published tag includes Linux amd64 and arm64 variants; Docker automatically
selects the variant for your machine. No architecture-specific tag is required.
For example, `latest`, `1.2.3`, and `sha-<full-commit-sha>` each resolve to both
architectures. The image includes the synthetic demo data; initialization runs
at startup with your credentials, and generated state stays in the named volumes.
You can also put `CHATBOT_IMAGE=ghcr.io/luca-palminteri/multi-source-chatbot:latest`
in `.env` instead of setting a shell variable.
It uses `http://localhost:20240` as the browser-visible API URL. Keep the default
host ports for this image; changing `.env` cannot change its compiled UI URL.
For a custom browser-visible URL, use the local build instructions above and
clear `CHATBOT_IMAGE` first: remove it from `.env` if present and run
`Remove-Item Env:CHATBOT_IMAGE -ErrorAction SilentlyContinue` in PowerShell.
