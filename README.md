# OmniForge

A self-updating, Dockerized MCP server platform. Write, test, and deploy custom
Python/Node scripts as live tools for LLMs over the Model Context Protocol — all
from a single container.

## Features

- **Web dashboard** to create, edit, test, and delete tools.
- **Ephemeral container-per-run execution** with resource limits (CPU, memory, timeout, read-only rootfs, no network, no capabilities).
- **Automatic dependency installation** (pip / npm) into a persistent volume.
- **Hot-reload**: tool registry is read per request — no restart needed.
- **MCP endpoint** (`/mcp`) exposing tools to external LLM clients.
- **SQLite metadata** with atomic writes.

## Quick start

```bash
# Create a private key (or leave OMNIFORGE_API_KEY empty for local testing)
cp .env.example .env

# Build and run
docker compose up --build

# Dashboard: http://localhost:8000
# MCP endpoint: http://localhost:8000/mcp
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OMNIFORGE_API_KEY` | *(empty)* | Bearer key required on `/mcp`. Empty disables auth. |
| `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS` | `30000` | Hard timeout per script run (ms). |
| `OMNIFORGE_MAX_SCRIPT_MEMORY_MB` | `512` | Memory cap per ephemeral container (MB). |
| `OMNIFORGE_RUNTIME_IMAGE` | `omniforge:latest` | Image used to run user scripts. |
| `OMNIFORGE_DB_PATH` | `/opt/omniforge/data/omniforge.db` | SQLite database path. |
| `OMNIFORGE_LIB_ROOT` | `/opt/omniforge/lib` | Persistent per-language library volume root. |
| `OMNIFORGE_SCRIPT_HOST` | `/opt/omniforge/scripts` | Host path where scripts are written before execution. |

## Architecture

```
Browser / LLM Client
  ├── Dashboard (GET /)  → FastAPI web UI
  ├── API (POST/PUT/DELETE /api/tools)  → tool CRUD
  └── MCP (POST /mcp)  → JSON-RPC tools/list, tools/call
        ↓
        FastAPI app (app/main.py)
        ├── database.py  → SQLite storage + hot-reload cache
        ├── runner.py    → ephemeral container execution engine
        └── mcp_server.py → MCP tool schema + routing
```

## Security

- Each tool runs in an ephemeral container with `--read-only`, `--cap-drop ALL`,
  `--network none`, a CPU quota, a memory cap, and a hard timeout.
- Tool names are validated against a strict regex.
- The `/mcp` endpoint accepts an optional Bearer API key.

## Deployment to Docker Hub

```bash
docker buildx build --load -t ionic-developer/omniforge:latest .
docker push ionic-developer/omniforge:latest
```

## Project layout

```
omniforge/
├── app/
│   ├── __init__.py
│   ├── database.py       # SQLite storage + hot-reload cache
│   ├── runner.py         # ephemeral container execution engine
│   ├── mcp_server.py     # MCP tool schema + routing
│   ├── main.py           # FastAPI app: dashboard, API, MCP endpoint
│   └── templates/
│       └── dashboard.html
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .gitignore
└── .env.example
```
