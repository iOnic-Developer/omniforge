# OmniForge full re-review (16 October 2026)

Lead re-review of `main` = `4ae443d` (the live build). Every reviewer claim was checked against the code; the unverified, low-confidence and Gemini claims were re-run on a throwaway WSL instance (`of-start.sh rereview 18307`, wiped afterwards; nothing on nucnas or the live instance was touched; all test tools were benign and deleted). Repro scripts and raw results are in `rr/` next to this report (`checks.py`, `phase1.json`, `legacy.py`, `redos.py`, `make_final.py`).

Severity and priority are for the real deployment: one user, LAN only, plain HTTP, no tunnel, key set, hardened container (UID 1000, read-only root, caps dropped). Notes say where the rating changes if the app is exposed or run keyless from the public image.

## Executive summary

- 59 incoming claims (26 backend, 21 frontend, 12 security, 5 Gemini, plus the verified defects in the features and LibreChat reviews) merge into 53 bugs: 48 CONFIRMED, 5 PLAUSIBLE; 3 P0, 9 P1, 20 P2, 21 P3; 6 high, 11 medium, 36 low. 12 sit inside documented limitations (`known: true`). 8 claims or ratings were refuted or downgraded.
- The live instance is exploitable from a browser today. Any web page opened on the LAN can blind-fire `POST /api/tools/<name>/run` and `/toggle` (no preflight, verified), and because no `Host`/`Origin` is checked, a DNS-rebinding page gets full same-origin access to the management API, i.e. in-container code execution plus the MCP key and database. Both fixes are small (BUG-001, BUG-002).
- The studio has a silent data-loss bug: `field('description')` matches `<meta name="description">`, so every description typed in the dashboard is discarded and never shown (BUG-003). Dashboard-authored tools reach the LLM with no description. One-line fix.
- The rest of the high tier is the known execution model: one worker, blocking `subprocess.run` and installs on the event loop (verified: concurrent runs serialise, `/api/config` waited 5.5 s), the full environment including `OMNIFORGE_API_KEY` handed to every script, and no auth on `/api/*`.
- Fresh sweep found three new defects: a ReDoS through `inputSchema.pattern` that blocks the whole server (4.4 s for a 27-character input, doubling per character), Copy buttons that always fail on the plain-HTTP LAN origin, and the absence of any cache pruning.
- Gemini's headline "concurrency race on the fixed scratch path" is refuted for the live build: the blocking loop serialises runs. It becomes a real constraint on the fix for the blocking model. Its lock-race claim is also refuted; its other three claims duplicate verified findings.
- The MCP transport is hand-rolled while the official `mcp` SDK is installed and unused; four conformance bugs (notifications, batches, version negotiation, `GET /mcp`) disappear together if the SDK transport is adopted.
- Healthy: installer hardening, revision guards, name/schema/argument validation, no XSS sinks, conservative service worker, static allow-list, parameterised SQL. The three service-worker defects cannot trigger on the real deployment because the worker never registers over plain HTTP.

## P0 list

| ID | Title | Why P0 | Fix |
|---|---|---|---|
| BUG-001 | No Host/Origin validation: DNS-rebinding page gets full same-origin API and `/mcp` access | Drive-by RCE plus key/DB theft from any page David visits; needs no LAN foothold | `TrustedHostMiddleware` with an explicit allow-list, Origin / `Sec-Fetch-Site` check on mutating routes and `/mcp` (S) |
| BUG-002 | Body-less `POST /run` and `/toggle` are CORS simple requests | Verified cross-origin execution and toggling with no preflight; example tool names are guessable | Require `Content-Type: application/json` plus a custom header, or same-origin `Sec-Fetch-Site`, on all POST/PUT/DELETE (S) |
| BUG-003 | Studio description bound to `<meta name="description">` | Every typed description silently lost; tools published unlabelled | `document.getElementById('toolForm').elements[name]` plus a real-browser regression (S) |

## Fix themes

1. No auth boundary (BUG-001, 002, 006, 013, 018, 026, 037, 039, 040). Strategy: `TrustedHostMiddleware` plus Origin/`Sec-Fetch-Site` checks and a custom-header requirement on every mutating route first (hours of work, closes both P0s); then a single-user session login for the dashboard and the same gate on `/api/*`; fail closed when the key is empty; `hmac.compare_digest`; security headers; a value-free `RequestValidationError` handler.
2. Blocking execution model (BUG-004, 019). Strategy: `asyncio.create_subprocess_exec` (or `anyio.to_thread.run_sync`) for runs, installs in a worker thread, a per-tool and global semaphore, no sleep-polling for the lock; argument validation off the loop with a time limit (or the `regex` module). Because runs will then overlap, this must land together with per-run scratch directories (BUG-015), which is also what makes Gemini's race claim true after the fix.
3. Runner output and process handling (BUG-005, 009, 010, 014, 015, 017, 021, 023). Strategy: allow-listed script environment mirroring `_installer_environment`; `start_new_session=True` plus `os.killpg` on timeout and stop reading pipes after the main process exits; bounded capture with a truncation marker; bytes decoded with `errors='replace'`; per-run temp dir as cwd and `python -P`; a real `timed_out` flag; rlimits via `preexec_fn`; keep the lib root out of the script env.
4. Handwritten MCP transport (BUG-007, 008, 024, 025). Strategy: mount the installed official `mcp` SDK's Streamable HTTP transport at `/mcp` with the dynamic registry as the tool provider (gets notifications, batches, sessions, version negotiation, Origin check, `list_changed` and `structuredContent` for free). If that is deferred: parse the raw body after auth, 202 for notifications, `-32700/-32600`, `{}` for ping, `-32602` for unknown tools, stdout-only text on success with stderr in a separate item.
5. Data lifecycle and legacy rows (BUG-016, 020, 022, 033, 036, 038). Strategy: a startup report (and one-off migration) for duplicate names and non-object schemas; conditional delete/update by id; PATCH semantics for PUT; sweep stale staging dirs under the lock and unreferenced digests on delete/change; runtime version in the cache key; fresh single-row reads in `tools/call`.
6. Dashboard correctness (BUG-003, 011, 012, 028-032, 042-053). Strategy: scope form lookups to the form; re-fetch the library on navigation/focus and after 412/404; a schema builder; `execCommand('insertText')` for indentation; the small copy, a11y and layout fixes; a clipboard fallback for HTTP.
7. Release, image and dependency hygiene (BUG-027, 034, 035, 041). Strategy: declare and pin dependencies, run the suites before pushing `:latest`, align the compose image name, add `/healthz` plus `HEALTHCHECK`, pin a supported Node, derive npm from the node binary.

## All bugs

| ID | Pri | Sev | Eff | Status | Known | Title | Sources |
|---|---|---|---|---|---|---|---|
| BUG-001 | P0 | high | S | CONFIRMED |  | No Host or Origin validation: a DNS-rebinding page gets full same-origin access to the management API and /mcp | SEC-03, BE-11, GEM-02, R-09 |
| BUG-002 | P0 | high | S | CONFIRMED | yes | Body-less POST /api/tools/{name}/run and /toggle are CORS 'simple requests': any web page on the LAN can execute or disable tools | BE-11, FE-04 |
| BUG-003 | P0 | high | S | CONFIRMED |  | Studio description field is bound to <meta name="description">: typed descriptions are silently discarded and never displayed | FE-01 |
| BUG-004 | P1 | high | M | CONFIRMED | yes | Tool execution, pip/npm installs and the lock busy-wait run synchronously inside async handlers and freeze the whole server | BE-01, FE-02, R-08, GEM-TR4, U-08 |
| BUG-005 | P1 | high | S | CONFIRMED | yes | Scripts inherit the full application environment, including OMNIFORGE_API_KEY, DB and lib paths | BE-10, SEC-02, GEM-03, R-04 |
| BUG-006 | P1 | high | M | CONFIRMED | yes | Dashboard and management API are unauthenticated: create + run is arbitrary code execution for anyone who reaches the port | SEC-01, R-01, B-03, FE-04 |
| BUG-007 | P1 | medium | S | CONFIRMED |  | JSON-RPC envelope handling is non-conformant: notifications get error replies, batches and malformed bodies get FastAPI 422 before auth | BE-04, BE-18, R-09 |
| BUG-008 | P1 | medium | S | CONFIRMED |  | Successful tools/call results append '[stderr] ...' to the stdout text, breaking JSON output | BE-03 |
| BUG-009 | P1 | medium | S | CONFIRMED | yes | Child processes that inherit the pipes turn a successful run into a 'timeout', and the timeout kills only the direct child | BE-08, SEC-06, GEM-04, R-06 |
| BUG-010 | P1 | medium | S | CONFIRMED | yes | stdout/stderr capture is unbounded and returned in full | BE-09, SEC-06, R-07 |
| BUG-011 | P1 | medium | S | CONFIRMED |  | Library list is never re-fetched on navigation: the advertised 412 recovery loops forever and MCP-created or externally deleted tools are invisible | FE-03 |
| BUG-012 | P1 | medium | M | CONFIRMED | yes | Studio cannot create or edit inputSchema: every dashboard-authored tool is parameterless | F-02, I1, features: read-only inputSchema |
| BUG-013 | P2 | medium | M | CONFIRMED | yes | MCP bearer key is equivalent to a shell: omniforge_create_tool makes an active tool with no approval step | SEC-04, R-02 |
| BUG-014 | P2 | medium | S | CONFIRMED |  | Non-UTF-8 script output discards the real stdout and exit code | BE-02 |
| BUG-015 | P2 | medium | S | CONFIRMED |  | All tools share one cwd that is also sys.path[0]; scratch scripts are never removed | BE-07, RR-08, GEM-01 (follow-on) |
| BUG-016 | P2 | medium | S | PLAUSIBLE |  | Legacy duplicate-name rows are advertised twice in tools/list and cannot be deleted from the dashboard | BE-06 |
| BUG-017 | P2 | medium | M | CONFIRMED | yes | Cross-tool dependency-cache poisoning via the writable, script-reachable OMNIFORGE_LIB_ROOT | SEC-05 |
| BUG-018 | P2 | low | S | CONFIRMED | yes | Empty OMNIFORGE_API_KEY silently disables MCP auth while the image binds 0.0.0.0 | SEC-09, B-03 |
| BUG-019 | P2 | low | S | CONFIRMED |  | Catastrophic regex in a tool's inputSchema 'pattern' blocks the event loop on every call (ReDoS) | RR-01 |
| BUG-020 | P2 | low | S | CONFIRMED |  | PUT /api/tools/{name} silently re-enables a disabled tool and wipes its input schema when fields are omitted | BE-22 |
| BUG-021 | P2 | low | S | CONFIRMED |  | Timeout accounting: exit code 124 is reported as a timeout, the message states the configured limit not the effective one, and partial output is discarded | BE-12, FE-11, BE-13 |
| BUG-022 | P2 | low | S | CONFIRMED |  | Dependency cache hygiene: crashed installs leave .install-* staging trees, and old digests and deleted tools' caches are never pruned | BE-14, GEM-TR5, R-22, RR-02 |
| BUG-023 | P2 | low | S | CONFIRMED | yes | OMNIFORGE_MAX_SCRIPT_MEMORY_MB is declared but never enforced; no rlimits on scripts | SEC-06, R-06, R-17 |
| BUG-024 | P2 | low | S | CONFIRMED |  | initialize echoes any protocolVersion (even empty), ping returns null, unknown tools are not protocol errors | BE-19, R-09 |
| BUG-025 | P2 | low | S | CONFIRMED | yes | GET /mcp is an unauthenticated SSE stub that emits a made-up event and closes | BE-20, SEC-11 |
| BUG-026 | P2 | low | S | CONFIRMED |  | REST 422 responses echo submitted code and arguments | BE-23, SEC-12 |
| BUG-027 | P2 | low | M | CONFIRMED |  | Release hygiene: unpinned and undeclared dependencies, :latest pushed without tests, compose/image drift, no health endpoint, HEAD 405 | BE-26, R-18, R-19, I9 |
| BUG-028 | P2 | low | S | CONFIRMED |  | Tab/Shift+Tab indentation uses setRangeText, which wipes the editor's undo history | FE-06 |
| BUG-029 | P2 | low | S | CONFIRMED |  | Connect 'HTTP request template' omits Content-Type: application/json | FE-08, U-04 |
| BUG-030 | P2 | low | S | CONFIRMED |  | Tool-name pattern attribute is an invalid v-flag regex: client-side validation is silently disabled | FE-09 |
| BUG-031 | P2 | low | S | CONFIRMED |  | Validation feedback in the studio is generic or hidden: schema errors give no path, package errors leave the Packages section collapsed | FE-12, B-02, U-01 |
| BUG-032 | P2 | low | S | CONFIRMED |  | Copy buttons never work on the plain-HTTP LAN origin the real deployment uses | RR-03 |
| BUG-033 | P3 | low | S | PLAUSIBLE |  | Tools saved by earlier versions with non-object schemas become unrunnable and unsaveable from the dashboard | BE-05 |
| BUG-034 | P3 | low | S | CONFIRMED |  | Installer PATH is hard-coded, so npm is not found outside the Docker image layout | BE-15 |
| BUG-035 | P3 | low | S | CONFIRMED |  | Requirement validation accepts archive filenames and rejects canonical .postN/.devN pins | BE-16 |
| BUG-036 | P3 | low | S | PLAUSIBLE |  | Dependency cache key ignores the interpreter and Node version | BE-17 |
| BUG-037 | P3 | low | S | CONFIRMED |  | API key comparison is not constant-time; the raw key is accepted without the Bearer scheme; 401 lacks WWW-Authenticate | BE-21, SEC-08 |
| BUG-038 | P3 | low | S | CONFIRMED |  | MCP tools/call executes from the 5-second process cache while dashboard runs read fresh rows; PUT without If-Match can resurrect a deleted id | BE-24, R-21 |
| BUG-039 | P3 | low | S | CONFIRMED |  | No size limits on code, description, schema or request bodies, and no rate limiting (slowapi installed but unused) | BE-25, SEC-07, R-16 |
| BUG-040 | P3 | low | S | CONFIRMED |  | No security headers on the dashboard (CSP, X-Frame-Options, Referrer-Policy, nosniff on HTML) | SEC-10 |
| BUG-041 | P3 | low | S | PLAUSIBLE |  | Node runtime in the image comes unpinned from Debian apt and is an end-of-life line | R-20, RR-04 |
| BUG-042 | P3 | low | S | CONFIRMED |  | After a deploy the new dashboard HTML is rendered with the old cached CSS/fonts until 'Update available' is accepted | FE-05 |
| BUG-043 | P3 | low | S | CONFIRMED |  | Test inputs and displayed output are round-tripped through JS numbers | FE-07 |
| BUG-044 | P3 | low | S | CONFIRMED |  | 'Update available' stays visible and does nothing in other tabs after the update is accepted elsewhere | FE-10 |
| BUG-045 | P3 | low | S | CONFIRMED |  | Offline fallback says 'Your workspace is online.' and ignores dark mode | FE-13 |
| BUG-046 | P3 | low | S | CONFIRMED |  | Connection indicator dot is always accent-coloured; Ctrl+S offline gives no feedback | FE-14 |
| BUG-047 | P3 | low | S | CONFIRMED |  | Enable/disable switch's accessible name is the action, contradicting its state | FE-15 |
| BUG-048 | P3 | low | S | CONFIRMED |  | 'Escape, then Shift+Tab' does not leave the code editor and unindents the line instead | FE-16 |
| BUG-049 | P3 | low | S | CONFIRMED |  | Scrollable output and request-template regions are not focusable (axe scrollable-region-focusable) | FE-17 |
| BUG-050 | P3 | low | S | PLAUSIBLE |  | viewport-fit=cover without left/right safe-area padding in phone landscape | FE-18 |
| BUG-051 | P3 | low | S | CONFIRMED |  | Cancelling a dirty Back navigation overwrites the previous history entry | FE-19 |
| BUG-052 | P3 | low | S | CONFIRMED |  | Every keystroke rebuilds the whole line-number gutter | FE-20 |
| BUG-053 | P3 | low | S | CONFIRMED |  | At 320 px the editor footer squeezes 'Run / Test' onto three lines | FE-21 |

## Refuted or downgraded claims

| Source | Claim | Reason |
|---|---|---|
| GEM-01 | Concurrency race on the fixed scratch path (High) | Not reachable in the live build: one worker and a blocking loop serialise runs (verified 3.02 s / 6.04 s), and both interpreters read the whole file before executing. Becomes a constraint on the BUG-004 fix (folded into BUG-015). |
| GEM-05 | Race between the `.complete` check and `staging.rename()` | Both happen while the per-digest exclusive `flock` is held; no interleaving is possible. |
| GEM-02 (severity) | DNS rebinding rated Critical | Mechanism confirmed (BUG-001) but high, not critical, for a single-user LAN with container hardening; critical if exposed. |
| SEC-12 (part) | `/api/config` discloses the auth posture | By design and secret-free; the dashboard needs it. The 422-echo half is kept (BUG-026). |
| FE-02 | Separate "Run / Test blocks the server" finding | Same defect as BE-01; merged into BUG-004. |
| FE-05, FE-10, FE-13 (severity) | Medium service-worker/offline defects | Real in code and on the HTTPS copy, but the worker never registers on the plain-HTTP LAN origin (verified `isSecureContext=false`), so they cannot trigger today. P3. |
| RR (own) | Legacy rows with `language` values the new select cannot show | The 42a5dd1 dashboard already used `python3`/`node`; dropped. |
| librechat-fable.md | Docs-only review | Restates known limitations; nothing new or wrong. |

## What is healthy

- Installer: minimal environment, official registries only, `--only-binary=:all:`, `--ignore-scripts`, strict name validation (every injection payload rejected), file lock, atomic rename, redacted bounded errors. Gemini's lock race is not real.
- Writes: `BEGIN IMMEDIATE`, content-hash revisions with `If-Match` -> 412, duplicate and reserved-name checks inside the transaction, create never overwrites.
- Validation: names, languages, schemas (local refs only, Draft 2020-12) and arguments are checked on both the REST and MCP paths before any code runs; arguments go in on stdin, never through a shell.
- Dashboard: `textContent`/`createElement` only, no XSS sink found by two reviewers; axe clean apart from the focusable-scroller rule; no secrets in `/api/config` or the DOM.
- Static serving: 14-file allow-list, `.env`/DB unreachable, `nosniff` on assets; service worker caches only 12 public assets, never HTML/API/MCP, strips credentials, cleans old caches.
- Image: non-root, read-only-root compatible, no secrets baked in; dependency versions resolved today have no known vulnerabilities.

## Test gaps

- No real-browser test exercises a typed description end to end; the fake-DOM suite lacks `<meta name="description">` and so passes with BUG-003 present.
- `tests/test_dependencies.py` asserts that scripts receive `OMNIFORGE_API_KEY`, locking BUG-005 in place; invert it.
- Nothing covers: a real timeout kill or a child holding the pipes; non-UTF-8 or oversized output; exit 124 vs a real timeout; JSON-RPC notifications, batches and malformed envelopes; version negotiation and the `ping` result; cross-origin and foreign-`Host` requests; duplicate names and legacy schemas; 422 bodies echoing input; PUT with omitted fields; cleanup after a crashed install; ReDoS patterns; the 320 px viewport in the axe matrix.
- Two unit tests only pass inside the image (hard-coded npm PATH, BUG-034). The publish workflow runs no tests at all (BUG-027).
- No MCP conformance test against a real client or the MCP Inspector; the README admits no third-party client has been verified.

## Reviewer appraisal

- Backend (BE-01..26): excellent. 24 of 26 verified by running with precise evidence; every claim confirmed, including the two read-only ones (BE-17, BE-25) which hold up in code. Severities were sound; I merged BE-04/BE-18 and BE-12/BE-13/FE-11 and downgraded BE-05 to PLAUSIBLE/P3 because the old dashboard could not produce such rows. Its notes correctly flagged the test that locks the env leak in.
- Frontend (FE-01..21): excellent and the most valuable single find (FE-01), reproduced here in Chrome 155. All 21 confirmed in code (FE-18 remains PLAUSIBLE, as it said). Three service-worker items were over-rated for the real deployment because the worker cannot register over plain HTTP; the reviewer's own notes mention this but the severities did not reflect it. It also spotted, but did not file, the Copy-button failure (now BUG-032).
- Security (SEC-01..12): accurate threat model and honest severity stance (high, not critical, for the LAN). All 12 confirmed; SEC-03 is the right headline. SEC-06 bundles three distinct runner defects, split here. SEC-12's `/api/config` half is design rather than defect. Its "CSRF, precisely" section is the clearest statement in the inputs of why only `/run` and `/toggle` are blind-fireable.
- Gemini (unverified): 2 of 5 claims wrong (the headline race and the lock race, both refuted), 3 duplicates of verified findings with inflated severity. Its "top risks" list correctly named disk growth from unpruned caches, now BUG-022. Treat as a prompt for verification, not a source.
- Features and LibreChat reviews: the defects they cite (env leak, blocking, uncapped output, child-only kill, read-only schema, transport non-conformance, Node EOL, CI gating) all check out and are mapped to bugs; no new or incorrect defect claims.
