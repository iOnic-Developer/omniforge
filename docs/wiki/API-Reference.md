# API reference

Every HTTP route the application serves, taken from `app/main.py` and FastAPI's defaults. The base URL is `http://your-host:8000`.

> [!WARNING]
> Apart from `POST /mcp`, which has an optional Bearer key, **no route is authenticated**. No CORS headers are sent, so browsers block cross-origin reads, but simple cross-site POSTs still reach the server. See [Security and limitations](Security-and-Limitations.md#browser-based-attacks).

## Route summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | none | Dashboard HTML |
| `GET` | `/assets/{asset}` | none | One of 14 allow-listed static files |
| `GET` | `/sw.js` | none | Service worker |
| `GET` | `/api/config` | none | Public connection metadata |
| `GET` | `/api/tools` | none | List every saved tool, **with source code** |
| `POST` | `/api/tools` | none | Create a tool |
| `PUT` | `/api/tools/{name}` | none | Replace a tool (all fields) |
| `DELETE` | `/api/tools/{name}` | none | Delete a tool |
| `POST` | `/api/tools/{name}/toggle` | none | Flip enabled and disabled |
| `POST` | `/api/tools/{name}/run` | none | Run a saved tool and return its output |
| `POST` | `/mcp` | Bearer (if `OMNIFORGE_API_KEY` is set) | MCP JSON-RPC: see [MCP protocol support](MCP-Protocol-Support.md) |
| `GET` | `/mcp` | none | Stub event stream |
| `GET`, `HEAD` | `/docs` | none | FastAPI Swagger UI (loads its scripts from a public CDN) |
| `GET`, `HEAD` | `/redoc` | none | FastAPI ReDoc |
| `GET`, `HEAD` | `/openapi.json` | none | OpenAPI schema |
| `GET`, `HEAD` | `/docs/oauth2-redirect` | none | Swagger UI helper page |

## Conventions

- **Request bodies** are JSON and need `Content-Type: application/json`. Models are **strict**: types must match exactly, and unknown fields are rejected.
- **Successful writes** return HTTP **200**, not 201.
- **Errors** use FastAPI's shape:
  - Application errors: `{"detail": "Human-readable message"}`
  - Validation errors (HTTP 422): `{"detail": [{"type": "…", "loc": ["body", "name"], "msg": "…", "input": …}]}`. FastAPI's `input` field **echoes the submitted value**, which may include code. The dashboard displays only `msg`.
- **`{name}` in the path** must match `^[a-zA-Z][a-zA-Z0-9_-]{0,62}$` and mustn't be a built-in name. Otherwise the response is HTTP 400 `{"detail": "Invalid tool name: …"}` or `{"detail": "Tool name is reserved for a built-in tool"}`.
- **`If-Match`** (optional) carries a tool's `revision`. When present, `PUT`, `DELETE`, `toggle` and `run` return **HTTP 412** if the tool changed since that revision. Leave it out for unconditional behaviour.

## The tool object

Returned by `GET /api/tools`:

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | string | `"3f9c2a1b7d4e"` | 12 hex characters. Stable across renames |
| `name` | string | `"add_vat"` | |
| `description` | string | `"Add UK VAT…"` | May be `""` |
| `language` | string | `"python3"` | `python3` or `node` |
| `code` | string | `"import json\n…"` | Full source |
| `requirements_json` | string | `"[\"requests==2.32.5\"]"` | A JSON array **encoded as a string** |
| `json_schema_json` | string | `"{\"type\": \"object\", …}"` | A JSON object **encoded as a string** |
| `is_active` | boolean | `true` | Enabled for MCP |
| `created_at` | string | `"2026-10-16T09:30:00Z"` | UTC |
| `updated_at` | string | `"2026-10-16T09:41:12Z"` | UTC. Changes on every save or toggle |
| `revision` | string | 64 hex characters | SHA-256 of the content fields and `is_active`. Use it with `If-Match` |

## The tool input (`ToolIn`)

The body for `POST /api/tools` and `PUT /api/tools/{name}`. Use **`json_schema`**, not `inputSchema` (the latter is the MCP authoring field). Types are strict and extra fields are rejected:

| Field | Type | Required | Default | Rules |
|---|---|---|---|---|
| `name` | string | **yes** | | Name pattern above. Not reserved, and unique |
| `code` | string | **yes** | | Not blank, and no NUL characters |
| `description` | string | no | `""` | |
| `language` | string | no | `"python3"` | `python`, `python3`, `node`, `js` or `javascript`. Stored as `python3` or `node` |
| `requirements` | array of strings | no | `[]` | Up to 50. See [Dependencies](Dependencies.md#accepted-forms). Deduplicated and sorted |
| `json_schema` | object | no | `{}` (no inputs) | See [schema rules](Writing-Tools.md#schema-rules) |
| `is_active` | boolean | no | `true` | |

---

## `GET /`

The dashboard. `Content-Type: text/html`, `Cache-Control: no-store`.

## `GET /assets/{asset}`

Serves only these files from `app/static/`. Anything else returns 404 `{"detail": "Asset not found"}`.

| Asset | MIME type |
|---|---|
| `product.css` | `text/css` |
| `mark.svg`, `favicon.svg` | `image/svg+xml` |
| `favicon-32.png`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `icon-maskable-512.png` | `image/png` |
| `manifest.webmanifest` | `application/manifest+json` |
| `offline.html` | `text/html` |
| `fonts/manrope.ttf`, `fonts/jetbrains-mono.ttf` | `font/ttf` |
| `fonts/OFL-Manrope.txt`, `fonts/OFL-JetBrainsMono.txt` | `text/plain` |

Headers: `Cache-Control: no-cache`, `X-Content-Type-Options: nosniff`.

## `GET /sw.js`

The service worker. Headers: `Content-Type: application/javascript`, `Cache-Control: no-cache`, `Service-Worker-Allowed: /`, `X-Content-Type-Options: nosniff`.

## `GET /api/config`

Connection metadata for the Connect screen. Never includes the key.

```json
{
  "mcp_path": "/mcp",
  "transport": "HTTP JSON-RPC POST (limited MCP implementation)",
  "auth_enabled": true,
  "auth_header": "Authorization: Bearer <YOUR_API_KEY>",
  "auth_configuration": "Set OMNIFORGE_API_KEY in the server environment and recreate the container.",
  "dashboard_auth_enabled": false,
  "connection_tracking": false,
  "methods": ["initialize", "tools/list", "tools/call", "ping"],
  "warnings": [
    "Dashboard and tool-management API are unauthenticated. Keep this server on a trusted network.",
    "Scripts share the application container; only run trusted code.",
    "OAuth, client/session tracking and full Streamable HTTP transport are not implemented."
  ]
}
```

## `GET /api/tools`

```json
{"tools": [ { "id": "3f9c2a1b7d4e", "name": "add_vat", "…": "…" } ]}
```

Returns every row, enabled and disabled, newest `updated_at` first. Rows left over from old versions that use a built-in name are included here; the dashboard hides them.

## `POST /api/tools`

Creates a tool. Saves only: nothing is run or installed.

```bash
curl -s http://localhost:8000/api/tools -H 'Content-Type: application/json' \
  -d '{"name":"hello","code":"print(\"hi\")"}'
```

| Status | Body |
|---|---|
| 200 | `{"ok": true, "id": "3f9c2a1b7d4e", "revision": "…"}` |
| 409 | `{"detail": "Tool name already exists; choose another name or edit it in the dashboard"}` |
| 422 | Validation error, for example an unknown field, a bad name, an invalid schema or an invalid requirement |

## `PUT /api/tools/{name}`

Replaces the tool currently called `{name}`. To rename it, send a different `name` in the body. The `id` is kept.

> [!IMPORTANT]
> This is a **full replacement**. Omitted fields take their defaults: `description` → `""`, `language` → `python3` (turning a Node tool into a Python one), `requirements` → `[]`, `json_schema` → no inputs, and `is_active` → `true`. Read the tool first and send every field, as in [this recipe](Writing-Tools.md#changing-the-schema-of-an-existing-tool).

Headers: `If-Match: <revision>` (optional, recommended).

| Status | Body |
|---|---|
| 200 | `{"ok": true, "revision": "…"}` |
| 400 | Invalid or reserved name in the path |
| 404 | `{"detail": "Tool not found"}` |
| 409 | The new name belongs to another tool |
| 412 | `{"detail": "Tool changed in another tab or client; reload before changing it"}` |
| 422 | Body validation error |

## `DELETE /api/tools/{name}`

Headers: `If-Match: <revision>` (optional). Without it, **every** row with that name is deleted, including old duplicates. With it, the delete only goes ahead if exactly one row matches that revision.

| Status | Body |
|---|---|
| 200 | `{"ok": true}` |
| 400 | Invalid or reserved name |
| 404 | `{"detail": "Tool not found"}` |
| 412 | `{"detail": "Tool changed in another tab or client; reload before deleting it"}` |

The tool's package cache isn't removed. See [Dependencies → Cleaning up](Dependencies.md#cleaning-up).

## `POST /api/tools/{name}/toggle`

No body. Flips `is_active`. Code and schema are untouched, but the revision changes.

| Status | Body |
|---|---|
| 200 | `{"ok": true, "is_active": false, "revision": "…"}` |
| 400 | Invalid or reserved name |
| 404 | `{"detail": "Tool not found"}` |
| 412 | `{"detail": "Tool changed in another tab or client; reload before toggling it"}` |

## `POST /api/tools/{name}/run`

Runs the **saved** tool (read fresh from the database) and waits for it to finish. Disabled tools run too.

Body (optional; leaving it out means `{}`):

```json
{"arguments": {"net": 99.99}}
```

`arguments` must be an object, and no other keys are allowed.

| Status | Body |
|---|---|
| 200 | `{"stdout": "…", "stderr": "…", "exit_code": 0, "timed_out": false, "duration_ms": 41}` |
| 400 | Invalid or reserved name |
| 404 | `{"detail": "Tool not found"}` |
| 412 | `{"detail": "Tool changed in another tab or client; reload before testing it"}` |
| 422 | `{"detail": "Arguments do not match inputSchema"}`, `{"detail": "Invalid arguments or unresolved local inputSchema reference"}`, or a body validation error |

**HTTP 200 doesn't mean the script succeeded.** Check `exit_code` (0 is success) and `timed_out`. `stdout` and `stderr` are trimmed and not size-limited. Dependency failures come back as `exit_code: 1` with the message in `stderr`. A timeout is `exit_code: 124` and `timed_out: true`. While the run is in progress, the server handles no other requests.

## `POST /mcp`

JSON-RPC 2.0 over HTTP. The full method list and behaviour are in [MCP protocol support](MCP-Protocol-Support.md).

| Status | When |
|---|---|
| 200 | Any well-formed JSON object body, including JSON-RPC errors such as "method not found" |
| 401 | A key is configured and the `Authorization` header is missing or wrong: `{"jsonrpc":"2.0","id":null,"error":{"code":-32000,"message":"Unauthorized"}}` |
| 422 | The body isn't a single JSON object (empty, an array, or not JSON), or `Content-Type` isn't JSON. This check happens **before** authentication |

## `GET /mcp`

Unauthenticated. Returns `Content-Type: text/event-stream` with this body, then closes the stream:

```text
event: initial-connections
data: {"protocolVersion": "2024-11-05"}

```

It doesn't carry MCP messages, and it isn't the legacy SSE transport's `endpoint` event.

## FastAPI documentation routes

FastAPI adds `/docs` (Swagger UI), `/redoc`, `/openapi.json` and `/docs/oauth2-redirect` by default, and OmniForge doesn't turn them off. They're handy for exploring the API, but they're unauthenticated, and Swagger's **Try it out** sends real requests. The Swagger and ReDoc pages fetch their JavaScript from a public CDN, so they need internet access in your browser.

---

← [Home](Home.md) · [Next: MCP protocol support →](MCP-Protocol-Support.md)
