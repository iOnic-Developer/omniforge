# OmniForge product redesign

## Direction and source of decisions

This is a new information architecture, not a reskin of the three-column workbench.
The intended user may never have used an MCP server. The interface introduces one
idea at a time: create a script, inspect a test, then connect a compatible client.

The UI/UX skill's searchable bundle was unavailable. These are deliberate design
decisions informed by its quick-reference and professional-interface rules, not
fabricated database search results. The existing vanilla HTML/JS + FastAPI stack
is retained. No framework or runtime frontend dependency is added.

## Information architecture

- **Overview:** purpose, live saved/enabled counts, first-use create/test/connect
  journey. It does not invent execution history or connected-client analytics.
- **Tools:** separate library; search name/description and filter by state/runtime.
  Plain, spacious rows rather than a permanent clunky tool-menu sidebar.
- **Tool studio:** dedicated route with name, runtime, description, code, a folded
  package section, explicit save/test actions and clearly attributed test output.
- **Connect:** current-origin endpoint and configuration metadata from /api/config,
  copyable HTTP request template, precise transport/auth/security limitations.
- **Help:** first-use guide, the exact original four examples, package/input/output
  contract, keyboard controls, install guidance and troubleshooting.

Hash routes: #overview, #tools, #tools/new, #tools/edit/NAME, #connect, #help.
An existing tool called `new` is unambiguous at #tools/edit/new. Browser history,
links and deep links work without additional server navigation routes. Cancelled
back-navigation restores the active editor URL; it cannot silently discard a draft.
Filters remain in memory when moving between screens. Drafts do not survive reload.

## Identity, tokens and typography

The original mark is an interlocking square frame: a script entering a contained
workspace, then returning an output. It remains recognizable at favicon size.
There are no emoji icons, sparkles, decorative gradients or generic AI motifs.
SVG and PNG favicon, Apple touch, 192/512 and safe-zone maskable icons are provided.

- UI: self-hosted variable **Manrope**; code: **JetBrains Mono**. Both vendored with
  their SIL OFL licenses in app/static/fonts. No external font/CDN requests.
- Warm neutral canvas, ink text, functional teal accent. Semantic surface, muted,
  line, danger, warning and on-accent tokens are paired for light and dark themes.
- Corners: at most 4 px. 4/8 px spacing rhythm; restrained borders and whitespace.
- Desktop: narrow application navigation, wide content, one task-focused editor.
- Phone: four labelled bottom navigation destinations with safe-area padding;
  single-column content and controls; no hidden hover-only actions.
- Native labelled inputs/selects/details/dialogs; explicit focus rings, a skip
  link, contextual live feedback, keyboard code indentation and reduced motion.
- Light/dark/system theme preference is the only localStorage write. System theme
  tracks media changes. No code, auth, results or drafts are stored there.

## Save, execute and destructive-action semantics

Dirty state covers name, runtime, description, code and normalized requirements.
Navigation, template replacement and browser unload warn about unsaved edits.
Save and execution are separate; testing never implicitly saves or runs a draft.

A save captures a snapshot. Edits made while that request is in flight remain in
the editor and stay dirty. Successful writes remain successful even when list
refresh fails, preventing accidental duplicate creation. Renames preserve tool
identity, enabled state and existing input schema. Refresh/toggle never replaces
unsaved editor fields. A toggle changes discovery, not saved code or schemas.

Deleting is explicit and confirmed. Partial example installation reports failures
and skips both existing and concurrently claimed names; it never overwrites or
executes. Built-in names cannot be edited, toggled or shadowed in the UI.

All dynamic tool names/descriptions/results/errors use textContent, not HTML.
API validation errors extract messages only, not submitted input values. Duplicate
names have an inline error. No secrets are fetched, changed or displayed.

## Honest security and transport boundaries

This redesign does **not** make the service publicly safe. Management and dashboard
are unauthenticated; GET /mcp is an unauthenticated SSE stub. Optional Bearer auth
protects MCP POST only. Scripts share the application container and its environment
and writable data. There is no isolated sandbox, OAuth, session tracking, enforced
per-script memory limit, output cap or process-tree termination. The handwritten
MCP transport is limited HTTP JSON-RPC, not full Streamable HTTP. These statements
are visible in the product, not hidden behind marketing claims.

Backend browser-input validation and atomic revision guards are implemented alongside the UI. Existing clients can omit conditional headers for backward compatibility. No auth policy is changed. No production
data edit, deployment, image publishing or merge is part of this review. PR #3 is an
alternative left untouched.

## PWA, cache and update contract

The manifest has root scope, standalone display and explicit regular/maskable icons.
The install control appears only after beforeinstallprompt. Help explains Safari
Share → Add to Home Screen, browser menu options, HTTPS and HTTP LAN limitations.
Execution, package installation and saving are always online-only.

/sw.js is served as application/javascript with no-cache, nosniff and root-scope
permission. Public assets are routed by a literal allowlist; no directory mount
can expose .env, database files, source or traversal paths. Dashboard responses
have Cache-Control: no-store; UI API fetches use no-store.

The worker precaches **12 known public resources** using credentials: omit. It
never caches the dashboard, API, MCP, tool code, results, credentials or non-GET
requests. Auth-header and cross-origin requests bypass it. Navigation is network
first, with **no caching of successful pages**; failures return generic offline
HTML. Runtime static misses are fetched but not added to cache. An offline open
tab preserves its memory-only draft while disabling save/run/toggle/install.

Each release must increment the worker cache version when assets change. Activation
cleans only obsolete OmniForge-public caches. A waiting worker shows Update available;
only accepting that action activates it and reloads the accepting tab. Dirty drafts
require confirmation. Other tabs are not automatically reloaded. Full OS installation
and a multi-version real deployment update are manual acceptance checks, not claimed
as proven by the synthetic prompt/update tests.

## Repeatable validation

Dependency-free tests:

```sh
node --test tests/dashboard_ui.cjs tests/service_worker.cjs
```

Actual browser tests (development dependencies only):

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci --ignore-scripts
npx playwright install chromium
npm run test:browser
```

The suite starts its **own temporary database and server** on an ephemeral port,
never a live service. It covers 375/768/1440 px in both themes, all five screens,
axe WCAG A/AA checks, reduced motion, landscape/large text, native modal focus,
keyboard controls, save/run/toggle/search/delete, errors, browser back dirty guards,
actual offline worker navigation, cache contents and synthetic install/update UX.
`OMNIFORGE_SCREENSHOTS` chooses an output directory (default temporary directory).
`OMNIFORGE_TEST_PYTHON` optionally selects the local venv Python executable.
GitHub CI installs Chromium's dependencies on its disposable runner and uploads
screenshots as an artifact. It does not install packages on the NAS host.

Python regressions and opt-in exact live examples:

```sh
docker build -t omniforge:test .
docker create --name omniforge-tests omniforge:test python -m unittest discover -s tests -v
docker cp tests omniforge-tests:/app/tests
docker start -a omniforge-tests
docker rm omniforge-tests
```

For live pip/npm coverage, use a separate test container with
OMNIFORGE_LIVE_INSTALL_TESTS=1 and run test_live_examples.py. It verifies all four
exact examples and cached MCP reruns; it never touches production tools.

Automated accessibility checks are not a substitute for a human screen-reader
review. Safari/iOS install, real external MCP-client compatibility and public-safe
hosting remain outside the tested scope. No claim of universal PWA installation
or production security is made.

## Review fixes and parameterized browser tests

- Initialize the requested route before the startup library fetch; loading the
  list never refills an already-selected editor or upgrades its saved revision.
- Snapshot the delete target before confirmation and check identity, busy state
  and connection again after approval. All mutations (including Ctrl/Cmd+S)
  are blocked while confirmation or template dialogs are open.
- Test inputs is a labelled, ephemeral JSON-object textarea, default `{}`. It is
  not part of the code draft or browser storage, resets on selection, survives
  save/run errors, and is sent as `{arguments: object}` with JSON Content-Type.
  Browser validation rejects malformed JSON, arrays, null and scalars; the backend
  validates the saved schema. Advanced settings show that schema read-only without
  fetching remote references. No schema editing is introduced.
- Update/delete/run send a raw `If-Match` revision only when available. Successful
  saves adopt the returned revision; HTTP 412 keeps the draft and gives a copy-first
  or reload-from-library recovery message, not a duplicate-name error. List
  refreshes and toggles do not silently upgrade an editor's code/revision baseline.
- Output is attributed to the executed fingerprint, revision and input snapshot.
  Editing, saving a different version or changing inputs labels the retained
  result **Previous version / inputs**, rather than presenting it as current.
- Library rerenders restore the original focused tool/control only when focus was
  inside the old list; disappearing rows use the nearest control or Search tools.
  Short desktop/landscape rails scroll, top actions wrap, and mobile page/toast
  clearance shares a safe-area-aware bottom-navigation token.
- Public cache v2 precaching rejects redirects and unexpected/missing MIME types;
  the worker fetch explicitly disallows redirect-following. Login HTML must not
  substitute for stylesheet, image, font or manifest assets.

Local verification for this review is 36 dependency-free DOM and 12 service-worker
tests (48 passing), plus JS syntax checks. New Playwright regressions cover deferred startup drafts,
modal shortcut blocking, switch focus, JSON arguments, stale output, 412 recovery
and compact layouts. Browser execution is deliberately deferred until the parent
backend changes are complete; API fixtures isolate most UI review tests.

## Final implementation verification — 2026-10-13

Independent review agents checked draft loss, mutation races, focus, result attribution,
responsive overflow and cache safety. Claude CLI was not installed and the local Ollama
endpoint was unavailable, so neither is claimed as a reviewer.

The final browser suite passes 21 tests with actual Chromium, including axe A/AA
checks at 375/768/1440px in light/dark themes, populated libraries, real offline
service-worker navigation, guarded updates, test inputs and conflict recovery.
The DOM/worker suite passes 48 tests. The Docker Python suite is also executed
with real pip/npm example installs under UID 1000, read-only root and restricted
capabilities. Browser testing on the workspace reuses existing extracted Chromium
shared libraries via LD_LIBRARY_PATH; the NAS host is not modified.

Optimistic update/delete/toggle operations compare content revisions inside
BEGIN IMMEDIATE transactions. Conditional execution uses an uncached database
snapshot, preventing another worker's stale cache from accepting old code.
Schema validation precedes execution. No production databases or tools are touched.

Manual screen-reader review, Safari/iOS installation, and real multi-release
updates remain acceptance checks. The existing backend security and MCP transport
gaps remain public-launch blockers; this PR does not deploy the product.
