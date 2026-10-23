# Release procedure

[简体中文](../zh-CN/releasing.md) · [Release notes](releases.md) · [Contributing](contributing.md)

The `Release` workflow builds one sdist and a wheel from that sdist, retains their
member inventory and SHA-256 values, and tests the same wheel in seven isolated
installation consumers. A manual main-branch run may upload those files only after
the build and every consumer succeed. Pull-request runs validate build/consumption
and cannot publish. Tags and ordinary main pushes do not trigger this workflow.

## Configure the publication boundary first

Before the first PR validation or publisher registration, configure the GitHub
`pypi` environment:

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

1. Review the source, matching bilingual notes and the seven acceptance items in
   the release tracker. Keep dependency policy, historical provenance and
   restore/recompute compatibility explicit.
2. Run locked complete checks locally and the PR quality/installation workflows.
   The existing quality matrix is Linux 3.11/3.14 and macOS/Windows 3.14. The seven
   retained-wheel consumers are Linux x86_64 3.11/3.12/3.13/3.14, Linux ARM64 3.14,
   macOS ARM64 3.14 and Windows amd64 3.14. These are distinct check sets, not every
   supported Python/platform combination.
3. Inspect the actual sdist/wheel members and metadata. The manifest records source
   commit, corpus version, Python/dependency requirements, the two artifact digests
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
manifest's SHA-256 values. Use the README's package-index installation command in
a fresh supported environment, then execute its chart and knowledge examples.
A successful source-snapshot installation is not this index-install check.

Create `v0.1.0` at the accepted source SHA and a GitHub Release only under the
publication authorization. Attach the verified wheel, sdist and manifest. GitHub's
automatic source ZIP/tar archives are git snapshots, not the published sdist.
Record actual workflow results, artifact identity, downloaded digests, installation
results and remaining limits in the release. Refresh the manually maintained
bilingual Pages site from that accepted source and verify the affected live pages.

If upload succeeds but tag/Release/site work fails, retain the successful upload
and report the partial state. Finish the missing delivery from the verified files;
do not rebuild or upload replacements under the same version. A duplicate-file
failure is not permission to enable `skip-existing`. Content changes require a
new reviewed release version.
