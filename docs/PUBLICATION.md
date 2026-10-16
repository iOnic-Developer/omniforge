# Publication controls

Prepared October 16, 2026 for PR #5 on `docs/review-2026-10-16`.
Updated October 16, 2026 after the owner made the repository public. Pages
publication was verified successfully; this checklist is not approval for additional
image releases, Docker Hub metadata updates, announcements or merges.

## Current boundaries

- The owner changed the source repository to **public** on October 16, 2026
  and authorized the configured Pages workflow at
  `https://ionic-developer.github.io/omniforge/site/`. Publication is being
  verified by the parent task (Actions run `38978598334`); do not claim it is live
  until hosted checks pass. No repository licence grants MIT or other permissive
  reuse rights; **all rights reserved** remains in effect. This pass makes no
  visibility/API changes.
- `docs/index.html` is site source, not evidence of a live public website.
- README screenshots use repository-relative assets. Docker Hub uses a public
  raw screenshot URL on `docs/review-2026-10-16`, plus the exact product-page URL.
  Do not use authenticated assets or private attachments.
- The wiki sources remain publicly accessible in `docs/wiki/`; the native
  GitHub wiki remains disabled (`has_wiki: false`). Link to those source files,
  not `/wiki`. Docker Hub links to the reviewed branch README and wiki sources
  until merge, rather than the older main-branch README.
- `docs/review/**` is a preserved historical audit. Do not edit it to make old
  findings or inventory look current. Current product docs are separate.

### Historical metadata snapshot — October 16, 2026, before owner visibility change

The earlier live metadata reported `private: true`, `has_wiki: false`,
`has_pages: false`, and no repository licence. These are preserved pre-change
observations, not the current visibility or Pages state.

## Copy ready for review

**Proposed short description** (ASCII; 94 characters):

> Turn your Python and Node scripts into tools for your AI. Self-hosted, trusted-code workspace.

The owner-requested Docker Hub overview uses this text after validation.
`DOCKERHUB.md` is the self-contained public long-description source, with
public repository, reviewed-guide, screenshot and product-page links.
Announcement drafts are in [media/ANNOUNCEMENTS.md](media/ANNOUNCEMENTS.md).

## Image provenance is not a release claim

Live Docker Hub inventory includes `latest` (October 13) and `0.2.0_beta`
(October 16), both with Linux/amd64 runtime images. See the dated
[inventory and observed digests](wiki/Release-and-Deployment.md#published-image-inventory).
The beta's OCI revision label is `6466945aef5a6854d241c286e0579db57bc50f42`;
`latest` has no revision label; the beta revision could not be resolved through
the authorised repository API (HTTP 404). These are registry/config observations, not
runtime verification. No stable `0.2.0` release or beta feature set is implied.
Internal FastAPI/MCP and UI-test package versions are not product release numbers.

Docs describe the reviewed source. Do not advertise its features as available
in `latest` or beta until the selected image digest is tested against them.
The Python image includes application source. Before the owner made GitHub
public, repository privacy did not make distributed image contents confidential.
Review contents and rights before any further public image publication. No image was built or published here.

## Approval gates

- [ ] Owner approves final copy and its intended destination.
- [ ] Image digest selected, provenance recorded and advertised features tested.
- [ ] Single-admin/no-login model, open management API, shared-container execution
      and limited MCP transport remain visible before installation instructions.
- [ ] No universal client-compatibility, sandbox, multi-account or stable-release claims.
- [ ] Public copy works without repository access or private asset links.
- [ ] Any screenshots are reviewed for code, keys, private data and visible hostnames.
- [ ] All rights reserved is retained; third-party font notices remain separate.
- [x] Owner made the repository public and authorized the exact Pages target.
- [ ] Parent verifies hosted Pages publication, guides, assets and metadata.
- [ ] This follow-up leaves repository visibility and Pages settings unchanged.
- [ ] Separate explicit approval obtained before updating Docker Hub metadata,
      publishing announcements, deploying, tagging or merging. Branch pushes update the existing review PR only.

## Validation scope

The implementation pass runs standard-library Python/Node examples and validates
create payloads and calls against the reviewed API in a temporary local database.
It checks owned documentation links and preserves the audit byte-for-byte.
This does not certify third-party MCP clients or published-image parity.
Site, capture scripts, media generation and product test edits belong to the
parallel task; this pass does not edit them. No dependency updates or backend
builds are needed for these docs changes.

### Historical checks completed before this follow-up — October 16, 2026

- Both examples passed direct execution, HTTP create/run and MCP discovery/call
  against reviewed source with temporary database/scratch storage. No packages
  were installed. Duplicate names, strict input/extra-field rejection, the
  50-entry requirement limit and stale-revision HTTP 412 guards were checked.
- 210 local Markdown/asset references across 25 owned Markdown files resolved.
  All 20 wiki pages remain; all 16 historical audit files match their original hashes.
- Public Docker Hub copy has no private links/assets; its generated-key and
  localhost-bind instructions were statically checked. Compose snippets parsed
  as YAML. Docker Compose's config/interpolation check was **not run** because
  the workspace lacks the Compose plugin; nothing was installed to add it.
- No third-party client test, published-image runtime test, backend build,
  deployment, commit, push, merge or publication was performed.

## Current delivery status

The product-presentation pass stays on existing PR #5. Application/runtime files
and historical review evidence are unchanged. The source is now public; the
native GitHub wiki remains disabled. The Pages workflow is configured and
publication was verified successfully. Docker Hub is already public; the overview source
now includes public links and a screenshot. The parent handles any Docker Hub
metadata update after review; this follow-up does not publish it. No new image,
release or application deployment is part of this task.

## Requested repository Pages target

The owner selected `https://ionic-developer.github.io/omniforge/site/` and authorized
public visibility if needed, offering to make the change manually otherwise. Pages
creation before the visibility change returned HTTP 422 (private-plan restriction).
A read-only history preflight found deployment identifiers and unpublished security
findings, so that earlier pass made no repository visibility change. The owner
subsequently made the repository public on October 16, 2026. The explicit-allowlist
builder and Pages workflow are configured, and the parent dispatched run
`38978598334`. Publication is being verified, not asserted as complete. Earlier
private runs produced a downloadable preview, not a live website. See
[PAGES.md](PAGES.md) for the deployment and verification handoff.
