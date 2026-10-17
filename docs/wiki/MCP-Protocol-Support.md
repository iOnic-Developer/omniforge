# MCP protocol support

OmniForge implements a **small, handwritten subset** of the Model Context Protocol over HTTP, in `app/main.py` (`_handle_rpc`) and `app/mcp_server.py` (`MCPHandler`). The official `mcp` Python SDK is installed as a dependency, but the transport doesn't use it. This page describes exactly what the code does.

## Transport

| Aspect | Behaviour |
|---|---|
| Endpoint | `POST /mcp` |
| Request | **One** JSON-RPC 2.0 request object per HTTP request. `Content-Type: application/json` |
| Response | Always `application/json` with one JSON-RPC response, whatever the `Accept` header says |
| Batches (JSON arrays) | **Not supported.** HTTP 422 |
| Sessions | **None.** No `Mcp-Session-Id` is issued or read. Every request stands alone |
| `MCP-Protocol-Version` header | Ignored |
| Server-to-client messages | **None.** No SSE responses, notifications or requests from the server |
| `GET /mcp` | An unauthenticated stub. It sends `event: initial-connections` and `data: {"protocolVersion": "2024-11-05"}`, then closes. It isn't a working SSE channel |
| `DELETE /mcp` | Not routed (HTTP 405) |
| Legacy HTTP+SSE transport (2024-11-05) | **Not supported.** There's no `endpoint` event and no separate message URL |
| Auth | Optional static Bearer key. No OAuth, no `/.well-known` metadata, no `WWW-Authenticate` challenge |
| `Origin` / `Host` validation | **None** |

In short, it's "JSON-RPC over POST", which overlaps with the request/response part of Streamable HTTP. Clients that need anything more will fail.

## Envelope handling

| Input | Result |
|---|---|
| `jsonrpc` field | Not checked. Responses always say `"jsonrpc": "2.0"` |
| `id` | Echoed back exactly. A missing `id` is echoed as `null` |
| `params` missing | Treated as `{}` |
| `params` not an object (`null`, an array or a string) | Error `-32602`, `"params must be a JSON object"` |
| Unknown method, or no method | Error `-32601`, `"Method not found: <method>"` (or `None`) |
| Notifications (no `id`), for example `notifications/initialized` | **Answered** with `-32601` and `"id": null`, HTTP 200. Spec-compliant servers return HTTP 202 with no body |
| Auth failure | HTTP 401, error `-32000`, `"Unauthorized"`, `"id": null` |

## Methods

### `initialize`

Request:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"example","version":"1.0"}}}
```

Response:

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":false}},"serverInfo":{"name":"omniforge-mcp","version":"0.1.0"}}}
```

- `protocolVersion` is **echoed** from the request, with no negotiation. If the client leaves it out, the result is `""`.
- Client `capabilities` and `clientInfo` are ignored.
- The only capability advertised is `tools` with `listChanged: false`. There's no `resources`, `prompts`, `logging`, `completions` or `instructions`.
- `initialize` is optional. Every other method works without it.

### `tools/list`

```json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

```json
{"jsonrpc":"2.0","id":2,"result":{"tools":[
  {"name":"omniforge_instructions","description":"…","inputSchema":{"type":"object","properties":{},"additionalProperties":false}},
  {"name":"omniforge_create_tool","description":"…","inputSchema":{"type":"object","properties":{"name":{"…":"…"}},"required":["name","code"],"additionalProperties":false}},
  {"name":"add_vat","description":"Add UK VAT…","inputSchema":{"type":"object","properties":{"net":{"type":"number"}},"required":["net"],"additionalProperties":false}}
]}}
```

- The two built-ins always come first, then every **enabled** saved tool, most recently updated first. Rows using a built-in name are skipped.
- Each tool has only `name`, `description` and `inputSchema`. There's no `title`, `outputSchema` or `annotations`.
- There's no pagination. `cursor` is ignored, and `nextCursor` is never returned.
- Read from the database on each call, through a cache of at most 5 s that writes in the same process clear immediately.

### `tools/call`

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"add_vat","arguments":{"net":10}}}
```

```json
{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\"net\": \"10\", \"rate\": \"20\", \"vat\": \"2.00\", \"gross\": \"12.00\"}"}],"isError":false}}
```

- `arguments` defaults to `{}` when left out. `null` or a non-object gives `isError: true`, `"arguments must be a JSON object"`.
- Arguments are validated against the tool's `inputSchema` **before** anything runs. A failure gives `isError: true`, `"Arguments do not match inputSchema"`.
- An unknown or disabled tool gives `isError: true`, `"Unknown or inactive tool"`.
- **Every tool-level problem is a successful JSON-RPC result with `isError: true`**, never a JSON-RPC `error`.
- The result is always one `text` content item. There's no `structuredContent`, no images and no resources.
- Text format: stdout (or `(no output)`), then on new lines any pre-run error, `[stderr] …`, `[exit N]` for a non-zero exit and `[timeout]`. `isError` is `true` when the exit code isn't 0 or the run timed out.
- The call is **synchronous**. The HTTP response is sent only after any package install and the script have finished, which can take minutes on a cold cache. No progress notifications are sent, and cancellation isn't supported.

Built-in tools are described in [Built-in authoring tools](Built-in-Authoring-Tools.md).

### `ping`

```json
{"jsonrpc":"2.0","id":4,"method":"ping"}
```

```json
{"jsonrpc":"2.0","id":4,"result":null}
```

The result is `null`. The specification expects an empty object `{}`, and strict clients may object.

## Not implemented

| Feature | Status |
|---|---|
| `resources/*`, `prompts/*`, `completion/complete`, `logging/setLevel`, `sampling/*`, `elicitation/*`, `roots/*` | Not implemented (`-32601`) |
| `notifications/tools/list_changed` | Never sent. Clients must refresh `tools/list` themselves |
| `notifications/cancelled`, `notifications/progress` | Not handled |
| JSON-RPC batching | Not supported |
| Session management, resumability | Not supported |
| OAuth 2.1 authorisation | Not supported |

## Compatibility notes

- Clients that send `initialize`, then `tools/list` and `tools/call` over POST, and accept JSON responses, have the best chance of working. Clients that refuse a 200 reply to a notification, require `ping` to return `{}`, insist on a session ID, or open an SSE stream and expect it to stay open may break.
- **No third-party client has been verified** by the project's test suite. Try `tools/list` from your client before you rely on it. See [Connecting MCP clients](Connecting-MCP-Clients.md).
- The handwritten transport is a known gap. Replacing it with the official SDK's Streamable HTTP server is listed under [future work](Security-and-Limitations.md#gaps-a-public-deployment-would-need-closing).

---

← [Home](Home.md) · [Next: Development and testing →](Development-and-Testing.md)
