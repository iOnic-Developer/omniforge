# OmniForge: Product Strategy & Roadmap Review

The following review identifies strategic gaps and growth opportunities for OmniForge, ranging from critical security requirements to visionary "big bets" for advanced users.

## 1. Missing Features
| Title | Area | Why (Pain) | What | Effort | Priority |
|---|---|---|---|---|---|
| **Per-Tool Env Vars** | Runtime | Hardcoding keys in `code` is a security risk; global `os.environ` is too broad. | Secure UI for defining tool-specific key-value pairs stored encrypted in SQLite. | M | P1 |
| **Git Synchronization** | Persistence | Dashboard edits are "islands"; users want to track tool changes in version control. | Bidirectional sync with a Git repo (pull tools from `/tools/*.py`, push changes). | L | P2 |
| **Tool Tagging/Groups** | Organization | Large libraries become unmanageable with just a name search. | Categorize tools (e.g., "DevOps", "Content", "Finance") for filtered discovery. | S | P3 |
| **Execution History** | Observability | Users can't see why a tool failed for an LLM client yesterday. | Persistent log of tool calls (inputs, outputs, latency, client info) in the DB. | M | P2 |

## 2. Missing Requirements
| Title | Area | Why (Pain) | What | Effort | Priority |
|---|---|---|---|---|---|
| **Dashboard Auth** | Security | "Unauthenticated" management is a non-starter for any network-attached server. | Support OIDC (Google/GitHub) or simple Basic Auth for the UI and Management API. | M | P1 |
| **Sandbox Isolation** | Security | Subprocesses share the app container; one bad script can `rm -rf /opt/omniforge`. | Option to run scripts in gVisor (runsc) or WebAssembly (Wasmtime) instead of shell. | L | P1 |
| **Full MCP Compliance** | Protocol | Currently "Limited JSON-RPC"; missing Prompts and Resources (Files/DBs). | Implement the full MCP spec including `resources/list`, `prompts/get`, and Sampling. | M | P2 |
| **Secrets Management** | Security | Environment variables are leaked to subprocesses; no vault integration. | Integration with HashiCorp Vault or AWS Secrets Manager for tool credentials. | L | P2 |
| **Audit & Supply Chain**| Compliance | No record of who changed a tool; `pip` installs unverified binaries. | Signed audit logs for all CRUD; enforce `pip` hash verification for requirements. | M | P3 |
| **Backup/Restore** | Reliability | SQLite on a volume is prone to corruption/loss without snapshots. | Built-in CLI/UI command to export/import the entire workspace as a ZIP/JSON. | S | P2 |

## 3. Improvements to Existing Features
| Title | Area | Why (Pain) | What | Effort | Priority |
|---|---|---|---|---|---|
| **Async Runner** | Performance | `subprocess.run` is blocking; one heavy install can hang the entire FastAPI server. | Migrate to `asyncio.create_subprocess_exec` to handle concurrent tool executions. | M | P1 |
| **Schema Visual Editor**| UX | Hand-writing JSON Schema in the dashboard is error-prone for users. | Replace the read-only schema block with a visual "Field → Type" builder. | M | P2 |
| **Conflict Diffing** | Persistence | 412 error is a "dead end"; users don't know what changed in the other tab. | Show a "Side-by-Side Diff" when a conflict occurs so users can merge changes. | S | P2 |
| **Live Logs (SSE)** | DevX | Dashboard Run/Test only shows final result; no visibility into progress. | Stream `stdout/stderr` in real-time to the dashboard via the existing SSE/MCP path. | S | P2 |

## 4. Usability for First-Time Users
| Title | Area | Why (Pain) | What | Effort | Priority |
|---|---|---|---|---|---|
| **The "Tool Gallery"** | Onboarding | Empty library is intimidating; templates are "hidden" in a dialog. | A visual marketplace-style landing page with "Install" buttons for common tools. | S | P1 |
| **Interactive Tutorial**| Training | MCP is a new concept; users don't know the "Create -> Test -> Connect" flow. | A guided "First Tool" walk-through using tooltips and highlight-masks. | S | P2 |
| **Auto-Doc Gen** | Onboarding | Descriptions are often forgotten; clients see cryptic tool names. | Use an LLM (if configured) to generate the `description` and `inputSchema` from `code`. | S | P3 |

## 5. Ideas for Less-Advanced Users
| Title | Area | Why (Pain) | What | Effort | Priority |
|---|---|---|---|---|---|
| **Natural Language UI** | Creation | Users know *what* they want but don't know Python or Node. | A "Prompt to Tool" interface that generates the script based on a description. | M | P1 |
| **No-Code Webhooks** | Logic | Connecting a tool to an API often requires boilerplate `requests` code. | A specialized "HTTP Tool" type where users just provide URL, Method, and Auth. | M | P2 |

## 6. Ideas for Advanced Users
| Title | Area | Why (Pain) | What | Effort | Priority |
|---|---|---|---|---|---|
| **Multi-File Scripts** | Complexity | One single `code` string makes complex logic/utility sharing impossible. | Support a virtual file system per tool (multiple files, sub-directories). | L | P2 |
| **TypeScript Support** | DevX | Node users prefer TS for safety; currently limited to CJS. | Built-in `esbuild` or `tsx` support to transpile/run TS tools on the fly. | S | P2 |
| **Custom Runtimes** | Flexibility | Restricted to Python/Node; cannot use Go, Rust, or specialized binaries. | Allow tools to specify a Docker image or `devcontainer` for their environment. | L | P3 |

## 7. Roadmap Focus

### Top 5 Quick Wins (High Impact, Low Effort)
1. **Async Runner:** Fixes the biggest stability bottleneck for concurrent users.
2. **Dashboard Auth:** Moves the product from "toy" to "deployable".
3. **Tool Gallery:** Significantly lowers the barrier to entry for new users.
4. **Live Logs:** Essential for debugging dependency installs and long-running scripts.
5. **Backup/Restore:** Provides immediate peace of mind for self-hosted users.

### Top 3 Big Bets (High Risk, Strategic Value)
1. **The "Agentic Author":** OmniForge becomes self-authoring. An LLM uses the `omniforge_create_tool` to build its own missing capabilities in real-time.
2. **WASM-First Execution:** Move to WebAssembly for "Near-Native" speed with "Gold-Standard" isolation, removing the Docker container escape risk.
3. **OmniForge Cloud Sync:** A centralized registry to discover, share, and "star" tools across the community, turning the platform into the "GitHub of MCP".
