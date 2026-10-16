<!-- Self-hosted MCP tool workspace: write Python/Node scripts, test with JSON, publish at /mcp. -->
# OmniForge

[![Docker pulls](https://img.shields.io/docker/pulls/dbzocchi/omniforge?logo=docker&logoColor=white)](https://hub.docker.com/r/dbzocchi/omniforge)
[![Image size](https://img.shields.io/docker/image-size/dbzocchi/omniforge/latest?logo=docker&logoColor=white)](https://hub.docker.com/r/dbzocchi/omniforge)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![Node.js CommonJS](https://img.shields.io/badge/node.js-CommonJS-339933?logo=nodedotjs&logoColor=white)
![MCP over HTTP JSON-RPC, partial](https://img.shields.io/badge/MCP-HTTP%20JSON--RPC%20%28partial%29-116859)
![Deploy on a trusted LAN only](https://img.shields.io/badge/deploy-trusted%20LAN%20only-b02d35)

**Write a Python or Node script, test it with JSON, and publish it as an MCP tool, all from one self-hosted container.**

OmniForge is a small web workspace for giving AI assistants new abilities. Each ability is a **tool**: a short script that reads a JSON object on stdin and prints its result. Write it in the browser dashboard, test it with sample input and save it. It's listed straight away at `/mcp`, where Model Context Protocol (MCP) clients can discover and call it.

> **Warning: trusted LAN only.** The dashboard and management API have **no authentication**. Scripts run as subprocesses **inside this container**, with its full environment (including `OMNIFORGE_API_KEY`), network and data. There's no per-run isolation. Never expose this container to the internet. Read [Security model and limitations](#security-model-and-limitations) before you deploy.

---

## Features

- **Web dashboard** with five screens (Overview, Tools, Tool studio, Connect, Help). Light, dark and system themes, a phone layout, keyboard support, and an installable PWA over HTTPS or `localhost`.
- **Python 3.12 and Node.js (CommonJS) tools.** Arguments arrive as one JSON object on stdin, never through a shell, and stdout comes back as MCP text.
- **Run / Test** against the saved version, showing stdout, stderr, the exit code and the duration.
- **Instant publishing.** Saved, enabled tools appear on the client's next `tools/list`, with no restart.
- **JSON Schema Draft 2020-12 input validation** before any code runs (local references only).
- **Lazy per-tool packages.** Up to 50 pip or npm packages per tool, installed on first run into a persistent cache. Wheels only, no npm lifecycle scripts, strict package names.
- **Built-in MCP authoring tools.** `omniforge_instructions` and `omniforge_create_tool` let an AI client learn the contract and save tools, without running them.
- **Optimistic concurrency.** Content revisions with `If-Match` stop stale tabs overwriting changed tools.
- **Non-root (UID 1000).** Works with a read-only root filesystem, a `noexec` `/tmp` and all capabilities dropped. Doesn't need the Docker socket.

## Quick start

Generate a key for the MCP endpoint:

```bash
openssl rand -hex 32
```

### docker run

```bash
docker run -d --name omniforge \
  -p 8000:8000 \
  -e OMNIFORGE_API_KEY='<your-random-key>' \
  -v omniforge_data:/opt/omniforge/data \
  -v omniforge_lib:/opt/omniforge/lib \
  --restart unless-stopped \
  dbzocchi/omniforge:latest
```

### Docker Compose

```yaml
services:
  omniforge:
    image: dbzocchi/omniforge:latest   # or pin: dbzocchi/omniforge@sha256:<digest>
    container_name: omniforge
    ports:
      - "8000:8000"
    environment:
      OMNIFORGE_API_KEY: ${OMNIFORGE_API_KEY:-}
    volumes:
      - omniforge_data:/opt/omniforge/data
      - omniforge_lib:/opt/omniforge/lib
    restart: unless-stopped

volumes:
  omniforge_data:
  omniforge_lib:
```

Open `http://localhost:8000`. Choose **Start with a template → Python greeting → Save tool → Run / Test**. The MCP endpoint is `http://localhost:8000/mcp`.

To limit who can connect, bind the port to one interface, for example `-p 127.0.0.1:8000:8000` for local-only access.

## Tags and platforms

| Tag | Platform | Notes |
|---|---|---|
| `latest` | `linux/amd64` | Rebuilt from the main branch on every change. **The only tag published.** |

There are no version tags, so `latest` changes over time. **For reproducible deploys and rollbacks, pin by digest:**

```bash
docker buildx imagetools inspect dbzocchi/omniforge:latest
```

```yaml
image: dbzocchi/omniforge@sha256:<digest>
```

Keep a record of each digest you deploy. Docker Hub doesn't guarantee to keep untagged images, so `docker save` a known-good image if rollback matters to you.

## Configuration

All settings are environment variables, read once at start-up. Recreate the container after changing them.

| Variable | Default | Description |
|---|---|---|
| `OMNIFORGE_API_KEY` | *(empty)* | Bearer key required on `POST /mcp`. Empty disables MCP auth. It doesn't protect the dashboard, the management API or `GET /mcp`. **Every script can read it.** |
| `OMNIFORGE_DB_PATH` | `/opt/omniforge/data/omniforge.db` | SQLite database file. |
| `OMNIFORGE_LIB_ROOT` | `/opt/omniforge/lib` | Persistent per-tool pip and npm caches. Must be writable by UID 1000. |
| `OMNIFORGE_SCRATCH_ROOT` | `/tmp/omniforge` | Shared directory where scripts are written and run. |
| `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS` | `30000` | Script timeout in ms. The runner adds 15 s (45 s effective), counted after dependency preparation. |
| `OMNIFORGE_MAX_SCRIPT_MEMORY_MB` | `512` | **Declared only, not enforced.** Use `--memory` on the container. |
| `OMNIFORGE_CACHE_TTL_MS` | `5000` | Lifetime of the in-process tool-list cache. Writes clear it immediately. |

Whole numbers only: a value such as `30s` stops the app from starting. `OMNIFORGE_SCRIPT_HOST` and `OMNIFORGE_RUNTIME_IMAGE` are historical and ignored.

## Ports and volumes

| Item | Value | Notes |
|---|---|---|
| Port | `8000/tcp` | Dashboard, REST API and `/mcp`. Plain HTTP, one uvicorn worker. |
| `/opt/omniforge/data` | Volume | `omniforge.db` holds all your tools. **Back this up.** |
| `/opt/omniforge/lib` | Volume | Package caches. They can be rebuilt, but reinstalling is slow. |
| `/tmp` | tmpfs (optional) | Scratch only. |

Named volumes get the right ownership automatically. **Bind mounts must be owned by UID/GID 1000**, so run `chown -R 1000:1000 /path/to/appdata` before the first start, or SQLite can't create its database.

## Connect an MCP client

The server accepts **JSON-RPC 2.0 over `POST /mcp`**: `initialize`, `tools/list`, `tools/call` and `ping`. When a key is set, it also needs `Authorization: Bearer <key>`. It is **not** full MCP Streamable HTTP: there are no sessions, SSE responses, notifications, batching or OAuth. **No third-party client is verified**, so test yours with `tools/list` first. Use a hostname the client can reach, and refresh the client after adding tools.

**Claude Code**

```bash
claude mcp add --transport http omniforge http://your-host:8000/mcp \
  --header "Authorization: Bearer <YOUR_API_KEY>"
```

**Claude Desktop** (`claude_desktop_config.json` starts stdio servers, so use the community `mcp-remote` bridge)

```json
{
  "mcpServers": {
    "omniforge": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://your-host:8000/mcp", "--allow-http",
               "--transport", "http-only", "--header", "Authorization:${AUTH_HEADER}"],
      "env": { "AUTH_HEADER": "Bearer <YOUR_API_KEY>" }
    }
  }
}
```

**LibreChat** (`librechat.yaml`)

```yaml
mcpServers:
  omniforge:
    type: streamable-http
    url: http://your-host:8000/mcp
    headers:
      Authorization: "Bearer ${OMNIFORGE_API_KEY}"
    timeout: 120000
```

**Any HTTP client**

```bash
curl -s http://your-host:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Writing a tool

| | Behaviour |
|---|---|
| Input | One JSON object on stdin (`{}` when there are no arguments), validated against the tool's input schema first. |
| Output | stdout, trimmed. Print JSON for structured results. Return values aren't captured. |
| Errors | A non-zero exit code or timeout gives `isError: true`. stderr is appended as `[stderr] …`, even on success, so keep successful runs quiet on stderr. |
| Time limit | Configured timeout + 15 s. Exit code `124` is reserved to mean "timed out". |
| Packages | Python `name` or `name==1.2.3` (wheels only). Node `name`, `@scope/name` or `name@1.2.3` (CommonJS `require`, no install scripts). Installed on first run. |

```python
import json
import sys

args = json.load(sys.stdin)
print(json.dumps({"message": "Hello " + args.get("name", "world")}))
```

```javascript
const fs = require('node:fs');
const args = JSON.parse(fs.readFileSync(0, 'utf8'));
console.log(JSON.stringify({ message: 'Hello ' + (args.name || 'world') }));
```

The dashboard can't edit input schemas yet. Tools created in the browser take no parameters. To give a tool inputs, create it through `POST /api/tools` with a `json_schema`, or through the `omniforge_create_tool` MCP tool with an `inputSchema`.

## Security model and limitations

OmniForge is a **trusted-LAN tool for trusted authors**. It makes no claim of isolation or production-grade security.

| Area | Reality today |
|---|---|
| Dashboard and `/api/*` | **No authentication.** Anyone who can reach the port can read every tool's code, and create, edit, delete and run tools. |
| `POST /mcp` | Optional static Bearer key. Holding it means code execution, because `omniforge_create_tool` plus `tools/call` runs arbitrary code. |
| `GET /mcp` | **Unauthenticated** stub event stream: one event, then it closes. |
| FastAPI `/docs`, `/redoc`, `/openapi.json` | Enabled and unauthenticated. |
| Script isolation | **None.** Scripts run in this container as the same user, with a copy of its **entire environment, including `OMNIFORGE_API_KEY`**, which a tool can print. They can read and write the database and caches, and reach the network. |
| Availability | Runs and package installs block the single worker. **One slow tool stalls the whole server.** |
| Resource limits | The timeout **kills only the direct child process**. **Output isn't capped.** **The memory setting isn't enforced.** No CPU or rate limits. |
| MCP transport | Handwritten and partial, not full Streamable HTTP. No OAuth or sessions. |
| Browser attacks | No CSRF, `Origin` or `Host` checks. A malicious page opened on your network could toggle tools or run tools that take no inputs. |
| PWA | Installation needs **HTTPS or `localhost`**. |

Safeguards that **are** in place: arguments via stdin (no shell), strict name, package and schema validation before execution, a scrubbed installer environment with redacted errors, atomic non-destructive caches, revision guards, a 14-file static allow-list, an XSS-safe dashboard, a service worker that caches public assets only, parameterised SQL, and a non-root image.

**Recommended deployment:** a trusted network only, no port forwarding, no other secrets in the container's environment, resource limits set, and the hardening below.

```bash
docker run -d --name omniforge \
  -p 8000:8000 \
  -e OMNIFORGE_API_KEY='<your-random-key>' \
  -v omniforge_data:/opt/omniforge/data \
  -v omniforge_lib:/opt/omniforge/lib \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --memory 1g --cpus 2 \
  --restart unless-stopped \
  dbzocchi/omniforge:latest
```

These flags protect the **host**. They don't isolate scripts from the app or from each other. Never mount the Docker socket.

## Backup

Everything that matters is in `/opt/omniforge/data/omniforge.db`. For a consistent copy while running, use SQLite's backup API through the container's Python:

```bash
docker exec omniforge python3 -c "import sqlite3; s=sqlite3.connect('/opt/omniforge/data/omniforge.db'); d=sqlite3.connect('/opt/omniforge/data/omniforge-backup.db'); s.backup(d); d.close(); s.close()"
docker cp omniforge:/opt/omniforge/data/omniforge-backup.db ./omniforge-backup.db
docker exec omniforge rm /opt/omniforge/data/omniforge-backup.db
```

Or stop the container and copy the volume. To restore, stop the container, replace `omniforge.db`, delete any `omniforge.db-journal`, make sure UID 1000 owns the file, and start it again. There are no schema migrations.

## Updating

```bash
docker pull dbzocchi/omniforge:latest
docker stop omniforge && docker rm omniforge
# re-run your docker run command, or: docker compose pull && docker compose up -d
```

Back up first. Your tools live on the data volume and survive updates. If the dashboard shows **Update available**, accept it to load the new interface.

## Licence

Private. All rights reserved. The source code isn't public. The bundled Manrope and JetBrains Mono fonts are used under the SIL Open Font Licence, and their licence texts ship inside the image.
