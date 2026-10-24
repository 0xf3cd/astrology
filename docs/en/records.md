# Chart results and text

[简体中文](../zh-CN/records.md) · [Chart](chart.md) · [API](reference.md)

`natal_chart` returns an immutable `NatalChart` in memory. Inspect its structured
values or pass it to `format_chart` with an explicit knowledge catalog. The
package provides no chart save/restore API or storage schema; see the
[release notes](releases.md) for the API removal.

## A complete example

This synthetic record falls in the half-hour repeated when clocks move back on
Lord Howe Island. Choose the earlier occurrence with `fold=0`. The location is
specified separately, not inferred from the timezone. There are no default
aspect orbs.

```{doctest}
>>> from datetime import date, time
>>> from astrology import (AspectRule, BirthRecord, Body, ChartConfig, HouseSystem,
...   IanaTimezone, Location, LunarNode, MajorAspect, ObjectOrb, OrbCombination,
...   TimePrecision, format_chart, load_catalog, natal_chart, prepare_natal_input)
>>> record = BirthRecord(date(2026, 4, 5), time(1, 45), IanaTimezone("Australia/Lord_Howe"),
...   Location(0, 0), TimePrecision.MINUTE, {"record": "synthetic"})
>>> config = ChartConfig(HouseSystem.WHOLE_SIGN, (*Body, LunarNode.MEAN_ASCENDING),
...   tuple(AspectRule(a, 6, (ObjectOrb(Body.SUN, 10),)) for a in MajorAspect),
...   aspect_objects=tuple(reversed(tuple(Body))), orb_combination=OrbCombination.MEAN_OF_ORBS)
>>> chart = natal_chart(prepare_natal_input(record, fold=0), config)
>>> chart.resolved.utc.isoformat()
'2026-04-04T14:45:00+00:00'
>>> len(chart.positions), bool(chart.aspects), sorted({h.orb_limit_deg for h in chart.aspects})
(11, True, [6.0, 8.0])
>>> catalog = load_catalog()
>>> table = format_chart(chart, catalog)
>>> print("\n".join(table.splitlines()[7:10]))
Sun [sun] | Aries 14°50'21" | 9 | D
Moon [moon] | Scorpio 13°32'41" | 4 | D
Mercury [mercury] | Pisces 17°05'04" | 8 | D
```

The Sun's orb is 10° and the other bodies use 6°; their mean is 8° for pairs with
the Sun and 6° otherwise. The explicit participant list excludes the node and
lists the bodies in reverse order; effective participants still follow the
requested object order.

The full table includes all requested objects, four axes, twelve cusps,
aspects with their oriented branches, deviations, limits and motion labels,
requested/effective configuration and provenance. Pass `language="zh-CN"` for
Chinese output. The supplied catalog must contain current names in that language;
missing or ambiguous names fail rather than fall back to another language.
Loading the catalog is explicit; formatting itself performs no resource I/O.

## Read the structured result

- `resolved.record` keeps the original Gregorian date, clock, stated precision,
  timezone form, location and source metadata. `resolved` separately keeps UTC,
  the offset, IANA key, fold and both timezone-data versions.
- `requested` keeps object/rule order, per-object orbs, their combination and
  the distinction between omitted (`None`) and explicit aspect participants.
  `effective.aspect_objects` gives the actual participants in requested object order.
- `positions` keeps unrounded longitude/latitude in degrees, physical distance
  in AU and longitude rate in degrees per TT day. Nodes have no distance (`None`).
  `times` keeps JD(UT1) and JDE(TT). Axes/cusps, placements and every aspect field
  are available, including the branch, signed deviation, limit and motion status.
- `provenance` keeps astrology/celestial-calendar versions, position frame and
  UT1 derivation; `effective` keeps the resolved Delta-T model and evaluation.

Direct construction of `NatalChart` checks field types, ranges and pure derived-value consistency:
signs, house membership and aspects must agree with the positions, cusps and rules.
It does not authenticate the supplied timezone choice, astronomical values,
their relationship to the claimed UTC/location or the software-version labels.
Use `natal_chart` to calculate values from resolved input.

Calling `natal_chart(chart.resolved, chart.requested)` calculates a fresh result
with the current implementation and records its provenance. It keeps the resolved
birth input without looking up the timezone again. The new result may differ
from an older result calculated with different code. The distribution must be
installed: missing `celestial-astrology` metadata raises
`importlib.metadata.PackageNotFoundError` rather than inventing a version.
A version label alone does not identify a unique source revision or guarantee
bitwise equality between trees.

## Display does not change classification

Angles use the named `truncate_display` rule: truncate toward zero to whole
arcseconds. Aries 29.9999999° displays as Aries 29°59'59", not Taurus 0°00'00".
House and aspect-motion labels come from the unrounded result. An object's
displayed longitude can match a cusp's while its unrounded position is still in
the preceding house; a nonzero deviation displayed as zero can still be applying
or separating. In the positions table's last column, `R` means decreasing object
longitude, `D` means increasing longitude and `S` means exactly zero rate, all
judged from the unrounded rate. The text is a rounded
presentation, not a lossless interchange format.

## Verification and limits

The [complete checks](contributing.md) build through an sdist, install the wheel
outside the checkout and compare its complete numeric result, resolved input,
requested/effective configuration and provenance with the source result exactly
for the same code revision. They also exercise both text languages and requested
Placidus failure. Import origins, including the explicitly loaded native adapter,
are checked.

`tests/reference/chart_regression.json` retains numbers from two project-calculated
synthetic Whole Sign cases: an IANA input with nonuniform aspect orbs from the
`0.0.0` development tree and a fixed-offset, two-body case without aspects from
the published v0.1.0 wheel. Extraction provenance includes the original sample
hashes and the released wheel/manifest digests, source commit and generation
procedure. These are regression samples, not independent astronomy references.
Tests construct their inputs explicitly; they do not restore saved charts.

Numerical regression checks models, frames, configuration, identities and
classifications without requiring historical package-version equality. Absolute
tolerances are 1e-8 degrees for angles, 1e-9 AU for distances, 1e-9 degrees/TT day
for rates and 1e-8 days for Julian dates. A changed model needs a separately
justified comparison. These finite cases do not establish global accuracy.

`tests/reference/complete_chart_reference.json` contains independently executed
Swiss Ephemeris 2.10.03 / pyswisseph 2.10.3.2 numeric states for four synthetic
instants, each with three house systems. It records the pyswisseph Python wheel's
SHA-256 hash, flags, coordinate/time conventions, source URLs, separate calibration
and per-field tolerances. Moshier is requested explicitly; returned `calc` flags
are checked. Swiss houses use Swiss UT1 and Delta-T, not Algo5, the fixed Delta-T
model used by this adapter. Their tolerance includes that time-model difference.
Signs, two-dimensional house membership (using longitude, not object latitude),
aspects and motion were derived by separate project-authored arithmetic from the
Swiss states; Swiss itself does not supply an aspect table. Mean-node
longitude/rate are compared as named models, not assumed identical formulas.
Node distance and true nodes are not equivalent comparisons; zero node latitude
is a definition-level check.

If a reference point is within the combined longitude/cusp tolerances of a cusp,
the comparison accepts either adjoining house. It does not claim an exact
independent house label for that point.

The [Swiss documentation](https://www.astro.com/swisseph/swisseph.htm) describes
Moshier's precision class. The recorded thresholds include both implementations'
model differences and finite calibration; they are not global accuracy guarantees.
The source tool was isolated and is not a runtime/dev dependency. Only generated
numbers and project-authored metadata are included, not Swiss code or ephemeris
files; see the [GNU output FAQ](https://www.gnu.org/licenses/gpl-faq.html#WhatCaseIsOutputGPL).
This does not change the project's MIT license or constitute a general license assurance.
