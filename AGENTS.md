# Agent instructions

## Scope

This is a Python Western astrology library in its initialization stage. Read
`README.md`, `docs/en/architecture.md`, `docs/en/knowledge.md`, and the relevant
issue before implementing a feature. GitHub issues hold the implementation scope
and acceptance criteria.

Use celestial-calendar for time scales, ephemerides, and house geometry. This
repository owns birth-input interpretation, astrological classifications, rule
variants, chart composition, and serialization.

## Domain contracts

- Preserve original birth records separately from resolved calculation instants.
  Missing time and location remain explicit; do not manufacture noon or a location.
- Distinguish physical objects, mathematical points, and constructed chart points.
  Name node and apogee definitions rather than using an ambiguous accuracy switch.
- Keep astronomical values separate from signs, house placement, and aspects.
- Record resolved models, versions, and configuration. A failed requested house
  system must not silently become another system.
- Cite the sources and applicability of astrological rules. Represent conflicting
  traditions as named variants; confirm unresolved definitions before encoding them.
- Begin with a concrete celestial adapter. Add shared abstractions only when
  actual implementations or callers need them.

## Python

Use complete type annotations, snake_case modules and functions, PascalCase types,
and two-space indentation. Inputs, configuration, rules, and results are immutable
by default; frozen dataclasses must also isolate mutable members and caller-owned
data. Prefer ordinary pure functions and declarative tables for data-shaped rules.
Keep I/O, native initialization, caches, and other effects explicit at their
owning boundary. Avoid global mutable configuration and silent substitutions.

Definitions belong to their domain; entry points compose them. Add shared
abstractions only for concrete callers. Names and types carry meaning; comments
explain reasons or constraints. Public input checks must work under `python -O`.

Python 3.11–3.14 is supported. Use `uv sync --locked`, then
`uv run --locked python tools/check.py` for the same checks as CI. Configuration
and pinned tool versions live in `pyproject.toml` and `uv.lock`. Change both when
updating dependencies and verify the minimum and maximum Python versions.
The development package provides a tropical natal chart API and
chart-independent knowledge queries. Importing it initializes no native
astronomy.

## Knowledge and documentation

Use English for PR and issue titles/bodies, comments, and review replies. English
is the primary documentation language; maintain matching Chinese pages.

The repository is also a knowledge base. Concepts, source records, rule variants,
and statements need stable, language-independent identities. Knowledge queries
must work without a chart or native astronomy initialization. Keep source status,
prerequisite status, default-output eligibility, and chart matching distinct.

Keep executable rules in their owning domain; reference them from knowledge and
generate reference tables from that source. Original quotations, translations,
and project-authored explanations remain distinguishable. Preserve uncertainty
and incomplete prerequisites instead of turning them into applicable conclusions.

Provide Chinese and English README, guides, and public reference documentation.
Update matching pages together; public docstring summaries and contracts are
bilingual. Identifiers, signatures, units, defaults, and machine-readable rule
definitions have one source. Check translation coverage and review semantic
equivalence; original quotations are not rewritten to match prose style.

This file is the single agent-instruction source; reader documentation follows the
bilingual paths above. Create source modules only when they contain functionality.

## Verification and delivery

Test domain boundaries and independently sourced reference cases with explicit
configuration and tolerances. A serialization round trip checks preservation;
recomputation and external references check different properties.

Run the complete check command before submitting. Demonstrate that new checks
reject representative defects. Review source fidelity, aliasing, unnecessary
abstractions, translation meaning, and gaps in the tested domain separately from
automated results. Record commands actually executed and unresolved limits in
the PR. Contribution guides in `docs/en/` and `docs/zh-CN/` explain these checks.

Use synthetic or appropriately anonymized examples. Public files and discussions
must contain only project-relevant information. Commit through the maintainer's
approved signing path. Merges and releases require explicit authorization.
