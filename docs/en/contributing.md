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

Python 3.11–3.14 is supported. The lower bound matches celestial-calendar 0.8.0;
the astronomy dependency will be added with the concrete adapter. CI runs the
same command on Linux 3.11/3.14 and macOS/Windows 3.14. Use
`uv sync --locked --python 3.11` to check the lower endpoint locally.

The command checks Ruff lint/two-space formatting, strict mypy, pytest in normal
and optimized modes, document pairs/local links, fresh strict HTML/doctest builds,
and an isolated wheel install. `python -m build` builds the wheel through the
sdist. The installed consumer runs outside the checkout, with isolated Python
imports, in normal and optimized modes. Temporary HTML, doctest reports,
distributions, and consumer environments use `SCRATCH` when set, otherwise the
system temporary directory, and are removed on exit. Build metadata and tool
caches may remain in ignored checkout directories.

Tool versions are locked in `uv.lock`. Sphinx 8.2.3 serves Python 3.11; Sphinx
9.1.0 serves newer Python versions. Coverage is reported to locate gaps; this
foundation has no numerical algorithms to certify. Tests currently exercise the
development checks. Add domain tests with each feature.

For local formatting, run `uv run ruff format .`. A failed command stops the
check run; fix its cause and rerun. Dependency changes must update the lock and
pass both Python endpoints. Keep suppressions narrow and explain their reason.

To keep HTML for inspection, build it into the ignored `build/` directory:

```sh
uv run python -m sphinx -E -a -n -W -b html -c docs . build/docs
```

Open `build/docs/docs/index.html` for both language entries. The current combined
search index uses English stemming; Chinese word segmentation is tracked in
[the documentation issue](https://github.com/0xf3cd/astrology/issues/2#issuecomment-6246614148).

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

## Knowledge and documentation

Follow the [knowledge design](knowledge.md). Link explanations to stable concepts,
rules and sources. Preserve original quotations and label translations; a checked
source is not evidence that a particular chart meets its prerequisites.

Update both language pages when behavior changes. Public docstring summaries and
contracts are bilingual; identifiers, signatures, units, and defaults have one
source. Execute examples and inspect the generated pages. Automated coverage can
detect a missing translation file, but cannot establish semantic equivalence.

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
