# OmniForge frontend bug check notes (16 Oct 2026)

**Passed checks (no finding):**
- **XSS:** none. Markup in names, descriptions, stdout and stderr renders as text; there is no `innerHTML`.
- **axe:** clean on every screen, editor, output and both dialogs, in both themes, at 375, 768 and 1440 px plus 3 landscape sizes. The only exceptions are FE-17.
- **Layout:** no horizontal overflow at 320, 375, 768, 1440 px or in landscape.
- **Service worker:** caches exactly 12 public assets, never API, MCP or dashboard responses. The offline fallback works, an open tab keeps its draft offline, and old caches are cleaned up.
- **Manifest and icons:** valid; the maskable icon respects the safe zone.
- **Theme:** persists across reloads.
- **API key:** never appears in `/api/config` or the DOM.
- **Large output:** a 40 MB result rendered in about 2.4 s and the page stayed responsive.

**Seen but not filed (backend or documented):**
- `HEAD` requests return 405.
- `/mcp` accepts the raw key without "Bearer", and the key comparison isn't constant-time.
- `notifications/initialized` gets "Method not found" instead of a 202 with no body.
- On the plain-HTTP LAN deployment, the Copy buttons and PWA features don't work.

**Reproduce:** the scripts in `pw-fe\` (e.g. `s4_desc.cjs` for FE-01, `s3_state.cjs` for FE-03), screenshots in `pw-fe\shots\`, and `make_findings.py` to regenerate the JSON. `wsl\fe-copy.sh` runs the deploy simulation on a copy.

**Root causes in the backend:** FE-02, FE-04, FE-11 and the server side of FE-12.
