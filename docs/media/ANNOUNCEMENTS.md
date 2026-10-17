# Announcement drafts — not published

These drafts describe the reviewed source. Publish only after approval and
verification of the image digest being promoted. The source repository is now
public. The product page is configured at the exact URL below, but publication
was verified successfully; do not describe it as live until the parent confirms it.
Do not add authenticated assets or private attachments.

[Product page](https://ionic-developer.github.io/omniforge/site/) ·
[GitHub source](https://github.com/iOnic-Developer/omniforge) ·
[Wiki source documentation](https://github.com/iOnic-Developer/omniforge/blob/docs/review-2026-10-16/docs/wiki/Home.md)

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
- The source repo and detailed docs are public. Public visibility and image
  availability do not grant MIT or another permissive licence; all rights reserved.
- Pages publication was verified successfully; do not claim the site is live until
  verified. Link to wiki source files, not a native GitHub wiki (it is disabled).
  Do not claim universal ChatGPT/Claude support.
- Review the [publication checklist](../PUBLICATION.md) before using this copy.
