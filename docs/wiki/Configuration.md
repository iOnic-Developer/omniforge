# Configuration

OmniForge is configured only through environment variables, which it reads **once, at start-up**. After changing a variable, recreate the container. A plain restart keeps the old environment if you edited the compose file without running `docker compose up -d` again.

There is no configuration file, no settings screen and no runtime reload of settings.

## Environment variables

These are all the variables the application reads (`os.environ` in `app/*.py`).

| Variable | Default | Read in | What it does |
|---|---|---|---|
| `OMNIFORGE_API_KEY` | *(empty)* | `app/main.py` | Bearer key required on `POST /mcp`. Empty disables MCP auth. It doesn't protect the dashboard, the REST API or `GET /mcp`. Never returned by any route, but **inherited by every script**. |
| `OMNIFORGE_DB_PATH` | `/opt/omniforge/data/omniforge.db` | `app/database.py` | SQLite database file. The parent directory is created if it's missing and must be writable. |
| `OMNIFORGE_CACHE_TTL_MS` | `5000` | `app/database.py` | How long, in milliseconds, the in-process tool-list cache lives. Any write through the same process clears the cache immediately. The TTL only matters across processes, for example with several workers. |
| `OMNIFORGE_LIB_ROOT` | `/opt/omniforge/lib` | `app/dependencies.py` | Root of the per-tool pip/npm caches. Must be writable by UID 1000. See [Dependencies](Dependencies.md). |
| `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS` | `30000` | `app/runner.py` | Script time limit in milliseconds. The runner **adds 15 seconds**, so the default allows 45 s. The timer starts after dependency preparation. |
| `OMNIFORGE_MAX_SCRIPT_MEMORY_MB` | `512` | `app/runner.py` | **Declared but not enforced.** The value is parsed and then never applied to any process. Use Docker's `--memory` to cap the whole container. |
| `OMNIFORGE_SCRATCH_ROOT` | `/tmp/omniforge` | `app/runner.py` | Shared directory where each script is written as `<tool-id>.py` or `<tool-id>.js`. It is also the working directory for every run. |

> [!IMPORTANT]
> `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS`, `OMNIFORGE_MAX_SCRIPT_MEMORY_MB` and `OMNIFORGE_CACHE_TTL_MS` are parsed with `int()` when the app starts. A value such as `30s` stops the app from starting.

### Variables that have no effect

These appear in the repository's `docker-compose.yml` or in older notes, but the current code never reads them.

| Variable | Status |
|---|---|
| `OMNIFORGE_SCRIPT_HOST` | Historical. The runner uses `OMNIFORGE_SCRATCH_ROOT` instead. |
| `OMNIFORGE_RUNTIME_IMAGE` | Historical, from an older design that started separate runtime containers. Unused. |

### Variables used only by tests

| Variable | Used by | Purpose |
|---|---|---|
| `OMNIFORGE_LIVE_INSTALL_TESTS` | `tests/test_live_examples.py` | Set to `1` to run real pip/npm installs of the four dashboard examples. |
| `OMNIFORGE_SCREENSHOTS` | `tests/product_browser.cjs` | Output directory for browser-test screenshots. Defaults to a temporary directory. |
| `OMNIFORGE_TEST_PYTHON` | `tests/product_browser.cjs` | Python interpreter used to start the test server. Defaults to `.venv/bin/python`. |

### Set by the image

The `Dockerfile` sets these for the app. Because scripts inherit the app's environment, scripts see them too.

| Variable | Value | Effect |
|---|---|---|
| `VIRTUAL_ENV` | `/opt/venv` | The app's virtualenv. |
| `PATH` | `/opt/venv/bin:$PATH` | `python3` resolves to the venv interpreter, for both the app and Python tools. |
| `PYTHONPATH` | `/app` | Lets the app import itself. Python tools get their package cache put in front of this. |
| `PYTHONUNBUFFERED` | `1` | Unbuffered logs. |
| `PYTHONDONTWRITEBYTECODE` | `1` | No `.pyc` files, which helps with read-only roots. |

## Ports

| Port | Protocol | Serves |
|---|---|---|
| `8000` | HTTP | Dashboard (`/`), REST API (`/api/*`), assets, service worker and MCP (`/mcp`) |

The container command is fixed at `uvicorn app.main:app --host 0.0.0.0 --port 8000`, with one worker and no TLS. To use a different port, change the host side of the mapping (`-p 9000:8000`). For HTTPS, put a reverse proxy in front: see [PWA and themes](PWA-and-Themes.md#https-for-installation).

### Workers

The shipped command runs **one** uvicorn worker. The run and MCP handlers block while a script or dependency install is running (see [Security and limitations](Security-and-Limitations.md#availability-one-slow-tool-stalls-everything)), so one long tool holds up every other request. You can override the command:

```bash
docker run … dbzocchi/omniforge:latest \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

The database layer is written with several processes in mind. Writes use `BEGIN IMMEDIATE`, test runs read a fresh snapshot, and package installs use a file lock. Even so, multi-worker operation isn't part of CI. Expect tool lists to lag by up to `OMNIFORGE_CACHE_TTL_MS` between workers.

## Paths and volumes

| Container path | Holds | Persist? |
|---|---|---|
| `/opt/omniforge/data` | `omniforge.db` (all tool metadata and code) | **Yes**: this is your data. |
| `/opt/omniforge/lib` | Per-tool package caches | Recommended. They can be rebuilt, but reinstalling is slow. |
| `/tmp/omniforge` | Scratch copies of scripts and the run working directory | No. tmpfs is fine. |
| `/opt/omniforge/scripts` | Nothing (legacy) | No |
| `/app` | Application code | No. Part of the image. |

Both persistent paths must be writable by UID 1000. Named Docker volumes take the right ownership from the image automatically. **Bind mounts don't**: run `chown -R 1000:1000` on the host directories. More in [Backup and restore](Backup-and-Restore.md).

## Changing the MCP key

1. Set the new `OMNIFORGE_API_KEY` in your compose file, `.env` or Unraid template.
2. Recreate the container: `docker compose up -d` or **Apply** in Unraid.
3. Update every MCP client's `Authorization: Bearer …` header.

The dashboard's **Connect** screen shows whether a key is set, as **Bearer key enabled · value hidden**, but never the value.

---

← [Home](Home.md) · [Next: Dashboard guide →](Dashboard-Guide.md)
