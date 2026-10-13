# OmniForge

A self-updating, Dockerized MCP server platform. Write, test, and deploy custom
Python/Node scripts as live tools for LLMs over the Model Context Protocol — all
from a single container.

## Features

- **Web dashboard** to create, edit, test, and delete tools.
- **Trusted-script execution** via Python/Node subprocesses in the application container (not isolated sandboxes).
- **Built-in MCP authoring tools** for instructions and create-only registration; available even with an empty database. Dynamic dependency installation is not implemented.
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
| `OMNIFORGE_API_KEY` | *(empty)* | Bearer key required on POST `/mcp`. Empty disables auth. |
| `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS` | `30000` | Configured timeout (ms); runner currently adds 15 seconds. |
| `OMNIFORGE_MAX_SCRIPT_MEMORY_MB` | `512` | Declared value only; not enforced per script. |
| `OMNIFORGE_DB_PATH` | `/opt/omniforge/data/omniforge.db` | SQLite database path. |
| `OMNIFORGE_LIB_ROOT` | `/opt/omniforge/lib` | Historical library volume setting; no dynamic installer is wired in. |
| `OMNIFORGE_SCRIPT_HOST` | `/opt/omniforge/scripts` | Historical setting; runner uses OMNIFORGE_SCRATCH_ROOT instead. |
| `OMNIFORGE_SCRATCH_ROOT` | `/tmp/omniforge` | Shared scratch directory for subprocess scripts. |

## Architecture

```
Browser / LLM Client
  ├── Dashboard (GET /)  → FastAPI web UI
  ├── API (POST/PUT/DELETE /api/tools)  → tool CRUD
  └── MCP (POST /mcp)  → JSON-RPC tools/list, tools/call
        ↓
        FastAPI app (app/main.py)
        ├── database.py  → SQLite storage + hot-reload cache
        ├── runner.py    → shared-container subprocess execution engine
        └── mcp_server.py → MCP tool schema + routing
```

## Security

- Scripts share the application environment, network and writable data, including
  potential credentials. Only allow trusted authors. Container-level protections
  are not a per-script sandbox; memory/output limits and process-tree termination
  are not implemented.
- Tool names are validated against a strict regex.
- The `/mcp` endpoint accepts an optional Bearer API key.

## Deployment to Docker Hub

```bash
docker buildx build --load -t dbzocchi/omniforge:latest .
docker push dbzocchi/omniforge:latest
```

## Project layout

```
omniforge/
├── app/
│   ├── __init__.py
│   ├── database.py       # SQLite storage + hot-reload cache
│   ├── runner.py         # shared-container subprocess execution engine
│   ├── mcp_server.py     # Built-ins, MCP tool schema + routing
│   ├── tool_authoring.py # Shared metadata/input validation + save-only helper
│   ├── main.py           # FastAPI app: dashboard, API, MCP endpoint
│   └── templates/
│       └── dashboard.html
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .gitignore
└── .env.example
```

## Dashboard example and connection settings

- **Load working example** fills the editor with a no-dependency Python tool that
  prints a greeting and UTC timestamp as JSON. Click **Save**, then **Run / Test**.
  Loading the example does not automatically create or overwrite a saved tool.
- **Run / Test** executes saved code via POST and shows stdout, stderr, exit status,
  execution time and HTTP errors. Save changes before running.
- **Config** shows the endpoint for the dashboard's current origin, Bearer auth
  status, supported methods and an HTTP request template. It never displays the
  configured API key. Set `OMNIFORGE_API_KEY` in the server environment and recreate
  the container to change it.
- The current MCP implementation is limited HTTP JSON-RPC, not a complete
  Streamable HTTP transport. OAuth and connected-client/session tracking are not
  implemented; the panel explicitly reports these limitations.

**Current security limitations:** the execution engine uses subprocesses inside
one shared application container, not per-run containers. The original ephemeral-container and automatic-installer
architecture are historical goals, not runtime guarantees. The dashboard and management API
are unauthenticated. Only run trusted code and keep the service on a trusted
network. A Bearer key on MCP alone does not secure the management API.


## Built-in MCP script authoring

Two tools are always discoverable through `tools/list`, including with an empty
SQLite database:

| Tool | Purpose |
|---|---|
| `omniforge_instructions` | Call with `{}` for the contract, copyable Python/Node creation examples, workflow and safety/transport limitations. No environment or credential values are returned. |
| `omniforge_create_tool` | Save a new script, **without executing it or installing dependencies**. It never overwrites an existing name. |

1. Read `omniforge_instructions`.
2. Submit `name`, `code`, optional `description`, `language` (default `python3`),
   `inputSchema`, `requirements: []`, and `is_active` (default `true`) to
   `omniforge_create_tool`. Code must be nonempty and contain no NUL characters.
   Languages `python`/`python3` and `node`/`js`/`javascript` are accepted and normalised.
3. Refresh `tools/list`. Active tools are available immediately; inactive tools
   remain saved but cannot be called over MCP. There are no list-change notifications.
4. Call the saved tool separately with an `arguments` JSON object. Existing tools
   are edited via the dashboard, not the create built-in.

Names must match `[a-zA-Z][a-zA-Z0-9_-]{0,62}`. Both built-in names are reserved
in dashboard creation/editing as well as MCP. Legacy rows using those names are
not removed, but cannot shadow the built-ins or be run via the dashboard. New
writes reject duplicate names (including inactive tools and rename collisions)
inside a serialized SQLite transaction. Existing legacy duplicates are preserved;
there is no destructive database migration.

Nonempty requirements are rejected by the create built-in because automatic
pip/npm/binary installation is **not implemented**. Dashboard requirements are
stored metadata only. Use standard libraries or packages already in the image.

### Input and output contract

`inputSchema` must be a JSON Schema Draft 2020-12 object schema. Omitted/empty
schemas mean no inputs (`additionalProperties: false`). Only local references
are accepted: validation does not fetch remote schemas. MCP validates arguments
before execution; formats are annotations, and schema defaults are not inserted.
Invalid arguments/metadata return MCP text content with `isError: true` and do
not execute code. Syntax and runtime errors are reported only on execution.

Arguments are encoded as **one JSON object on stdin**, without shell interpolation
or converting inputs to environment variables. Dashboard Run / Test supplies `{}`
without schema validation; use fallback values or MCP to test required inputs.
Stdout is returned as MCP text; print JSON if clients need structured data.
A function's return value is not captured. Avoid printing secrets.

Python example:

```python
import json
import sys

args = json.load(sys.stdin)
print(json.dumps({"message": "Hello " + args.get("name", "world")}))
```

Node example (CommonJS):

```javascript
const fs = require('node:fs');
const args = JSON.parse(fs.readFileSync(0, 'utf8'));
console.log(JSON.stringify({message: 'Hello ' + (args.name || 'world')}));
```

For either example, supply this `inputSchema` when creating it:

```json
{"type":"object","properties":{"name":{"type":"string"}},"additionalProperties":false}
```

Then POST this JSON-RPC request to `/mcp` (use the existing Bearer credential
locally when enabled; never put credential values in source or tool instructions):

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"greet_python","arguments":{"name":"David"}}}
```

**Important:** this is still limited HTTP JSON-RPC, not full MCP Streamable HTTP.
GET `/mcp` is an initial SSE stub. OAuth, sessions and list-change notifications
are absent. JSON stdin does not fix subprocess isolation: scripts still inherit
the application environment and can access credentials/data. No shell/host,
credential configuration, deployment or automatic dependency-install tools are
added. Keep both authors and clients trusted and the service on a trusted network.
