# Repository structure and calculation boundaries

[简体中文](../zh-CN/architecture.md) · [Project](../../README.md) · [Knowledge](knowledge.md)

Birth records, modern time resolution, requested configuration, the tropical
natal chart, major aspects, text output and independent knowledge are implemented; their
usage and constraints are in the [birth](birth.md), [configuration](configuration.md),
[chart](chart.md), [aspect](aspects.md), [cross-chart](cross_aspects.md), [result](records.md)
and [knowledge](knowledge.md) guides.
The current chart is
a reproducible modern tropical, geocentric natal chart, with independent access
to its underlying knowledge.

## Organization

The intended package layout is below. Create modules as their first functionality
arrives; a name in this map does not require an empty package or an extra layer.

```text
src/astrology/
  birth.py          Original records and resolved instants
  config.py         Requested chart and tradition choices
  celestial.py      Concrete adapter to celestial-calendar
  zodiac.py         Zodiac definitions and sign classification
  houses.py         House-placement rules over supplied geometry
  aspects.py        Aspect definitions, orbs, and local motion
  chart.py          Composition and immutable chart results
  cross_aspects.py  Static comparison of supplied charts, retaining both sources
  lunar_phase.py    Oriented solar/lunar arc and named lunation types
  dignities.py      Named seven-planet rulership and four essential statuses
  summaries.py      Explicit-population statistics and supplied-chart summaries
  text.py           Result tables with supplied vocabulary
  knowledge/        Concepts, sources, entries, and independent queries
tests/              Domain tests and installed-consumer tests
docs/en/            English guides and explanations
docs/zh-CN/         Matching Chinese guides and explanations
```

Executable definitions live with their domain. `chart.py` composes them and owns
the success contract of a complete chart; it does not become the owner of every
shared definition. Common values move to a shared module only when actual users
need them. Package imports and knowledge queries must not initialize celestial.

`cross_aspects.py` composes existing chart results without astronomy. Shared
angular/orb arithmetic remains in `aspects.py`; single-chart pair eligibility
and local motion stay with `find_aspects`, separate from static cross pairing.

Knowledge and calculation remain connected by stable identifiers, described in
[Knowledge organization](knowledge.md). Additional UI applications can consume
the result later without moving calculation into a frontend.

## Birth data and time

Preserve the original date, calendar, clock reading, precision, location, source,
and timezone information. Store the resolved instant and the choices used to
resolve it separately. An explicit offset and an IANA timezone are distinct input
forms; timezone attachment alone does not detect a DST gap or choose a fold.

The current `prepare_natal_input` validates known time, timezone and location;
it does not calculate a chart. The `natal_chart` entry point requires that input.
Unknown time remains representable and is rejected by preparation
rather than replaced with noon. Historical inputs need their own calendar and time-scale
contract, including the difference between pre-1972 UT1 and modern UTC.

## Astronomy and astrology

The adapter returns astronomical values with their units, coordinate conventions,
and provenance. The astrology modules derive signs, house membership, and aspects
without discarding those values.

Keep these choices distinct:

| Choice | Example | What changes |
|---|---|---|
| Model for a quantity | Ephemeris or Delta T model | Method and supported domain |
| Definition or tradition | Whole Sign versus Placidus; tropical versus sidereal | The question being calculated |
| Implementation | Cache or an equivalent numerical implementation | Internal execution, unless the public numerical contract changes |

An object's identity also survives model selection. Mean nodes, Meeus five-term
true nodes, and osculating nodes cannot silently substitute for one another.
Constructed composite points retain their construction identity rather than
pretending to be physical bodies at a birth instant.

## Composition and failures

Represent positions, axes/house geometry, and astrological classifications
separately. A complete natal calculation may require all requested components;
future partial-chart entry points must state their own success contract.

celestial v0.8.0 provides a strict fourteen-object snapshot with rates and houses.
The adapter uses it within its joint domain. Selecting seven output
objects does not widen that domain. Genuine independent positions and house
queries are candidate celestial v0.10.0 work.

If requested Placidus geometry is unavailable, the adapter reports that result
explicitly and never falls back. Any future fallback requires an explicit policy
and must record both requested and effective systems. Equal and Whole Sign also
retain the upstream restrictions on undefined axes; they are not universal
fallbacks.

## Reproducibility

Retain input and resolved configuration, actual models and versions, TT/UT1
values, raw astronomy, and derived results. Defaults must resolve to named
choices before being recorded.

Results remain in memory; constructor checks verify pure derived-value consistency,
not the claimed astronomical origin. A new natal calculation uses resolved UTC
and the requested configuration without re-resolving timezones. Structured results,
provenance and text output are described in the [result guide](records.md).

Numerical agreement with celestial checks composition. Independent cases check
the complete result under matched conventions. Tests must exercise timezone
ambiguities, wrap, cusp ownership, rounding carry, retrograde motion, exact
aspects, and undefined house geometry.

## Delivery order

Birth/configuration values, the independent knowledge catalog, the tropical
natal chart, major aspects and text output are implemented,
with bilingual documentation and installed-package verification.

The [v0.1.0 milestone](https://github.com/0xf3cd/astrology/milestone/1) owns task
status. The source layout can evolve as these concrete implementations reveal
shared needs; a general backend/plugin framework is not a prerequisite.
