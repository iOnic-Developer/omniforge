# Configurable execution deadlines — 0.3.1

User request: make the prior 45-second script kill configurable, default to two
minutes, and expose the setting to AI authors and the tool window.

Implemented `timeout_seconds`, strict integer 1–3600, default120. Old tools
migrate to120 and old client edits preserve an omitted setting. The value is
persisted and included in content revisions. MCP schema, initialization guidance
and authoring instructions teach the setting; the editor displays and saves it.
Runtime uses the exact duration without the old additional15seconds. Expiry
kills the Linux process group. Remaining ordinary children are stopped on parent
completion, preventing an early-return script from leaving work running.
Dependency preparation retains separate bounded waits. Shared-container trust,
output caps and memory isolation are unchanged.

Independent review caught the early-parent-exit child escape and the local
OpenAI caller's old600second cap. Both addressed: a real Python/Node regression
covers redirected child stdio plus immediate parent exit; only the OmniForge
bridge/Codex caller timeouts were increased to4000seconds to cover the valid
execution maximum and bounded preparation. Credentials were unchanged.

Validation:113 Python tests in the exact Docker Desktop-built release image,
zero failures/errors, one opt-in package-install test skipped;56 UI/service-worker
tests; real browser MCP45→editor45→save90 and template120, mobile accessibility.
Live public MCP verified default120, custom45, discoverable schema/instructions,
and a1second tool stopped in1.062seconds with a timeout error. LAN/public desktop
and mobile browsers showed45, the120second hint and V0.3.1 05/11. Test tools were
removed and the original bonusBall tool is preserved with timeout120.

Release source:2d4c4591e1e7fc6888fc5297ee9825cdca12ddb9.
Build:2026-11-05T00:48:32Z via Docker Desktop CLI.
Docker Hub0.3.1/latest digest:
sha256:558baffb6bb0a6825097a81f24747c5834863893da1ed31faa6e60747384b057.
NucNas running image:
sha256:725cbe12786a7ad507d0cc1030bf604afd83cf745ae9fb70202a5491f57f781a.
All original deployment settings/mounts, tool identity/code and credentials were
preserved. Rollback container:omniforge-rollback-20261105T005018Z (stopped0.3.0).
Backup NAS/offhost copies and deployment/runtime proof:
W:/Work/Backups/OmniForge/20261105T003815Z/.
Backup SHA256:7442a8760b1caa268e646a0809d38b2aee7f0306e042cba389212bdbe42d7965.
The offhost SQLite restore quick_check passed. A rollback/return was not exercised.

The separate TrueNAS/MCPStation repair remains stopped; no live fixes were applied
to that integration as part of this task.
