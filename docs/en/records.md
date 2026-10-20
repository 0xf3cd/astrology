# Save, restore, replay and inspect a chart

[简体中文](../zh-CN/records.md) · [Chart](chart.md) · [API](reference.md)

`NatalChart.resolved` retains the actual resolved birth input, including its
original record. Save it with `dumps_chart`, restore the stored values with
`loads_chart`, or calculate a fresh result explicitly with `recompute_chart`.
Restoration never resolves the timezone again or imports native astronomy.

## A complete example

This synthetic record falls in the repeated half-hour on Lord Howe Island.
Choose the earlier occurrence with `fold=0`. The location here is deliberately
synthetic, not inferred from the timezone. There are no default aspect orbs.

```{doctest}
>>> from datetime import date, time
>>> from astrology import (AspectRule, BirthRecord, Body, ChartConfig, HouseSystem,
...   IanaTimezone, Location, LunarNode, MajorAspect, ObjectOrb, OrbCombination,
...   TimePrecision, dumps_chart, format_chart, load_catalog, loads_chart,
...   natal_chart, prepare_natal_input, recompute_chart)
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
>>> packed = dumps_chart(chart)
>>> restored = loads_chart(packed)
>>> restored == chart, dumps_chart(restored) == packed
(True, True)
>>> recompute_chart(restored) == chart
True
>>> catalog = load_catalog()
>>> table = format_chart(restored, catalog)
>>> print("\n".join(table.splitlines()[7:10]))
Sun [sun] | Aries 14°50'21" | 9 | D
Moon [moon] | Scorpio 13°32'41" | 4 | D
Mercury [mercury] | Pisces 17°05'04" | 8 | D
```

The Sun's orb is 10° and the other bodies use 6°; their mean is 8° for pairs with
the Sun and 6° otherwise. The explicit participant list excludes the node and
records the bodies in reverse order; effective participants still follow the
requested object order. The exact replay equality above holds in this same code
tree. For comparisons across trees, compare numerical fields with stated
tolerances, as in [Verification and limits](#verification-and-limits).

The full table also includes all requested objects, four axes, twelve cusps,
aspects with their oriented branches, deviations, limits and motion labels,
requested/effective configuration and provenance. Pass `language="zh-CN"` for
Chinese output. The supplied catalog must contain current names in that language;
missing or ambiguous names fail rather than fall back to another language.
Loading the catalog is explicit; formatting itself performs no resource I/O.

## What schema v1 preserves

The JSON root has `schema_version`, `input`, `requested`, `effective`, `provenance`,
`times`, `positions`, `houses`, `placements` and `aspects`. These encode the
corresponding public result values, not a rounded text table.

- `input.record` retains the Gregorian date, clock, stated precision, timezone
  form, location and string source metadata. `input.resolved` separately retains
  UTC, the offset, IANA key, fold and both timezone-data versions. Dates/clocks use
  canonical ISO text. UTC uses an explicit `+00:00` offset. Offset values are exact
  signed integer microseconds, not floating seconds.
- `requested` retains object/rule order, per-object orbs, their combination, and
  the distinction between omitted (`null`) and explicit aspect participants.
  `effective.aspect_objects` gives the actual participants in requested object order.
- `positions` retains unrounded longitude/latitude in degrees, physical distance
  in AU, and longitude rate in degrees per TT day. Nodes have no distance (`null`).
  `times` retains JD(UT1) and JDE(TT). Axes/cusps, placements and every aspect field
  are stored, including the branch, signed deviation, limit and motion status.
- `provenance` retains astrology/celestial-calendar versions, position frame and
  UT1 derivation; `effective` retains the resolved Delta-T model and evaluation.

JSON object keys are sorted and output formatting is deterministic. Array order
is preserved; finite floats round-trip without decimal rounding, including signed
zero. Input JSON may use different whitespace or object-key order, but timestamps
must be canonical. This API accepts strings, not files or arbitrary byte encodings.
The caller owns file/network I/O and any resource limits for untrusted input.

## Restoration is not recalculation

`loads_chart` rejects duplicate, unknown or missing fields, wrong types (including
booleans used as numbers), nonfinite numbers, unsupported schema/enum/frame identities
and inconsistent pure results with `ChartRecordError`. Direct result construction
uses the same domain checks: signs, house membership and aspects must agree with
the stored positions and rules. Stored values are checked, not replaced.

This does **not** authenticate the original timezone choice, astronomical values,
their relationship to the claimed UTC/location, or the claimed software versions.
No native time/house computation occurs at restoration. If a later version changes
a pure rule, its schema compatibility must be handled explicitly; old values must
not silently acquire new meanings.

Unknown nonempty package-version or Delta-T-model strings remain restorable because
their stored results are still inspectable. Unknown frame, UT1-derivation or
evaluation identities are not restorable under schema v1: the interpretation of
the values would be unknown.

```{doctest}
>>> import json
>>> from dataclasses import replace
>>> from astrology import ChartRecordError, ChartReplayError
>>> unsupported = json.loads(packed)
>>> unsupported["schema_version"] = 999
>>> try:
...   loads_chart(json.dumps(unsupported))
... except ChartRecordError as error:
...   print(type(error).__name__)
ChartRecordError
>>> old_model = replace(chart, effective=replace(chart.effective, delta_t_model="unavailable"))
>>> old_model = loads_chart(dumps_chart(old_model))
>>> old_model.effective.delta_t_model
'unavailable'
>>> try:
...   recompute_chart(old_model)
... except ChartReplayError as error:
...   print(type(error).__name__)
ChartReplayError
```

Replay requires matching astrology and celestial-calendar versions and the
available fixed Delta-T model. It uses the stored resolved UTC and request, not
today's timezone database, and returns a fresh chart without modifying the record.
An unavailable version/model raises `ChartReplayError`; a requested computation
outside the upstream domain still raises `ChartDomainError`, with no house fallback.
Version equality is only a compatibility check: the development label `0.0.0`
does not identify a unique code revision or guarantee bitwise equality between trees.

## Display does not change classification

Angles use the named `truncate_display` rule: truncate toward zero to whole
arcseconds. Aries 29.9999999° displays as Aries 29°59'59", not Taurus 0°00'00".
House and aspect-motion labels always come from the stored result. An object's
displayed longitude can match a cusp's while its unrounded position is still in
the preceding house; a nonzero deviation displayed as zero
can still be applying or separating. `R` uses the sign of the unrounded rate, `D`
means increasing longitude, and `S` means exactly zero rate. The text is not a
lossless alternative to JSON.

## Verification and limits

The [complete checks](contributing.md) build through an sdist, install the wheel
outside the checkout, and compare a complete installed chart's JSON with the
development entry point, without dropping provenance fields. They also exercise
restoration, replay, both text languages, unavailable models and requested Placidus
failure. Import origins, including the explicitly loaded native adapter, are checked.

`tests/reference/chart_record_v1.json` is a project-calculated replay fixture, not an
independent astronomy reference. Recalculation uses absolute tolerances of 1e-8
degrees for angles, 1e-9 AU for distances, 1e-9 degrees/TT day for rates and 1e-8 days
for Julian dates; identities and classifications must agree. Exact restoration is
tested separately, without these tolerances.

`tests/reference/complete_chart_reference.json` contains independently executed
Swiss Ephemeris 2.10.03 / pyswisseph 2.10.3.2 numeric states for four synthetic
instants, each with three house systems. It records the pyswisseph Python wheel's
SHA-256 hash, flags,
coordinate/time conventions, source URLs, separate calibration and per-field
tolerances. Moshier is requested explicitly; returned `calc` flags are checked.
Swiss houses use Swiss UT1 and Delta-T, not Algo5, the fixed Delta-T model used
by this adapter. Their tolerance includes that
time-model difference. Signs, two-dimensional house membership (using longitude,
not object latitude), aspects and motion
were derived by separate project-authored arithmetic from the Swiss states;
Swiss itself does not supply an aspect table. Mean-node longitude/rate are compared
as named models, not assumed identical formulas. Node distance and true nodes are
not equivalent comparisons; zero node latitude is a definition-level check.

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
