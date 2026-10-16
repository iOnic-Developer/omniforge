# Announcement drafts — not published

These drafts describe the reviewed source. Publish only after approval and
verification of the image digest being promoted. No public product-site or
private-repository links are assumed. Do not add private raw asset URLs.

## Short

**Turn your Python and Node scripts into tools for your AI.**

OmniForge is a self-hosted workspace for trusted code: author a script, save it,
test the saved version with JSON, then expose an enabled tool through MCP.
MCP Station connects integrations; OmniForge turns code you author into tools.

Single-admin, trusted-network use only. There is no dashboard login, scripts
share the app container, and MCP transport is limited HTTP JSON-RPC—not full
Streamable HTTP. Client compatibility must be checked.

## Longer

**Your script. Your tool. Callable by your AI.**

OmniForge brings Python and Node scripts into one self-hosted workspace. Write
and save trusted code, test the saved version, inspect its output and enable it
for discovery by an MCP client. Useful starting points include text slugging
and JSON number summaries, both possible without installing packages.

The reviewed source supports JSON input validation, per-tool package caches and
built-in authoring helpers. Saving and execution are deliberately separate.
Clients refresh their tool list to see enabled scripts; there is no server restart.

This is not an integration catalogue, a multi-account service or a sandbox.
The dashboard and management API are unauthenticated; scripts share the app's
environment, network and writable data. Keep deployment local or on a trusted
admin network. The MCP endpoint is limited HTTP JSON-RPC POST; full Streamable
HTTP and OAuth are not implemented. Verify the exact client and image digest.

## Publication notes

- Docker Hub has `latest` and `0.2.0_beta` (inventory checked October 16, 2026).
  Tag existence does not establish feature parity or a stable product release.
- Do not announce beta features until they have been tested in that image.
- The source repo and detailed docs are private and require access. Image
  availability is not an open-source licence; all rights reserved.
- Do not claim a live public site, public wiki or universal ChatGPT/Claude support.
- Review the [publication checklist](../PUBLICATION.md) before using this copy.
