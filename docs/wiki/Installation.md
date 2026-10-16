# Installation

OmniForge has published `latest` and `0.2.0_beta` tags, both with Linux/amd64 runtime images (checked October 16, 2026). Tag availability is not feature verification; see [image inventory and provenance](Release-and-Deployment.md#published-image-inventory). This guide describes reviewed source behaviour. Everything listens on port **8000**: the dashboard, the REST API and `/mcp`.

| Method | Best for |
|---|---|
| [`docker run`](#docker-run) | A quick start on any Docker host |
| [Docker Compose](#docker-compose) | Repeatable deployments, with or without the hardening options |
| [Unraid](#unraid) | Unraid servers, via a user template |
| [From source](#from-source) | Development on Linux, macOS or WSL |

> [!WARNING]
> Whatever method you choose, expose port 8000 only to a network you trust. Don't port-forward it to the internet. The reasons are in [Security and limitations](Security-and-Limitations.md).

## Before you begin

- Docker Engine 20.10 or later (or Docker Desktop) on an `amd64` host.
- Outbound HTTPS to `pypi.org`/`files.pythonhosted.org` and `registry.npmjs.org` if your tools declare packages. Installs don't use proxy settings; see [Dependencies](Dependencies.md#failure-modes).
- A random key for the MCP endpoint, for example from `openssl rand -hex 32`.

## docker run

In a new deployment directory, generate and load a private MCP key first:

```bash
umask 077
printf 'OMNIFORGE_API_KEY=%s\n' "$(openssl rand -hex 32)" > .env
set -a
. ./.env
set +a
```

```bash
docker volume create omniforge_data
docker volume create omniforge_lib

docker run -d --name omniforge \
  -p 127.0.0.1:8000:8000 \
  -e OMNIFORGE_API_KEY="$OMNIFORGE_API_KEY" \
  -v omniforge_data:/opt/omniforge/data \
  -v omniforge_lib:/opt/omniforge/lib \
  --restart unless-stopped \
  dbzocchi/omniforge:latest
```

Open `http://localhost:8000` on the Docker host. The default bind is local-only. To make it reachable on a trusted LAN, explicitly choose `-p <lan-ip>:8000:8000` and firewall access. This does not authenticate the dashboard.

### Hardened variant

The project's Docker test runs used UID 1000, a read-only root filesystem and restricted capabilities (see [product design notes](../product-design.md#final-implementation-verification--2026-10-13)). The image supports this setup: the package installer keeps its staging area, `HOME`, `TMPDIR` and npm cache inside the library volume, and scripts run from `/tmp`.

```bash
docker run -d --name omniforge \
  -p 127.0.0.1:8000:8000 \
  -e OMNIFORGE_API_KEY="$OMNIFORGE_API_KEY" \
  -v omniforge_data:/opt/omniforge/data \
  -v omniforge_lib:/opt/omniforge/lib \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --restart unless-stopped \
  dbzocchi/omniforge:latest
```

These flags protect the **host** from the container. They do **not** separate one script from another, or a script from OmniForge itself. Scripts still share the app's environment, network and writable volumes.

> [!NOTE]
> `noexec` on `/tmp` is fine. OmniForge writes each script to `/tmp/omniforge/<tool-id>.py|.js` and runs it as `python3 <file>` or `node <file>`, so nothing in `/tmp` is executed directly.

## Docker Compose

### Using the published image

Create a `compose.yaml` like this:

```yaml
services:
  omniforge:
    image: dbzocchi/omniforge:latest
    # For reproducible deploys pin a digest instead (see Release-and-Deployment.md):
    # image: dbzocchi/omniforge@sha256:<digest>
    container_name: omniforge
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      OMNIFORGE_API_KEY: ${OMNIFORGE_API_KEY:?Generate a key in .env first}
      OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS: "30000"
    volumes:
      - omniforge_data:/opt/omniforge/data
      - omniforge_lib:/opt/omniforge/lib
    # Optional hardening (host protection only, not script isolation):
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=128m
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    restart: unless-stopped

volumes:
  omniforge_data:
  omniforge_lib:
```

Generate `.env` with the commands above, next to `compose.yaml`, then:

```bash
docker compose up -d
docker compose logs -f omniforge
```

### Using the repository's `docker-compose.yml`

The repository's `docker-compose.yml` **builds the image from source**. It doesn't pull from Docker Hub. It tags the local build as `ionic-developer/omniforge:latest`.

```bash
umask 077
printf 'OMNIFORGE_API_KEY=%s\n' "$(openssl rand -hex 32)" > .env
set -a
. ./.env
set +a
# First change the source file's port mapping to 127.0.0.1:8000:8000.
docker compose up --build -d
```

> [!CAUTION]
> Do not copy the sample credential from `.env.example`. Generate a fresh key. The source Compose file also binds all interfaces by default: change its port mapping to `127.0.0.1:8000:8000` before starting. Keep `.env` private and out of version control.

That file also sets `OMNIFORGE_RUNTIME_IMAGE` and `OMNIFORGE_SCRIPT_HOST`, and mounts an `omniforge_scripts` volume at `/opt/omniforge/scripts`. **The current code uses none of these.** They are leftovers from an earlier design. You can delete them from your own compose file without any effect. See [Configuration](Configuration.md#variables-that-have-no-effect).

## Unraid

This optional template exposes a LAN port, unlike the local-only quickstart.
Restrict access to a trusted admin network. Generate a fresh key with the
commands above and enter it in the masked MCP API key field; it does not
protect the dashboard. Do not publish this port through a tunnel.

Unraid has no Community Applications listing for OmniForge. Add it with a user template.

### 1. Prepare the appdata folders

The container runs as UID/GID **1000:1000**. Unraid's appdata shares usually belong to `nobody:users` (99:100), so set ownership before the first start, or SQLite can't create its database:

```bash
mkdir -p /mnt/user/appdata/omniforge/data /mnt/user/appdata/omniforge/lib
chown -R 1000:1000 /mnt/user/appdata/omniforge
```

### 2. Add the template

Save the XML below as `/boot/config/plugins/dockerMan/templates-user/my-OmniForge.xml`. Then go to **Docker → Add Container** and choose **OmniForge** from the template list. Alternatively, enter the same values in the **Add Container** form by hand.

```xml
<?xml version="1.0"?>
<Container version="2">
  <Name>OmniForge</Name>
  <Repository>dbzocchi/omniforge:latest</Repository>
  <Registry>https://hub.docker.com/r/dbzocchi/omniforge</Registry>
  <Network>bridge</Network>
  <Privileged>false</Privileged>
  <Shell>bash</Shell>
  <Overview>Self-hosted MCP tool workspace. Write Python or Node scripts, test them with JSON and publish them at /mcp. Trusted LAN only: the dashboard has no authentication and scripts run inside this container.</Overview>
  <Category>Tools: Productivity:</Category>
  <WebUI>http://[IP]:[PORT:8000]/</WebUI>
  <Icon/>
  <ExtraParams>--read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m --cap-drop ALL --security-opt no-new-privileges</ExtraParams>
  <Config Name="Web UI and MCP port" Target="8000" Default="8000" Mode="tcp" Description="Dashboard, REST API and /mcp" Type="Port" Display="always" Required="true" Mask="false">8000</Config>
  <Config Name="Data" Target="/opt/omniforge/data" Default="/mnt/user/appdata/omniforge/data" Mode="rw" Description="SQLite database. Must be writable by UID 1000." Type="Path" Display="always" Required="true" Mask="false">/mnt/user/appdata/omniforge/data</Config>
  <Config Name="Package caches" Target="/opt/omniforge/lib" Default="/mnt/user/appdata/omniforge/lib" Mode="rw" Description="Per-tool pip/npm caches. Must be writable by UID 1000." Type="Path" Display="always" Required="true" Mask="false">/mnt/user/appdata/omniforge/lib</Config>
  <Config Name="MCP API key" Target="OMNIFORGE_API_KEY" Default="" Mode="" Description="Bearer key for POST /mcp. Empty disables MCP auth. Does not protect the dashboard." Type="Variable" Display="always" Required="true" Mask="true"></Config>
  <Config Name="Script timeout (ms)" Target="OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS" Default="30000" Mode="" Description="Runner adds 15 seconds to this value." Type="Variable" Display="advanced" Required="false" Mask="false">30000</Config>
</Container>
```

The `<Icon/>` element is empty on purpose: the source repository is private, so raw image URLs from it won't load on your server. Point it at a copy of `app/static/icon-192.png` that you host yourself, if you want an icon. If the hardening flags in `ExtraParams` cause trouble in your environment, remove them. They're optional.

> [!NOTE]
> This template was written from the image's paths, ports and variables. It hasn't been run through Unraid's template validator. If a field doesn't import, enter it by hand.

### 3. Update

Use **Check for Updates** on the Docker tab. It pulls `latest` and recreates the container. The database and caches are kept in appdata. Back up first: see [Backup and restore](Backup-and-Restore.md).

## From source

For development. You need **Linux, macOS or WSL**: the dependency installer imports `fcntl`, so the app won't start on native Windows Python. You also need Python 3.12, and Node.js with npm if you want Node tools.

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

- Activate the virtualenv. The runner finds `python3` on `PATH` for Python tools and their pip installs, as it does in the container.
- `omniforge_data/` and `omniforge_lib/` are already in `.gitignore`.
- Scripts are written to `/tmp/omniforge` unless you set `OMNIFORGE_SCRATCH_ROOT`.
- The repository is private. Cloning needs access to it.

## Verify the install

```bash
curl -s http://localhost:8000/api/config
```

You should get JSON that includes `"mcp_path": "/mcp"` and `"auth_enabled": true` (or `false` if you set no key). The key itself is never returned.

---

← [Home](Home.md) · [Next: Configuration →](Configuration.md)
