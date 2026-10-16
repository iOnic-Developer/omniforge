<p align="center"><img src="../assets/banner.png" alt="OmniForge: write a script, test it, publish it as an MCP tool" width="1280"></p>

# OmniForge documentation

OmniForge is a self-hosted, single-container workspace for turning small Python and Node scripts into tools that AI clients can call over the Model Context Protocol (MCP). You write a script in the browser, test it with a JSON input, save it, and it is listed at `/mcp` straight away.

> [!WARNING]
> **Trusted LAN only.** The dashboard and management API have no authentication, and every script runs as a subprocess inside the application container with access to its environment (including `OMNIFORGE_API_KEY`) and data. Read [Security and limitations](Security-and-Limitations.md) before you deploy.

## Where to start

| If you want to… | Read |
|---|---|
| Run OmniForge for the first time and make one working tool | [Getting started](Getting-Started.md) |
| Install with Docker, Compose, Unraid or from source | [Installation](Installation.md) |
| Write a tool that accepts inputs and returns JSON | [Writing tools](Writing-Tools.md) |
| Point Claude, LibreChat or your own code at `/mcp` | [Connecting MCP clients](Connecting-MCP-Clients.md) |
| Understand exactly what is and isn't protected | [Security and limitations](Security-and-Limitations.md) |
| Look up a route or a JSON-RPC method | [API reference](API-Reference.md) · [MCP protocol support](MCP-Protocol-Support.md) |

## Table of contents

### Using OmniForge

1. [Getting started](Getting-Started.md): a 10-minute first run, from container to first tool call.
2. [Installation](Installation.md): Docker, Docker Compose, an Unraid template and running from source.
3. [Configuration](Configuration.md): every environment variable, port and path.
4. [Dashboard guide](Dashboard-Guide.md): Overview, Tools, Tool studio, Connect and Help, screen by screen.
5. [Writing tools](Writing-Tools.md): the script contract (stdin JSON, stdout, stderr, exit codes, timeouts) with examples.
6. [Dependencies](Dependencies.md): package syntax, per-tool caches, accepted forms and failure modes.
7. [Testing tools](Testing-Tools.md): Run / Test in the browser, plus testing with `curl`.
8. [Connecting MCP clients](Connecting-MCP-Clients.md): Claude Code, Claude Desktop, LibreChat and plain HTTP.
9. [Built-in authoring tools](Built-in-Authoring-Tools.md): `omniforge_instructions` and `omniforge_create_tool`.
10. [PWA and themes](PWA-and-Themes.md): installing the app, offline behaviour, updates and appearance.

### Operating OmniForge

11. [Security and limitations](Security-and-Limitations.md): the trust model, stated plainly.
12. [Backup and restore](Backup-and-Restore.md): consistent SQLite backups and volume handling.
13. [Troubleshooting and FAQ](Troubleshooting-and-FAQ.md): error messages and what to do about them.
14. [Release and deployment](Release-and-Deployment.md): CI, the `latest` tag, pinning by digest and rollback.

### Reference

15. [Architecture](Architecture.md): modules, request flow and diagrams.
16. [API reference](API-Reference.md): every HTTP route, with method, auth, request and response.
17. [MCP protocol support](MCP-Protocol-Support.md): exactly which JSON-RPC methods and behaviours exist.
18. [Development and testing](Development-and-Testing.md): local setup and the CI test commands.
19. [Glossary](Glossary.md): the terms used across these pages.

### Design background

- [Product design notes](../product-design.md): information architecture, accessibility, the PWA cache contract and validation history.

## At a glance

| | |
|---|---|
| Image | `dbzocchi/omniforge:latest` (Docker Hub, `linux/amd64`, the only tag) |
| Port | `8000` (dashboard, REST API and MCP on one port) |
| MCP endpoint | `POST /mcp`: HTTP JSON-RPC (`initialize`, `tools/list`, `tools/call`, `ping`) |
| Auth | Optional Bearer key on `POST /mcp` only |
| Runtimes | Python 3.12 and the Debian-packaged Node.js in the image |
| Storage | SQLite at `/opt/omniforge/data/omniforge.db`; package caches at `/opt/omniforge/lib` |
| Licence | Private. All rights reserved. |

---

← [Home](Home.md) · [Next: Getting started →](Getting-Started.md)
