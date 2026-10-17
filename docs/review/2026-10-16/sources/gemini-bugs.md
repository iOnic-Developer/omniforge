This is a comprehensive bug check and risk assessment for **OmniForge**.

### Bug Check & Security Report

#### 1. Concurrency Race in Script Execution
*   **Severity:** High
*   **File + Function:** `app/runner.py`: `run_tool`
*   **Failure Scenario:** The runner writes the tool's code to a fixed path based only on the tool's ID: `os.path.join(SCRATCH_ROOT, f"{tool.id}{ext}")`. If two concurrent requests execute the same tool (e.g., two users calling an MCP tool, or a user clicking "Run" while an MCP call is in flight), the second request will overwrite the code file while the first request's subprocess is potentially still initializing or reading the script. This leads to non-deterministic execution of different code versions.
*   **Suggested Fix:** Use a unique execution ID or `tempfile.NamedTemporaryFile` to ensure each execution has its own isolated script file.

#### 2. DNS Rebinding & CSRF Vulnerability
*   **Severity:** Critical
*   **File + Function:** `app/main.py` (Missing Security Middleware)
*   **Failure Scenario:** OmniForge is designed for "trusted LAN only" and has no authentication on the dashboard or management API. A malicious website can use **DNS Rebinding** to bypass the Same-Origin Policy (SOP). The victim's browser, while visiting the malicious site, can be tricked into sending POST requests to `localhost:8000/api/tools` to create a new tool containing a reverse shell or data exfiltration script, and then hit `/run` to execute it.
*   **Suggested Fix:** Implement FastAPI's `TrustedHostMiddleware` to restrict `Host` headers to `localhost` or specific internal IPs. Additionally, require a custom non-standard header (e.g., `X-OmniForge-Request`) for all mutation calls (`POST/PUT/DELETE`) to prevent simple CSRF.

#### 3. Sensitive Environment Variable Leakage
*   **Severity:** High
*   **File + Function:** `app/runner.py`: `run_tool`
*   **Failure Scenario:** The execution engine uses `os.environ.copy()` to prepare the subprocess environment. This means every tool script has full read access to `OMNIFORGE_API_KEY` and other sensitive server environment variables. Any user (or even a malicious MCP client if auth is weak) can author a tool that simply prints `os.environ` to exfiltrate the server's master key.
*   **Suggested Fix:** Explicitly scrub sensitive keys (especially `OMNIFORGE_API_KEY` and `OMNIFORGE_DB_PATH`) from the environment dictionary before passing it to the `subprocess.Popen/run` call.

#### 4. Orphaned Subprocesses (No Process Group Termination)
*   **Severity:** Medium
*   **File + Function:** `app/runner.py`: `run_tool`
*   **Failure Scenario:** The runner uses `subprocess.run` with a `timeout`. While this kills the immediate child process when the timeout expires, it does **not** kill any orphaned background processes spawned by that child (e.g., a script that runs `node -e "setInterval(() => {}, 1000)" &`). Over time, a container can become cluttered with "zombie" or orphaned long-running processes that consume CPU/Memory.
*   **Suggested Fix:** On Unix, use `preexec_fn=os.setsid` in the subprocess call and send `SIGTERM/SIGKILL` to the entire process group (`os.killpg`) upon timeout.

#### 5. Race Condition in Dependency Installation
*   **Severity:** Medium
*   **File + Function:** `app/dependencies.py`: `ensure_dependencies`
*   **Failure Scenario:** While there is a file-lock (`flock`) to prevent concurrent installations for the *same* tool/requirements, there is a race in the atomic rename. The code checks `if destination.exists(): raise DependencyError`. If a process finishes installation and renames its `staging` to `destination` between another process's `marker.is_file()` check and its own `staging.rename(destination)`, the second rename will fail or overwrite.
*   **Suggested Fix:** Wrap the rename in a `try/except` block and check if the destination was already populated by a winner; use the existing one instead of failing.

---

### Top 5 Riskiest Areas

1.  **Subprocess Execution Isolation (`runner.py`):** The lack of a sandbox means any tool script can read/write any file the container user (UID 1000) can access, including the SQLite database and the shared library root.
2.  **Management API Exposure (`main.py`):** The zero-auth policy for the dashboard and CRUD API assumes a perfectly secure network. DNS Rebinding makes this assumption invalid for any user browsing the web while the server is running.
3.  **Credential Management:** The inheritance of `os.environ` by scripts is a direct path to privilege escalation, as the `OMNIFORGE_API_KEY` is meant to be a secret known only to the admin/MCP client, not the tools themselves.
4.  **Lazy Installer Stability (`dependencies.py`):** Synchronous dependency installation can block the entire FastAPI event loop if multiple requests trigger cache misses, leading to 504 timeouts or "Server Unavailable" errors in the dashboard.
5.  **Disk Exhaustion:** The system never prunes old dependency caches (`OMNIFORGE_LIB_ROOT`). Every time a user changes a single package version in a tool, a new directory (potentially hundreds of MBs for Node) is created and never deleted.
