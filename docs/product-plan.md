# OmniForge product plan

## Implementation state — 2026-10-13

Review branch: `feat-professional-workbench`, based on main `28161d0` (PR #2).
This work is not deployed. The product remains a trusted-network developer tool,
not a production-ready public execution platform.

## Product and visual direction

A focused developer workbench, not a landing page: library → code → settings.
Preserve the lightweight FastAPI/vanilla-JS stack. No new runtime UI dependency.
Semantic surface/text/border/state tokens, system typography, monospaced source,
4px maximum corner radius, 44px controls, clear focus and responsive stacked panels.
Palette and layout use general accessibility/design defaults; no verified skill
search-database output was available. The custom forge/anvil F mark is shared by
favicon and deterministic PNG icons, with a padded maskable version.

## Primary flows and acceptance

| Flow | Acceptance |
| --- | --- |
| Create | New tool → metadata/code → save; errors retain fields; create never overwrites a saved name. |
| Edit | Visible unsaved state; switching scripts requires confirmation; cancelled switch preserves all fields. Save shows progress and preserves edits made during an in-flight request. |
| Test | Save before run; first-run dependency notice; real stdout/stderr/exit/duration or actionable HTTP error; no simulated output. |
| Discover | Toggle hides from MCP discovery without deleting; built-in tools remain available. Existing templates, install examples, Config and Help stay functional. |
| Personalise | Light/dark/system choice persists locally; system changes apply only in system mode; native controls and browser theme color follow resolved theme. |
| Mobile/install | Panels stack without page overflow; manifest/icons have explicit routes and MIME; install hint distinguishes insecure LAN HTTP from HTTPS/localhost. Installation remains browser-dependent. |

## Honest PWA boundary

Manifest, standalone display, icons and browser theme color are implemented.
No service worker, cache storage, offline dashboard/scripts/outputs, background
sync, offline execution or fabricated connection tracking. HTTPS/localhost is an
installation prerequisite, not proof of installation or security. Keep the
service trusted-network-only even behind HTTPS until management auth is fixed.
Manual cross-browser installation, keyboard and visual checks remain release gates.

## Prioritised roadmap

1. **Review this workbench:** regression suite, browser checks at 375/768/1440px,
   light/dark, keyboard-only operation, reduced motion and 200% zoom. Merge/deploy
   only with David's separate approval; retain data/credentials/native Unraid setup.
2. **Security gate before public exposure:** authenticated/authorised dashboard and
   every management/MCP route, origin/CSRF policy, safe credential scoping and
   rotation, audit trail. Current management API is unauthenticated; GET MCP also
   lacks POST authentication. HTTPS alone does not fix these blockers.
3. **Execution gate:** replace shared subprocess trust with a deliberately selected
   isolation boundary; protect DB/env, process-tree cancellation, hard output and
   resource caps, network/package policies. Do not expose an unrestricted host
   Docker socket. Current scripts share app container access; installers can block.
4. **Protocol gate:** official SDK/compliant transport, lifecycle/session/discovery
   updates, schemas and real-client integration tests; current transport is limited.
5. **Operational gate:** consistent backups and tested restore, immutable releases,
   bounded asynchronous execution jobs with cancellation and truthful progress,
   dependency diagnostics, health/metrics and accessible error recovery.
6. **Workflow depth after gates:** version history/rollback, input-schema editor and
   JSON test inputs, searchable library, client onboarding, least-privilege roles.
   Each requires working backend contracts and tests, not decorative UI stubs.

## Release criteria

Automated regressions green; documented visual/browser checks; no sensitive offline
cache; no false isolation/compliance/auth claims; existing tools and dependencies
preserved. Public readiness additionally requires the security/execution/protocol
and operational gates above. This PR does not merge, publish, or deploy anything.

## Verification — 2026-10-13

46 Python tests passed, including the opt-in real requests/lodash installs and
all four existing templates. Image built on the workspace private Docker engine;
tests ran as UID 1000 with read-only root, dropped capabilities, no-new-privileges,
noexec scratch and writable executable library tmpfs. JavaScript syntax, expanded
DOM harness, actual ASGI manifest/icon routes, MIME/PNG dimensions, asset allowlist,
radius ceiling and text contrast checks passed. Playwright was not already
available: no interactive visual/responsiveness, install or cross-browser checks
were performed. DOM tests are not browser rendering tests.

Installability reference: MDN, Making PWAs installable (checked 2026-10-13):
https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable
A service worker is not an installation requirement; this design deliberately
avoids offline caching. Installation support still varies by browser/platform.
