Working from the pasted README and `docs/product-design.md` at `4ae443d` plus the SiYuan handover only — nothing touched on the live instance, no tools run, nothing pushed.

## Where OmniForge actually stands (anchor for everything below)

What the docs say exists: tool CRUD with a content revision and `If-Match` guards; stdin-JSON arguments, stdout-as-text results; per-tool pip/npm caches with locks, markers and strict name validation; two built-ins (`omniforge_instructions`, `omniforge_create_tool`); a hash-routed PWA with Overview/Tools/Studio/Connect/Help; good test coverage of the UI, worker and installer. What the docs say does **not** exist: any auth except optional Bearer on `POST /mcp`; any isolation beyond "subprocess in the app container inheriting the app environment"; a compliant transport (`GET /mcp` is a stub, no `initialize`/session, no notifications); run history; schema editing in the studio; memory/output/process-tree limits; async installs; cache cleanup; HTTPS.

Two things stood out that the backlog doesn't name: **the studio can't edit `inputSchema`** (it's read-only in Advanced settings, so a dashboard-created tool has no inputs unless created via MCP/API), and **scripts inherit the app environment**, which means today the only place a tool could get a secret from is the same place every other tool can read it. Those two shape a lot of the priorities.

Effort: S ≈ one agent session, M ≈ 2–4, L ≈ a week-plus with design. Priority: P1 = before any exposure beyond the trusted LAN or before building on top; P2 = this quarter; P3 = nice.

---

## 1. Missing features

| # | Title | Area | Why (the pain) | What | Effort | Pri |
|---|---|---|---|---|---|---|
| F1 | Tool version history and rollback | Studio / DB | A bad save over a working tool is unrecoverable; the content revision exists but only the latest row is kept. Handover already lists rollback as P2. | Append-only `tool_versions` (code, schema, requirements, description, author, timestamp, revision). Studio: history list, diff against current, "Restore this version" (creates a new revision, never rewrites). Foundation for F6, F7, A2. | M | P1 |
| F2 | Per-tool secrets | Runner / Studio | Nowhere to put an API key except the container env, which every script inherits. Blocks any real-world tool (lottery, Booker, POS…) from being safe. | `secrets` table encrypted at rest with `OMNIFORGE_SECRET_KEY`; set/rotate/delete via studio, never readable back; injected only into that tool's child env; values redacted from stdout/stderr/logs. Requires R2's env scrubbing first or it's theatre. | M | P1 |
| F3 | Run history and logs | Runner / Overview | Overview explicitly "does not invent execution history"; nobody can answer "did my client actually call it, and what happened?" | `runs` table: tool, revision, args hash (args optional), origin (dashboard/MCP + client key id), status, exit code, duration, bounded stdout/stderr, timestamps. Runs tab per tool + global; re-run with same inputs; retention policy. Unlocks F8 observability and the onboarding "it worked" moment (U1). | M | P1 |
| F4 | Scheduling, webhook triggers and result caching | Runner / Integrations | The lottery tool must be fresh at 20:01; LLM-side polling is the wrong place for that. | Per-tool: optional cron, optional webhook URL with its own token, optional "cache last result for N minutes" so MCP calls return the cached output. Decision D5: build in, or expose only webhooks and let n8n schedule. | M | P2 |
| F5 | MCP prompts and resources | MCP | Clients get only `tools/*`; every tool's docs/examples/last result are invisible except through a call. | Resources: `omniforge://tools/{name}` (description, schema, examples), optionally last run output. Prompts: user-authored prompt templates in the dashboard. Depends on R3 (a real transport). | M | P3 |
| F6 | Import / export | Tools | No way to copy a tool between instances, share one, or back a single tool up. | Export a tool (or the whole library) as a bundle: `tool.yaml` + source file + schema; import with name-collision handling and dry-run. Same format feeds F7 and A2. | S | P2 |
| F7 | Git sync | Tools / DevEx | SQLite is the only source of truth; no review, PR or history outside the box. | Phase 1: "export to directory"/"import from directory" in the F6 format. Phase 2: optional repo URL + branch, pull-on-webhook, DB stays the runtime index. Decision D4. | L | P3 |
| F8 | Observability | Ops | Only container logs; no counts, durations, failure rates, install times. | Structured JSON logs with request/run ids; `/healthz` (DB writable, lib root writable, interpreters present) for Docker `HEALTHCHECK`/Unraid; `/metrics` (Prometheus) over F3 data. | S–M | P2 |
| F9 | Template gallery | Help / Studio | Four templates, all greeting/HTTP. First-timers don't see what a *useful* tool looks like. | 10–15 templates: HTTP JSON fetch with error handling, HTML scrape, CSV/Excel read, SQLite query, date/time, call-another-tool, n8n webhook, image→base64, "static reference text". Each with schema and example inputs. | S | P2 |
| F10 | Async dependency preparation | Installer | Installs are synchronous and block the single worker for up to 120 s. | Background job + progress via SSE/polling; "Prepare packages" button in the studio; MCP call during preparation returns a clear "preparing, retry" error rather than blocking everything. | M | P2 |
| F11 | Environment cache management | Installer | "Old caches remain until an administrator removes them" — the lib volume grows forever. | Dashboard view of environments per tool with size; "remove unused"; optional GC on startup for environments not referenced by any revision (after F1). | S | P2 |
| F12 | Tool tags, groups and per-endpoint exposure | Tools / MCP | One flat list, one endpoint; a client that only needs the shop tools sees the Sonarr ones too. | Tags in metadata; `/mcp/{group}` or key-scoped visibility (ties to R1 scopes). | M | P3 |
| F13 | Soft delete / trash | Tools | Delete is confirmed but final. | 30-day trash with restore; falls out of F1 cheaply. | S | P3 |
| F14 | Schema migrations framework | DB | Docs promise "no destructive migration" case by case; F1–F3 all add tables. | Numbered migrations table + runner at startup, with pre-migration `VACUUM INTO` backup (ties to R5). Do first; everything else depends on it. | S | P1 |

## 2. Missing requirements

| # | Title | Area | Why | What | Effort | Pri |
|---|---|---|---|---|---|---|
| R1 | Authentication and authorisation everywhere | Security | Dashboard, `/api/*` and `GET /mcp` are open; one Bearer key for all clients, no revocation. Blocks HTTPS exposure, PWA install off-LAN, and any client beyond the LAN. | Tier 1 (S): admin session login for dashboard + API (cookie, CSRF, rate-limited), `GET /mcp` behind the same Bearer, Origin/Host validation. Tier 2 (M): per-client keys table (hashed), create/rotate/revoke in Connect, scopes (`tools:list`, `tools:call`, `tools:author`, tag/group restrictions), key id recorded on every run (F3). Tier 3 (L): OAuth 2.1 resource server per the MCP spec — protected-resource metadata, token validation against an external AS (Authentik/Cloudflare Access/etc.), PKCE, dynamic client registration if remote clients like claude.ai connectors are wanted. Decision D3. | S / M / L | P1 |
| R2 | Real per-run isolation without a Docker socket | Runner | Scripts can read the DB, the env (including `OMNIFORGE_API_KEY`), the lib root and every other tool's cache; a `fork()` loop or 10 GB print kills the app. | Tier 1 (S–M, in-container): minimal child env (same as installers get), `start_new_session` + kill the process group on timeout, `prlimit` (AS/CPU/NOFILE/NPROC/FSIZE), stdout/stderr byte caps, per-run private scratch dir deleted after, run as a second unprivileged UID that cannot read the DB/secrets files, fix the "+15 s" timeout. Tier 2 (M): a `runner` sidecar container with no DB, no secrets, no API key, read-only lib mount, talking to the app over a Unix socket/internal HTTP — still shared between runs but credentials are out of reach. Tier 3 (L): per-run namespaces via bubblewrap/nsjail in the sidecar (needs user namespaces → relaxed seccomp/AppArmor on Unraid, which is the trade-off) or gVisor if ever feasible. No socket at any tier. Decision D2. | S–M / M / L | P1 |
| R3 | Full MCP Streamable HTTP compliance | MCP | Handwritten JSON-RPC: no `initialize`/capabilities/protocol-version negotiation, no `Mcp-Session-Id`, no SSE for server→client messages, no `notifications/tools/list_changed`, no progress/cancellation, no pagination, no structured output, no Origin check. Clients "may" work. | Adopt the official `mcp` Python SDK's Streamable HTTP transport (mount at `/mcp`), keep the dynamic registry as a custom tool provider; emit `list_changed` on save/toggle/delete; `structuredContent` + optional `outputSchema` when stdout parses as JSON; tool annotations (`readOnlyHint` etc.) editable in the studio; conformance tests with MCP Inspector, Claude Desktop/Code and LibreChat. Decision D1. | L | P1 |
| R4 | Audit trail | Security | No record of who changed what, which key called what, or when a secret was rotated. | `audit_events` (actor: admin session/client key/built-in; action; target; before/after revision; IP; timestamp). Fed by F1 and F3; viewable and exportable. | S (after F1/F3) | P2 |
| R5 | Backup and restore | Ops | One SQLite file on a volume; no consistent snapshot, no restore path, lib caches rebuildable but slowly. | Scheduled `VACUUM INTO` to a backups dir with retention; "Download backup" / "Restore from backup" (admin only, dry-run diff); documented Unraid appdata-backup path; import/export (F6) as the portable layer. | S–M | P1 |
| R6 | Supply-chain controls for pip/npm | Installer | Pinned-by-name only; unpinned names "reuse first resolved versions" silently; `--no-audit`; any public package allowed. | Lockfile per tool revision (resolved versions + hashes; `pip --require-hashes`, `npm ci` from generated `package-lock.json`); optional allow/deny list; `pip-audit`/`npm audit` run on prepare with results shown; optional private mirror URL; install size cap; "re-resolve" action to upgrade deliberately. | M | P2 |
| R7 | Resource limits and rate limiting | Runner / API | Memory limit is "declared only"; a single client can saturate the single worker. | Per-tool concurrency cap and global run queue with bounded size; per-key rate limits; per-tool timeout/memory overrides within global ceilings; enforced via R2 tier 1 `prlimit` and later cgroups in the sidecar. | M | P1 |
| R8 | HTTPS for the LAN (PWA install) | Deployment | HTTP LAN isn't a secure context; install and some APIs unavailable. | Document and ship a compose profile for one of: Tailscale Serve (simplest, private, valid certs), Caddy with internal CA + `.lan` name, or the existing Cloudflare Tunnel with Cloudflare Access in front. **Only after R1 tier 1** — HTTPS without auth is a worse position than HTTP on the LAN. Decision D6. | S | P2 |
| R9 | Egress control for scripts | Runner | Scripts have unrestricted network, including to the NAS's other containers and the Unraid host. | Sidecar on its own Docker network with optional allow-list/proxy; at minimum document it. | M | P3 |

## 3. Improvements to existing features

| # | Title | Area | Why | What | Effort | Pri |
|---|---|---|---|---|---|---|
| I1 | Schema editor in the studio | Studio | Tools created in the dashboard can't take inputs; schema only via MCP/API. The single biggest functional hole for a dashboard user. | Two modes: form builder (name, type, description, required, enum, default) and raw JSON with Draft 2020-12 validation; "generate from example input"; revision-guarded like code. | M | P1 |
| I2 | Stderr, exit code and structured results in the contract | Runner / MCP | Contract documents stdout only; a crashed script's traceback and a successful script's structured JSON are both second-class. | Return exit code + bounded stderr in dashboard results and MCP error text; if stdout is valid JSON, also return `structuredContent` (R3). | S | P2 |
| I3 | Timeout semantics | Runner | README: "runner currently adds 15 seconds" — undocumented behaviour, and timeout only starts after preparation. | Enforce the configured value exactly; separate install timeout; per-tool override ≤ global. | S | P1 |
| I4 | Connect page: per-client setup | Connect | A JSON-RPC curl template doesn't help someone configuring Claude Desktop. | Tabs with copy-ready config for Claude Desktop, Claude Code (`claude mcp add`), Cursor/Windsurf, LibreChat, n8n MCP client, MCP Inspector; shows per-key values once (R1 tier 2). | S | P2 |
| I5 | "Last seen" connected clients | Connect | Handover P2 item; no way to tell if a client ever connected. | Derived from F3/R1: key id, last `tools/list`, last call, client `name/version` from `initialize` (R3). | S (after deps) | P2 |
| I6 | Saved example inputs and lightweight tool tests | Studio | Test inputs reset on selection; nothing records "this is what a good run looks like". | Save named example inputs per tool; optional expected-output assertion; "Run all examples" button; same cases usable in CI (A3). | S–M | P2 |
| I7 | Built-in `omniforge_update_tool` | MCP built-ins | LLM clients can create but not fix a tool; forces a round-trip to the dashboard. | Update with mandatory revision (`If-Match` equivalent) and `author` scope only; writes a version (F1). | S | P3 |
| I8 | Duplicate / clone tool | Studio | Copy-first is the recommended 412 recovery, yet there's no copy action. | "Duplicate as…" pre-fills a new draft. | S | P3 |
| I9 | Dead/misleading config | Config / README | `OMNIFORGE_SCRIPT_HOST` is historical; README architecture claims are wrong (handover P3). | Remove the setting with a startup warning if set; rewrite README architecture to match the code. | S | P2 |
| I10 | Error hints | Studio | Raw tracebacks for first-timers. | Pattern-match common failures: `ModuleNotFoundError` → "add X to Packages", JSON decode on stdin → "arguments", `SyntaxError` line pointer, timeout → "raise limit or cache". | S | P2 |
| I11 | Description quality linting | Studio | LLM tool selection depends almost entirely on description; nothing nudges towards good ones. | Inline guidance + simple checks (length, starts with a verb, mentions inputs/outputs). | S | P3 |
| I12 | Multi-worker safety | Backend | Single worker is a throughput ceiling; docs already note cross-worker cache staleness. | After F10/R7, allow N workers: registry cache invalidation via DB version counter, install locks already file-based. | M | P3 |

## 4. Usability for first-time users

| # | Title | Area | Why | What | Effort | Pri |
|---|---|---|---|---|---|---|
| U1 | Close-the-loop onboarding | Overview | Create → test → connect ends in silence; the user can't tell whether the client saw the tool. | Step 4 "Call it from your assistant" with a live indicator fed by F3 ("`greet_python` was called 12 s ago by *Claude Desktop*"). | S (after F3) | P2 |
| U2 | Plain-language primer | Help / Overview | "MCP", "schema", "tool" assumed. | Three short panels: what a tool is (a script your assistant can run), what inputs are (the form the assistant fills in), what connecting means. Pictures over prose. | S | P2 |
| U3 | Schema from example | Studio | JSON Schema is the steepest part of the hill. | Paste `{"postcode":"PR1 1AA"}` → generated schema with editable descriptions (part of I1). | S | P2 |
| U4 | "Ask your assistant to build it" | Overview | The built-ins already let an LLM author tools, but nobody is told. | Copyable prompt: "Connect to OmniForge, read `omniforge_instructions`, then create a tool that…". | S | P3 |
| U5 | Safe defaults | Studio | New users won't know about timeouts, packages or destructive actions. | New tools default to `readOnlyHint: true`, short timeout, no network note; one-line toggles to change. | S | P3 |
| U6 | Install/HTTPS explanation | Help | Users on the LAN see no Install button and don't know why. | Detect insecure context and show the specific reason with a link to the R8 guide. | S | P3 |

## 5. Ideas for less-advanced users

| # | Title | Area | Why | What | Effort | Pri |
|---|---|---|---|---|---|---|
| L1 | No-code tool types | Studio | Many useful tools are "GET this URL and return the JSON" or "answer from this text" — no code needed. | Declarative tool kinds executed by built-in runners: HTTP request (URL with `{{input}}` placeholders, headers from secrets, JSON-path pick), Reference text (paste docs/FAQ; returned verbatim), Table lookup (upload CSV; query by column). Same metadata, same MCP surface. | L | P3 |
| L2 | Form-based test inputs | Studio | Typing JSON is a barrier. | Render a form from the schema (comes free with I1). | S | P2 |
| L3 | One-click client config download | Connect | Hand-editing config files is where people give up. | Download `claude_desktop_config.json` fragment / deep link where the client supports it. | S | P3 |
| L4 | Guided "fix it" with the assistant | Studio | When a run fails, the user has an LLM connected already. | "Copy failure report" bundling code, inputs, error (secrets redacted) for pasting into any assistant. | S | P3 |

## 6. Ideas for more-advanced users

| # | Title | Area | Why | What | Effort | Pri |
|---|---|---|---|---|---|---|
| A1 | Documented API + CLI | DevEx | FastAPI already generates OpenAPI; nobody is pointed at it, and there's no CLI. | Publish `/docs` behind auth; `omniforge` CLI (`login`, `pull`, `push`, `run`, `logs`, `export`, `import`) over the API using F6 format and R1 keys. | M | P3 |
| A2 | Git-backed tools and CI | DevEx | Review, PRs, history outside the box. | F7 plus a GitHub Action: validate bundle, run I6 examples in a throwaway OmniForge container, push on merge. | L | P3 |
| A3 | Draft → published revisions | Studio | "Multiple environments" is mostly "don't break the tool my assistant is using while I edit it". | Each tool has a published revision served over MCP and an optional draft; test the draft, then Publish. Cheaper than multi-env; multi-instance promote via CLI (A1) covers real dev/prod. Decision D10. | M | P3 |
| A4 | n8n integration | Integrations | David runs n8n; it's the natural scheduler and glue. | Webhook triggers (F4), "export as n8n Code node", confirm n8n's MCP client node works against R3, template calling an n8n webhook. | S–M | P3 |
| A5 | Tool composition and shared modules | Runner | Copy-pasting helpers between tools. | Tiny in-child SDK (`omniforge.call(name, args)`, `omniforge.secret(name)`) and per-tool "shared library" packages. | M | P3 |
| A6 | Extra runtimes | Runner | Only system Python/Node. | `uv`-managed Python versions per tool, Deno/TypeScript, bash (explicitly flagged dangerous). | M | P3 |
| A7 | Streaming progress and cancellation | MCP / Runner | Long runs look hung. | Progress notifications from stderr markers, `cancel` kills the process group (R2/R3). | S (after deps) | P3 |

## 7. Quick wins and big bets

**Quick wins (each one session or less, no design debate):** R2 tier 1 (env scrub, process group kill, output caps, prlimit); R1 tier 1 (admin login + `GET /mcp` behind Bearer + Origin check); I3 timeout fix; F14 migrations + R5 scheduled `VACUUM INTO`; F8 `/healthz`; I9 README/dead setting; I4 client setup snippets; I2 stderr/exit code; F9 templates; F11 cache listing; I10 error hints.

**Big bets (change what OmniForge is):**
1. **R3 on the official SDK** — turns "verify your client's compatibility" into "works with any MCP client", and unlocks F5, A7, I5.
2. **R2 tier 2/3 runner sidecar** — the honest route from "trusted LAN only" to "safe to give a key to someone else", without a Docker socket.
3. **F1 + F3 + R4** — history, runs and audit as one data model; everything advanced (git, CI, publish gates, observability) sits on it.
4. **L1 no-code tool types** — the only item that widens the audience rather than deepening it.
5. **R1 tier 3 OAuth 2.1** — only worth it if remote hosted clients are a goal (D3).

Sequencing that matters: F14 → F1/F3 → R4/I5/U1; R2 tier 1 → F2; R1 tier 1 → R8; R3 → F5/A7/I2's structured output; F6 → F7/A1/A2.

---

## Kanban-ready list

**Next**
- `[P1|S] DB: Schema migrations framework with pre-migration backup`
- `[P1|S] Runner: Scrub child env, process-group kill, output caps, prlimit`
- `[P1|S] Runner: Enforce configured timeout exactly; separate install timeout`
- `[P1|S] Security: Admin login for dashboard + API; Bearer on GET /mcp; Origin/Host check`
- `[P1|M] Studio: Input schema editor (form + raw JSON, generate from example)`
- `[P1|M] DB: Tool version history, diff and rollback`
- `[P1|M] Runner: Run history with bounded output and origin`
- `[P1|M] Security: Per-tool encrypted secrets injected only into that tool`
- `[P1|S] Ops: Scheduled SQLite backup, download and restore`
- `[P1|M] Security: Per-client keys with scopes, rotation and revocation`
- `[P1|M] Runner: Concurrency caps, run queue, per-key rate limits`
- `[P1|L] MCP: Streamable HTTP on the official SDK with list_changed, sessions, conformance tests`
- `[P2|S] Docs: Fix README architecture; remove OMNIFORGE_SCRIPT_HOST`
- `[P2|S] Ops: /healthz and Docker HEALTHCHECK`
- `[P2|S] Connect: Per-client setup snippets (Claude Desktop/Code, Cursor, LibreChat, n8n, Inspector)`
- `[P2|S] Runner: Return exit code and bounded stderr; structuredContent for JSON stdout`

**Backlog**
- `[P1|M] Runner: Runner sidecar container with no DB/secrets/API key`
- `[P1|L] Runner: Per-run namespaces (bubblewrap/nsjail) inside the sidecar`
- `[P2|S] Security: Audit trail of authoring, key and secret events`
- `[P2|S] Connect: Last-seen connected clients from run history`
- `[P2|S] Overview: Onboarding step 4 — "your assistant called it" indicator`
- `[P2|S] Help: Plain-language primer on tools, inputs and connecting`
- `[P2|S] Studio: Error hints for common failures`
- `[P2|S] Studio: Saved example inputs and run-all-examples`
- `[P2|S] Studio: Form-based test inputs rendered from schema`
- `[P2|S] Help: Template gallery (10–15 real-world templates)`
- `[P2|M] Installer: Async dependency preparation with progress`
- `[P2|S] Installer: Environment list, sizes and remove-unused`
- `[P2|M] Installer: Lockfiles with hashes, audit on prepare, allow/deny list`
- `[P2|S] Tools: Import/export bundle format`
- `[P2|S] Deployment: HTTPS profile (Tailscale Serve / Caddy / Tunnel+Access) after auth`
- `[P2|M] Runner: Cron, webhook triggers and cached results per tool`
- `[P2|M] Ops: Structured logs and /metrics`
- `[P3|L] Security: OAuth 2.1 resource server for remote clients`
- `[P3|M] MCP: Resources and prompts`
- `[P3|S] MCP: Built-in omniforge_update_tool with revision guard`
- `[P3|M] Tools: Tags, groups and per-endpoint/key visibility`
- `[P3|S] Tools: Soft delete / trash`
- `[P3|S] Studio: Duplicate tool`
- `[P3|S] Studio: Description quality linting`
- `[P3|S] Studio: Safe defaults (readOnlyHint, short timeout)`
- `[P3|S] Help: Explain missing Install button on insecure contexts`
- `[P3|S] Overview: Copyable "ask your assistant to build it" prompt`
- `[P3|S] Studio: Copy failure report (redacted) for an assistant`
- `[P3|L] Studio: No-code tool types (HTTP, reference text, table lookup)`
- `[P3|S] Connect: One-click client config download`
- `[P3|M] DevEx: Publish /docs behind auth; omniforge CLI`
- `[P3|L] DevEx: Git sync and GitHub Action for validate/test/push`
- `[P3|M] Studio: Draft vs published revisions`
- `[P3|S] Integrations: n8n webhook templates and MCP client node verification`
- `[P3|M] Runner: In-child SDK for tool composition and secrets`
- `[P3|M] Runner: Extra runtimes via uv/Deno`
- `[P3|S] MCP: Progress notifications and cancellation`
- `[P3|M] Backend: Multi-worker safety`
- `[P3|M] Runner: Script egress controls`
- `[P3|S] Repo: Close PR #3 (older workbench) or convert to a reference branch`

## Decisions for David

1. **D1 Transport:** replace the handwritten JSON-RPC with the official `mcp` SDK's Streamable HTTP (my recommendation), or keep extending the handwritten one?
2. **D2 Isolation target:** stop at in-container hardening, add the runner sidecar, or go to per-run namespaces (which likely needs a relaxed seccomp profile on Unraid)?
3. **D3 Who are the clients?** LAN-only clients (per-client keys suffice) or remote hosted clients such as claude.ai connectors (requires OAuth 2.1 and an authorisation server — Authentik, Cloudflare Access, or similar)?
4. **D4 Source of truth:** SQLite stays canonical with export/import, or move towards git-backed tool files?
5. **D5 Scheduling:** build cron into OmniForge, or ship webhook triggers only and let n8n schedule?
6. **D6 HTTPS route:** Tailscale Serve, Caddy with an internal CA, or the existing Cloudflare Tunnel plus Access?
7. **D7 Secrets at rest:** encrypted in SQLite under a master key from the env, or sourced from an external store (Proton Pass/Vault) at run time?
8. **D8 Run history privacy:** store arguments and output (how much, how long), or only metadata?
9. **D9 Admin identity:** single admin password/session, or multiple users from day one?
10. **D10 Environments:** draft/published per tool, or separate dev/prod instances promoted via CLI?
11. **D11 PR #3:** close it now so it can't be merged over the redesign by accident?

If you want, the next step from here is to turn the **Next** column into tracer-bullet tickets with blocking edges (`/to-tickets`) once you've answered D1–D3, since those three change the shape of the P1 work.
