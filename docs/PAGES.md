# Product Pages build and publishing handoff

Target: `https://ionic-developer.github.io/omniforge/site/`.

## Current status

The build is public-ready, not a claim that a site is deployed. The repository
remains private. Pages creation for the private repository returned HTTP 422
because the current plan does not support it. This work does not change visibility.

**Making the repository public exposes its existing history as well as the page.** The privacy preflight
found NAS deployment identifiers and 53 unpublished audit findings in reachable
history. It found no actual credential matches; that is not a guarantee that
history is safe to disclose. The owner requested this exact repository URL and offered to change visibility manually
if necessary. Review those records before using that fallback. A clean, separate public publishing repository is an alternative,
but requires its own workflow and target configuration.

## Build locally

Run in a development workspace, not in the application container:

```sh
python3 -m venv /workspace/scratch/omniforge-docs-venv
/workspace/scratch/omniforge-docs-venv/bin/python -m pip install -r requirements-docs.txt
/workspace/scratch/omniforge-docs-venv/bin/python scripts/build-product-site.py
python3 -m http.server 8765 --bind 127.0.0.1 --directory _site
```

Open `http://127.0.0.1:8765/site/`. Only serve `_site`, never the repository
or `docs` directory. Stop the local server when finished. The builder replaces
only its generated `_site` directory. Do not commit generated output.

## What is published

The explicit allowlist in `scripts/build-product-site.py` contains the landing
page, its CSS/JS, ten demo PNG captures, four product PNGs, four SVGs, two fonts
and their two licences. Eight reviewed wiki pages become HTML guides. Raw HTML
in Markdown is escaped; approved screenshot wrappers become Markdown images.
Guide-to-guide links are rewritten and heading fragments checked. Home links
return to the landing page. Links outside the eight-guide scope become plain
text marked “repository access required”, not broken public links.

The build does not recurse through arbitrary asset folders. It does not copy
application source, repository history, review evidence, capture manifests,
databases, environment files, development scripts or the unpublished audit.
`site/build-manifest.json` records approved source paths/hashes and output
paths/SHA-256 hashes (excluding its own recursive hash). It contains no source
file bodies. The build rejects known deployment identifiers and credential
patterns in textual output, but this is a guardrail, not a full privacy audit.

The generated landing page receives indexable metadata, canonical and
Open Graph URLs for the exact target, public guide links, a product strip and
copyright footer. Generated guides also receive canonical URLs and indexable metadata. Source `docs/index.html`, `docs/site.css`, `docs/site.js`,
application files and existing parent-owned tests are left unchanged.

## Workflow behavior

`product-site.yml` builds on main/docs branch pushes affecting documentation,
the builder, its pinned dependency or the workflow; it also supports manual
runs. It installs only `requirements-docs.txt` in a separate docs environment.

- **Private repository:** upload downloadable `pages-preview`; skip Pages
  artifact preparation, configuration and deployment. No public URL is live
  as a result of that run. A normal private artifact requires repository access.
- **Public repository:** upload the same preview plus a Pages artifact, enable
  Pages with Actions and deploy `_site`. The artifact root contains `site/`,
  so the product URL ends in `/omniforge/site/`, not `/omniforge/`.

After the owner has resolved the history/privacy concerns and authorized public
publication, confirm Pages uses GitHub Actions and the `github-pages` environment
allows the intended deployment branch (`docs/review-2026-10-16` for this review,
or main after merge). Existing environment branch restrictions may otherwise
block deployment. Then run the workflow on the approved ref and verify the exact
public URL, guides, images, CSS/fonts, canonical and social image. Public Pages
serves documentation, **not** the OmniForge app; never expose its dashboard/API.

No visibility change, commit, push or workflow dispatch is performed by the local
builder. Local validation is not a successful hosted deployment or CI run.

## Local verification for this handoff

- Deterministic rebuild: 36 allowlisted files, eight guides, 174 checked local
  references, including heading fragments and bundled CSS font URLs.
- Source and output SHA-256 values in the generated manifest verified.
- Negative checks reject the known NAS address/name, token/private-key patterns,
  unexpected output files and script URLs; raw HTML is escaped.
- Chromium at 1440 × 1000 and 375 × 900: all nine pages loaded successfully,
  with no horizontal overflow, broken loaded images, request failures or JS
  errors. Axe WCAG 2 A/AA and 2.1 AA checks reported no violations in all 18 runs.
  Automated accessibility results do not replace manual assistive-tech testing.
- Existing product-page static checks passed. The parent source landing page,
  CSS/JS, test scripts and application requirements remained byte-identical to
  `730d311`. No app audit or application dependency installation was run.
- Browser results/screenshots are local only in
  `/workspace/scratch/omniforge-pages-qa/`; the independent QA runner is
  `/workspace/scratch/omniforge-pages-qa.cjs`. Neither enters the Pages artifact.
- Hosted Actions/Pages deployment has not run. Environment approval and hosted
  behavior remain to be verified after the owner's publication decision.

For the parent handoff, stage only the five owned source files: this document,
`docs/site-docs.css`, `requirements-docs.txt`, `scripts/build-product-site.py`
and `.github/workflows/product-site.yml`. Leave generated `_site/` untracked.
