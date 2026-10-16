# Connecting MCP clients

OmniForge publishes your enabled tools, plus two built-in helpers, at one endpoint:

```text
http://your-host:8000/mcp
```

The **Connect** screen in the dashboard shows the exact URL, based on the address you opened it from, and whether a key is required.

## What the endpoint actually speaks

Read this before choosing a client. OmniForge's MCP transport is **handwritten and partial**.

| Supported | Not supported |
|---|---|
| `POST /mcp` with one JSON-RPC 2.0 request object and `Content-Type: application/json` | Full MCP Streamable HTTP: no SSE responses, no `Mcp-Session-Id`, no resumable streams |
| Methods `initialize`, `tools/list`, `tools/call`, `ping` | The legacy HTTP+SSE transport. `GET /mcp` is a stub that sends one event and closes |
| Plain `application/json` responses | OAuth, or any discovery under `/.well-known/…` |
| Optional `Authorization: Bearer <key>` header | Notifications, including `notifications/tools/list_changed`, and JSON-RPC batches |

Full details are in [MCP protocol support](MCP-Protocol-Support.md).

> [!IMPORTANT]
> **Client compatibility is not verified.** The project's tests exercise the JSON-RPC handler directly; they don't run any third-party client. The configurations below match what the server accepts, but whether a given client version tolerates the gaps above is for you to check. A quick `tools/list` from the client is the test.

### Before you connect

- **Use a name or IP the client can reach.** `localhost` only works when the client runs on the same machine, and not from inside another container.
- **Have the key ready** if `OMNIFORGE_API_KEY` is set. Keep it in the client's own configuration or environment. Never put it in tool code.
- **Warm package caches.** Run tools that declare packages once from the dashboard first. A cold install can take minutes and outlast a client's timeout.
- **Refresh after changes.** OmniForge never announces new or changed tools, so reconnect or refresh the client's tool list.

## Claude Code

Add the server with the CLI:

```bash
claude mcp add --transport http omniforge http://your-host:8000/mcp \
  --header "Authorization: Bearer <YOUR_API_KEY>"
```

Leave out `--header` if you didn't set a key. Add `--scope project` to write it to the project's `.mcp.json`, or `--scope user` for every project.

Or put it in `.mcp.json` yourself, referencing an environment variable so the key stays out of the file:

```json
{
  "mcpServers": {
    "omniforge": {
      "type": "http",
      "url": "http://your-host:8000/mcp",
      "headers": {
        "Authorization": "Bearer ${OMNIFORGE_API_KEY}"
      }
    }
  }
}
```

Check it with `claude mcp list`, or with `/mcp` inside a session. If first calls to tools with packages time out, raise Claude Code's tool timeout (the `MCP_TOOL_TIMEOUT` environment variable, in milliseconds), or warm the cache from the dashboard first.

## Claude Desktop

Claude Desktop's `claude_desktop_config.json` starts **local** (stdio) servers. To reach an HTTP server on your LAN, run a stdio-to-HTTP bridge. The community package [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) is the usual choice, and needs Node.js on the desktop machine.

Config file locations:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "omniforge": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://your-host:8000/mcp",
        "--allow-http",
        "--transport",
        "http-only",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer <YOUR_API_KEY>"
      }
    }
  }
}
```

- `--allow-http` is needed because the URL isn't HTTPS. Leave it out if you put OmniForge behind HTTPS.
- `--transport http-only` stops the bridge falling back to the legacy SSE transport, which OmniForge doesn't support.
- The header is passed through `env` because spaces inside `args` are mangled on some platforms.
- With no key set, drop the `--header` pair and the `env` block.
- Fully quit and restart Claude Desktop after editing the file.

Custom connectors added in Claude's settings are aimed at internet-reachable remote servers, and OmniForge must not be one. Use the bridge.

## LibreChat

In `librechat.yaml`:

```yaml
mcpServers:
  omniforge:
    type: streamable-http
    url: http://your-host:8000/mcp
    headers:
      Authorization: "Bearer ${OMNIFORGE_API_KEY}"
    timeout: 120000
```

- `${OMNIFORGE_API_KEY}` is resolved from **LibreChat's** `.env`, so add the key there. With no key set, remove `headers`.
- If LibreChat runs in Docker on the same host, `localhost` is LibreChat's own container. Use the host's LAN name or IP, or put both containers on one Docker network and use `http://omniforge:8000/mcp`.
- `timeout` is in milliseconds. Allow for slow tools and first-run installs.
- Restart LibreChat after editing the file. If your version refuses private addresses for MCP servers, check its MCP allow-list settings.

## Generic HTTP

Any HTTP client can talk to OmniForge. No session handshake is needed: each POST stands alone.

**1. Initialise (optional, but polite):**

```bash
curl -s http://your-host:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":false}},"serverInfo":{"name":"omniforge-mcp","version":"0.1.0"}}}
```

OmniForge echoes back whatever `protocolVersion` you send.

**2. List tools:**

```bash
curl -s http://your-host:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {"name": "omniforge_instructions", "description": "Read how to author and register trusted Python/Node scripts…", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": false}},
      {"name": "omniforge_create_tool", "description": "Save a new trusted script as a tool without executing it…", "inputSchema": {"…": "…"}},
      {"name": "add_vat", "description": "Add UK VAT to a net amount…", "inputSchema": {"type": "object", "properties": {"net": {"type": "number", "minimum": 0}}, "required": ["net"], "additionalProperties": false}}
    ]
  }
}
```

**3. Call a tool:**

```bash
curl -s http://your-host:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"add_vat","arguments":{"net":10}}}'
```

**Python (standard library only):**

```python
import json
import os
import urllib.request

def mcp(method, params=None, *, url="http://your-host:8000/mcp", request_id=1):
    body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}).encode()
    headers = {"Content-Type": "application/json"}
    if key := os.environ.get("OMNIFORGE_API_KEY"):
        headers["Authorization"] = f"Bearer {key}"
    with urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=300) as response:
        return json.load(response)

print(mcp("tools/call", {"name": "add_vat", "arguments": {"net": 10}})["result"]["content"][0]["text"])
```

## When it doesn't connect

| Symptom | Likely cause |
|---|---|
| HTTP 401, `{"error":{"code":-32000,"message":"Unauthorized"}}` | Missing or wrong key. The header must be `Authorization: Bearer <key>`. |
| HTTP 422 with a FastAPI `detail` body | The body isn't a single JSON object: an empty body, a batch array, or the wrong `Content-Type`. |
| `Method not found: notifications/initialized` in a log | Harmless. OmniForge answers notifications with an error instead of HTTP 202. A strict client may complain. |
| Client hangs or loops on SSE | It expects the legacy HTTP+SSE transport or a server-sent event stream. OmniForge doesn't provide either. |
| A tool is missing from the list | It's disabled, or the client hasn't refreshed. Tools aren't announced. |
| `Unknown or inactive tool` | The name is wrong, or the tool is disabled. |
| First call times out, the second works | The first call installed packages. Warm the cache from the dashboard. |
| Whole server unresponsive for a while | Another tool call is still running. See [Security and limitations](Security-and-Limitations.md#availability-one-slow-tool-stalls-everything). |

More in [Troubleshooting and FAQ](Troubleshooting-and-FAQ.md).

---

← [Home](Home.md) · [Next: Built-in authoring tools →](Built-in-Authoring-Tools.md)
