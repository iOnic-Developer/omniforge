# Publication controls

Prepared October 16, 2026 for PR #5 on `docs/review-2026-10-16`.
This is an approval checklist, **not permission to publish**.

## Current boundaries

- The source repository is private. Live metadata reports `private: true`, `has_wiki: false`,
  `has_pages: false`, and no repository licence. Do not change visibility,
  enable GitHub Pages, create a public mirror or grant an open-source licence.
- `docs/index.html` is site source, not evidence of a live public website.
- README screenshots use repository-relative assets. Do not copy private raw,
  attachment or authenticated asset URLs into Docker Hub or public announcements.
- The wiki sources remain in `docs/wiki/`. Their `.md` relative links are for
  the private repository browser. A separate native GitHub wiki export would
  need link/asset rewriting and validation; it has not been published here.
- `docs/review/**` is a preserved historical audit. Do not edit it to make old
  findings or inventory look current. Current product docs are separate.

## Copy ready for review

**Proposed short description** (ASCII; 94 characters):

> Turn your Python and Node scripts into tools for your AI. Self-hosted, trusted-code workspace.

The owner-requested Docker Hub overview uses this text after validation.
`DOCKERHUB.md` is the self-contained public long-description source: no private wiki links or external private media.
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
The Python image includes application source: a private GitHub repo does not
make distributed image contents confidential. Review contents and rights before
any further public image publication. No image was built or published here.

## Approval gates

- [ ] Owner approves final copy and its intended destination.
- [ ] Image digest selected, provenance recorded and advertised features tested.
- [ ] Single-admin/no-login model, open management API, shared-container execution
      and limited MCP transport remain visible before installation instructions.
- [ ] No universal client-compatibility, sandbox, multi-account or stable-release claims.
- [ ] Public copy works without repository access or private asset links.
- [ ] Any screenshots are reviewed for code, keys, private data and visible hostnames.
- [ ] All rights reserved is retained; third-party font notices remain separate.
- [ ] Repository visibility and Pages settings stay unchanged.
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

### Checks completed in this worktree

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

The product-presentation pass stays on existing PR #5. Application/runtime files and
historical review evidence are unchanged. The source remains private; Wiki and Pages
remain disabled. A public website needs a separate hosting/privacy decision. Docker Hub
is already public; its overview is updated from this self-contained text without private
asset links. No new image or application deployment is part of this task.
