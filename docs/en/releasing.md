# Release procedure

[简体中文](../zh-CN/releasing.md) · [Release notes](releases.md) · [Contributing](contributing.md)

The `Release` workflow builds one sdist and a wheel from that sdist, retains their
member inventory and SHA-256 values, and tests the same wheel in seven isolated
installation consumers. A manual main-branch run may upload those files only after
the build and every consumer succeed. Pull-request runs validate build/consumption
and cannot publish. Tags and ordinary main pushes do not trigger this workflow.

## Check the publication boundary

Before release acceptance, read back main's branch protection and the GitHub
`pypi` environment, including its branch-policy list. Setting changes require
separate maintainer authorization. The publication boundary is:

- Use selected deployment branches/tags with exactly one **branch** rule, `main`.
  Do not allow PR merge refs, tags or unrestricted deployments. Read back both
  the environment policy and its branch-policy list; a workflow `if` alone does
  not protect against a PR that changes the workflow.
- Require maintainer approval before the publication job starts. Do not bypass
  that approval or deployment restrictions as an administrator.
- Leave existing main-branch protection and the separate Pages environment intact.

Register a PyPI [pending Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
for project `celestial-astrology`, owner `0xf3cd`, repository `astrology`, workflow
`release.yml`, environment `pypi`. A pending publisher does not reserve the name.
For an existing project, use its [publisher settings](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).
No long-lived upload password is supplied. A missing publisher or denied environment
is a blocker; do not switch to a token or weaken protection to continue.

## Prepare and inspect the candidate

Before publishing a new version, prepare its version bump and matching
documentation in a separate reviewed change. Release notes describe what shipped;
actual package-index availability belongs in the release record.

1. Review the source, matching bilingual notes and the acceptance criteria in
   the release tracker. Keep dependency policy, calculation conventions and
   breaking API changes explicit.
2. Run locked complete checks locally and the PR quality/installation workflows.
   The existing quality matrix is Linux 3.11/3.14 and macOS/Windows 3.14. The seven
   retained-wheel consumers are Linux x86_64 3.11/3.12/3.13/3.14, Linux ARM64 3.14,
   macOS ARM64 3.14 and Windows amd64 3.14. These are distinct check sets, not every
   supported Python/platform combination.
3. Inspect the actual sdist/wheel members and metadata, including the UTF-8
   Markdown descriptions in the sdist's `PKG-INFO` and the wheel's `METADATA`.
   Both contain the English `README.md`, not separate English/Chinese descriptions.
   They must match the accepted `README.md` and contain no
    stale candidate-only statements. Check the README's package name and installation
    commands, and execute its examples against the accepted package. Check the rendered English and
   Chinese pages from both the checkout and the extracted sdist. Snapshot labels
   are always checked; fixed-SHA source/archive links are checked when
   `ASTROLOGY_DOCS_SOURCE_SHA` identifies the build's source revision.
   The manifest records source
   commit, Python/dependency requirements, the two artifact digests
   and every archived file's path/size/digest. Unexpected members, changed source bytes or
   changed runtime requirements fail inspection.
4. Verify representative rejection cases for the new release checks. Every new
   uv step pins uv 0.12.5, its named archive SHA-256, and a fresh tool cache. On an
   unmerged probe branch, wrong archive digests must fail before uv runs, including
   the ARM consumer. A network failure is not that evidence.

To retain the distributions from a local complete check, use a new output directory:

```sh
uv sync --locked --python 3.14
uv run --locked python tools/check.py --artifacts-dir dist/packages
```

The destination must not already exist. This retains the files that passed the
complete distribution check; it does not upload them or establish a release.
The workflow's `tools/release.py prepare` checks the unchanged source and writes
`dist/manifest.json` plus separate build-job digest outputs. No second distribution
wheel is built by preparation or consumption.

The README installs the latest release by package name and offers source
installation separately. Release notes link to the index page for their version.
Actual availability and partial delivery belong in the release record, with the
accepted source SHA, workflow run/artifact IDs and file digests.
The Pages site remains a source snapshot even when it shows a published version.

### Merge and publication acceptance

Check results must belong to the candidate being accepted. A successful old-head
run or review is not a current-head result.

| Condition | Enforcement and required action |
|---|---|
| Four full quality jobs: Linux 3.11/3.14, macOS/Windows 3.14 | Required main status contexts with strict up-to-date checks. All must succeed before merge; verify the publication SHA's main results before approving publication. |
| Release build and seven retained-wheel consumers | Workflow dependencies prevent publication until they succeed. Inspect them before merge too; they are not extra required branch-protection contexts. |
| Code and security review, including bot findings | Maintainer acceptance, not a configured required status. Resolve blocking findings. Record missing, unavailable or stale results as not performed, never as success; only the maintainer may explicitly accept proceeding with those recorded limits. |
| Human merge and publication authorization | Maintainer decisions; a green check does not authorize either operation. Record the exact accepted version, SHA and artifacts. |
| Publication job | Manual dispatch on main, successful build/consumers, and approval by the pypi environment's required reviewers. Its only selected deployment branch rule is main. |

If actual protection or workflow configuration differs, stop the affected
acceptance and report the difference. Do not weaken settings or silently turn a
manual requirement into a claim of automatic enforcement.

### Rehearse without uploading

Use a no-upload rehearsal when changes to the release procedure or workflows leave
a failure path untested by the normal pre-publication checks. To check instructions,
run the affected steps locally with the retained wheel and sdist; to check changed
build/consumer steps, use a pull-request workflow run. Record the gap, exact wheel
and sdist filenames/digests, commands and results. A routine release can use the
formal workflow's build and same-wheel consumers before manual approval without
a separate rehearsal. A no-upload run does not verify OIDC credentials, PyPI upload
or live deployment; those require authorized publication and post-publication checks.

## Authorize and run publication

After the candidate is accepted and merged, obtain publication authorization for
its version and full main commit SHA. In Actions, choose `Release`, `Run workflow`,
branch `main`, and enter that exact `version` and `sha`. The build rejects a source
that differs from the requested/current remote main. Do not substitute a moving
branch name for the SHA.

The artifact is downloaded by the exact ID returned by this run's build job, not
by a reusable name or another run. Each consumer compares wheel/sdist digests with
separate build-job outputs, checks the manifest against source, and installs only
the retained wheel outside the checkout. Its expected source chart is computed on
that same runner. Normal/optimized knowledge, chart, metadata-failure and README
checks must pass without rebuilding the publication wheel.

Inspect those results and `manifest.json` before approving the `pypi` deployment.
Only the Linux publication job has `id-token: write`; it needs both the build and
the entire consumer matrix. It rechecks the exact two package filenames and
SHA-256 values, then calls the commit-pinned PyPI action with attestations enabled
and `skip-existing: false`. It runs no repository build code with that permission.

## Verify and record the published result

Download both distribution files from PyPI and compare their bytes with the saved
manifest's SHA-256 values. Read that version's PyPI description, check its package
name and installation commands, and compare it with the accepted README and descriptions
inside the downloaded files. Use the README's package-index installation command in
a fresh supported environment, then execute its chart and knowledge examples.
A successful source-snapshot installation is not this index-install check.

Create the version tag (`v` followed by the authorized release version) at the
accepted source SHA and a GitHub Release only under the publication authorization.
Attach the verified wheel, sdist and manifest. GitHub's
automatic source ZIP/tar archives are git snapshots, not the published sdist.
Read back the Release's version, tag target, description and attached artifact
digests; do not infer success from the creation request alone.
Record actual workflow results, artifact identity, downloaded digests, installation
results and remaining limits in the release. Refresh the manually maintained
bilingual Pages site from that accepted source and verify the affected live pages.
Check the site root's version and source SHA, both README installation paths,
release notes and affected English/Chinese feature pages. Compare them with the
accepted build; a local HTML success is not evidence that the site was deployed.

If upload succeeds but tag/Release/site work fails, retain the successful upload
and report the partial state. Finish the missing delivery from the verified files;
do not rebuild or upload replacements under the same version. A duplicate-file
failure is not permission to enable `skip-existing`. Content changes require a
new reviewed release version.

## Mirror an accepted release to Gitee

GitHub remains the source repository. Before the first mirror, the maintainer must
select a public Gitee namespace/repository and verify its permissions, two-factor
authentication, recovery readiness, fresh sign-in and Git/API clients. Repository
creation, account settings and publication each require authorization.

Use a clean checkout at the accepted full SHA with the matching package version.
Retain the original files from its GitHub Release or formal workflow artifact in
this layout; do not rebuild packages or regenerate a published manifest:

```text
release-files/
  manifest.json
  packages/
    celestial_astrology-0.6.0-py3-none-any.whl
    celestial_astrology-0.6.0.tar.gz
```

For a read-only preflight, replace the repository and SHA placeholders:

```sh
uv run --locked python tools/mirror.py check --version 0.6.0 --sha ACCEPTED_FULL_SHA --repository NAMESPACE/REPOSITORY --branch main --files release-files
```

Keep the retained files outside the checkout. `check` is anonymous and makes no
remote writes. It verifies the GitHub tag and stable Release's uploaded assets,
including each raw size and SHA-256, cross-checks the two distribution digests with
PyPI, then checks the original manifest and archive/source agreement without
installing or rebuilding. Unrelated digest environment variables are ignored.
An older accepted release need not be the current GitHub main tip.

After separate publication authorization, run the same command with `publish`
instead of `check`. The operator supplies `GITEE_ACCESS_TOKEN` through the process
environment for API writes and establishes Git authentication separately. Do not
put credentials in a URL, command argument or retained log. The tool installs no
authentication files or helpers; prompting is disabled. Anonymous Git reads ignore
operator credentials, URL rewrites and extra headers. API writes use the fixed
HTTPS Gitee origin, documented form/multipart token fields and no redirects.

Only the selected `refs/heads/main` (or the explicitly named landing branch) and
`refs/tags/v0.6.0` may be written, resolving to the accepted commit. Branch updates
must be known fast-forwards; matching annotated tags are retained after peeling.
An existing repository's default branch must match the landing branch. An empty
repository may receive its first selected branch, but its default branch is read
back before release creation. A mismatch requires separately authorized operator
configuration. No force push, all-ref mirror, webhook or automatic setting change
is performed. An ahead/divergent branch or unknown ancestry fails; completing an
older partial mirror after a newer release advanced the branch needs operator
intervention.

The release body is the exact Chinese version section from the accepted Git
object's `docs/zh-CN/releases.md`, using absolute tagged guide links. Comparison
normalizes CRLF only. Matching release metadata and attachments are retained.
The tool requests the first attachment page at 100 records per page. Any inventory
above the expected three files is a conflict; a successful inventory fits entirely
on that page. JSON responses are bounded at 2 MiB and each original file at 64 MiB.
Missing files are uploaded from the same immutable buffers that passed verification. Duplicate names,
unexpected names or different downloaded bytes fail with attachment IDs.

After a failed or timed-out write, the tool reads anonymous state without
automatically retrying that write. An observed matching result is retained;
unconfirmed state stops the run. Inspect the partial delivery before an explicit
rerun, which inventories fresh state and adds only missing content from the
original files. The tool never deletes conflicts or rolls back completed work.

Anonymous attachment downloads allow only HTTPS `gitee.com` on the standard
port, including redirects. An unknown download origin fails; investigate actual
platform behavior during account acceptance rather than widening this policy
automatically. No API credential is sent during readback.

Record the accepted version/SHA, ref targets, notes, attachment IDs and anonymous
download digests. Inspect the actual Gitee landing page and Chinese README
selection, Chinese release rendering and source links. Verify all three anonymous
downloads against the retained files. Record these results with the other
publication checks before closing the release tracker or mirror issue.
