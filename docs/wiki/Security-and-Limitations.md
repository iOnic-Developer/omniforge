# Security and limitations

> [!CAUTION]
> **OmniForge is built for a trusted LAN.** It is not production-grade, it isn't safe to expose to the internet, and it doesn't isolate scripts from one another or from itself. Anyone who can reach port 8000 can read, change and run every tool. Every tool can read everything the application can, including its MCP key.

This page lists what OmniForge does and doesn't protect, as the code stands today. Nothing here is hidden in the product either: the dashboard's Overview, Connect and Help screens and the built-in `omniforge_instructions` tool say the same.

## Who can do what

| Surface | Authentication | What an unauthenticated caller can do |
|---|---|---|
| Dashboard `GET /` | **None** | Everything the UI offers |
| Management API `/api/*` | **None** | List every tool **including its source code**, create, edit, rename, enable, disable, delete and **run** tools |
| `POST /mcp` | Optional Bearer key (`OMNIFORGE_API_KEY`) | With no key set: list, call and **create** tools. With a key: nothing (HTTP 401) |
| `GET /mcp` | **None** | Receive a two-line stub event stream. No data is exposed |
| `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` | **None** | FastAPI's built-in interactive API docs. "Try it out" can call the unauthenticated API |
| `/assets/*`, `/sw.js` | None (public by design) | Fetch 14 allow-listed static files |

The API key therefore **only** gates `POST /mcp`. Anyone who can reach the dashboard or `/api` can do more than an MCP client can, without any key.

### MCP access means code execution

`omniforge_create_tool` saves arbitrary code, and `tools/call` runs it. Anyone holding the MCP key, or anyone at all when no key is set, can run code inside the container. Treat the key like a shell password.

### The key itself

- Read once at start-up from `OMNIFORGE_API_KEY`. Changing it means recreating the container.
- Sent as `Authorization: Bearer <key>`. The server also accepts the bare key as the whole header value.
- Compared with a plain string equality, not a constant-time comparison.
- Never returned by `/api/config`, which reports only `auth_enabled: true|false`, and never included in `omniforge_instructions`.
- **Visible to every script**, because scripts inherit the application environment (see below).

## Scripts are not isolated

Every run is `python3 <file>` or `node <file>`, started with `subprocess.run` **inside the application container, as the same user (UID 1000), with a copy of the application's environment**. Consequently:

- **Environment.** A tool sees every variable the container has, **including `OMNIFORGE_API_KEY`**, and can print it. `print(os.environ["OMNIFORGE_API_KEY"])` returns the key to whoever called the tool. The project's own tests confirm that scripts inherit it (`tests/test_dependencies.py`). Anything else you pass to the container, such as cloud credentials, is equally exposed.
- **Files.** A tool can read and write the SQLite database, every other tool's code and package cache, and `/tmp`. Unless the root filesystem is read-only, it can also write the application code in `/app`.
- **Processes.** A tool can signal or stop the server process, since it runs as the same user. Anything it spawns survives timeouts.
- **Network.** A tool can reach whatever the container can, including other services on your LAN.
- **Other tools.** There's no per-tool boundary. One tool can rewrite another.

Container hardening (`--read-only`, `--cap-drop ALL`, `no-new-privileges`, no Docker socket) protects the **host**. It does nothing to separate scripts from OmniForge or from each other. Only run code, and packages, you trust as much as the app itself.

## Resource limits that don't exist

| Limit | Status |
|---|---|
| Memory per script | **Not enforced.** `OMNIFORGE_MAX_SCRIPT_MEMORY_MB` is read but never applied. Cap the container with Docker's `--memory`. |
| Output size | **Not capped.** stdout and stderr are buffered in full in the server's memory and returned whole. |
| Timeout | Configured value + 15 s (45 s by default). On expiry, **only the direct child process is killed**. Grandchildren keep running. |
| CPU | None. Use Docker's `--cpus`. |
| Concurrency or rate limiting | None. (`slowapi` is installed but not used.) |
| Disk | Package caches are never cleaned automatically. See [Dependencies](Dependencies.md#cleaning-up). |

## Availability: one slow tool stalls everything

The run endpoint (`POST /api/tools/{name}/run`) and the MCP endpoint (`POST /mcp`) are `async` handlers that call the blocking `subprocess.run`, and the blocking pip/npm install, directly on the event loop. The image runs a single uvicorn worker. While one tool runs or installs, **the whole server stops responding**: the dashboard, `/api` and every other MCP client wait.

A first run with packages can block for up to 120 s of install plus a 125 s lock wait. A normal run can block for up to the script timeout, 45 s by default. A tool that loops forever blocks for the full timeout on every call. See [Configuration → Workers](Configuration.md#workers) for a partial, untested mitigation.

## Browser-based attacks

There's no CSRF protection and no `Origin` or `Host` checking.

- A web page that someone on your network happens to open can send **simple cross-site POST requests** to OmniForge. For example, it can toggle tools on or off (`POST /api/tools/{name}/toggle`) or run any tool that accepts empty input (`POST /api/tools/{name}/run` with no body). Neither request needs a preflight, so the browser sends both. Endpoints that need a JSON body or a `DELETE`/`PUT` method trigger a CORS preflight, which OmniForge doesn't answer, so a browser won't send those cross-site.
- **DNS rebinding** can, in principle, give a malicious site full same-origin access to the unauthenticated API, because OmniForge accepts any `Host` header.

Keep OmniForge on a segment where browsing the web isn't routine, or bind it to an interface only trusted devices can reach.

## MCP transport gaps

- A handwritten, partial JSON-RPC transport, not full Streamable HTTP. The official `mcp` Python SDK is installed (it also supplies `jsonschema`, which the app uses for validation), but the transport doesn't use it.
- No OAuth, no sessions and no client tracking.
- `GET /mcp` is an unauthenticated stub.
- Exact behaviour is in [MCP protocol support](MCP-Protocol-Support.md).

## Supply chain

- Tools can name any public PyPI or npm package. Validation blocks URLs, flags and shell tricks in package names, **not** malicious packages.
- Unpinned names resolve to the newest version on first install and then stay frozen in that tool's cache.
- The app's own Python dependencies (`requirements.txt`) are unpinned, so each image build picks up the newest versions.

## What *is* protected

| Control | Detail |
|---|---|
| No shell anywhere | Arguments reach scripts as JSON on stdin, never through a shell, the command line or environment variables. |
| Strict input validation | Tool names match `^[a-zA-Z][a-zA-Z0-9_-]{0,62}$`. Package names have strict patterns. Schemas are Draft 2020-12 with local references only, and remote references are never fetched. |
| Arguments validated before execution | Calls that don't match the schema never start a process. |
| No echo of submitted values | Validation errors leave out the submitted values, code and secrets. |
| Installer environment scrubbed | pip and npm get a minimal environment, with no app keys, `PIP_*`/`NPM_*` configuration or proxy variables. Installer error output has secret-looking values and URLs redacted and is truncated to 3000 characters. |
| Atomic, never-destructive caches | Installs stage into a unique directory, publish with an atomic rename and never delete directories they didn't create. |
| Optimistic concurrency | `If-Match` revisions stop stale tabs overwriting, deleting, toggling or testing changed tools (HTTP 412). |
| Static file allow-list | Only 14 named files are served from `/assets/`. Path traversal, `.env`, databases and source files return 404. |
| XSS-safe dashboard | All dynamic text is set with `textContent`. The template contains no `innerHTML`. |
| Careful PWA cache | Only public assets are cached. No HTML, API data, code, results or credentials. |
| Non-root container | Runs as UID 1000. Works with a read-only root, `noexec` `/tmp`, all capabilities dropped and `no-new-privileges`. |
| Parameterised SQL | Every database query uses bound parameters. |

## Deployment checklist

- [ ] Port 8000 is reachable only from trusted devices: no port forwarding, and no public reverse proxy.
- [ ] `OMNIFORGE_API_KEY` is set to a long random value (not `change-me`).
- [ ] The container holds **no other secrets** in its environment, since every tool can read them.
- [ ] Only people you'd give a shell to can reach the dashboard.
- [ ] The container has `--memory` and `--cpus` limits.
- [ ] The hardened flags are applied: `--read-only`, `--tmpfs /tmp`, `--cap-drop ALL`, `no-new-privileges`.
- [ ] The Docker socket is **not** mounted.
- [ ] Backups of the data volume are scheduled ([Backup and restore](Backup-and-Restore.md)).
- [ ] The image is pinned by digest for reproducible deploys ([Release and deployment](Release-and-Deployment.md)).

## Gaps a public deployment would need closing

These are known and tracked for future work. None of them is implemented today.

- Authentication for the dashboard, the management API, `GET /mcp` and the FastAPI docs routes.
- Per-run isolation (a separate user, sandbox or container), plus a scrubbed environment for scripts.
- Non-blocking execution (a thread pool or job queue), with process-group kills, output caps and enforced memory limits.
- Full MCP Streamable HTTP, ideally via the official SDK, with OAuth and `Origin` validation.
- CSRF protection and `Host` checking.
- Editing input schemas in the dashboard. Today, tools made in the browser take no parameters.

---

← [Home](Home.md) · [Next: Backup and restore →](Backup-and-Restore.md)
