# Glossary

| Term | Meaning in OmniForge |
|---|---|
| **Built-in tool / helper** | `omniforge_instructions` or `omniforge_create_tool`. Always listed to MCP clients, never stored in the database, and impossible to edit or shadow. See [Built-in authoring tools](Built-in-Authoring-Tools.md). |
| **Bearer key** | The value of `OMNIFORGE_API_KEY`, sent by clients as `Authorization: Bearer <key>`. It protects `POST /mcp` only. |
| **Dependency cache** | A per-tool directory under `OMNIFORGE_LIB_ROOT` holding that tool's installed pip or npm packages, keyed by tool ID, language and the hash of its requirements. See [Dependencies](Dependencies.md). |
| **Digest** | The immutable `sha256:…` identifier of an image. Deploying `dbzocchi/omniforge@sha256:…` always gives exactly the same image, unlike `:latest`. |
| **Disabled tool** | A saved tool with `is_active: false`. Hidden from `tools/list` and refused by `tools/call`, but still editable and runnable from the dashboard. |
| **Enabled tool** | A saved tool with `is_active: true`. Discoverable and callable over MCP. |
| **Exit code** | The number a script ends with. `0` means success. OmniForge reports any other value as an error, and treats `124` as a timeout. |
| **Hot reload** | Saved changes are visible on the next `tools/list` without restarting, because the tool list is read from the database on each request. |
| **`If-Match`** | An HTTP header carrying a tool's `revision`. When present, OmniForge refuses to change, delete, toggle or run a tool that has changed since, with HTTP 412. |
| **Input schema (`inputSchema` / `json_schema`)** | The JSON Schema (Draft 2020-12, root `type: object`) describing a tool's arguments. Called `inputSchema` in MCP and `json_schema` in the REST API. Empty means no inputs. |
| **JSON-RPC** | The request/response message format MCP uses: `{"jsonrpc":"2.0","id":…,"method":…,"params":…}`. |
| **Library** | The **Tools** screen: every saved tool. |
| **MCP (Model Context Protocol)** | An open protocol that lets AI clients discover and call tools on a server. OmniForge supports a [subset](MCP-Protocol-Support.md). |
| **MCP client** | An application that connects to MCP servers on an AI's behalf, such as Claude Code, Claude Desktop (via a bridge) or LibreChat. |
| **PWA (Progressive Web App)** | A website that can be installed like an app. OmniForge's dashboard is one, when served over HTTPS or `localhost`. See [PWA and themes](PWA-and-Themes.md). |
| **Requirements** | The package list declared for a tool, such as `requests==2.32.5` or `lodash@4.17.21`. Installed on the first run. |
| **Revision** | A SHA-256 of a tool's content and enabled state. It changes on every save or toggle. |
| **Run / Test** | The Tool studio button that runs the saved version of a tool with the Test inputs, and shows stdout, stderr, the exit code and the duration. |
| **Runtime** | The language a tool runs in: Python 3 (`python3`) or Node.js (`node`). |
| **Scratch directory** | `OMNIFORGE_SCRATCH_ROOT` (`/tmp/omniforge`), where scripts are written before each run and where they run. Shared by all tools. |
| **Secure context** | A page served over HTTPS or from `localhost`. Browsers only allow service workers and app installation in one. |
| **Service worker** | `sw.js`, the dashboard's background script. It caches 12 public assets and shows an offline page. It never caches tools, code or results. |
| **SSE (Server-Sent Events)** | A one-way HTTP stream from server to browser or client. OmniForge's `GET /mcp` only pretends to offer one: it sends a single event and closes. |
| **stdin / stdout / stderr** | A process's standard input, output and error streams. Tools receive arguments on stdin, return results on stdout and report problems on stderr. |
| **Streamable HTTP** | The current standard MCP transport over HTTP, with sessions and optional SSE streaming. OmniForge implements only its basic POST request and JSON response part. |
| **Template** | One of the four ready-made examples in Help and the template picker: Python greeting, Node greeting, Python + requests and Node + lodash. |
| **Test inputs** | The JSON object typed into the Tool studio for Run / Test. Temporary: it's never saved. |
| **Tool** | A named Python or Node script, with a description, optional packages and an optional input schema, that an AI client can call. |
| **Tool studio** | The editor screen (`#tools/new`, `#tools/edit/<name>`) where you write, save and test one tool. |
| **Trusted LAN** | A private network where every device and person able to reach OmniForge is trusted with full control of it, which is the only safe place to run it. See [Security and limitations](Security-and-Limitations.md). |

---

← [Home](Home.md) · [Next: Home →](Home.md)
