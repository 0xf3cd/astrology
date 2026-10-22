# Contributing

[简体中文](../zh-CN/contributing.md) · [Documentation](index.md)

Start with the relevant issue and the [architecture](architecture.md). An issue
defines the feature's scope and acceptance cases. Keep changes small enough to
explain and review as one behavior.

Use English for pull requests, issues, comments, and review replies, including
their titles. Documentation is English-first, with matching Chinese pages.

## Run the checks

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from
the repository root:

```sh
uv sync --locked --python 3.14
uv run --locked python tools/check.py
```

Python 3.11–3.14 is supported. The lower bound matches celestial-calendar 0.8.0,
which is a hard dependency of the package. CI runs the
same command on Linux 3.11/3.14 and macOS/Windows 3.14. Use
`uv sync --locked --python 3.11` to check the lower endpoint locally.
Use a current patch release for development checks. Safe sdist extraction in these checks
requires Python 3.11.4 or later; the installed library's supported minor versions
remain 3.11–3.14.

The astronomy dependency publishes wheels for Linux x86_64 and aarch64, macOS 14+
arm64 and Windows amd64, and no source distribution. This package therefore
cannot be installed on any other platform, and browsing the knowledge catalog
needs the same install.

The command checks Ruff lint/two-space formatting, strict mypy, pytest in normal
and optimized modes, document pairs/local links, fresh strict HTML/doctest builds,
and an isolated wheel install with its declared runtime dependencies.

The distribution check runs `python -m build --sdist`, extracts the archive, and
runs `python -m build --wheel` inside the extracted tree. Strict HTML/doctest builds
also run there and import the extracted package sources. The check then validates
the API/catalog pages, generated search index and query code, and doctest results.

The installed consumer exercises birth,
timezone provenance and configuration outside the checkout; its complete-chart,
restoration, replay and text checks are described in the
[record guide](records.md#verification-and-limits). A separate knowledge-only
consumer lists, looks up, filters and resolves citations without time/native
initialization. Both use isolated imports in normal and optimized modes; wheel
and sdist checks require the actual corpus resources.

Temporary HTML, doctest reports,
distributions, and consumer environments use `SCRATCH` when set, otherwise the
system temporary directory, and are removed on exit. Build metadata and tool
caches may remain in ignored checkout directories.
Strict documentation builds may fetch the Python intersphinx inventory from
`docs.python.org`; allow network access as well as installing the build dependencies.

CI installs uv 0.12.5 with a SHA-256 digest for each platform archive from its
[upstream release](https://github.com/astral-sh/uv/releases/tag/0.12.5). A fresh
tool-cache directory prevents setup-uv from skipping archive verification on a cache hit.

When uv, setup-uv or the runner platform changes, repeat the negative check on a
temporary branch: replace every matrix `uv-checksum` with a quoted string of 64
zeros and push it. Each setup-uv step must fail with a checksum-mismatch error,
and subsequent uv commands must be skipped. An unrelated download/network failure
is not sufficient. Do not merge this branch.

Tool versions are locked in `uv.lock`. Sphinx 8.2.3 serves Python 3.11; Sphinx
9.1.0 serves newer Python versions. Coverage is reported to locate gaps; it
cannot certify the astronomy values, which the reference cases do. Tests exercise
birth/time, chart/configuration, record and text contracts as well as development checks. Add domain
tests with each feature.

For local formatting, run `uv run ruff format .`. A failed command stops the
check run; fix its cause and rerun. Dependency changes must update the lock and
pass both Python endpoints. Keep suppressions narrow and explain their reason.

To keep HTML for inspection, build it into the ignored `build/` directory:

```sh
uv run python -m sphinx \
  -E -a -n -W -b html -c docs \
  -d build/docs-doctrees . build/docs
```

Open `build/docs/index.html` for both language entries. The current combined
search index keeps English stemming and uses matching Python/JavaScript Chinese
character-bigram tokenization. See [search limits](knowledge.md#translation-revisions-and-search).
The gate checks the actual generated search index and emitted splitter/stemmer
contract, per-page language/counterpart navigation, complete catalog anchors and
current translations. A successful build alone is insufficient. Independent
verification can execute the generated JavaScript query/index code; a Python
tokenizer unit test does not prove browser behavior.

Sphinx discovers only the two root READMEs and sources under `docs/`. Keep virtual
environments outside `docs/`: sources anywhere under that directory are documentation
inputs, while sibling directories are not. Warnings in these document sources still
fail the strict build.

Install this development package from the checkout using `uv sync` above. Its
distribution name/version is `celestial-astrology` / `0.1.0`; the Python import
remains `astrology`. This candidate has not been published on PyPI. The unrelated
PyPI project `astrology` is not this library. Confirm the installed identity:

```{doctest}
>>> from importlib.metadata import version
>>> version("celestial-astrology")
'0.1.0'
```

The checks execute both READMEs against an isolated wheel install, compare their
documented output, inspect the wheel's actual Markdown links, and resolve both
language paths against the built site. They also hide each distribution's metadata
separately in a disposable install. With metadata hidden they verify unchanged restoration,
`ChartReplayError` on replay, and `PackageNotFoundError` on direct calculation when project
metadata is missing. Both Python modes run before the metadata is restored.

For manual Pages delivery, build from a clean committed checkout and set
`ASTROLOGY_DOCS_SOURCE_SHA` to its full lowercase commit SHA. The root page then
renders that source archive and its install command; an ordinary local build is
labeled without a fixed revision. Keep doctrees, caches and other build-control
files outside the exported site. Inspect all generated sources/downloads/assets
before updating the dedicated `gh-pages` branch with `.nojekyll`. This is a manual
site update, not automatic source publishing or a package release. Actual acceptance
also checks the deployed root, every README URL and English/Chinese browser search;
local HTML success alone is insufficient. Snapshot installation and the Python
intersphinx inventory require network access.

## Design

Use immutable values for inputs, configuration, rules, and results. A frozen
dataclass still permits mutations inside a list or dictionary: store immutable
members or copy and isolate mutable input at the boundary. A caller changing its
input after construction must not change a stored chart.

Prefer ordinary functions with explicit arguments and return values. Keep file
access, native initialization, network calls, and caches visible at their owning
boundary. Importing the package or reading knowledge must not calculate a chart.

Use tables for data-shaped rules and functions for computation. Keep definitions
in their domain and compose them at the entry point. Add an abstraction when
actual callers share a contract; a possible future backend is not a caller.
Names and types should express meaning before comments have to explain it.

Configuration must affect the computation it describes. Reject unsupported
choices and retain requested/effective settings. Avoid implicit global settings,
silent substitutions, and factories whose return type depends on hidden state.

## Correctness

Test the domain boundary as well as representative values: non-finite numbers,
time ambiguity, coordinate wrap, exact endpoints, missing information, and
unsupported combinations. Public validation must still run under `python -O`.

Record the source, model/version, time scale, coordinate convention, configuration,
units, and tolerance with numerical fixtures. A round trip tests preservation;
recomputation tests execution; an independent source tests agreement. Shared
formulas or copied datasets can make apparently independent checks agree on the
same mistake. Explain why a reference can detect the defect being tested.

Use synthetic examples or sources that can be redistributed. Keep astronomical
validation separate from the claimed interpretation of a chart.

The natal chart cases in `tests/reference/natal_reference.json` compare two
instants, one per hemisphere, against JPL Horizons and against definition-level
checks. The fixture records the query URLs, the ephemeris kernel Horizons names
for each body and for the geocenter (the Sun, the Moon, Mercury and Venus use
DE441, the other bodies their own kernels), the retrieval time and the
conventions used.

To fetch the two Horizons cases again without changing the committed fixture:

```sh
uv run --locked python tools/fetch_reference.py --output build/natal_reference.json
```

This requires network access and only the Python standard library. The output path
is required; the tool reads no local reference or review files. It writes query URLs,
source kernels, conventions, retrieval time and values, then prints the output file's
SHA-256. Inspect numerical and provenance changes before deliberately replacing the
versioned fixture. Offline tests use controlled responses and are separate from a live fetch.

The body tolerances follow the upstream's own model error against Horizons, not
the two instants. The Sun and the planets agree to about 0.8 arcseconds in
longitude over 24 instants in 2000-2002 and to 1.3 at the 2020 instant; the
truncated lunar model agrees within 10 arcseconds in longitude and 2.4 in
latitude over 60 instants in 2000-2030. Those samples were taken ad hoc and are
not kept in the repository. The tolerances are 3 arcseconds for the Sun and the
planets, 15 for the Moon, 1 for latitude, 3 for the Moon's latitude and 1 for
the nodes. The axes and the Placidus cusps use 0.001 degrees (3.6 arcseconds):
the two instants differ by at most 0.91 arcseconds there, which is the difference
between the UT1 the library models and the UT1 Horizons observes.

Each reference detects a different defect. Whether a defect is caught depends on the
tolerance and on the offset the library already has from the reference (up to 0.91
arcseconds for the axes and 3.4 for the Moon's longitude), so a shift somewhat below
the tolerance can still be caught. The cases below were judged with that offset counted:

| Reference | Detects | Does not detect |
|---|---|---|
| Horizons longitudes | A wrong ephemeris or body mapping. UTC used for TT (64-69 seconds) moves the Moon 35-42 arcseconds and Mercury 3-5. | A shift that stays inside the tolerance with that offset counted, including a path that corrupts only the Sun (2.6-2.8 arcseconds). |
| Exact leap-second relation | UTC or UT1 passed where TT belongs: the reported JDE(TT) is 0.2-0.3 seconds off. | A rotation path that treats UTC as UT1; the reported JDE(TT) stays exact. |
| Horizons sidereal time, axes | The mean sidereal time used for the apparent one (0.002-0.005 degrees). UT1 taken as UTC: 5.0 arcseconds at the northern instant and 3.7 at the southern one, only just past the 3.6 threshold. A mean obliquity for the true one at the northern instant (5.7). | A mean obliquity for the true one at the southern instant (under 1 arcsecond). |
| Horizons sidereal time, Placidus cusps 2, 3, 11 and 12 | Cusps away from the Placidus time division by more than about 0.0015 degrees, such as another house system. | A misreading of the Placidus definition shared with the check. This fixture has no external cusp values; cusps 5, 6, 8 and 9 are checked only as exact opposites. |
| Meeus chapter 47 nodes | A wrong node definition, direction or missing nutation term. | A mistake in the shared formula, and a TT/UT mix, which moves a node by under 0.4 arcseconds. |

The Horizons-based and hand-computed aspect checks have three parts. Cases in `tests/test_aspects.py`
need no astronomy. Dividing a one-hour longitude change by the elapsed time checks
the sign and unit of the rates used to determine applying or separating motion.
The reference tests configure the orbs that Astrodienst publishes for its
Hellenistic drawing style and compare the resulting aspect set with one derived from
the Horizons longitudes. Where a pair lies near an orb limit, they detect a wrong orb,
combination rule or angle; they also detect a node that takes part. They cannot
detect a longitude error smaller than the 0.4-degree margin, and the two instants
hold no sextile or opposition, so those angles rest on the hand-computed cases. They
do not check the status against an external source: Horizons supplies no rates here,
and the style page gives parameters, not the aspect list of a chart.

The separate Swiss complete-chart fixture adds independent rates and all house
cusps, plus separately derived placements, aspects and motion for four synthetic
instants. All five aspect identities occur. Its case-specific tolerances and source
limits are documented in the [record guide](records.md#verification-and-limits).
The stored development record tests replay separately; it is not external evidence.

## Knowledge and documentation

Follow the [knowledge design](knowledge.md). Link explanations to stable concepts,
rules and sources. Preserve original quotations and label translations; a checked
source is not evidence that a particular chart meets its prerequisites.

Update both language pages when behavior changes. Public docstring summaries and
contracts are bilingual; identifiers, signatures, units, and defaults have one
source. Execute examples and inspect the generated pages. Automated coverage can
detect a missing translation file, but cannot establish semantic equivalence.
The catalog checks also reject stale text revisions, missing record descriptions,
unknown references and duplicate IDs. Both language views have executable examples;
source and translation review checks that conditions and limits retain their meaning.

## Review evidence

For contributions written with AI, the contributor remains responsible for the
result. Include the issue, behavior change, checks actually run, and unresolved
questions in the pull request. Distinguish executed evidence from proposed checks.

Reviewers check source fidelity, unsupported assumptions, mutation/aliasing,
failure behavior, unnecessary abstractions, and translation meaning. Passing
lint or achieving high coverage does not answer these questions. When changing
a check, demonstrate both an accepted input and a defect it rejects.

Merge and publication require maintainer approval. CI reports checks; repository
rules must separately require them if merging is to be blocked automatically.
