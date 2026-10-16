# OmniForge security review notes (16 Oct 2026)

Only a local WSL instance was tested (`of-start.sh security 18303 test-key`). Proof-of-concept scripts were benign, and all PoC tools and markers were removed. The instance was wiped afterwards.

## Threat model
Real deployment: a single-container app on David's NAS, LAN only, no tunnel, one user, hardened container runtime. Three realistic attackers:

1. A device, person or malware already on the LAN.
2. David's own browser, driven from another origin by CSRF or DNS rebinding. This is the only vector that needs no foothold on the LAN.
3. An LLM or MCP client that holds the bearer key, or a prompt-injected model given it.

Container hardening limits host takeover and persistence. It does NOT stop in-container code execution or theft of the key, the database and all tool source.

## Verified by running
- **Auth coverage:** `/`, `/api/config`, `GET /api/tools`, create, `/run`, `DELETE`, toggle and `GET /mcp` all answer with no credential. Only `POST /mcp` is gated.
- **Code execution with no auth (SEC-01).**
- **Secret and DB exfiltration (SEC-02):** scripts run as uid 1000 with uvicorn as the parent process.
- **The MCP key is equivalent to a shell (SEC-04):** `omniforge_create_tool` makes an active tool with no approval, and calling it returned the server's own key.
- **Cache poisoning (SEC-05):** a script could write into `OMNIFORGE_LIB_ROOT`.
- **No resource limits (SEC-06):** no RLIMITs, a 20 MiB stdout came back whole, and a detached child process survived after the timeout.
- **No rate or size limits (SEC-07):** slowapi is installed but unused, and an 8 MiB request body was accepted.
- **No Host check (SEC-03):** an arbitrary `Host:` header gets 200.
- **Missing headers (SEC-10):** no CSP, X-Frame-Options, Referrer-Policy or HSTS.
- **Errors (SEC-12):** responses are clean 401/422 with no tracebacks; a 422 echoes the request body.

## CSRF, precisely
Classic JSON CSRF is blocked:
- pydantic rejects `text/plain` and form bodies with 422;
- `application/json` needs a preflight, and with no CORS middleware the OPTIONS request gets 405, so the browser blocks it.

The real cross-origin vector is DNS rebinding (SEC-03). After a rebind the requests are same-origin, and because the Host header isn't checked, the server answers for the attacker's hostname.

## Fine (not findings)
- **The dependency installer is well hardened.** Every injection payload was rejected, pip runs with `--only-binary=:all:`, npm runs with `--ignore-scripts`, and the installer environment is scrubbed. Installs use a lock and an atomic rename.
- **No stored or DOM XSS.** The dashboard uses `textContent` and `createElement` throughout.
- **The service worker is conservative.** It caches only an allowlist of public assets, strips credentials, and never caches HTML, `/api` or `/mcp`.
- **No secrets are baked into the image.** `.dockerignore` excludes `.env*` and `*.db`.
- **Revision and overwrite guards are solid.** Updates use `If-Match`, writes use `BEGIN IMMEDIATE`, duplicate creates are rejected, and built-in tool names are reserved.

## Dependencies
`requirements.txt` is fully unpinned. It resolved to fastapi 0.143.2, starlette 1.8.0, pydantic 2.14.1, uvicorn 0.54.0 and mcp 2.3.0, with no known vulnerable versions. The real problems are reproducibility and supply-chain drift, so pin the versions, add a lockfile, and use Dependabot.

## Severity stance
The code-execution findings are rated **high** for the real deployment, not critical. The bar to exploit is a LAN position or a browser rebind. They become **critical** if the app is exposed, tunnelled, shared, or run from the public image without a key. The most dangerous item for a single LAN user is SEC-03: the drive-by rebinding attack needs nothing more than David browsing the web while the service runs.

## Cosmetic
`docker-compose.yml` sets `image: ionic-developer/omniforge:latest`, while the README and CI use `dbzocchi/omniforge:latest`.
