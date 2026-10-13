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

## Product dashboard and PWA

The dashboard is organized into **Overview, Tools, Connect and Help**, with a
separate tool studio instead of permanent editor side panels. Start with a template,
save, then Run / Test. The tool library supports search and state/runtime filters.
Enabled scripts become discoverable on the client's next tool-list refresh.

- **Overview:** first-use create/test/connect guide and real library counts.
- **Tools:** searchable saved scripts; dedicated editor with folded packages,
  dirty-state safeguards, independent save/test and explicit output/error feedback.
- **Connect:** current-origin endpoint, real POST auth status and copyable HTTP
  request metadata. Configured API keys are never returned or displayed.
- **Help:** the four original templates, input/output/package contracts,
  troubleshooting, keyboard shortcuts and app installation instructions.

Self-hosted Manrope and JetBrains Mono fonts include their OFL licenses. An original
geometric logo, SVG/PNG favicons, Apple touch icon and regular/maskable app icons
are included. Light, dark and system appearance are supported. Phone navigation
has four labelled destinations; keyboard editing and reduced motion are supported.

**PWA:** on eligible HTTPS browsers, use Install app when shown; Safari users can
use Share → Add to Home Screen. HTTP LAN addresses generally aren't eligible;
localhost is usable for development. Saving, package installation and execution
require the server. Offline navigation shows a generic reconnect page. The worker
caches only known public static assets — never dashboard HTML, API/MCP responses,
code, results or credentials. Updates are opt-in; unsaved drafts are guarded. Theme
is the only localStorage preference; drafts live only in the current tab.

**Security limitations remain unchanged:** dashboard and management API are
unauthenticated. Optional Bearer auth protects POST /mcp only, not GET /mcp or the
management API. Scripts share the application container, environment and writable
data; they are not isolated sandboxes. Keep the service on a trusted network.

Transport is limited HTTP JSON-RPC, not full Streamable HTTP. OAuth and connected
client/session tracking are not implemented. Verify your client's compatibility.

See `docs/product-design.md` for architecture, cache/update semantics, accessibility
choices and repeatable browser tests. No auth migration or deployment is required
by the UI architecture itself.

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
are accepted: validation does not fetch remote schemas. MCP and dashboard tests validate arguments
before execution; formats are annotations, and schema defaults are not inserted.
Invalid arguments/metadata return MCP text content with `isError: true` and do
not execute code. Syntax and runtime errors are reported only on execution.

Arguments are encoded as **one JSON object on stdin**, without shell interpolation
or converting inputs to environment variables. Dashboard Run / Test accepts a JSON object in Test inputs (default `{}`) and validates it against the saved schema before executing. Invalid inputs are rejected without running code.
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

Use **Create a tool** in Overview or Tools to enter the focused studio. Choose
**Use a template** or a template in Help, then **Save tool → Run / Test**. Templates
always prepare a new draft; replacing dirty fields requires confirmation. Saved
tools are unchanged until Save. Changing name, code, description, runtime or
requirements disables testing until those changes are saved.

The four original examples remain unchanged. Python and Node greeting examples
need no packages; requests and lodash examples fill Packages automatically and
install on first execution. **Add all missing examples** in Help saves missing
names only; existing/customized examples are never overwritten or executed.

### Concurrent edits and testing

Tool metadata includes a content revision. The dashboard sends it with
`If-Match` for updates, deletion, enabling/disabling and tests. Stale operations
return HTTP 412 without changing the tool or discarding the draft. Update, delete
and toggle guards run within SQLite write transactions; tests read a fresh saved
snapshot. Existing API callers may omit the header for backward compatibility.
The guard is not authentication or authorization. No database migration is needed.

Browser test request: `POST /api/tools/{name}/run` with JSON
`{"arguments":{"name":"Ada"}}`. An omitted body defaults to empty arguments.
Required arguments must match the saved schema. Code, inputs and results remain
in tab memory and are never written to the PWA cache or browser storage.
