# OmniForge

A self-updating, Dockerized MCP server platform. Write, test, and deploy custom
Python/Node scripts as live tools for LLMs over the Model Context Protocol — all
from a single container.

## Features

- **Web dashboard** to create, edit, test, and delete tools.
- **Trusted-script execution** via Python/Node subprocesses in the application container (not isolated sandboxes).
- **Built-in MCP authoring tools** for instructions and create-only registration; available even with an empty database.
- **Lazy dependency installation**: per-tool persistent pip/npm caches, strict package names, wheels-only Python installs and disabled npm lifecycle scripts.
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
| `OMNIFORGE_LIB_ROOT` | `/opt/omniforge/lib` | Writable persistent per-tool pip/npm dependency caches. |
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
one shared application container, not per-run containers. Dependency installation
is implemented, but neither scripts nor their dependencies are isolated from
the application filesystem. The dashboard and management API are unauthenticated. Only run trusted code and keep the service on a trusted
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
   `inputSchema`, `requirements` (optional package-name array), and `is_active` (default `true`) to
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

### Requirements: install on first execution

Both dashboard and MCP creation accept up to 50 package names. Saving validates
names but never installs or runs code. The first Run / Test or MCP call installs
missing environments; subsequent calls reuse a completed cache.

- Python: `requests` or `requests==2.32.5`. Strict package names and optional
  exact numeric/release-version pins only; no extras, ranges or markers.
  `pip --target --only-binary=:all: --no-cache-dir --disable-pip-version-check`
  uses the official PyPI index. No source builds or system binaries.
- Node (CommonJS `require`): `lodash`, `lodash@4.17.21`, or
  `@scope/package@1.2.3`. Exact semver pins only, not ranges or tags.
  `npm --prefix --ignore-scripts --no-audit --no-fund` uses the official registry
  and a writable cache. Packages requiring lifecycle scripts/native builds are
  unsupported; ESM imports do not resolve through `NODE_PATH`.
- URLs, VCS, paths, flags, aliases, tarballs and installation commands are rejected.

Environments live at `OMNIFORGE_LIB_ROOT/<tool-id-hash>/<language>/<requirements-hash>`.
Each install uses a unique staging directory and an `fcntl` file lock (125-second
bounded wait). A success marker is published atomically only after the installer
finishes. Failed/120-second timed-out installs abort execution, return bounded
sanitized diagnostics and remove only their own staging directory. Existing
unmarked directories are never deleted automatically. Changed requirements make
another environment; old caches remain until an administrator removes them.
Unpinned names reuse their first resolved versions, not automatically updated ones.

The library volume must be writable by UID 1000. New image directories are owned
by UID 1000; existing bind mounts need matching ownership configured separately.
Read-only root filesystems and a 128 MiB `noexec` `/tmp` tmpfs are supported: package
installation staging, HOME, TMPDIR and npm cache use the writable library volume.
Do not mount the Docker socket. No packages install on the NAS host.

Installer children receive a minimal environment, no app API keys or inherited
pip/npm configuration. Script children still inherit the application environment
with their own dependency directory prepended to `PYTHONPATH`/`NODE_PATH`:
**trusted code and trusted dependencies only; this is not sandbox isolation**.
Dependency preparation is synchronous and may block other requests in the current
single-worker design. The existing script timeout starts after preparation.

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
credential configuration or deployment tools are added. Dependency installation
is limited to the validated package requirements described above. Keep both authors and clients trusted and the service on a trusted network.

### Starting a new tool and loading examples

Use **+ New Tool** to leave an existing tool and clear the editor. Confirming
clears only the editor, not the saved tool; cancelling preserves the editor.
Select one of the four examples, click **Load example**, then **Save → Run / Test**.
Loading an example prepares a NEW tool, never edits the previously selected tool.
The Python and Node basic examples need no requirements. The `requests` and
`lodash` examples fill Requirements automatically and install on first execution.
Changing code, language, name or requirements must be saved before running.

## Workbench redesign (review branch, 2026-10-13)

See [product plan](docs/product-plan.md) for flows, acceptance and security gates.
The dashboard supports persistent light/dark/system appearance, unsaved-edit
protection, responsive panels and a custom forge mark. The manifest uses explicit
allowlisted static routes; no service worker or sensitive offline caching is added.
Installation is browser-dependent and requires HTTPS/localhost, not the current
plain-HTTP LAN address. Execution always needs the server. These changes do not
secure the unauthenticated management API or isolate scripts: trusted network only.
