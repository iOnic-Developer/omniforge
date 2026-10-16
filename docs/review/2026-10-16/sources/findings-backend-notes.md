# OmniForge backend bug check notes (16 Oct 2026)

**Setup:** an isolated WSL instance on 127.0.0.1:18301 with `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS=2000`, so the real timeout is about 17 seconds. The only real install was `requests` (latest, then `==2.32.3`). Old-version data was simulated by inserting rows directly into the instance's own SQLite file. The live instance, nucnas and LibreChat were never touched. The instance was wiped afterwards.

**Tests** (WSL, Python 3.12.15, Node 22.20.0): 60 ran, 57 passed, 2 errors, 1 skipped.
- **Errors:** "npm runtime is unavailable". The installer's PATH is hardcoded, so these only pass in the Docker image (BE-15).
- **Skipped:** `test_live_examples` is opt-in and container-only.
- **Not run:** the Node, Playwright and Docker builds.

**Test gaps.** Nothing covers:
- a real timeout kill, or a child process holding the output pipes;
- non-UTF-8 output, output size, or exit code 124 versus a real timeout;
- JSON-RPC notifications, malformed requests or batches;
- version negotiation and the `ping` result;
- cross-origin requests;
- old schemas or duplicate names;
- 422 responses echoing input;
- PUT defaults;
- cleanup after a crashed install.

`test_dependencies` asserts that scripts DO get `OMNIFORGE_API_KEY`, which locks BE-10 in place.

**Backend/frontend mismatches:**
- A dashboard save always resends the stored schema, so an old-style schema makes every save fail with 422, and there's no UI schema editor to fix it (BE-05).
- A dashboard delete always sends `If-Match`, which can never succeed for a duplicated name; the UI shows a misleading message (BE-06).

**Healthy:**
- Static files come from an allowlist; `.env` and the database return 404.
- `/api/config` discloses only the auth flag.
- Tool-name rules and reserved names are enforced on both paths; create refuses to overwrite.
- Duplicate and rename checks run inside a locked transaction.
- Stale-revision checks return 412.
- Arguments are validated against the schema (remote refs rejected) and passed as JSON on stdin.
- The key is enforced on every POST `/mcp` method.
- The installer is properly hardened: minimal environment, official registries only, wheel-only pip, npm `--ignore-scripts`, no flags allowed, atomic publish, OS-released locks, redacted errors.

**Not checked:**
- No Docker build; container behaviour is inferred from the Dockerfile.
- No live npm install.
- No unreachable-registry simulation.
- No real MCP client.
- DNS rebinding.
- Two findings from reading only: BE-17 (package cache reused across runtime versions) and BE-25 (very large descriptions).
- Slow regexes in input schemas.
