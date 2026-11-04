# OmniForge 0.3.0

Features: optional persistent cron/IANA-timezone schedules, saved inputs, pause and
status/history; selected output folders with mounted-host support; named MCP
connections, hashed credentials, disconnect and per-connection visibility (new
tools default on). Sidebar release identity comes from image build metadata.

The starting source matches Docker Hub 0.2.1, a8c26a7. Implementation is on
feat/scheduled-tools-connections. Source and deployment evidence are distinct.

Validation before release: 99 Python tests in the Docker Desktop-built image,
zero failures/errors, one opt-in package-install test skipped. Scheduling covers
actual HTTP download/file output, Python/Node, DST, leases and cancellation.
Independent audit regressions cover fresh settings preservation and legacy
reserved-name collisions. UI and actual browser tests cover saved configuration,
pause, file output, persistent connection policies, revocation and accessibility.

OpenAI local desktop/CLI/IDE configured globally and actual app-server discovery
verified. The bearer credential is held in Windows Credential Manager. ChatGPT
web setup remains separate and was interrupted by the user's Escape action.

Pre-deploy backup: NAS and offhost W:/Work/Backups/OmniForge/20261104T221941Z,
SHA256 ed72f688ae9e1289319dd2549d6b1896bcb8558e49bc8882f12c44354cd2f367.
Online SQLite backup and offhost extracted restore quick_check both passed;
299 archived files verified. No credentials are in the backup metadata.

Deployment to 192.168.0.180 is authorized and in progress. Preserve all existing
mounts, server environment, port, read-only root, capabilities/resource limits,
network and labels; add /mnt/user/appdata/omniforge/files as the output mount.
Keep the stopped old container and exact image for rollback. Update this record
after the new Docker Hub digest and live acceptance are verified.
