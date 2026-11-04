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

## Verified deployment

Docker Desktop CLI built source `02cf35397fca76f7782aebfb4582b7ab166b86b2` at
2026-11-04T22:27:25Z. Both Docker Hub tags `dbzocchi/omniforge:0.3.0` and
`dbzocchi/omniforge:latest` were published and independently verified as digest
`sha256:75678554a07eb1b99006efeb6207feb9c4c956a44a4c900cd2e66b04950f4397`.
The Docker Desktop login was refreshed from the existing saved credential after
the old login lacked push scope; no new registry credential was created.

NucNas container `omniforge` now runs image
`sha256:87b88138218abe976e73e54a588ff28db6fc17f81721c9fec58cab87e957d5f4`.
Existing tool identity/code (`bonusBall`), all original mounts, environment,
port 192.168.0.180:8000, UID1000, read-only root, resource limits, dropped
capabilities, network and labels were verified preserved. Added persistent
`/mnt/user/appdata/omniforge/files:/opt/omniforge/files` and its Unraid template
entry. No secret values were serialized into deployment artifacts.

Stopped rollback container `omniforge-rollback-20261104T223658Z` retains exact old
image `sha256:f1e8d8998081303d726468ed608af529910b15d1e6c91204f30f0134d99704b6`.
It is retained for rollback; a post-deploy rollback/return was not exercised.

Final validation: 99 Python tests in the release image, 0 failures/errors,
1 optional package-install test skipped; 54 UI/service-worker tests; 23 full
browser tests plus focused footer positioning/accessibility. Official MCP SDK
1.30 verified handshake/create/run and an actual clock-triggered scheduled
file write under the production container restrictions before deployment.

Both LAN and public browsers verified `V0.3.0 04/11`, Connections navigation,
preserved enabled bonusBall, exact source revision, and no uncaught browser errors.
Live public MCP created a temporary cron/folder tool, downloaded the actual
release JSON into the mounted folder, executed on real cron at 22:39:04 UTC
(exit0, 322ms), persisted history and paused correctly. Per-connection discovery
and execution filtering persisted across reconnect. Temporary tool/output were
removed; original tool count is one. Local OpenAI's named connection remains
all-enabled, with its key in Windows Credential Manager, and bridge discovery
passes on the new session transport. Master management key remains in its own
secure-store entry. ChatGPT web setup remains unfinished after the user's Escape.

Sanitized deployment and live proof: W:/Work/Backups/OmniForge/20261104T221941Z/.
Screenshots: C:/Users/dbzoc/AppData/Local/Temp/omniforge-production-acceptance/.
