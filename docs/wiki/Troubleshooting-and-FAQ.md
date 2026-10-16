# Troubleshooting and FAQ

Start with the container logs. They show uvicorn's request log and any start-up traceback:

```bash
docker logs --tail 100 omniforge
```

## The container won't start

| Log shows | Cause | Fix |
|---|---|---|
| `sqlite3.OperationalError: unable to open database file`, or `PermissionError … /opt/omniforge/data` | The data path isn't writable by UID 1000, which is typical with bind mounts | `chown -R 1000:1000 <host data dir>` |
| `ValueError: invalid literal for int() with base 10` | `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS`, `OMNIFORGE_MAX_SCRIPT_MEMORY_MB` or `OMNIFORGE_CACHE_TTL_MS` isn't a whole number | Use plain integers, such as `30000` |
| `exec format error` | The host isn't `amd64`. The published image is `linux/amd64` only | Build locally on that host with `docker build -t omniforge .` (untested on other architectures) |
| `ModuleNotFoundError: No module named 'fcntl'` | Running from source on native Windows | Use Docker, WSL, Linux or macOS |
| `Bind for 0.0.0.0:8000 failed: port is already allocated` | Something else is using port 8000 | Map another host port: `-p 8010:8000` |

## The dashboard

| Symptom | What's going on |
|---|---|
| Top bar says **Server unavailable** and *Couldn't load your tools* | The browser can't reach `/api/tools`. Check the container is running and the address and port are right, then select **Try again**. |
| The whole page hangs for a while, then recovers | A tool is running or installing packages. The server handles one thing at a time. See [Security and limitations](Security-and-Limitations.md#availability-one-slow-tool-stalls-everything). |
| **Install app** never appears | You're on plain HTTP over the LAN. Installation needs HTTPS or `localhost`. See [PWA and themes](PWA-and-Themes.md). |
| **Update available** won't go away in another tab | Only the tab where you accepted the update reloads. Reload the others yourself. |
| *You're offline…* banner | Your device lost its connection. Your draft is safe in the tab. Reconnect to save or run. |
| A **Reconnect** page instead of the dashboard | The installed app couldn't reach the server when it opened. |

## Saving and editing

| Message | Meaning and fix |
|---|---|
| *That name is already taken…* (HTTP 409) | Another tool, possibly disabled, has that name. Pick another one. |
| *This name is reserved for a built-in helper.* | `omniforge_instructions` and `omniforge_create_tool` are reserved. |
| *Invalid tool name: use a letter followed by up to 62 letters, digits, underscores or hyphens* | Fix the name. No spaces or dots. |
| *HTTP 412: Changed in another tab/client; draft retained…* | Someone or something changed the tool after you opened it. Copy your draft somewhere, open the tool again from **Tools**, and reapply your edits. |
| *Invalid requirement: use Python name or name==version; …* | A package line breaks the rules. See [Dependencies → Accepted forms](Dependencies.md#accepted-forms). |
| *Tool saved, but the library refresh failed. Retry from Tools; do not recreate it.* | The save worked. Only the list reload failed. |

## Running and testing

| Message or symptom | Meaning and fix |
|---|---|
| *Arguments do not match inputSchema* (HTTP 422 or `isError`) | The inputs don't fit the schema. A tool made in the dashboard has **no inputs**, so only `{}` is accepted. Add a schema via the API or MCP: see [Writing tools → Giving a tool inputs](Writing-Tools.md#giving-a-tool-inputs). |
| *Enter a valid JSON object…* | Test inputs must be a JSON object such as `{}` or `{"net": 10}`, not an array, string or `null`. |
| **Run / Test** is greyed out | Save first. Testing always uses the saved version. It's also disabled while offline or while another action is running. |
| `(no output)` | The script printed nothing. Use `print(...)` or `console.log(...)`. A returned value isn't captured. |
| `Script exceeded 30000ms timeout` (after about 45 s) | The script ran past the limit (configured value + 15 s). Make it faster, add timeouts to network calls, or raise `OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS`. |
| A timeout although the script finished quickly | The script exited with code **124**, which OmniForge treats as "timed out". Use a different exit code. |
| `SyntaxError` or a traceback on the first run | Code isn't checked on save. Fix the error and save again. |
| `ModuleNotFoundError` or `Cannot find module` despite a requirement | The package name and the import name can differ (`beautifulsoup4` → `import bs4`, `pyyaml` → `import yaml`). For Node, use `require`, not `import`. |
| `Dependency installation failed; script was not run: …` | Read the excerpt. Usually there's no wheel for Python 3.12 on x86-64, the name is wrong, or there's no internet. More in [Dependencies → Failure modes](Dependencies.md#failure-modes). |
| `Incomplete dependency cache exists; administrator review required` | Remove that one cache directory. See [Dependencies → Cleaning up](Dependencies.md#cleaning-up). |
| The first run is very slow, later runs are fast | The first run installs packages. Later runs reuse the cache. |
| MCP output has `[stderr] …` after the JSON | The script wrote warnings to stderr on a successful run. Silence them so clients get clean JSON. |

## MCP clients

See the [connection troubleshooting table](Connecting-MCP-Clients.md#when-it-doesnt-connect). The most common issues:

- **401 Unauthorized:** the header must be exactly `Authorization: Bearer <key>`, matching `OMNIFORGE_API_KEY`.
- **A new tool doesn't appear:** refresh or reconnect the client. OmniForge sends no notifications.
- **The client insists on SSE or OAuth:** that client needs full Streamable HTTP, which OmniForge doesn't implement.

## FAQ

**Can I put OmniForge on the internet?**
No. The dashboard and management API have no authentication, and scripts aren't isolated. See [Security and limitations](Security-and-Limitations.md).

**Does disabling a tool stop it from running?**
Over MCP, yes: it disappears from `tools/list`, and `tools/call` returns `Unknown or inactive tool`. The dashboard's Run / Test and `POST /api/tools/{name}/run` still run it.

**Where are my tools stored?**
In the SQLite file `/opt/omniforge/data/omniforge.db`. See [Backup and restore](Backup-and-Restore.md).

**Will updating the image delete my tools?**
No, as long as `/opt/omniforge/data` is on a volume or bind mount. Back up before updating anyway.

**Can a tool call another tool, or OmniForge's own API?**
Not safely. While a tool runs, the server is busy waiting for it, so a request from the tool back to OmniForge hangs until the tool times out. Put shared logic in both scripts, or in a package.

**Can I use Bash, Go or another language?**
No. Only Python 3 and Node.js runtimes are supported. A Python script can run other programs with `subprocess`, but only programs already in the image.

**Is there a run history or log of tool calls?**
No. OmniForge stores tools, not runs. `docker logs` shows uvicorn's request log (method, path and status), without arguments or output.

**Is `OMNIFORGE_MAX_SCRIPT_MEMORY_MB` enforced?**
No. Use Docker's `--memory` on the container.

**Why are there two tools I didn't create?**
`omniforge_instructions` and `omniforge_create_tool` are always listed to MCP clients. See [Built-in authoring tools](Built-in-Authoring-Tools.md).

**Can I edit a tool's input schema in the dashboard?**
Not yet. It's shown read-only under **Packages & advanced settings**. Use the API recipe in [Writing tools](Writing-Tools.md#changing-the-schema-of-an-existing-tool).

**Does it run on ARM (Raspberry Pi, Apple silicon servers)?**
The published image is `amd64` only. The `Dockerfile` uses multi-architecture base images and Debian's Node.js, so a local `docker build` will probably work, but it hasn't been tested.

**How do I start completely fresh?**
Stop the container and delete its volumes (`docker volume rm omniforge_data omniforge_lib`). This deletes all your tools.

---

← [Home](Home.md) · [Next: Release and deployment →](Release-and-Deployment.md)
