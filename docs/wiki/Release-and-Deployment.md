# Release and deployment

## How a release happens

```mermaid
flowchart LR
  A[Feature branch] -->|push| T[Test dashboard workflow]
  A -->|pull request| T
  T -->|green| M[Merge to main]
  M -->|push to main, matching paths| B[Build and push to Docker Hub workflow]
  B --> L["dbzocchi/omniforge:latest<br/>linux/amd64"]
  L -->|pull and recreate| D[Your deployment]
```

There are two GitHub Actions workflows.

| Workflow | File | Runs on | Does |
|---|---|---|---|
| **Test dashboard** | `.github/workflows/test.yml` | Every pull request, and pushes to any branch **except** `main` | Checks the dashboard JavaScript syntax, runs the DOM and service-worker unit tests, builds the image and runs the Python suite inside it, and runs the Playwright browser and accessibility suite (screenshots uploaded as an artefact) |
| **Build & Push to Docker Hub** | `.github/workflows/dockerhub.yml` | Pushes to `main` that touch `Dockerfile`, `requirements.txt`, `app/**` or `.github/workflows/**`, or a manual **Run workflow** | Builds the `Dockerfile` with Buildx and pushes `dbzocchi/omniforge:latest` |

The exact test commands are in [Development and testing](Development-and-Testing.md#what-ci-runs).

Things to know:

- The checked-in workflow publishes **`latest` only**; this is workflow behaviour, not the complete registry inventory. A separately published `0.2.0_beta` tag also exists. See the dated inventory below.
- **Tests don't run on the push to `main`.** The image is built from whatever lands on `main`. Merge through a pull request so the tests have run first.
- Changes only to docs, tests or `docker-compose.yml` **don't** trigger a new image.
- The image is built for **`linux/amd64`** only. The build step doesn't set `platforms`.
- Python dependencies in `requirements.txt` are unpinned, so two builds of the same commit can differ.
- Docker Hub credentials come from the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`.

## Published image inventory

Registry and OCI configuration checked **October 16, 2026**. This is an inventory,
not a runtime certification or a promise of feature parity with this branch.

| Tag | Last published (UTC) | Runtime platform | OCI revision |
|---|---|---|---|
| `latest` | 2026-10-13 02:43 | Linux/amd64 | No revision label |
| `0.2.0_beta` | 2026-10-16 09:44 | Linux/amd64 | `6466945aef5a6854d241c286e0579db57bc50f42` |

Registry index digests observed:

- `latest`: `sha256:5fba6e224b0e4f46518efa570f6910a075d0c876c0a97266c9f15e72b7d1b123`
- `0.2.0_beta`: `sha256:7f66f403b571d062ebf6736c1a87b5116afed17b6a3861a7d811957dfc5a74fe`

The beta index also includes an unknown-platform attestation entry; that is not
an additional supported runtime architecture. `latest` is a moving main-channel
tag, **not a stable release designation**. The beta's version/source/revision
labels identify a declared build provenance, not an executed feature test.
FastAPI/MCP server `0.1.0` and UI-test package `0.1.0` are internal values, not
product release numbers. Do not infer beta features from the tag name.

A read-only source check on October 16 found remote `main` at
`4ae443d26601c217d33aec77fa5002a7dc3dac2e`; `app/main.py` and `app/runner.py`
matched the reviewed worktree byte-for-byte. This identifies source, **not** the
October 13 image contents. The beta's declared revision could not be resolved
through the authorised repository API (HTTP 404); its source parity remains
unverified. No image was rebuilt or runtime-tested in this documentation pass.

The source walkthroughs describe the reviewed branch. The older `latest` image
must not be assumed to contain its dashboard, authoring, validation or dependency
changes. Without a revision label or a verified source comparison, its exact
parity is unproven. Test the selected digest independently before deployment.
The workflow does not automatically publish the beta tag.

Source repository visibility remains private; GitHub Pages is disabled. Public
Docker availability is not an open-source licence or a privacy boundary: the
Python image contains application code. See [publication controls](../PUBLICATION.md).

## Pin by digest for reproducible deploys

`latest` can move when a matching-path push to `main` or a manual workflow dispatch publishes it. To know exactly what you're running, and to roll back, deploy by **digest**.

Find the digest of the current `latest`:

```bash
docker buildx imagetools inspect dbzocchi/omniforge:latest
# or, after a pull:
docker image inspect --format '{{index .RepoDigests 0}}' dbzocchi/omniforge:latest
```

Use it in Compose:

```yaml
services:
  omniforge:
    image: dbzocchi/omniforge@sha256:<digest-from-above>
```

Or with `docker run`:

```bash
docker run -d --name omniforge … dbzocchi/omniforge@sha256:<digest>
```

Record each digest you deploy, with the date, so you have a list of rollback targets.

## Updating

1. **Back up** the database ([Backup and restore](Backup-and-Restore.md)).
2. Pull and recreate:

   ```bash
   # Compose, tracking latest
   docker compose pull && docker compose up -d

   # Compose, pinned: change the digest in compose.yaml, then
   docker compose up -d

   # docker run
   docker pull dbzocchi/omniforge:latest
   docker stop omniforge && docker rm omniforge
   docker run -d --name omniforge …same flags as before… dbzocchi/omniforge:latest
   ```

   On Unraid, use **Check for Updates → Apply update**.
3. Open the dashboard. If the service worker changed, **Update available** appears. Accept it in one tab and reload any others.
4. Run one or two tools from the dashboard to confirm they still work.

There are no database migrations. The reviewed source creates the schema if missing and otherwise leaves it alone. This is not a guarantee that an unverified image upgrade or downgrade is data-compatible; keep a restorable backup.

## Rolling back

Redeploy the previous digest:

```bash
docker compose down
# set image: dbzocchi/omniforge@sha256:<previous-digest>
docker compose up -d
```

Older digests usually stay pullable after `latest` moves on. Docker Hub doesn't promise to keep untagged images forever, though. If a known-good version matters to you, keep a copy:

```bash
docker save dbzocchi/omniforge@sha256:<digest> | gzip > omniforge-<date>.tar.gz
# restore later with
docker load < omniforge-<date>.tar.gz
```

## Building and pushing by hand

CI normally does this, but it works from any machine logged in to Docker Hub with push rights:

```bash
docker buildx build --platform linux/amd64 -t dbzocchi/omniforge:latest --push .
```

To keep a build local for testing, use `--load -t omniforge:dev` instead of `--push`.

## Service worker cache version

The PWA caches 12 public assets under the cache name in `app/static/sw.js`:

```javascript
const CACHE = 'omniforge-public-v2';
```

**If a release changes any allow-listed asset** (`product.css`, icons, fonts, `offline.html` or the manifest), increment this name, for example to `omniforge-public-v3`. Otherwise installed apps keep serving the old files. On activation, the new worker deletes older `omniforge-public-*` caches. Users see **Update available** and choose when to reload.

Changes to `dashboard.html` alone don't need a bump, because the dashboard is never cached.

## Release checklist

- [ ] Pull request opened and **Test dashboard** passed, including the browser job.
- [ ] Service-worker `CACHE` name bumped if any public asset changed.
- [ ] `README.md` and `docs/wiki/` updated for behaviour changes.
- [ ] Merged to `main`, and **Build & Push to Docker Hub** finished.
- [ ] New digest recorded. Deployment updated, then checked.

---

← [Home](Home.md) · [Next: Architecture →](Architecture.md)
