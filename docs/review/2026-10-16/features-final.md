# OmniForge: merged feature board

*Built 2026-10-16 from three independent reviews: Claude Fable with code access (84 items, primary), Claude Fable in LibreChat working from the docs (52 items + 11 decisions), and Gemini (22 items + 3 big bets). Machine-readable version: `features-final.json` (same IDs).*

## Summary

The three reviews were merged into **64 cards** with duplicates combined, pure bug reports removed and every source item traced to a card or to the exclusion list below. The reviews agree closely on the core: adopt the official MCP SDK transport, add dashboard login with scoped keys, isolate script execution, and give tools memory (versions, run history, export, backup). For beginners, they agree on a schema editor, realistic templates, per-client connection recipes and plain-language errors. They disagree mainly on *how* to isolate scripts, whether OmniForge should call an LLM itself, and how far to go with OAuth, Git and scheduling. Those disagreements are the cards in the **Decide** column.

**How the columns were assigned.** *Decide* holds every open question as a `decision` card. It also holds one P1 feature, the per-run sandbox, because it cannot start until the isolation target is chosen. *Next* holds P1 work that can start now. Some of these cards link a decision in `depends_on`. In those cases the decision only tunes defaults, or it confirms the route every review already recommends (SDK transport, single-admin login, encrypted-SQLite secrets, run history metadata). *Backlog* holds P2 and P3 work. Where the reviews disagreed on priority, the card carries a one-line `priority_note`.

**Suggested order inside Next** (from the reviews' own sequencing): first harden the core with FEAT-021, FEAT-031, FEAT-015, FEAT-032, FEAT-033, FEAT-034, FEAT-016. Then the SDK transport (FEAT-017). Then login and keys, first boot and recipes (FEAT-018, FEAT-019, FEAT-020). Then memory and safety nets (FEAT-022, FEAT-023, FEAT-024, FEAT-025, FEAT-026). Then authoring (FEAT-027, FEAT-028, FEAT-029, FEAT-030).

### Counts

| By column | n | By priority | n | By type | n | By audience | n |
|---|---|---|---|---|---|---|---|
| decide | 14 | P1 | 28 | decision | 13 | all | 27 |
| next | 20 | P2 | 27 | requirement | 16 | beginner | 11 |
| backlog | 30 | P3 | 9 | feature | 16 | advanced | 26 |
|  |  |  |  | improvement | 3 |  |  |
|  |  |  |  | usability | 8 |  |  |
|  |  |  |  | beginner | 5 |  |  |
|  |  |  |  | advanced | 3 |  |  |
| **total** | **64** | | | | | | |

## Decisions for David

Answer the P1 decisions first; the transport, admin-identity and client decisions change the shape of the P1 work.

| ID | Pri | Question | Unblocks / shapes | Note |
|---|---|---|---|---|
| FEAT-001 | P1 | Adopt the official mcp SDK's Streamable HTTP transport, or keep extending the handwritten JSON-RPC? | FEAT-017 | Both Fable reviews recommend the SDK, so this only needs a quick confirmation. The transport card stays in Next. |
| FEAT-002 | P1 | How far should script isolation go: in-container hardening only, a runner sidecar, or per-run sandboxing (bubblewrap/nsjail, gVisor, WASM)? | FEAT-006 | Gemini's WASM-first idea is a big bet. Fable and LibreChat favour namespaces or a sidecar. |
| FEAT-003 | P1 | Admin identity: single admin password and session, multiple local users from day one, or OIDC sign-in? | FEAT-018, FEAT-064 | Only decides what comes after the single-admin first step. |
| FEAT-004 | P1 | Secrets at rest: encrypted in SQLite under a master key from the environment, or fetched from an external store (Proton Pass, HashiCorp Vault) at run time? | FEAT-026 | All three reviews agree on the first step, so the secrets card stays in Next. |
| FEAT-005 | P1 | Which clients must OmniForge serve: LAN-only clients with per-client keys, or remote hosted clients such as Claude.ai connectors that need OAuth 2.1? | FEAT-060 | LibreChat says decisions D1-D3 change the shape of the P1 work. |
| FEAT-007 | P1 | Run history privacy: store arguments and output (how much, for how long), or metadata only? | FEAT-023 | This tunes the run-history card's defaults. The card can start with metadata. |
| FEAT-008 | P1 | Close PR #3 (the older workbench) now, or convert it to a reference branch? | - | A five-minute guard. LibreChat says do it now. |
| FEAT-009 | P2 | Which HTTPS route: Tailscale Serve, Caddy with an internal CA, or the existing Cloudflare Tunnel plus Access? | FEAT-035 | - |
| FEAT-010 | P2 | Build cron scheduling into OmniForge, or ship webhook triggers only and let n8n do the scheduling? | FEAT-052 | - |
| FEAT-011 | P2 | Should SQLite stay the source of truth with export/import, or should OmniForge move toward git-backed tool files? | FEAT-038 | - |
| FEAT-012 | P2 | Should the dashboard generate tools with its own configured LLM, or keep AI authoring in the user's connected assistant? | - | Gemini rated the in-dashboard generator P1. The other two reviews route AI authoring through the connected assistant. |
| FEAT-013 | P3 | Environments: draft/published revisions per tool, or separate dev and prod instances promoted via the CLI? | - | - |
| FEAT-014 | P3 | Is a shared or community tool registry in scope, or only private bundles and Git packs? | - | Fable F-11's pack-install half lives here. Its template half is on the gallery card. |

Waiting in Decide until its decision is answered: FEAT-006 Per-run sandbox for script execution.

## Next column (P1, startable now)

- **FEAT-015** Resource limits: per-tool overrides, concurrency cap, quotas and rate limits [M/high]
- **FEAT-016** Regression and MCP conformance test suite [M/high]
- **FEAT-017** Adopt the official MCP SDK Streamable HTTP transport [M/high] (confirm FEAT-001)
- **FEAT-018** Dashboard login + scoped API keys [L/high] (confirm FEAT-003)
- **FEAT-019** Secure-by-default first boot and safe new-tool defaults [M/high]
- **FEAT-020** Per-client connection recipes [S/high]
- **FEAT-021** Schema migration framework [S/high]
- **FEAT-022** Tool version history, rollback and trash [M/high]
- **FEAT-023** Run history and logs [M/high] (confirm FEAT-007)
- **FEAT-024** Export / import tool bundles [S/high]
- **FEAT-025** Backup and restore [S/high]
- **FEAT-026** Per-tool encrypted secrets [M/high] (confirm FEAT-004)
- **FEAT-027** Input-schema editor in the dashboard [M/high]
- **FEAT-028** Plain-language errors and failed-run explainer [M/high]
- **FEAT-029** Guided 'new tool' wizard [M/high]
- **FEAT-030** Realistic templates and a tool gallery [S/high]
- **FEAT-031** Per-run working directory [S/medium]
- **FEAT-032** Health and readiness endpoints [S/medium]
- **FEAT-033** Supported Node runtime (Node 22 LTS) [S/medium]
- **FEAT-034** CI gating, release pipeline and config clean-up [M/medium]

## Quick wins

S-effort cards with high or medium value that are not waiting on a decision.

| ID | Title | Pri | Value | Column | Why (short) |
|---|---|---|---|---|---|
| FEAT-020 | Per-client connection recipes | P1 | high | next | Connect shows one generic JSON-RPC template, which doesn't help anyone configuring a real client. |
| FEAT-021 | Schema migration framework | P1 | high | next | `_ensure_schema` only runs `CREATE TABLE IF NOT EXISTS` and there is no schema version, so every feature that adds a table or column (versions, runs, keys, secrets, audit) risks breaking older DBs. |
| FEAT-024 | Export / import tool bundles | P1 | high | next | Tools live only inside one SQLite file in a named Docker volume. |
| FEAT-025 | Backup and restore | P1 | high | next | All state is `omniforge.db` plus the `lib/` caches in Docker volumes. |
| FEAT-030 | Realistic templates and a tool gallery | P1 | high | next | The four examples are two greetings, a `requests` example that deliberately sends nothing, and a lodash sort of four numbers. |
| FEAT-031 | Per-run working directory | P1 | medium | next | `run_tool` writes `SCRATCH_ROOT/{tool.id}.py` and every run shares one `cwd`. |
| FEAT-032 | Health and readiness endpoints | P1 | medium | next | There is no `/healthz` and no Dockerfile `HEALTHCHECK`, so Unraid and compose cannot tell a wedged event loop from a healthy one. |
| FEAT-033 | Supported Node runtime (Node 22 LTS) | P1 | medium | next | The Dockerfile installs `nodejs npm` from Debian bookworm apt. |
| FEAT-035 | HTTPS and secure-context setup | P2 | high | backlog | PWA install and service workers need a secure context, so LAN users see no Install button and don't know why, and hosted MCP clients require HTTPS. |
| FEAT-040 | 'What is MCP?' plain-language primer | P2 | medium | backlog | Help says 'Think of a tool as a named script your AI can ask the server to run', then jumps straight to JSON-RPC methods. |
| FEAT-043 | Save & Test and Duplicate actions | P2 | medium | backlog | Testing needs a save first because Run is disabled while there are unsaved changes, so every edit-save-run loop costs two clicks and a status message. |
| FEAT-044 | Library tags, filters and richer rows | P2 | medium | backlog | The list is flat and sorted by `updated_at`, and search matches substrings of name and description. |
| FEAT-047 | Tool titles, annotations and 'how your AI sees this tool' | P2 | medium | backlog | MCP clients use `title` and annotations (readOnlyHint, destructiveHint, idempotentHint, openWorldHint) to decide when to ask the user for confirmation, but OmniForge sends only name, description and inputSchema. |
| FEAT-056 | Per-client tool visibility | P2 | medium | backlog | Every client holding the one Bearer key sees every enabled tool, so a client that only needs the shop tools sees the Sonarr ones too. |

## Big bets

L-effort cards, plus M-effort cards with high value. These change what OmniForge is.

| ID | Title | Effort | Value | Pri | Column | Depends on |
|---|---|---|---|---|---|---|
| FEAT-006 | Per-run sandbox for script execution | L | high | P1 | decide | FEAT-002, FEAT-031 |
| FEAT-015 | Resource limits: per-tool overrides, concurrency cap, quotas and rate limits | M | high | P1 | next | FEAT-018 |
| FEAT-016 | Regression and MCP conformance test suite | M | high | P1 | next | - |
| FEAT-017 | Adopt the official MCP SDK Streamable HTTP transport | M | high | P1 | next | FEAT-001 |
| FEAT-018 | Dashboard login + scoped API keys | L | high | P1 | next | FEAT-003 |
| FEAT-019 | Secure-by-default first boot and safe new-tool defaults | M | high | P1 | next | FEAT-018 |
| FEAT-022 | Tool version history, rollback and trash | M | high | P1 | next | FEAT-021 |
| FEAT-023 | Run history and logs | M | high | P1 | next | FEAT-007, FEAT-021 |
| FEAT-026 | Per-tool encrypted secrets | M | high | P1 | next | FEAT-004 |
| FEAT-027 | Input-schema editor in the dashboard | M | high | P1 | next | - |
| FEAT-028 | Plain-language errors and failed-run explainer | M | high | P1 | next | - |
| FEAT-029 | Guided 'new tool' wizard | M | high | P1 | next | FEAT-027 |
| FEAT-036 | Connection readiness checklist, self-test and last-seen clients | M | high | P2 | backlog | FEAT-023, FEAT-018, FEAT-020 |
| FEAT-037 | Test-input form generated from the schema | M | high | P2 | backlog | FEAT-027 |
| FEAT-038 | Git sync and CI for tools | L | high | P2 | backlog | FEAT-024, FEAT-022, FEAT-011 |
| FEAT-039 | Derive input and output schemas from code | M | high | P2 | backlog | FEAT-027 |
| FEAT-058 | No-code tool types (HTTP request, reference text, table lookup) | L | high | P3 | backlog | FEAT-026, FEAT-027 |
| FEAT-060 | OAuth 2.1 resource server for hosted MCP clients | L | medium | P3 | backlog | FEAT-018, FEAT-035, FEAT-017, FEAT-005 |
| FEAT-064 | Lightweight multi-user and attribution | L | low | P3 | backlog | FEAT-018, FEAT-022, FEAT-003 |

## Beginner highlights

Cards aimed at first-time users, ordered by board position.

- **FEAT-019** Secure-by-default first boot and safe new-tool defaults (P1, next): Leaving `OMNIFORGE_API_KEY` empty disables MCP auth entirely, the dashboard is open, and Overview tells users to rely on a trusted network.
- **FEAT-020** Per-client connection recipes (P1, next): Connect shows one generic JSON-RPC template, which doesn't help anyone configuring a real client.
- **FEAT-028** Plain-language errors and failed-run explainer (P1, next): Errors are accurate but technical ('Dependency installation failed; script was not run: <pip tail>', 'Arguments do not match inputSchema').
- **FEAT-029** Guided 'new tool' wizard (P1, next): In David's words, users have 'never seen anything like this'.
- **FEAT-030** Realistic templates and a tool gallery (P1, next): The four examples are two greetings, a `requests` example that deliberately sends nothing, and a lodash sort of four numbers.
- **FEAT-036** Connection readiness checklist, self-test and last-seen clients (P2, backlog): Connect says 'Connected clients: Not tracked' and lists limitations instead of checking them.
- **FEAT-037** Test-input form generated from the schema (P2, backlog): Test inputs are a raw JSON textarea that defaults to `{}`.
- **FEAT-040** 'What is MCP?' plain-language primer (P2, backlog): Help says 'Think of a tool as a named script your AI can ask the server to run', then jumps straight to JSON-RPC methods.
- **FEAT-041** Build tools with your AI assistant (P2, backlog): `omniforge_instructions` and `omniforge_create_tool` already let an LLM author tools, but the dashboard never tells beginners this exists or how to phrase the request.
- **FEAT-058** No-code tool types (HTTP request, reference text, table lookup) (P3, backlog): Many useful tools are just 'GET this URL and return the JSON' or 'answer from this text', yet connecting to an API still takes boilerplate `requests` code.

## Advanced highlights

Cards for David and other power users, ordered by board position.

- **FEAT-016** Regression and MCP conformance test suite (P1, next): The tests are strong on dashboard races, revision conflicts and dependency caching.
- **FEAT-032** Health and readiness endpoints (P1, next): There is no `/healthz` and no Dockerfile `HEALTHCHECK`, so Unraid and compose cannot tell a wedged event loop from a healthy one.
- **FEAT-034** CI gating, release pipeline and config clean-up (P1, next): `dockerhub.yml` pushes `:latest` on every push to `main` with no test step, and tests run only on PRs and non-main branches.
- **FEAT-038** Git sync and CI for tools (P2, backlog): Code review, blame, branching and off-box history all need files, not BLOBs.
- **FEAT-039** Derive input and output schemas from code (P2, backlog): Authors have to hand-write JSON Schema, which they can't do at all in the browser, even though the code already defines the inputs it reads.
- **FEAT-046** Package environments: background preparation and cache management (P2, backlog): Installs are synchronous and can take up to 120 s.
- **FEAT-048** Structured results, output schemas and saved test cases (P2, backlog): Every result is a single text block.
- **FEAT-049** MCP prompts and resources (P2, backlog): Only `tools/*` exists; `resources/list` and `prompts/list` return -32601.
- **FEAT-050** Audit trail (P2, backlog): Nothing records that an LLM created `foo` via `omniforge_create_tool` at 02:14, which key called what, when a secret was rotated, or that a tool was deleted.
- **FEAT-051** Supply-chain and install-path hardening (P2, backlog): Packages are installed from PyPI and npm by name, and unpinned names silently freeze at whatever resolved first.
- **FEAT-052** Scheduled runs and cached results (P2, backlog): A bonus-ball fetcher should naturally run every Wednesday and Saturday evening and be fresh at 20:01.
- **FEAT-053** Webhook triggers and n8n integration (P2, backlog): n8n, GitHub, Home Assistant and cron on another machine can only call a tool by speaking JSON-RPC and holding the global Bearer key.
- **FEAT-054** Structured logs, usage stats and /metrics (P2, backlog): Only uvicorn access logs exist, so tool failures, install failures and conflicts are returned to the caller and then vanish.
- **FEAT-055** omniforge CLI and documented API (P2, backlog): The management API is REST built for the browser, so scripting it means hand-rolling `curl` calls with `If-Match` headers.
- **FEAT-056** Per-client tool visibility (P2, backlog): Every client holding the one Bearer key sees every enabled tool, so a client that only needs the shop tools sees the Sonarr ones too.
- **FEAT-057** Split the single-file dashboard into modules (P2, backlog): `dashboard.html` is 574 lines (about 50 KB) with all the JS inline.
- **FEAT-059** Per-tool network egress policy (P3, backlog): Scripts have unrestricted network access, including to the NAS's other containers and the Unraid host.
- **FEAT-060** OAuth 2.1 resource server for hosted MCP clients (P3, backlog): Claude.ai custom connectors and other hosted MCP clients require OAuth (authorization-server discovery via RFC 9728/8414, dynamic client registration) and cannot send a static Bearer header.
- **FEAT-061** Additional runtimes: TypeScript, shell and more (P3, backlog): `_runtime` hard-codes python and node.
- **FEAT-062** Script helpers: run context, shared modules and multi-file tools (P3, backlog): A script can't tell which tool it is, which client called it, or what run id to use when correlating its own logs.
- **FEAT-063** Multi-worker and multi-instance story (P3, backlog): `Database._cache` is per process with a 5 s TTL, so `uvicorn --workers 2` would silently serve stale code for up to 5 s and double install-lock contention.

## Full board

| ID | Column | Pri | Type | Title | Area | Audience | Effort | Value | Depends on | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| FEAT-001 | decide | P1 | decision | Adopt the official mcp SDK's Streamable HTTP transport, or keep extending the handwritten JSON-RPC? | MCP | advanced | S | high | - | librechat:D1 |
| FEAT-002 | decide | P1 | decision | How far should script isolation go: in-container hardening only, a runner sidecar, or per-run sandboxing (bubblewrap/nsjail, gVisor, WASM)? | Security / runner | all | S | high | - | librechat:D2, gemini:WASM-First Execution |
| FEAT-003 | decide | P1 | decision | Admin identity: single admin password and session, multiple local users from day one, or OIDC sign-in? | Security | all | S | high | - | librechat:D9 |
| FEAT-004 | decide | P1 | decision | Secrets at rest: encrypted in SQLite under a master key from the environment, or fetched from an external store (Proton Pass, HashiCorp Vault) at run time? | Security | all | S | high | - | librechat:D7 |
| FEAT-005 | decide | P1 | decision | Which clients must OmniForge serve: LAN-only clients with per-client keys, or remote hosted clients such as Claude.ai connectors that need OAuth 2.1? | Security / MCP | all | S | high | - | librechat:D3 |
| FEAT-006 | decide | P1 | requirement | Per-run sandbox for script execution | Security / runner | all | L | high | FEAT-002, FEAT-031 | fable:R-05, librechat:R2, gemini:Sandbox Isolation |
| FEAT-007 | decide | P1 | decision | Run history privacy: store arguments and output (how much, for how long), or metadata only? | Observability / privacy | all | S | medium | - | librechat:D8 |
| FEAT-008 | decide | P1 | decision | Close PR #3 (the older workbench) now, or convert it to a reference branch? | Repo | advanced | S | medium | - | librechat:D11 |
| FEAT-009 | decide | P2 | decision | Which HTTPS route: Tailscale Serve, Caddy with an internal CA, or the existing Cloudflare Tunnel plus Access? | Deployment | all | S | medium | - | librechat:D6 |
| FEAT-010 | decide | P2 | decision | Build cron scheduling into OmniForge, or ship webhook triggers only and let n8n do the scheduling? | Automation | advanced | S | medium | - | librechat:D5 |
| FEAT-011 | decide | P2 | decision | Should SQLite stay the source of truth with export/import, or should OmniForge move toward git-backed tool files? | Storage | advanced | S | medium | - | librechat:D4 |
| FEAT-012 | decide | P2 | decision | Should the dashboard generate tools with its own configured LLM, or keep AI authoring in the user's connected assistant? | Onboarding / AI authoring | beginner | S | medium | - | gemini:Natural Language UI, gemini:Auto-Doc Gen, gemini:Agentic Author |
| FEAT-013 | decide | P3 | decision | Environments: draft/published revisions per tool, or separate dev and prod instances promoted via the CLI? | Ops / studio | advanced | S | low | - | librechat:D10, librechat:A3, fable:A-03 |
| FEAT-014 | decide | P3 | decision | Is a shared or community tool registry in scope, or only private bundles and Git packs? | Ecosystem | all | S | low | - | gemini:OmniForge Cloud Sync, fable:F-11 |
| FEAT-015 | next | P1 | requirement | Resource limits: per-tool overrides, concurrency cap, quotas and rate limits | Runner / API | all | M | high | FEAT-018 | fable:R-17, fable:I-07, fable:F-15, fable:R-16, fable:R-06, fable:R-08, librechat:R7, librechat:I3 |
| FEAT-016 | next | P1 | improvement | Regression and MCP conformance test suite | Quality | advanced | M | high | - | fable:I-08 |
| FEAT-017 | next | P1 | requirement | Adopt the official MCP SDK Streamable HTTP transport | MCP | all | M | high | FEAT-001 | fable:I-01, fable:R-09, fable:I-05, fable:I-11, librechat:R3, gemini:Full MCP Compliance |
| FEAT-018 | next | P1 | requirement | Dashboard login + scoped API keys | Security | all | L | high | FEAT-003 | fable:R-01, fable:R-02, librechat:R1, gemini:Dashboard Auth |
| FEAT-019 | next | P1 | requirement | Secure-by-default first boot and safe new-tool defaults | Security / onboarding | beginner | M | high | FEAT-018 | fable:B-03, librechat:U5 |
| FEAT-020 | next | P1 | usability | Per-client connection recipes | Connect | beginner | S | high | - | fable:U-04, librechat:I4, librechat:L3 |
| FEAT-021 | next | P1 | requirement | Schema migration framework | Storage | all | S | high | - | fable:R-14, fable:I-04, librechat:F14 |
| FEAT-022 | next | P1 | feature | Tool version history, rollback and trash | Storage / studio | all | M | high | FEAT-021 | fable:F-01, librechat:F1, librechat:F13, gemini:Conflict Diffing |
| FEAT-023 | next | P1 | feature | Run history and logs | Observability | all | M | high | FEAT-007, FEAT-021 | fable:F-06, librechat:F3, gemini:Execution History |
| FEAT-024 | next | P1 | feature | Export / import tool bundles | Storage | all | S | high | - | fable:F-03, librechat:F6 |
| FEAT-025 | next | P1 | requirement | Backup and restore | Ops | all | S | high | FEAT-018 | fable:R-12, librechat:R5, gemini:Backup/Restore |
| FEAT-026 | next | P1 | feature | Per-tool encrypted secrets | Security / runner | all | M | high | FEAT-004 | fable:F-05, fable:I-10, librechat:F2, gemini:Per-Tool Env Vars, gemini:Secrets Management |
| FEAT-027 | next | P1 | feature | Input-schema editor in the dashboard | Studio | all | M | high | - | fable:F-02, librechat:I1, librechat:U3, gemini:Schema Visual Editor |
| FEAT-028 | next | P1 | usability | Plain-language errors and failed-run explainer | Studio / help | beginner | M | high | - | fable:B-02, fable:U-01, librechat:I10, librechat:L4 |
| FEAT-029 | next | P1 | beginner | Guided 'new tool' wizard | Onboarding | beginner | M | high | FEAT-027 | fable:B-01, gemini:Interactive Tutorial |
| FEAT-030 | next | P1 | beginner | Realistic templates and a tool gallery | Onboarding | beginner | S | high | FEAT-027, FEAT-026 | fable:B-04, fable:F-11, librechat:F9, gemini:Tool Gallery |
| FEAT-031 | next | P1 | improvement | Per-run working directory | Runner | all | S | medium | - | fable:I-03, librechat:R2 |
| FEAT-032 | next | P1 | requirement | Health and readiness endpoints | Ops | advanced | S | medium | - | fable:R-18, librechat:F8 |
| FEAT-033 | next | P1 | requirement | Supported Node runtime (Node 22 LTS) | Runtime | all | S | medium | - | fable:R-20 |
| FEAT-034 | next | P1 | requirement | CI gating, release pipeline and config clean-up | Deployment / maintainability | advanced | M | medium | - | fable:R-19, fable:I-02, fable:R-14, librechat:I9 |
| FEAT-035 | backlog | P2 | requirement | HTTPS and secure-context setup | Deployment | all | S | high | FEAT-018, FEAT-009 | fable:R-13, librechat:R8, librechat:U6 |
| FEAT-036 | backlog | P2 | beginner | Connection readiness checklist, self-test and last-seen clients | Connect / overview | beginner | M | high | FEAT-023, FEAT-018, FEAT-020 | fable:B-05, fable:U-05, fable:B-07, librechat:I5, librechat:U1 |
| FEAT-037 | backlog | P2 | usability | Test-input form generated from the schema | Studio | beginner | M | high | FEAT-027 | fable:U-02, librechat:L2 |
| FEAT-038 | backlog | P2 | feature | Git sync and CI for tools | Storage / DevEx | advanced | L | high | FEAT-024, FEAT-022, FEAT-011 | fable:F-04, fable:A-02, librechat:F7, librechat:A2, gemini:Git Synchronization |
| FEAT-039 | backlog | P2 | advanced | Derive input and output schemas from code | Studio / DevEx | advanced | M | high | FEAT-027 | fable:A-04 |
| FEAT-040 | backlog | P2 | usability | 'What is MCP?' plain-language primer | Help / onboarding | beginner | S | medium | - | fable:U-03, librechat:U2 |
| FEAT-041 | backlog | P2 | beginner | Build tools with your AI assistant | Onboarding / MCP authoring | beginner | M | medium | FEAT-023, FEAT-022, FEAT-018 | fable:B-06, librechat:U4, librechat:I7 |
| FEAT-042 | backlog | P2 | usability | Real code editor (CodeMirror 6) | Studio | all | M | medium | - | fable:U-06 |
| FEAT-043 | backlog | P2 | usability | Save & Test and Duplicate actions | Studio | all | S | medium | - | fable:U-09, fable:U-10, librechat:I8 |
| FEAT-044 | backlog | P2 | usability | Library tags, filters and richer rows | Tools | all | S | medium | FEAT-023 | fable:F-17, fable:U-07, librechat:F12, gemini:Tool Tagging/Groups |
| FEAT-045 | backlog | P2 | usability | Live progress, streaming output and cancel | Studio / MCP | all | M | medium | FEAT-017, FEAT-015 | fable:U-08, fable:U-12, fable:A-10, gemini:Live Logs (SSE), librechat:A7 |
| FEAT-046 | backlog | P2 | feature | Package environments: background preparation and cache management | Installer | advanced | M | medium | FEAT-022 | librechat:F10, librechat:F11, fable:F-19, fable:I-12 |
| FEAT-047 | backlog | P2 | feature | Tool titles, annotations and 'how your AI sees this tool' | MCP / studio | all | S | medium | - | fable:F-16, fable:U-11, librechat:I11 |
| FEAT-048 | backlog | P2 | feature | Structured results, output schemas and saved test cases | MCP / studio | advanced | M | medium | FEAT-017, FEAT-027 | fable:R-10, fable:F-09, librechat:I2, librechat:I6 |
| FEAT-049 | backlog | P2 | feature | MCP prompts and resources | MCP | advanced | M | medium | FEAT-017 | fable:F-10, fable:A-05, librechat:F5, gemini:Full MCP Compliance |
| FEAT-050 | backlog | P2 | requirement | Audit trail | Security | advanced | M | medium | FEAT-018, FEAT-022, FEAT-023 | fable:R-11, librechat:R4, gemini:Audit & Supply Chain |
| FEAT-051 | backlog | P2 | requirement | Supply-chain and install-path hardening | Security / installer | advanced | M | medium | FEAT-046 | fable:R-15, fable:R-22, librechat:R6, gemini:Audit & Supply Chain |
| FEAT-052 | backlog | P2 | feature | Scheduled runs and cached results | Automation | advanced | M | medium | FEAT-023, FEAT-010 | fable:F-07, librechat:F4 |
| FEAT-053 | backlog | P2 | feature | Webhook triggers and n8n integration | Automation / integration | advanced | M | medium | FEAT-018, FEAT-023, FEAT-017 | fable:F-08, fable:A-08, librechat:F4, librechat:A4 |
| FEAT-054 | backlog | P2 | feature | Structured logs, usage stats and /metrics | Observability | advanced | M | medium | FEAT-023 | fable:I-09, fable:F-14, fable:A-06, librechat:F8 |
| FEAT-055 | backlog | P2 | advanced | omniforge CLI and documented API | DevEx | advanced | M | medium | FEAT-018, FEAT-024 | fable:A-01, librechat:A1 |
| FEAT-056 | backlog | P2 | feature | Per-client tool visibility | MCP / security | advanced | S | medium | FEAT-018, FEAT-044 | fable:F-20, librechat:F12 |
| FEAT-057 | backlog | P2 | improvement | Split the single-file dashboard into modules | Frontend maintainability | advanced | M | medium | - | fable:I-06 |
| FEAT-058 | backlog | P3 | beginner | No-code tool types (HTTP request, reference text, table lookup) | Studio | beginner | L | high | FEAT-026, FEAT-027 | librechat:L1, gemini:No-Code Webhooks |
| FEAT-059 | backlog | P3 | requirement | Per-tool network egress policy | Security / runner | advanced | M | medium | FEAT-006 | fable:A-11, librechat:R9 |
| FEAT-060 | backlog | P3 | requirement | OAuth 2.1 resource server for hosted MCP clients | Security / MCP | advanced | L | medium | FEAT-018, FEAT-035, FEAT-017, FEAT-005 | fable:R-03, librechat:R1 |
| FEAT-061 | backlog | P3 | feature | Additional runtimes: TypeScript, shell and more | Runner | advanced | M | low | FEAT-033 | fable:F-12, librechat:A6, gemini:TypeScript Support, gemini:Custom Runtimes |
| FEAT-062 | backlog | P3 | advanced | Script helpers: run context, shared modules and multi-file tools | Runner | advanced | M | low | FEAT-031, FEAT-023, FEAT-026 | fable:A-09, fable:F-18, librechat:A5, gemini:Multi-File Scripts |
| FEAT-063 | backlog | P3 | requirement | Multi-worker and multi-instance story | Server / ops | advanced | M | low | - | fable:R-21, fable:A-07, librechat:I12 |
| FEAT-064 | backlog | P3 | feature | Lightweight multi-user and attribution | Collaboration | all | L | low | FEAT-018, FEAT-022, FEAT-003 | fable:F-13 |

## Card details

### Column: decide

#### FEAT-001 Adopt the official mcp SDK's Streamable HTTP transport, or keep extending the handwritten JSON-RPC?

*decision | MCP | audience advanced | effort S | value high | P1*

- **Why:** The handwritten `_handle_rpc` covers four methods and keeps diverging from the spec (verified: notifications get error replies, batches return 422, `initialize` echoes any version, no sessions or Origin check), while the official `mcp` package already sits unused in `requirements.txt`.
- **What:** Confirm the SDK route, which both Fable reviews recommend. If the answer is 'keep handwritten', replace the transport card with a list of targeted protocol fixes.
- **Priority note:** Both Fable reviews recommend the SDK, so this only needs a quick confirmation. The transport card stays in Next.
- **Sources:** librechat:D1

#### FEAT-002 How far should script isolation go: in-container hardening only, a runner sidecar, or per-run sandboxing (bubblewrap/nsjail, gVisor, WASM)?

*decision | Security / runner | audience all | effort S | value high | P1*

- **Why:** Scripts run as the app user with the app's filesystem, network and database. The reviews propose different first steps: bubblewrap inside the image (Fable), a credential-free runner sidecar followed by namespaces (LibreChat), and gVisor or WebAssembly (Gemini). Per-run namespaces probably need a relaxed seccomp/AppArmor profile on Unraid.
- **What:** Choose the target tier and the first step. Every option except per-tool container images keeps the no-Docker-socket stance. Fable rejected Firecracker and container-per-run as too heavy for one container.
- **Priority note:** Gemini's WASM-first idea is a big bet. Fable and LibreChat favour namespaces or a sidecar.
- **Sources:** librechat:D2, gemini:WASM-First Execution

#### FEAT-003 Admin identity: single admin password and session, multiple local users from day one, or OIDC sign-in?

*decision | Security | audience all | effort S | value high | P1*

- **Why:** All three reviews make dashboard login P1, but they disagree on identity: a first-boot admin password with a signed session (Fable, LibreChat), OIDC via Google/GitHub or Basic Auth (Gemini), and lightweight multi-user roles as a later P3 (Fable).
- **What:** Choose the identity model for the first release. Either way, the login card starts with a single admin.
- **Priority note:** Only decides what comes after the single-admin first step.
- **Sources:** librechat:D9

#### FEAT-004 Secrets at rest: encrypted in SQLite under a master key from the environment, or fetched from an external store (Proton Pass, HashiCorp Vault) at run time?

*decision | Security | audience all | effort S | value high | P1*

- **Why:** Real tools need API keys (lottery API, Pushover, Xero). Fable and LibreChat design an encrypted SQLite table. Gemini wants encrypted per-tool values first and Vault or AWS Secrets Manager integration later. The choice affects key management and backups.
- **What:** Confirm encrypted SQLite as the first step, and decide whether an external-store backend should follow.
- **Priority note:** All three reviews agree on the first step, so the secrets card stays in Next.
- **Sources:** librechat:D7

#### FEAT-005 Which clients must OmniForge serve: LAN-only clients with per-client keys, or remote hosted clients such as Claude.ai connectors that need OAuth 2.1?

*decision | Security / MCP | audience all | effort S | value high | P1*

- **Why:** Claude.ai custom connectors and other hosted MCP clients cannot send a static Bearer header. They need OAuth discovery (RFC 9728/8414) and an external authorisation server such as Authentik or Cloudflare Access. LAN clients such as LibreChat and Claude Code work with named keys.
- **What:** Decide whether remote hosted clients are a goal. If they are, the OAuth card moves up to P2 and HTTPS becomes mandatory. If not, per-client keys are enough.
- **Priority note:** LibreChat says decisions D1-D3 change the shape of the P1 work.
- **Sources:** librechat:D3

#### FEAT-006 Per-run sandbox for script execution

*requirement | Security / runner | audience all | effort L | value high | P1*

- **Why:** Scripts run as the app user with the app's filesystem, network and DB. One careless `shutil.rmtree` or one malicious dependency owns the instance, and a script can read the DB, the lib root and every other tool's cache. The original brief asked for per-run isolation, and the no-Docker-socket stance rules out a container per run.
- **What:** Tiered, with no Docker socket at any tier. Tier 1: bubblewrap in the image (`--unshare-all`, optional `--share-net`, read-only runtime and deps, tmpfs `/tmp`, per-run work dir, `--die-with-parent`, seccomp), and scripts run as a second unprivileged UID that cannot read the DB or secrets. Tier 2: nsjail, or a credential-free runner sidecar (no DB, no secrets, no API key, read-only lib mount), for cgroup CPU/memory/pids limits. Tier 3: gVisor `runsc` as the container runtime. A per-tool 'network on/off' flag.
- **Depends on:** FEAT-002 (How far should script isolation go: in-container hardening only, a runner sidecar, or per-run sandboxing (bubblewrap/nsjail, gVisor, WASM)?), FEAT-031 (Per-run working directory)
- **Related bugs:** The pure bug fixes it builds on are tracked separately: API key leaking via the inherited env, timeout killing only the direct child, uncapped output.
- **Priority note:** P1 in all three reviews. It waits on the isolation decision because each review proposes a different first tier.
- **Sources:** fable:R-05, librechat:R2, gemini:Sandbox Isolation

#### FEAT-007 Run history privacy: store arguments and output (how much, for how long), or metadata only?

*decision | Observability / privacy | audience all | effort S | value medium | P1*

- **Why:** Run history is the main way to debug a failure a client reports. But arguments and stdout can hold personal or secret data, and they would sit in the same SQLite file as everything else.
- **What:** Set the default: metadata only, hashed arguments, or bounded arguments and output kept for a set retention period.
- **Priority note:** This tunes the run-history card's defaults. The card can start with metadata.
- **Sources:** librechat:D8

#### FEAT-008 Close PR #3 (the older workbench) now, or convert it to a reference branch?

*decision | Repo | audience advanced | effort S | value medium | P1*

- **Why:** An open PR from the earlier design could be merged over the redesign by accident.
- **What:** Close it, or turn it into a clearly named reference branch.
- **Priority note:** A five-minute guard. LibreChat says do it now.
- **Sources:** librechat:D11

#### FEAT-009 Which HTTPS route: Tailscale Serve, Caddy with an internal CA, or the existing Cloudflare Tunnel plus Access?

*decision | Deployment | audience all | effort S | value medium | P2*

- **Why:** Plain HTTP on the LAN is not a secure context, so the PWA cannot install, and hosted MCP clients require HTTPS. The route decides which compose profile and docs ship first.
- **What:** Choose one route to document and ship first. The others can follow as notes.
- **Sources:** librechat:D6

#### FEAT-010 Build cron scheduling into OmniForge, or ship webhook triggers only and let n8n do the scheduling?

*decision | Automation | audience advanced | effort S | value medium | P2*

- **Why:** A results fetcher has to be fresh at a fixed time, such as just after a Wednesday or Saturday draw, but today only an LLM or a person can trigger a tool. David already runs n8n, which can schedule jobs and call a webhook.
- **What:** Choose between an in-process scheduler (per-tool cron, a missed-run policy, results in run history) and webhooks only, plus an n8n template.
- **Sources:** librechat:D5

#### FEAT-011 Should SQLite stay the source of truth with export/import, or should OmniForge move toward git-backed tool files?

*decision | Storage | audience advanced | effort S | value medium | P2*

- **Why:** Tools exist only as rows in one SQLite file in a Docker volume. Code review, blame, branching and off-box history all need files. Git sync is L effort and shapes the bundle format, the CLI and CI.
- **What:** Choose between keeping SQLite canonical (with Git only as an export target) and tools-as-files (with the DB as a runtime index).
- **Sources:** librechat:D4

#### FEAT-012 Should the dashboard generate tools with its own configured LLM, or keep AI authoring in the user's connected assistant?

*decision | Onboarding / AI authoring | audience beginner | effort S | value medium | P2*

- **Why:** Users know what they want but not Python or Node. Gemini proposes an in-dashboard 'Prompt to Tool' generator and LLM-generated descriptions and schemas (P1), plus an 'Agentic Author' big bet. Fable and LibreChat instead expose the existing `omniforge_instructions`/`omniforge_create_tool` built-ins through the user's own assistant, which needs no LLM credentials inside OmniForge.
- **What:** Decide whether OmniForge holds an LLM key and calls a model itself. If yes, add a 'Prompt to Tool' panel and 'generate description and schema from code'. If no, the 'Build tools with your AI assistant' card covers this.
- **Priority note:** Gemini rated the in-dashboard generator P1. The other two reviews route AI authoring through the connected assistant.
- **Sources:** gemini:Natural Language UI, gemini:Auto-Doc Gen, gemini:Agentic Author

#### FEAT-013 Environments: draft/published revisions per tool, or separate dev and prod instances promoted via the CLI?

*decision | Ops / studio | audience advanced | effort S | value low | P3*

- **Why:** Most of the 'multiple environments' pain is 'don't break the tool my assistant is using while I edit it'. David tests on a scratch instance and runs production at 192.168.0.180, and there is no way to move an exact revision between them.
- **What:** Option A: each tool has a published revision served over MCP plus an optional draft. Test the draft, then Publish. Option B: bundles carry revision hashes, and `omniforge promote <name> --to prod` imports a pinned revision. Each instance shows an environment label and colour. Both options build on version history.
- **Sources:** librechat:D10, librechat:A3, fable:A-03

#### FEAT-014 Is a shared or community tool registry in scope, or only private bundles and Git packs?

*decision | Ecosystem | audience all | effort S | value low | P3*

- **Why:** Gemini's 'OmniForge Cloud Sync' big bet imagines a central registry for discovering, sharing and starring tools (the 'GitHub of MCP'). Fable proposes installing packs from a Git URL or bundle with a clear 'community, unreviewed' label.
- **What:** Choose between no sharing beyond export/import, installable packs from Git URLs or bundles, and a hosted registry. Packs depend on export/import and on the isolation decision.
- **Priority note:** Fable F-11's pack-install half lives here. Its template half is on the gallery card.
- **Sources:** gemini:OmniForge Cloud Sync, fable:F-11

### Column: next

#### FEAT-015 Resource limits: per-tool overrides, concurrency cap, quotas and rate limits

*requirement | Runner / API | audience all | effort M | value high | P1*

- **Why:** The timeout is global (`OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS` plus an undocumented 15 s) and the memory setting is 'declared only', so a scraper that needs 90 s shares settings with a 50 ms formatter. A looping LLM can call a tool hundreds of times, and nothing caps concurrency, calls per minute or daily runtime. `slowapi` is in `requirements.txt` but never imported.
- **What:** Per-tool overrides for timeout, memory, CPU seconds, output cap and network access, bounded by admin maximums. They sit in the studio's advanced section and are enforced with rlimits (`RLIMIT_AS/NPROC/FSIZE/CPU`). Enforce exactly the configured timeout, keep a separate install timeout, and report both durations plus `timed_out` as structured fields. A global run queue or semaphore that returns a clear 'busy' result. Per-key calls per minute and per-tool daily caps. Token-bucket limits on `tools/call`, `/run` and login, answering `429` with `Retry-After`.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys)
- **Related bugs:** Companion to the separate fixes for blocking subprocess calls in async handlers, timeouts that kill only the direct child, and the '+15 s' timeout.
- **Priority note:** LibreChat makes all of it P1. Fable makes per-tool limits P1 and quotas/rate limits P2. Fable R-06 and R-08 contribute only their non-bug halves (rlimits, concurrency cap).
- **Sources:** fable:R-17, fable:I-07, fable:F-15, fable:R-16, fable:R-06, fable:R-08, librechat:R7, librechat:I3

#### FEAT-016 Regression and MCP conformance test suite

*improvement | Quality | audience advanced | effort M | value high | P1*

- **Why:** The tests are strong on dashboard races, revision conflicts and dependency caching. Nothing covers secrets leaking into scripts (they do), process-tree kill, output caps, event-loop blocking under concurrent requests, MCP conformance with a real client, or backup/restore.
- **What:** An MCP conformance suite using the official Python client over Streamable HTTP. A secret-leak regression test, a 'spawn a child, then time out' test and an output-cap test. An asyncio concurrency test (list tools while a 3 s tool runs) and a backup/restore test. Make Playwright runs mandatory in CI on `main`.
- **Related bugs:** Locks in the fixes for the verified runner bugs (env leak, orphaned children, uncapped output, blocking handlers).
- **Sources:** fable:I-08

#### FEAT-017 Adopt the official MCP SDK Streamable HTTP transport

*requirement | MCP | audience all | effort M | value high | P1*

- **Why:** The transport is hand-rolled and non-conformant, while the official `mcp` SDK is already installed and unused. Verified: `notifications/initialized` gets an error reply instead of 202, batches return a FastAPI 422, `initialize` echoes any `protocolVersion`, and there is no `Mcp-Session-Id` or Origin check. Also verified: `GET /mcp` returns a made-up event, `tools/list` ignores `cursor`, and `listChanged: false` means clients never learn about new tools.
- **What:** Mount the SDK's Streamable HTTP ASGI app at `/mcp`, register tools from the DB on each list/call so hot reload still works, and keep the built-ins as SDK tools. Adds sessions, SSE for server-to-client messages, protocol negotiation (2024-11-05/2025-03-26/2025-06-18) and Origin validation. Also adds cursor pagination, `notifications/tools/list_changed` on save/toggle/delete, spec-shaped JSON-RPC errors and `WWW-Authenticate` on 401. Conformance tests with MCP Inspector, Claude Desktop/Code and LibreChat. This unlocks prompts, resources, structured results, progress and n8n compatibility.
- **Depends on:** FEAT-001 (Adopt the official mcp SDK's Streamable HTTP transport, or keep extending the handwritten JSON-RPC?)
- **Related bugs:** Fixes the verified transport bug class: error replies to notifications, batch 422s, protocol-version echo, no Origin/Host check (DNS rebinding), and the fake GET /mcp SSE event.
- **Priority note:** Effort is M (Fable) vs L (LibreChat, which also bundled structured output and annotations; those are split out here). It stays in Next because every review recommends the SDK.
- **Sources:** fable:I-01, fable:R-09, fable:I-05, fable:I-11, librechat:R3, gemini:Full MCP Compliance

#### FEAT-018 Dashboard login + scoped API keys

*requirement | Security | audience all | effort L | value high | P1*

- **Why:** `/`, `/api/tools*`, `/api/config`, `/api/tools/{name}/run` and `GET /mcp` have no auth, so anyone on the LAN can read every script (embedded credentials included), and edit, delete or run code in the container. MCP uses one shared `OMNIFORGE_API_KEY`. It can't be rotated without recreating the container or revoked per client, and it gives LibreChat the same rights as a throwaway test client, including `omniforge_create_tool`.
- **What:** Tier 1: an admin password set on first boot or via env, and a signed session cookie (SameSite=Strict) with a CSRF token and a rate-limited login. That session gates the dashboard, `/api/*` and `GET /mcp`. Keep an env escape hatch for trusted-LAN dev. Tier 2: a hashed `api_keys` table with create/rotate/revoke in Connect, each key shown once. Scopes `tools:list`, `tools:call`, `tools:author` and `admin`, with the key id recorded on runs and audit rows. The env key stays as a bootstrap option.
- **Depends on:** FEAT-003 (Admin identity: single admin password and session, multiple local users from day one, or OIDC sign-in?)
- **Related bugs:** Fixes the unauthenticated management API and dashboard bug class.
- **Priority note:** P1 in all three reviews. It starts with a single admin; the admin-identity decision only sets what follows (multi-user or OIDC).
- **Sources:** fable:R-01, fable:R-02, librechat:R1, gemini:Dashboard Auth

#### FEAT-019 Secure-by-default first boot and safe new-tool defaults

*requirement | Security / onboarding | audience beginner | effort M | value high | P1*

- **Why:** Leaving `OMNIFORGE_API_KEY` empty disables MCP auth entirely, the dashboard is open, and Overview tells users to rely on a trusted network. Newcomers will deploy with the defaults and won't know about timeouts, packages or destructive actions.
- **What:** On first boot with no admin configured, a setup screen sets the admin password and generates the first MCP key (shown once). Auth is on by default, timeout and output caps are on, and per-tool network is off once the sandbox exists. New tools default to `readOnlyHint: true` and a short timeout, each changeable with a one-line toggle.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys)
- **Priority note:** Fable P1. LibreChat made the tool defaults P3.
- **Sources:** fable:B-03, librechat:U5

#### FEAT-020 Per-client connection recipes

*usability | Connect | audience beginner | effort S | value high | P1*

- **Why:** Connect shows one generic JSON-RPC template, which doesn't help anyone configuring a real client. LibreChat needs a `librechat.yaml` `mcpServers` block with `type: streamable-http` and headers, and Claude Code needs `claude mcp add --transport http ... --header`. Claude Desktop needs `mcp-remote`, and n8n needs MCP Client node settings. Hand-editing config files is where people give up.
- **What:** A client picker (LibreChat, Claude Code, Claude Desktop, Claude.ai connector, Cursor/Windsurf, n8n, MCP Inspector, curl). It emits copy-ready snippets with the real origin and a `<YOUR_API_KEY>` placeholder (or the key itself, shown once), plus caveats such as HTTPS/OAuth requirements and header support. Where a client supports it, offer a downloadable `claude_desktop_config.json` fragment or a deep link.
- **Priority note:** Fable P1. LibreChat P2, with the one-click download at P3.
- **Sources:** fable:U-04, librechat:I4, librechat:L3

#### FEAT-021 Schema migration framework

*requirement | Storage | audience all | effort S | value high | P1*

- **Why:** `_ensure_schema` only runs `CREATE TABLE IF NOT EXISTS` and there is no schema version, so every feature that adds a table or column (versions, runs, keys, secrets, audit) risks breaking older DBs. `tools.name` has only a non-unique index and legacy duplicates are tolerated. The default `sqlite3.connect` settings (no WAL, 5 s busy timeout) can throw 'database is locked'.
- **What:** A `schema_version` table with numbered, idempotent migrations that run at startup under a lock, each preceded by a `VACUUM INTO` backup. First migration: rename legacy duplicates to `name__dupN`, add `UNIQUE(name)`, enable WAL and set `busy_timeout`, keeping the transactional guard as a second safety net.
- **Priority note:** Fable P2, LibreChat P1 ('do first; everything else depends on it'). P1 because versions, runs, keys and secrets all add tables.
- **Sources:** fable:R-14, fable:I-04, librechat:F14

#### FEAT-022 Tool version history, rollback and trash

*feature | Storage / studio | audience all | effort M | value high | P1*

- **Why:** Every save overwrites the single `tools` row, so a bad edit from a second tab, an LLM via `omniforge_create_tool` or a mis-paste can't be undone. The content-hash `revision` only detects conflicts. Delete is confirmed but final, and a 412 conflict is a dead end because users can't see what changed in the other tab.
- **What:** An append-only `tool_versions` table written on every upsert (revision, code, schema, requirements, description, author/client, timestamp). A studio History panel with a diff against the current version and one-click Restore, which creates a new version and never rewrites history. A side-by-side diff when a 412 conflict occurs. Deleted tools go to a 30-day trash and can be restored from history.
- **Depends on:** FEAT-021 (Schema migration framework)
- **Priority note:** Trash (LibreChat P3) and the conflict diff (Gemini P2) are folded in because they come cheaply from the same table.
- **Sources:** fable:F-01, librechat:F1, librechat:F13, gemini:Conflict Diffing

#### FEAT-023 Run history and logs

*feature | Observability | audience all | effort M | value high | P1*

- **Why:** Run results exist only in the browser tab and in MCP responses, and stderr is lost. When LibreChat reports that a tool failed yesterday, the server has nothing to look at. Nobody can answer 'did my client actually call it, and what happened?'
- **What:** A `runs` table: tool, revision, origin (dashboard, MCP, key id, client name), argument hash (arguments optional), status, exit code, timed_out, duration, bounded stdout/stderr and timestamps. A Runs page and a per-tool recent-runs list in the studio, re-run with the same inputs, and retention settings. Feeds usage stats, last-seen clients, onboarding ticks and the audit trail.
- **Depends on:** FEAT-007 (Run history privacy: store arguments and output (how much, for how long), or metadata only?), FEAT-021 (Schema migration framework)
- **Priority note:** Fable and LibreChat P1, Gemini P2. P1 because many cards build on it.
- **Sources:** fable:F-06, librechat:F3, gemini:Execution History

#### FEAT-024 Export / import tool bundles

*feature | Storage | audience all | effort S | value high | P1*

- **Why:** Tools live only inside one SQLite file in a named Docker volume. There is no way to move a tool to another instance, share it, or keep a copy outside the container.
- **What:** `GET /api/tools/{name}/export` and `GET /api/export` emit a bundle (metadata, code, schema, requirements and versions, e.g. `tool.yaml` plus the source file). `POST /api/import` takes a rename/skip/overwrite strategy and a dry-run, and reuses `ToolIn` validation. Git sync, the CLI and promotion use the same format.
- **Priority note:** Fable P1, LibreChat P2. P1 because it is cheap and Git sync, the CLI and packs need it.
- **Sources:** fable:F-03, librechat:F6

#### FEAT-025 Backup and restore

*requirement | Ops | audience all | effort S | value high | P1*

- **Why:** All state is `omniforge.db` plus the `lib/` caches in Docker volumes. There is no documented backup, no consistent snapshot (a file copy of a live SQLite DB can be torn) and no restore path. The caches can be rebuilt; the DB cannot.
- **What:** `GET /api/admin/backup` using SQLite's online backup or `VACUUM INTO`. Scheduled backups to a mounted path with retention. 'Download backup' and 'Restore from backup' (admin only, with a dry-run diff), WAL mode, and a README runbook that includes the Unraid appdata-backup path.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys)
- **Priority note:** Fable and LibreChat P1, Gemini P2.
- **Sources:** fable:R-12, librechat:R5, gemini:Backup/Restore

#### FEAT-026 Per-tool encrypted secrets

*feature | Security / runner | audience all | effort M | value high | P1*

- **Why:** Scripts need API keys (lottery API, Pushover, Xero). Today they can only be hard-coded in `code`, stored in plaintext and visible to every dashboard visitor, or set as container env vars, which every script inherits. No real-world tool can be made safe this way.
- **What:** A `secrets` table encrypted with a master key from env or a keyfile (`OMNIFORGE_SECRET_KEY`). Secrets are set, rotated and deleted in the studio and are write-only. Each is injected as an env var only into its own tool's subprocess, after the environment is scrubbed. Values are redacted from stdout/stderr, logs and run history, extending what `_safe_stderr` already does for installer output. External stores (HashiCorp Vault, AWS Secrets Manager) can come later as a backend.
- **Depends on:** FEAT-004 (Secrets at rest: encrypted in SQLite under a master key from the environment, or fetched from an external store (Proton Pass, HashiCorp Vault) at run time?)
- **Related bugs:** Needs the env-leak fix first (scripts currently inherit `OMNIFORGE_API_KEY` via `os.environ.copy()`); without it the vault is theatre.
- **Priority note:** P1 in all three reviews (Gemini via per-tool env vars). Gemini put external vault integration at P2.
- **Sources:** fable:F-05, fable:I-10, librechat:F2, gemini:Per-Tool Env Vars, gemini:Secrets Management

#### FEAT-027 Input-schema editor in the dashboard

*feature | Studio | audience all | effort M | value high | P1*

- **Why:** The dashboard cannot create or edit `inputSchema`: `save()` reuses the existing schema or `{}`, and the UI says 'Create or change schemas through MCP'. So every tool authored in the browser takes no parameters; a lottery fetcher can only take a draw date if an LLM created it. This is the biggest functional hole for dashboard users, and JSON Schema is the steepest part of the learning curve.
- **What:** A form builder (name, type, description, required, enum, default) that emits Draft 2020-12. 'Generate from example': paste `{"postcode":"PR1 1AA"}` and get an editable schema. A raw-JSON advanced mode validated with the existing `validate_schema`. Schema edits are revision-guarded like code.
- **Priority note:** Fable and LibreChat P1, Gemini P2.
- **Sources:** fable:F-02, librechat:I1, librechat:U3, gemini:Schema Visual Editor

#### FEAT-028 Plain-language errors and failed-run explainer

*usability | Studio / help | audience beginner | effort M | value high | P1*

- **Why:** Errors are accurate but technical ('Dependency installation failed; script was not run: <pip tail>', 'Arguments do not match inputSchema'). A failed test shows a raw traceback with a scratch path like `/tmp/omniforge/46c2b4.py` and no link back to the user's code.
- **What:** Map known failure classes to a short explanation and a next step, with the technical detail behind 'Show details'. Examples: `ModuleNotFoundError` becomes 'add X to Packages'; '`reqests` is not on PyPI, did you mean `requests`?'; 'Your AI sent `date` but the tool expects `draw_date`'; a timeout becomes 'raise the limit or cache'. Parse tracebacks, show the scratch path as 'your script', highlight the failing line and show the exact stdin JSON that was sent. Add 'Copy failure report' (code, inputs and error, secrets redacted) for pasting into any assistant.
- **Priority note:** Fable P1 for both halves. LibreChat P2 for hints, P3 for the failure report.
- **Sources:** fable:B-02, fable:U-01, librechat:I10, librechat:L4

#### FEAT-029 Guided 'new tool' wizard

*beginner | Onboarding | audience beginner | effort M | value high | P1*

- **Why:** In David's words, users have 'never seen anything like this'. The studio shows name, runtime, description, a blank script, folded packages and a JSON textarea all at once, and nothing explains the create, test, connect flow.
- **What:** Five steps: What should it do? Which inputs (name and type, in plain words)? Python or Node ('not sure: Python')? A generated skeleton that reads inputs and prints JSON. Then Test and Connect. Each step writes into the normal studio, so nothing is hidden afterwards. Optionally, a tooltip walk-through of the studio for the first tool.
- **Depends on:** FEAT-027 (Input-schema editor in the dashboard)
- **Priority note:** Fable P1. Gemini P2 for the tooltip tutorial.
- **Sources:** fable:B-01, gemini:Interactive Tutorial

#### FEAT-030 Realistic templates and a tool gallery

*beginner | Onboarding | audience beginner | effort S | value high | P1*

- **Why:** The four examples are two greetings, a `requests` example that deliberately sends nothing, and a lodash sort of four numbers. None shows how to accept an input, call a real URL, use a secret or return a table. An empty library is intimidating, and the templates are hidden in a dialog.
- **What:** A visible gallery page with 'Install' buttons and 10-15 curated templates, each with a schema, sample inputs and expected output. Examples: fetch a page and extract a number (bonus-ball style), call a JSON API with a secret, summarise a CSV from a URL, send a Pushover/Telegram message, scrape HTML, query SQLite, date/time, an n8n webhook, static reference text.
- **Depends on:** FEAT-027 (Input-schema editor in the dashboard), FEAT-026 (Per-tool encrypted secrets)
- **Priority note:** Fable B-04 and Gemini P1, LibreChat P2, Fable F-11 P3. Installing packs moved to the registry decision.
- **Sources:** fable:B-04, fable:F-11, librechat:F9, gemini:Tool Gallery

#### FEAT-031 Per-run working directory

*improvement | Runner | audience all | effort S | value medium | P1*

- **Why:** `run_tool` writes `SCRATCH_ROOT/{tool.id}.py` and every run shares one `cwd`. Two concurrent runs of the same tool rewrite the same file, so a save mid-run can execute mixed code, and any tool can read every other tool's source.
- **What:** Create a directory per run with `tempfile.mkdtemp`, write the code there and set `cwd` to it. Delete it afterwards unless 'keep for debugging' is on. This is also where the sandbox will mount.
- **Related bugs:** Shared scratch directory: concurrent runs overwrite each other's code and tools can read each other's source.
- **Priority note:** P1 in both reviews that raise it. Part of LibreChat's isolation tier 1.
- **Sources:** fable:I-03, librechat:R2

#### FEAT-032 Health and readiness endpoints

*requirement | Ops | audience advanced | effort S | value medium | P1*

- **Why:** There is no `/healthz` and no Dockerfile `HEALTHCHECK`, so Unraid and compose cannot tell a wedged event loop from a healthy one.
- **What:** `GET /healthz` (process up) and `GET /readyz` (DB readable and writable, lib root writable, python and node present), both reporting uptime and version. Add a `HEALTHCHECK` to the Dockerfile.
- **Priority note:** Fable P1, LibreChat P2. Kept P1 because it takes one session.
- **Sources:** fable:R-18, librechat:F8

#### FEAT-033 Supported Node runtime (Node 22 LTS)

*requirement | Runtime | audience all | effort S | value medium | P1*

- **Why:** The Dockerfile installs `nodejs npm` from Debian bookworm apt. That is Node 18, end-of-life since April 2025, with an old npm, and many current packages need Node 20+.
- **What:** Install Node 22 LTS from the official tarball or NodeSource, with a pinned version and checksum. Show runtime versions on `/api/config` and in the studio's runtime selector.
- **Sources:** fable:R-20

#### FEAT-034 CI gating, release pipeline and config clean-up

*requirement | Deployment / maintainability | audience advanced | effort M | value medium | P1*

- **Why:** `dockerhub.yml` pushes `:latest` on every push to `main` with no test step, and tests run only on PRs and non-main branches. Compose references `ionic-developer/omniforge:latest` while CI pushes `dbzocchi/omniforge:latest`, and only amd64 is built. `OMNIFORGE_RUNTIME_IMAGE`, `OMNIFORGE_SCRIPT_HOST` and the `omniforge_scripts` volume are left over from the Docker-per-run era. The README architecture no longer matches the code, and the version is hard-coded as `0.1.0`.
- **What:** Make the publish job `needs: test` and run tests on `main`. Tag images with semver and git SHA as well as `latest`, build `linux/amd64,linux/arm64` and attach SBOM/provenance. Ship a pull-only `docker-compose.yml` and a `compose.dev.yml`. Delete the dead env vars, the volume, unused dependencies and the misleading `lifespan` comment, warning at startup if a dead variable is still set. Use one canonical image name, make `.env.example` match reality and rewrite the README architecture. Add `/api/version` with the build SHA, a CHANGELOG and an 'update available' check against Docker Hub tags.
- **Priority note:** R-19 is P1. The dead-config clean-up was P2 in Fable and LibreChat but shares the image-name fix. The update check comes from Fable R-14 (P2).
- **Sources:** fable:R-19, fable:I-02, fable:R-14, librechat:I9

### Column: backlog

#### FEAT-035 HTTPS and secure-context setup

*requirement | Deployment | audience all | effort S | value high | P2*

- **Why:** PWA install and service workers need a secure context, so LAN users see no Install button and don't know why, and hosted MCP clients require HTTPS. The Connect page derives the endpoint from `location.origin`, which is wrong behind a reverse proxy that doesn't forward headers.
- **What:** Ship a compose profile and docs for the chosen route (Tailscale Serve, Caddy with an internal CA, or Cloudflare Tunnel plus Access). Run uvicorn with `--proxy-headers --forwarded-allow-ips` and honour `X-Forwarded-Proto/Host` in `/api/config`. Optional built-in TLS via `OMNIFORGE_TLS_CERT/KEY`. When the dashboard detects an insecure context, explain why Install is missing and link to the guide.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys), FEAT-009 (Which HTTPS route: Tailscale Serve, Caddy with an internal CA, or the existing Cloudflare Tunnel plus Access?)
- **Priority note:** Fable P1. LibreChat P2, and 'only after auth: HTTPS without auth is a worse position than HTTP on the LAN'. Taken as P2 so it follows login.
- **Sources:** fable:R-13, librechat:R8, librechat:U6

#### FEAT-036 Connection readiness checklist, self-test and last-seen clients

*beginner | Connect / overview | audience beginner | effort M | value high | P2*

- **Why:** Connect says 'Connected clients: Not tracked' and lists limitations instead of checking them. Create, test, connect ends in silence: a beginner can't tell whether the blocker is HTTPS, a missing key or a disabled tool, or whether LibreChat ever reached the server.
- **What:** A 'Test from this browser' button that runs initialize and tools/list through the real endpoint with the user's key. A live checklist: reachable at this origin, HTTPS yes/no, key configured, at least one tool enabled, client has called `initialize`. A last-seen list (key name, client `name/version`, last call, tool count) and a QR code for phone clients. On Overview, a tick list driven by real state (first tool saved, first successful test, key created, first external `tools/list` and `tools/call`), ending with a live line such as 'your assistant called `greet_python` 12 s ago'.
- **Depends on:** FEAT-023 (Run history and logs), FEAT-018 (Dashboard login + scoped API keys), FEAT-020 (Per-client connection recipes)
- **Priority note:** Fable B-05 P1, the rest P2. P2 because it needs run history, keys and HTTPS status first.
- **Sources:** fable:B-05, fable:U-05, fable:B-07, librechat:I5, librechat:U1

#### FEAT-037 Test-input form generated from the schema

*usability | Studio | audience beginner | effort M | value high | P2*

- **Why:** Test inputs are a raw JSON textarea that defaults to `{}`. A user whose tool needs `{"draw_date":"2026-10-15"}` has to know JSON syntax and the schema, which is shown read-only further up the page.
- **What:** Render fields from `properties` (type-aware controls, required markers, descriptions) with an 'Edit as JSON' toggle. Reuse the same renderer for webhook and cron arguments.
- **Depends on:** FEAT-027 (Input-schema editor in the dashboard)
- **Sources:** fable:U-02, librechat:L2

#### FEAT-038 Git sync and CI for tools

*feature | Storage / DevEx | audience advanced | effort L | value high | P2*

- **Why:** Code review, blame, branching and off-box history all need files, not BLOBs. The README's 'self-updating' vision covers updating the image but not the tools. Advanced users want pull requests and automatic deployment of tools, the same way the image is built.
- **What:** Phase 1: export to and import from a directory in the bundle format. Phase 2: an optional `OMNIFORGE_TOOLS_DIR` holding `tools/<name>/main.py|main.js` plus `tool.json`, with the DB as the runtime index, a watcher that imports changes, and push/pull to a configured remote (pull on webhook). `omniforge validate` (schema, requirements, syntax) as a GitHub Action that runs saved tests in a throwaway container and deploys on merge.
- **Depends on:** FEAT-024 (Export / import tool bundles), FEAT-022 (Tool version history, rollback and trash), FEAT-011 (Should SQLite stay the source of truth with export/import, or should OmniForge move toward git-backed tool files?)
- **Priority note:** Fable and Gemini P2, LibreChat P3. Its shape depends on the source-of-truth decision.
- **Sources:** fable:F-04, fable:A-02, librechat:F7, librechat:A2, gemini:Git Synchronization

#### FEAT-039 Derive input and output schemas from code

*advanced | Studio / DevEx | audience advanced | effort M | value high | P2*

- **Why:** Authors have to hand-write JSON Schema, which they can't do at all in the browser, even though the code already defines the inputs it reads.
- **What:** Convention: in Python, `def main(draw_date: str, count: int = 1) -> dict` with a docstring, or a `SCHEMA = {...}` constant; in Node, JSDoc or `module.exports.schema`. On save, parse these and generate `inputSchema`/`outputSchema`. The studio shows the derived schema and lets the author override it.
- **Depends on:** FEAT-027 (Input-schema editor in the dashboard)
- **Sources:** fable:A-04

#### FEAT-040 'What is MCP?' plain-language primer

*usability | Help / onboarding | audience beginner | effort S | value medium | P2*

- **Why:** Help says 'Think of a tool as a named script your AI can ask the server to run', then jumps straight to JSON-RPC methods. Connect talks about `initialize`, `tools/list`, Streamable HTTP and SSE. It assumes users already know 'MCP', 'schema' and 'tool'.
- **What:** A short illustrated page: your AI app, then OmniForge, then your script, then the answer. It covers the three roles (client, server, tool), what inputs are (the form the assistant fills in), a glossary (endpoint, key, schema, enable), and 'you never need to send JSON-RPC yourself'. Protocol detail moves under 'Advanced'.
- **Priority note:** Fable P1, LibreChat P2. Medium value and not a prerequisite, so P2.
- **Sources:** fable:U-03, librechat:U2

#### FEAT-041 Build tools with your AI assistant

*beginner | Onboarding / MCP authoring | audience beginner | effort M | value medium | P2*

- **Why:** `omniforge_instructions` and `omniforge_create_tool` already let an LLM author tools, but the dashboard never tells beginners this exists or how to phrase the request. LLM clients can create a tool but not fix it, which forces a trip back to the dashboard.
- **What:** A 'Build it with your AI' panel with a copyable prompt ('Connect to OmniForge, read `omniforge_instructions`, then create a tool that ...') and a note that the AI saves the tool but does not run it. The library shows a 'Created by <client>' badge, and MCP-created tools start disabled ('Review before enabling'). A built-in `omniforge_update_tool` that requires the current revision (the If-Match equivalent) and the `tools:author` scope, and writes a new version.
- **Depends on:** FEAT-023 (Run history and logs), FEAT-022 (Tool version history, rollback and trash), FEAT-018 (Dashboard login + scoped API keys)
- **Priority note:** Fable P2, LibreChat P3.
- **Sources:** fable:B-06, librechat:U4, librechat:I7

#### FEAT-042 Real code editor (CodeMirror 6)

*usability | Studio | audience all | effort M | value medium | P2*

- **Why:** The editor is a `<textarea>` with a line-number gutter and Tab handling. It has no syntax highlighting, bracket matching, search or error squiggles, which is painful beyond about ten lines.
- **What:** Vendor CodeMirror 6 (no CDN, matching the self-hosted stance) with Python and JS modes. Keep the textarea as a fallback, and keep the existing keyboard and Escape behaviour and dirty tracking.
- **Sources:** fable:U-06

#### FEAT-043 Save & Test and Duplicate actions

*usability | Studio | audience all | effort S | value medium | P2*

- **Why:** Testing needs a save first because Run is disabled while there are unsaved changes, so every edit-save-run loop costs two clicks and a status message. Making a variant means copying code into a new tool and re-entering requirements and schema. Copying first is even the recommended way to recover from a 412, yet there is no copy action.
- **What:** A 'Save & Test' primary action (Ctrl/Cmd+Enter) that saves, then runs the saved revision, keeping the dirty-state model and 412 handling. 'Make a copy' opens a new draft named `name_copy` with the same code, requirements, schema and annotations.
- **Priority note:** Save & Test is P2. Duplicate is P3 in Fable and LibreChat.
- **Sources:** fable:U-09, fable:U-10, librechat:I8

#### FEAT-044 Library tags, filters and richer rows

*usability | Tools | audience all | effort S | value medium | P2*

- **Why:** The list is flat and sorted by `updated_at`, and search matches substrings of name and description. Rows don't show whether a tool has ever run, failed or takes inputs. With 30+ tools, 'all my lottery tools' or 'everything that needs a secret' can't be found.
- **What:** Free-form tags (e.g. DevOps, Content, Finance) with filter chips next to the state/runtime filter. Rows show last-run status and time, call count, and 'needs inputs' and 'needs secrets' badges. Sort by name, last run or most called.
- **Depends on:** FEAT-023 (Run history and logs)
- **Priority note:** Richer rows are P2 (Fable). Tags are P3 in all three reviews.
- **Sources:** fable:F-17, fable:U-07, librechat:F12, gemini:Tool Tagging/Groups

#### FEAT-045 Live progress, streaming output and cancel

*usability | Studio / MCP | audience all | effort M | value medium | P2*

- **Why:** The first run of a tool with packages shows a static 'Preparing dependencies... up to 120 seconds' message, so the user can't tell whether pip is downloading or stuck. Run/Test shows only the final result, the only busy cue is 'Working... Keep this tab open', and there is no cancel. Long scrapers look hung to MCP clients too.
- **What:** Server-sent progress events for installs (packages resolved, downloading, complete) and runs (started, stdout/stderr chunks, finished), shown live with elapsed time. A Cancel button that kills the run's process group, and a clear 'server busy' state when the concurrency cap is reached. Over MCP, forward script progress lines as progress notifications and honour `notifications/cancelled`.
- **Depends on:** FEAT-017 (Adopt the official MCP SDK Streamable HTTP transport), FEAT-015 (Resource limits: per-tool overrides, concurrency cap, quotas and rate limits)
- **Related bugs:** Depends on the separate fixes for blocking subprocess calls and timeouts that kill only the direct child.
- **Priority note:** The dashboard parts are P2 (Fable, Gemini). MCP progress and cancellation are P3 (Fable, LibreChat).
- **Sources:** fable:U-08, fable:U-12, fable:A-10, gemini:Live Logs (SSE), librechat:A7

#### FEAT-046 Package environments: background preparation and cache management

*feature | Installer | audience advanced | effort M | value medium | P2*

- **Why:** Installs are synchronous and can take up to 120 s. Each requirements change creates a new hashed environment, and old caches 'remain until an administrator removes them', so the lib volume grows forever. Incomplete directories raise 'administrator review required', but there is no UI to review them. Ten tools that need `requests==2.32.5` install it ten times.
- **What:** A background preparation job with a 'Prepare packages' button. An MCP call made during preparation gets a clear 'preparing, retry' result instead of blocking. A Packages page lists each tool's environments (size, requirements, last used, complete or incomplete) with prune, rebuild, 'clear incomplete' and remove-unused actions; remove-unused garbage-collects environments that no revision references. Optionally, key environments by `(language, requirements-hash)` so tools with identical requirements share one copy.
- **Depends on:** FEAT-022 (Tool version history, rollback and trash)
- **Related bugs:** Complements the separate fix for blocking installs inside async handlers.
- **Priority note:** Cache sharing (Fable I-12) was P3, low value.
- **Sources:** librechat:F10, librechat:F11, fable:F-19, fable:I-12

#### FEAT-047 Tool titles, annotations and 'how your AI sees this tool'

*feature | MCP / studio | audience all | effort S | value medium | P2*

- **Why:** MCP clients use `title` and annotations (readOnlyHint, destructiveHint, idempotentHint, openWorldHint) to decide when to ask the user for confirmation, but OmniForge sends only name, description and inputSchema. How an LLM picks a tool depends almost entirely on the description. Yet the exact `tools/list` entry is never shown, and nothing nudges authors toward good descriptions.
- **What:** An optional `title` and four annotation checkboxes in the studio, included in `tools/list`. A preview card shows the entry as clients receive it (name, title, description, schema as a parameter table, annotations). It adds inline guidance and simple checks: length, starts with a verb, mentions inputs and outputs.
- **Priority note:** Fable P2. LibreChat P3 for description checks.
- **Sources:** fable:F-16, fable:U-11, librechat:I11

#### FEAT-048 Structured results, output schemas and saved test cases

*feature | MCP / studio | audience advanced | effort M | value medium | P2*

- **Why:** Every result is a single text block. A crashed script's traceback and exit code and a successful script's JSON are both second-class, and clients have to re-parse strings. Tools are tested by eyeballing stdout once: test inputs reset when another tool is selected, and nothing records what a good run looks like.
- **What:** Return the exit code and bounded stderr in dashboard results and in MCP error text. When stdout parses as a JSON object, also return it as `structuredContent` next to the text block. An optional `outputSchema` (MCP 2025-06-18) validated against the parsed stdout. Named example inputs saved per tool, with optional expected-output checks, a 'Run all tests' button and a CLI/CI hook.
- **Depends on:** FEAT-017 (Adopt the official MCP SDK Streamable HTTP transport), FEAT-027 (Input-schema editor in the dashboard)
- **Sources:** fable:R-10, fable:F-09, librechat:I2, librechat:I6

#### FEAT-049 MCP prompts and resources

*feature | MCP | audience advanced | effort M | value medium | P2*

- **Why:** Only `tools/*` exists; `resources/list` and `prompts/list` return -32601. Clients such as Claude and LibreChat can show prompts and resources, which is how a model gets usage guidance and reference data without calling a tool. As it stands, every tool's docs, examples and last result are only visible by calling it.
- **What:** Resources such as `omniforge://tools/{name}` (description, schema, examples), the latest run output and uploaded reference files, plus user-authored prompt templates with arguments. Expose `prompts/list|get` and `resources/list|read|templates/list` with change notifications. Prompt and Resource kinds in the library, each with its own studio form and a `prompts/get` preview. Gemini also suggests sampling.
- **Depends on:** FEAT-017 (Adopt the official MCP SDK Streamable HTTP transport)
- **Priority note:** Fable and Gemini P2. LibreChat and Fable's authoring UI (A-05) P3.
- **Sources:** fable:F-10, fable:A-05, librechat:F5, gemini:Full MCP Compliance

#### FEAT-050 Audit trail

*requirement | Security | audience advanced | effort M | value medium | P2*

- **Why:** Nothing records that an LLM created `foo` via `omniforge_create_tool` at 02:14, which key called what, when a secret was rotated, or that a tool was deleted. `updated_at` is the only trace, and it gets overwritten.
- **What:** An append-only `audit_events` table: actor (admin session, client key, built-in), action (create, update, delete, toggle, run, install, key-rotate, secret-change, import), target, revision before and after, remote address and timestamp. Viewable and exportable from the dashboard, with optional signed entries.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys), FEAT-022 (Tool version history, rollback and trash), FEAT-023 (Run history and logs)
- **Priority note:** Gemini P3.
- **Sources:** fable:R-11, librechat:R4, gemini:Audit & Supply Chain

#### FEAT-051 Supply-chain and install-path hardening

*requirement | Security / installer | audience advanced | effort M | value medium | P2*

- **Why:** Packages are installed from PyPI and npm by name, and unpinned names silently freeze at whatever resolved first. There is no hash verification and no allow/deny list, npm runs with `--no-audit`, and install logs are deleted after success. The installer has full network access, writes into a volume the app also reads, and has no size quota or limit on concurrent installs.
- **What:** Generate a per-tool lockfile on first install (pip `--require-hashes` via `pip-compile --generate-hashes`; npm `package-lock.json` integrity and `npm ci`). Add an admin allow/deny list, an optional private index or mirror, retained install logs, and `pip-audit`/`npm audit` on prepare, shown on the Packages page. Upgrades happen through a deliberate 're-resolve' action. A global install semaphore and a volume size quota with a clear error. Once the sandbox exists, optionally restrict install egress to registry hosts. Record installs in run history and the audit trail.
- **Depends on:** FEAT-046 (Package environments: background preparation and cache management)
- **Priority note:** Fable and LibreChat P2, Gemini P3. Install-path hardening (Fable R-22) was P3.
- **Sources:** fable:R-15, fable:R-22, librechat:R6, gemini:Audit & Supply Chain

#### FEAT-052 Scheduled runs and cached results

*feature | Automation | audience advanced | effort M | value medium | P2*

- **Why:** A bonus-ball fetcher should naturally run every Wednesday and Saturday evening and be fresh at 20:01. Today only an LLM or a person can trigger it, and the LLM side is the wrong place to poll from.
- **What:** A per-tool cron expression with fixed arguments, and an in-process scheduler (APScheduler or an asyncio loop) with jitter and a missed-run policy. Results go to run history and, optionally, to a notification tool. Optional 'cache last result for N minutes', so MCP calls get the cached output.
- **Depends on:** FEAT-023 (Run history and logs), FEAT-010 (Build cron scheduling into OmniForge, or ship webhook triggers only and let n8n do the scheduling?)
- **Priority note:** Build only if the scheduling decision says to build it in. Otherwise n8n schedules through webhooks.
- **Sources:** fable:F-07, librechat:F4

#### FEAT-053 Webhook triggers and n8n integration

*feature | Automation / integration | audience advanced | effort M | value medium | P2*

- **Why:** n8n, GitHub, Home Assistant and cron on another machine can only call a tool by speaking JSON-RPC and holding the global Bearer key. David runs n8n, and its MCP Client and HTTP Request nodes are the natural way to chain OmniForge tools into workflows.
- **What:** `POST /hooks/{tool}/{hook-token}`: the body becomes the arguments, each tool has its own token, and the request goes through schema validation and the normal run pipeline. It replies synchronously or with `202` and a run id. Verify n8n's MCP Client node against the new transport, accept n8n payloads, and publish an n8n workflow template that calls `tools/call`. Document a round trip: n8n cron, then an OmniForge tool, then an n8n notification.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys), FEAT-023 (Run history and logs), FEAT-017 (Adopt the official MCP SDK Streamable HTTP transport)
- **Priority note:** Webhooks P2 in Fable and LibreChat. n8n integration P2 (Fable) vs P3 (LibreChat).
- **Sources:** fable:F-08, fable:A-08, librechat:F4, librechat:A4

#### FEAT-054 Structured logs, usage stats and /metrics

*feature | Observability | audience advanced | effort M | value medium | P2*

- **Why:** Only uvicorn access logs exist, so tool failures, install failures and conflicts are returned to the caller and then vanish. Overview shows only saved and enabled counts. Nobody can answer 'which tools does LibreChat actually call, how often do they fail, and how slow is the install path?', and Prometheus/Grafana users on Unraid have nothing to graph.
- **What:** JSON logs with request id, actor, tool, revision, duration and exit status, an `OMNIFORGE_LOG_LEVEL` setting, and correlation with run ids. Per-tool and per-client counters (calls, errors, p50/p95 duration, install time) on Overview and on each tool. A `/metrics` endpoint in Prometheus text format (run counts, durations, errors, install times, queue depth) and optional OpenTelemetry export.
- **Depends on:** FEAT-023 (Run history and logs)
- **Sources:** fable:I-09, fable:F-14, fable:A-06, librechat:F8

#### FEAT-055 omniforge CLI and documented API

*advanced | DevEx | audience advanced | effort M | value medium | P2*

- **Why:** The management API is REST built for the browser, so scripting it means hand-rolling `curl` calls with `If-Match` headers. FastAPI already generates OpenAPI docs, but nothing points users to them.
- **What:** Publish `/docs` behind auth. Add a small pip-installable `omniforge` CLI that uses API keys: `login`, `list`, `pull/push <name>`, `run <name> --args`, `logs` and `export/import`, with JSON output for scripting.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys), FEAT-024 (Export / import tool bundles)
- **Priority note:** Fable P2, LibreChat P3.
- **Sources:** fable:A-01, librechat:A1

#### FEAT-056 Per-client tool visibility

*feature | MCP / security | audience advanced | effort S | value medium | P2*

- **Why:** Every client holding the one Bearer key sees every enabled tool, so a client that only needs the shop tools sees the Sonarr ones too. David wants some tools for LibreChat only, or a read-only subset for a phone client.
- **What:** A per-key allowlist of tool names or tags. `tools/list` and `tools/call` are filtered by the authenticated key. Optionally, group endpoints such as `/mcp/{group}`.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys), FEAT-044 (Library tags, filters and richer rows)
- **Priority note:** Fable P2, LibreChat P3.
- **Sources:** fable:F-20, librechat:F12

#### FEAT-057 Split the single-file dashboard into modules

*improvement | Frontend maintainability | audience advanced | effort M | value medium | P2*

- **Why:** `dashboard.html` is 574 lines (about 50 KB) with all the JS inline. CI extracts the `<script>` by string-splitting so it can lint it, and `tests/dashboard_ui.cjs` hand-rolls a 300-line fake DOM. Every dashboard feature on this board would land in that one file.
- **What:** Move the JS to `/assets/app.js` as ES modules (api, router, editor, library, connect) with no build step, served through the existing allowlist and precached. Replace the fake DOM with jsdom or rely on Playwright.
- **Sources:** fable:I-06

#### FEAT-058 No-code tool types (HTTP request, reference text, table lookup)

*beginner | Studio | audience beginner | effort L | value high | P3*

- **Why:** Many useful tools are just 'GET this URL and return the JSON' or 'answer from this text', yet connecting to an API still takes boilerplate `requests` code. Users know what they want but not Python or Node.
- **What:** Declarative tool kinds run by built-in runners. HTTP request: a URL with `{{input}}` placeholders, a method, headers or auth from secrets, and a JSON-path pick. Reference text: paste docs or an FAQ, returned verbatim. Table lookup: upload a CSV and query it by column. Same metadata and MCP surface as script tools.
- **Depends on:** FEAT-026 (Per-tool encrypted secrets), FEAT-027 (Input-schema editor in the dashboard)
- **Priority note:** LibreChat P3, though it calls this the only bet that widens the audience. Gemini P2. Revisit after the wizard and templates.
- **Sources:** librechat:L1, gemini:No-Code Webhooks

#### FEAT-059 Per-tool network egress policy

*requirement | Security / runner | audience advanced | effort M | value medium | P3*

- **Why:** Scripts have unrestricted network access, including to the NAS's other containers and the Unraid host. Even once isolation exists, 'network off' is all or nothing, but a lottery tool should reach `national-lottery.co.uk` and nothing else.
- **What:** A per-tool egress allowlist (hosts/CIDRs), enforced through the sandbox's network namespace and a small forwarding proxy (or the sidecar on its own Docker network). Default deny for new tools when enabled. At minimum, document the current exposure.
- **Depends on:** FEAT-006 (Per-run sandbox for script execution)
- **Sources:** fable:A-11, librechat:R9

#### FEAT-060 OAuth 2.1 resource server for hosted MCP clients

*requirement | Security / MCP | audience advanced | effort L | value medium | P3*

- **Why:** Claude.ai custom connectors and other hosted MCP clients require OAuth (authorization-server discovery via RFC 9728/8414, dynamic client registration) and cannot send a static Bearer header. Today OmniForge works only with clients that allow custom headers.
- **What:** Implement the MCP resource-server role: `/.well-known/oauth-protected-resource`, bearer JWT validation against an external authorisation server (Authentik, Keycloak, Cloudflare Access or Auth0), PKCE, and mapping of OAuth scopes to the API-key scopes. Do not build an authorisation server.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys), FEAT-035 (HTTPS and secure-context setup), FEAT-017 (Adopt the official MCP SDK Streamable HTTP transport), FEAT-005 (Which clients must OmniForge serve: LAN-only clients with per-client keys, or remote hosted clients such as Claude.ai connectors that need OAuth 2.1?)
- **Priority note:** Fable P2. LibreChat P3: 'only worth it if remote hosted clients are a goal'. Becomes P2 if the clients decision says yes.
- **Sources:** fable:R-03, librechat:R1

#### FEAT-061 Additional runtimes: TypeScript, shell and more

*feature | Runner | audience advanced | effort M | value low | P3*

- **Why:** `_runtime` hard-codes python and node. Many tools are one-line shell pipelines, most Node authors write TypeScript, and some jobs need other Python versions or binaries.
- **What:** A data-driven runtime registry shared by `validate_requirements` and the runner. Add TypeScript via Node 22's `--experimental-strip-types` (or esbuild, tsx or Deno), `bash` (no package manager, flagged as dangerous), and optional `uv`-managed Python versions. Per-tool container images (Gemini) conflict with the no-Docker-socket stance and depend on the isolation decision.
- **Depends on:** FEAT-033 (Supported Node runtime (Node 22 LTS))
- **Priority note:** Fable and LibreChat P3. Gemini P2 for TypeScript.
- **Sources:** fable:F-12, librechat:A6, gemini:TypeScript Support, gemini:Custom Runtimes

#### FEAT-062 Script helpers: run context, shared modules and multi-file tools

*advanced | Runner | audience advanced | effort M | value low | P3*

- **Why:** A script can't tell which tool it is, which client called it, or what run id to use when correlating its own logs. Each run is a single file in a scratch directory, so tools that call the same API duplicate their auth and parsing code. A single `code` string makes complex logic impossible.
- **What:** Inject `OMNIFORGE_TOOL`, `OMNIFORGE_RUN_ID` and `OMNIFORGE_CALLER`, plus a tiny optional in-child helper (`omniforge.log()`, `omniforge.progress()`, `omniforge.secret(name)`, `omniforge.call(name, args)`). A versioned 'library' tool kind that is copied into the run directory (`omniforge_lib/`) and put on `PYTHONPATH`/`NODE_PATH`. Optionally, multiple files per tool.
- **Depends on:** FEAT-031 (Per-run working directory), FEAT-023 (Run history and logs), FEAT-026 (Per-tool encrypted secrets)
- **Priority note:** Gemini rated multi-file scripts P2. The other two reviews rated this P3.
- **Sources:** fable:A-09, fable:F-18, librechat:A5, gemini:Multi-File Scripts

#### FEAT-063 Multi-worker and multi-instance story

*requirement | Server / ops | audience advanced | effort M | value low | P3*

- **Why:** `Database._cache` is per process with a 5 s TTL, so `uvicorn --workers 2` would silently serve stale code for up to 5 s and double install-lock contention. The single worker is also a throughput ceiling. Two replicas behind a proxy would split the SQLite and lib-volume state.
- **What:** Either document single worker and single instance as a hard constraint and refuse to start with `--workers>1`, or invalidate caches via SQLite `PRAGMA data_version` and allow N workers once runs are non-blocking. Optionally, a thin DB adapter for PostgreSQL and shared cache storage for replicas.
- **Sources:** fable:R-21, fable:A-07, librechat:I12

#### FEAT-064 Lightweight multi-user and attribution

*feature | Collaboration | audience all | effort L | value low | P3*

- **Why:** Even a household or small team shares one dashboard, and nothing records who changed what. Full RBAC is overkill for a self-hosted, single-container product.
- **What:** A users table with roles (admin, author, viewer) layered on dashboard login. The author is stored on versions and runs, and tools can be marked read-only to non-owners.
- **Depends on:** FEAT-018 (Dashboard login + scoped API keys), FEAT-022 (Tool version history, rollback and trash), FEAT-003 (Admin identity: single admin password and session, multiple local users from day one, or OIDC sign-in?)
- **Sources:** fable:F-13

## Excluded as pure bug reports

These belong to the separate verified bug list and are not cards here:

- `fable:R-04`: Scrub the subprocess environment (API key leaks into every script). Referenced as a prerequisite in the secrets card's related_bug_hint.
- `fable:R-07`: Bounded stdout/stderr (uncapped output). Referenced in the sandbox and test-suite hints.
- `gemini:Async Runner`: Blocking `subprocess.run` in async handlers. Referenced in the resource-limits, progress and package-environment hints.

Fable R-06 (process-tree kill + rlimits) and R-08 (non-blocking + concurrency cap) are listed as sources on the resource-limits card only for their non-bug halves (rlimits, concurrency cap); their bug halves belong to the verified bug list. Fable I-05 and I-11 (JSON-RPC envelope, version negotiation) are pure protocol bugs that the SDK transport card fixes, so they are listed as its sources.

Source coverage check: all 84 Fable items, all 63 LibreChat items/decisions and all 25 Gemini items map to a card or to the list above.
