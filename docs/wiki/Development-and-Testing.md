# Development and testing

## Local set-up

You need Linux, macOS or WSL, plus Python 3.12. Node.js 22 and npm are needed for the dashboard tests and for Node tools. Native Windows Python won't work, because `app/dependencies.py` imports `fcntl`.

```bash
git clone https://github.com/iOnic-Developer/omniforge.git
cd omniforge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdir -p omniforge_data omniforge_lib
export OMNIFORGE_DB_PATH="$PWD/omniforge_data/omniforge.db"
export OMNIFORGE_LIB_ROOT="$PWD/omniforge_lib"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000`. Because that address is `localhost`-equivalent, the service worker and install prompt work locally.

Or build and run the image exactly as CI does:

```bash
docker build -t omniforge:dev .
docker run --rm -p 8000:8000 omniforge:dev
```

## Test suites

| Suite | Files | Needs | What it covers |
|---|---|---|---|
| Python unit and integration | `tests/test_*.py` (`unittest`) | The image, or a venv on Linux | Routes, validation, MCP handler, built-ins, revisions and 412s, dependency caches (mocked installers), JSON stdin, timeouts, asset allow-list, manifest and icons |
| Live package installs (opt-in) | `tests/test_live_examples.py` | The image plus internet, `OMNIFORGE_LIVE_INSTALL_TESTS=1` | Real pip and npm installs of the four dashboard examples, with cached MCP reruns |
| Dashboard DOM and service worker | `tests/dashboard_ui.cjs`, `tests/service_worker.cjs` | Node 22 only. No npm packages | UI logic in a simulated DOM, and worker caching rules |
| Browser and accessibility | `tests/product_browser.cjs` | Playwright, Chromium, axe-core and the local venv | Real Chromium at 375, 768 and 1440 px in both themes, axe WCAG A/AA, keyboard, dialogs, offline navigation, update and install flows, conflict recovery |

The browser suite starts its **own** server on a random port, with a temporary database, library and scratch directory, and an empty API key. It never touches a running instance.

## What CI runs

These are the exact commands from `.github/workflows/test.yml`. Run them from the repository root.

### Job `test`

```bash
# 1. Syntax-check the dashboard's inline script and the service worker
python3 - <<'PY'
from pathlib import Path
page = Path('app/templates/dashboard.html').read_text()
Path('/tmp/dashboard.js').write_text(page.split('<script>', 1)[1].split('</script>', 1)[0])
PY
node --check /tmp/dashboard.js
node --check app/static/sw.js

# 2. Dependency-free DOM and service-worker tests (also: npm test)
node --test tests/dashboard_ui.cjs tests/service_worker.cjs

# 3. Python suite inside the real image (tests are mounted read-only; .dockerignore excludes them from the image)
docker build -t omniforge:test .
docker run --rm -v "$PWD/tests:/app/tests:ro" omniforge:test python -m unittest discover -s tests -v
```

### Job `browser`

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci --ignore-scripts
npx playwright install --with-deps chromium
OMNIFORGE_SCREENSHOTS=test-artifacts/screenshots npm run test:browser
```

CI uploads `test-artifacts/screenshots` as the `product-browser-screenshots` artefact. Locally, leave out `--with-deps` if your system already has Chromium's libraries. `OMNIFORGE_TEST_PYTHON` can point the suite at a different interpreter.

### Opt-in live installs

```bash
docker build -t omniforge:test .
docker run --rm -e OMNIFORGE_LIVE_INSTALL_TESTS=1 \
  -v "$PWD/tests:/app/tests:ro" \
  omniforge:test python -m unittest discover -s tests -p 'test_live_examples.py' -v
```

This downloads `requests` and `lodash` from the public registries into a temporary directory under `/opt/omniforge/lib`.

## Working on the code

### Ground rules the tests enforce

- **No `innerHTML`** in the dashboard. Set dynamic text with `textContent`.
- **One `localStorage.setItem`** call, for `omniforge-theme`. Nothing else is persisted in the browser.
- **Touch targets** are at least 44 px, `button:focus-visible` styles exist, and `prefers-reduced-motion` is respected.
- **The service worker precaches exactly 12 assets**, all of them in `PUBLIC_ASSETS`. It must never cache `/`, `/api` or `/mcp`, requests with an `Authorization` header, or non-GET requests.
- **Saving never executes or installs**, whether through the dashboard API or MCP.
- **Validation errors never echo submitted values.**
- **Security copy stays visible**: the dashboard must keep saying "not ready for public exposure", "not GET /mcp" and "not full Streamable HTTP".

### Adding a static asset

1. Put the file in `app/static/`.
2. Add it to `PUBLIC_ASSETS` in `app/main.py`, with its MIME type.
3. If it should work offline, add it to `ASSETS` in `app/static/sw.js` **and** bump `CACHE`. Then update the count of 12 in `tests/test_product.py` and in the worker tests.

### Adding an environment variable

Read it in the module that needs it, document it in [Configuration](Configuration.md) and the README table, and add it to `docker-compose.yml` if users should normally set it.

### Python dependencies

`jsonschema` and `referencing` are imported by `app/tool_authoring.py` but only reach the image as dependencies of `mcp`. If you ever remove `mcp` from `requirements.txt`, add those two explicitly. `pydantic-settings`, `sse-starlette` and `slowapi` are listed but not imported.

### Design reference

The [product design notes](../product-design.md) record the information architecture, PWA cache contract, accessibility decisions and validation history. Read them before changing the dashboard.

## Contributing

1. Branch from `main`.
2. Make your change, along with tests and documentation (`README.md`, `docs/wiki/`).
3. Push and open a pull request. **Test dashboard** runs both jobs.
4. Merge when green. The push to `main` publishes `dbzocchi/omniforge:latest` (see [Release and deployment](Release-and-Deployment.md)).

---

← [Home](Home.md) · [Next: Glossary →](Glossary.md)
