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

The astronomy dependency publishes wheels for Linux x86_64 and aarch64, macOS 14+
arm64 and Windows amd64, and no source distribution. This package therefore
cannot be installed on any other platform, and browsing the knowledge catalog
needs the same install.

The command checks Ruff lint/two-space formatting, strict mypy, pytest in normal
and optimized modes, document pairs/local links, fresh strict HTML/doctest builds,
and an isolated wheel install with its declared runtime dependencies. `python -m
build` builds the wheel through the sdist. The installed consumer exercises birth,
timezone provenance and configuration outside the checkout. A separate knowledge-only
consumer lists, looks up, filters and resolves citations without time/native
initialization. Both use isolated imports in normal and optimized modes; wheel
and sdist checks require the actual corpus resources. Temporary HTML, doctest reports,
distributions, and consumer environments use `SCRATCH` when set, otherwise the
system temporary directory, and are removed on exit. Build metadata and tool
caches may remain in ignored checkout directories.

Tool versions are locked in `uv.lock`. Sphinx 8.2.3 serves Python 3.11; Sphinx
9.1.0 serves newer Python versions. Coverage is reported to locate gaps; it
cannot certify the astronomy values, which the reference cases do. Tests exercise
birth/time and configuration contracts as well as development checks. Add domain
tests with each feature.

For local formatting, run `uv run ruff format .`. A failed command stops the
check run; fix its cause and rerun. Dependency changes must update the lock and
pass both Python endpoints. Keep suppressions narrow and explain their reason.

To keep HTML for inspection, build it into the ignored `build/` directory:

```sh
uv run python -m sphinx -E -a -n -W -b html -c docs . build/docs
```

Open `build/docs/docs/index.html` for both language entries. The current combined
search index keeps English stemming and uses matching Python/JavaScript Chinese
character-bigram tokenization. See [search limits](knowledge.md#translation-revisions-and-search).
The gate checks the actual generated search index and emitted splitter/stemmer
contract, per-page language/counterpart navigation, complete catalog anchors and
current translations. A successful build alone is insufficient. Independent
verification can execute the generated JavaScript query/index code; a Python
tokenizer unit test does not prove browser behavior.

Install this development package from the checkout using `uv sync` above. Its
local distribution name/version is `astrology` / `0.0.0`. The PyPI name
`astrology` belongs to an unrelated project; choose a publishing name before the
first release. Confirm the installed development identity:

```{doctest}
>>> from importlib.metadata import version
>>> version("astrology")
'0.0.0'
```

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
for each body and for the geocenter (the Sun and the Moon use DE441, the other
bodies their own kernels), the retrieval time and the conventions used.

The body tolerances follow the upstream's own model error against Horizons, not
the two instants. The Sun and the planets agree within 0.8 arcseconds in
longitude over 24 instants in 2000-2002 and within 1.3 at the 2020 instant; the
truncated lunar model agrees within 10 arcseconds in longitude and 2.4 in
latitude over 60 instants in 2000-2030. Those samples were taken ad hoc and are
not kept in the repository. The tolerances are 3 arcseconds for the Sun and the
planets, 15 for the Moon, 1 for latitude, 3 for the Moon's latitude and 1 for
the nodes. The axes and the Placidus cusps use 0.001 degrees (3.6 arcseconds):
the two instants agree within 0.92 arcseconds there, which is the difference
between the UT1 the library models and the UT1 Horizons observes.

Each reference detects a different defect, and only above its tolerance:

| Reference | Detects | Does not detect |
|---|---|---|
| Horizons longitudes | A wrong ephemeris or body mapping. UTC used for TT (64-69 seconds) moves the Moon 35-42 arcseconds and Mercury 3-5. | A shift below the tolerance, including a path that corrupts only the Sun (2.6 arcseconds). |
| Exact leap-second relation | UTC or UT1 passed where TT belongs: the reported JDE(TT) is 0.2-0.3 seconds off. | A rotation path that treats UTC as UT1; the reported JDE(TT) stays exact. |
| Horizons sidereal time, axes | The mean sidereal time used for the apparent one (0.004-0.005 degrees). | UT1 taken as UTC, or a mean obliquity for the true one: they move the axes by 0.0016 degrees at most, near the threshold. |
| Horizons sidereal time, Placidus cusps 2, 3, 11 and 12 | Cusps away from the Placidus time division by more than about 0.0015 degrees, such as another house system. | A misreading of the Placidus definition shared with the check. Cusps 5, 6, 8 and 9 are checked only as the exact opposites; no external source publishes the cusps. |
| Meeus chapter 47 nodes | A wrong node definition, direction or missing nutation term. | A mistake in the shared formula, and a TT/UT mix, which moves a node by under 0.4 arcseconds. |

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
