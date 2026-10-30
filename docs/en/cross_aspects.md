# Cross-chart aspects and house overlays

[简体中文](../zh-CN/cross_aspects.md) · [Documentation](index.md) · [API](reference.md)

Given two `NatalChart` results, use `cross_chart_aspects` to find static major
aspects between them, or `cross_chart_house_overlays` to find which houses in one
chart contain the other chart's objects. The result distinguishes the left
chart's Sun from the right chart's Sun without renaming objects or merging charts.
Both operations use the stored longitudes; check the
[coordinate requirements](#source-compatibility-and-calculation-boundaries) before comparing charts.

Static cross-chart aspects are available from 0.2.0. House overlays and comparison
text are 0.3.0 additions still in development; use the
[source installation instructions](../../README.md#install-from-source) for them.

## Compare two example charts

This example calculates charts from two synthetic birth records, then checks
whether their Suns form a conjunction within a 3-degree orb. The comparison takes
its own aspect rules, so the natal charts do not need to include aspects.

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (AspectRule, BirthRecord, Body, ChartConfig, FixedOffset,
...   HouseSystem, Location, MajorAspect, ObjectOrb, OrbCombination,
...   cross_chart_aspects, natal_chart, prepare_natal_input)
>>> config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ())
>>> def source_chart(year):
...   record = BirthRecord(date(year, 7, 17), time(6), FixedOffset(timedelta(0)),
...     Location(0, 0), source={"record": "synthetic", "year": str(year)})
...   return natal_chart(prepare_natal_input(record), config)
>>> chart_left, chart_right = source_chart(2003), source_chart(2004)
>>> rules = [AspectRule(MajorAspect.CONJUNCTION, 3)]
>>> result = cross_chart_aspects(chart_left=chart_left, chart_right=chart_right, rules=rules)
>>> [(h.left_object.value, h.right_object.value, h.aspect.value) for h in result.hits]
[('sun', 'sun', 'conjunction')]
>>> result.chart_left is chart_left, result.chart_right is chart_right
(True, True)
>>> result.chart_left.resolved.utc.year, result.chart_right.resolved.utc.year
(2003, 2004)
>>> hit = result.hits[0]
>>> abs(hit.deviation_deg) <= hit.orb_limit_deg == 3
True
```

`result.chart_left` and `result.chart_right` are still the complete charts you
passed in. You can read their original birth records, resolved instants, positions,
requested and effective configuration, and calculation provenance.
The result's `rules` and `combination` record the rules and orb combination used
for this comparison. Neither chart's natal aspect rules or participants are inherited.

## Find houses in the other chart

Each record in `placements` identifies the chart the object comes from
(`object_owner`), the chart whose houses are used (`house_owner`), and the house
number (`house`). Below, the first record places the left chart's Sun in the right
chart's first house; the second places the right chart's Sun in the left chart's
first house. The two directions remain separate.

```{doctest}
>>> from astrology import cross_chart_house_overlays
>>> overlays = cross_chart_house_overlays(chart_left, chart_right)
>>> [(p.object_owner, p.identity.value, p.house_owner, p.house) for p in overlays.placements]
[('left', 'sun', 'right', 1), ('right', 'sun', 'left', 1)]
>>> overlays.chart_left is chart_left, overlays.chart_right is chart_right
(True, True)
>>> one_way = cross_chart_house_overlays(chart_left, chart_right,
...   left_objects=(Body.SUN,), right_objects=())
>>> [(p.object_owner, p.house_owner) for p in one_way.placements]
[('left', 'right')]
```

Use `left_objects` to choose objects from the left chart and `right_objects` to
choose objects from the right chart. In the example, `right_objects=()` skips
placements of the right chart's objects. Its cusps are still used to place the
left chart's Sun. Passing empty sequences for both returns empty `placements`.

Omitting a selection or passing `None` selects all bodies and nodes in that chart,
without axes. To include axes, explicitly select any stored `Axis`, as in the
[example below](#select-axes-on-each-side). Within each chart, bodies and nodes
follow the order of its position records, followed by selected axes in
ASC/MC/DSC/IC order, regardless of the selection argument's order. `placements`
lists left objects in right houses, then right objects in left houses.

Placement compares an object's stored longitude with the other chart's actual
cusps, in degrees. Each house starts at its cusp and ends just before the next
cusp: the half-open interval `[cusp, next cusp)`, wrapping from 360 to 0 degrees.
A longitude exactly on a cusp belongs to the house starting there. Each chart
keeps its own house system and remains unchanged. Swapping the chart arguments
swaps the owners in the result; you can also pass the same chart on both sides.

Selecting an object twice on one side, or selecting an object absent from that
chart, raises `ValueError`. Non-object values or non-sequence selections raise
`TypeError`. These checks still run when the other selection is empty.
Constructing `CrossChartHouseOverlays` directly recomputes the complete placement
sequence from the charts and selections. Missing records, different house numbers
or a different order are rejected.

## Choose pairs and orbs

<!-- usage: cross.selection -->

When calling `cross_chart_aspects`, use `left_objects` and `right_objects` to
select objects from each chart independently. `None` selects all bodies and nodes
in that chart, without axes, even if its natal aspects used only a subset.
Objects follow the order of the chart's position records, not the selection argument.
Every selected left object is paired with every selected right object. This
includes same-named objects, such as the two Suns, and every combination of the
nodes selected on each side. You can also pass the same chart on both sides.
These pairings are this project's geometric conventions, not traditional interpretation rules.
The [single-chart node exclusion](aspects.md#choose-the-objects) remains unchanged.

```{doctest}
>>> cross_chart_aspects(chart_left, chart_right, rules, left_objects=[]).hits
()
>>> cross_chart_aspects(chart_left, chart_right, ()).rules
()
```

`hits=()` can mean that a selection is empty, the rules are empty, or no aspects
match. Read the recorded selections and rules to distinguish these cases.

<!-- /usage: cross.selection -->

<!-- usage: cross.orbs -->

An `ObjectOrb` override for a `Body`, `LunarNode` or `Axis` applies to both sides.
For example, a Sun override applies to both Suns; you cannot give the left and
right Suns separate values. The object must be selected on at least one side.
If any rule has overrides, choose an `OrbCombination`; otherwise, leave
`combination=None`. The [three combination rules](aspects.md#combine-orbs-when-objects-differ)
are the same as for natal aspects. A deviation whose absolute value equals the
orb limit also counts as a hit.

```{doctest}
>>> own_sun = [AspectRule(MajorAspect.CONJUNCTION, 1, [ObjectOrb(Body.SUN, 5)])]
>>> adjusted = cross_chart_aspects(chart_left, chart_right, own_sun,
...   combination=OrbCombination.MEAN_OF_ORBS)
>>> adjusted.hits[0].orb_limit_deg
5.0
```

The following requests raise `ValueError`, even when there are no pairs to compare:

- Selecting an object twice on one side, or selecting an object absent from that chart.
- Repeating an aspect in the rules, or overriding an object selected on neither side.
- Omitting the combination when there are overrides, or supplying one without overrides.

Input sequences are copied into immutable tuples. Changing the originals later
does not change the result.

<!-- /usage: cross.orbs -->

## Select axes on each side

To include axes, explicitly select any stored axis in `left_objects` or
`right_objects`. The chart's natal axis selection does not affect this comparison.
Bodies and nodes keep their chart order, followed by selected axes in
ASC/MC/DSC/IC order. Each chart supplies its actual axis fields, not substitute
cusps or axes from the other chart. Axes can pair with axes, including same-named
and opposite axes; their identities remain distinct and no hits are removed on
that basis. An axis override applies to the same axis on both sides, just like a
body override.

```{doctest}
>>> from astrology import Axis
>>> axes = cross_chart_aspects(chart_left, chart_left, rules,
...   left_objects=(Axis.ASCENDANT,), right_objects=(Axis.ASCENDANT,))
>>> [(h.left_object.value, h.right_object.value, h.deviation_deg) for h in axes.hits]
[('ascendant', 'ascendant', 0.0)]
>>> hasattr(axes.hits[0], 'motion')
False
```

The comparison reads the stored axes without repeating native astronomy, and
does not add distance or motion fields to them.
See [natal axis selection](aspects.md#select-axes-explicitly) for single-chart aspects.

## Render comparison text

Use `format_house_overlays` for a house-placement table and `format_cross_aspects`
for an aspect table. Both take the knowledge catalog returned by `load_catalog()`
and use its names. English is the default; pass `language="zh-CN"` for Chinese.

```{doctest}
>>> from astrology import format_house_overlays, format_cross_aspects, load_catalog
>>> catalog = load_catalog()
>>> print(format_house_overlays(overlays, catalog))  # doctest: +ELLIPSIS
Cross-chart house overlays
...
Object owner | Object | House owner | House
Left | Sun [sun] | Right | 1
Right | Sun [sun] | Left | 1
>>> print(format_cross_aspects(result, catalog))  # doctest: +ELLIPSIS
Static cross-chart aspects
...
Left object | Right object | Aspect | Branch | Deviation | Orb limit
Sun [sun] | Sun [sun] | Conjunction | 0°00'00" | ... | 3°00'00"
...
Aspect rule / base orb / object overrides: Conjunction / 3°00'00" / None
...
```

Both tables start with each chart's house system, coordinate convention, time-scale
values, model and version labels, and selected objects. The overlay table then lists
the owners and house number for each placement. The aspect table lists every
matching branch, including multiple hits for one pair, without motion labels such
as applying or separating. It also shows base orbs, object overrides, the combination
rule and each hit's effective orb limit. A deviation whose absolute value equals
the limit counts as a hit. Empty results still show the selections and aspect rules.

Branches, deviations and orbs are displayed in degrees, minutes and seconds using
the [whole-arcsecond truncation rule](records.md#display-does-not-change-classification).
Truncation affects only the display; it does not re-evaluate aspects or discard
records. Required names and translations must be present and current in the
catalog. Missing, stale or ambiguous names raise `ValueError`; there is no fallback
to another language. The tables escape nonprinting characters and table delimiters.
They are for reading, not for restoring a chart without loss.

## Read static geometry

Each hit identifies its objects with `left_object` and `right_object`, and its
aspect with `aspect`. `branch_deg`, `deviation_deg` and `orb_limit_deg` give the
branch angle, deviation and orb limit, all in degrees. See the
[branch and deviation definitions](aspects.md#read-the-branch-and-the-deviation).
Results follow left-chart position order, then right-chart position order, then
ascending aspect angle, with the negative branch first for each aspect. Broad
orbs can admit several aspects or both branches for one pair. Every match is
returned; the comparison does not choose only the nearest or round to display
precision before testing.

Hits have no motion field or applying/separating label: rates at two birth
instants cannot describe how this pair changes over time. Zero deviation means
only that the static geometry is exact in this comparison; it predicts no later event.

## Source compatibility and calculation boundaries

Both comparisons require the charts to use the same zodiac, center and
position-frame conventions. A mismatch raises `ValueError`. Current public
constructors accept only tropical, geocentric positions on the true ecliptic and
equinox of each chart's own date. Different dates therefore have different equinox
references. Cross-chart aspects compare the stored longitudes without converting
them to a common epoch, so they do not measure the angle between two positions at
one moment.

The charts may have different dates, locations, house systems, models and software
labels. These are retained and do not by themselves cause rejection. Constructing
a cross-aspect result recomputes all hits from the charts, selections and rules;
constructing an overlay result recomputes all placements from the charts and
selections. Any difference from the supplied records is rejected. These checks do
not authenticate the supplied astronomical values or provenance labels.

House overlays likewise compare each object's stored longitude at its own date
with the other chart's cusps. They do not convert to a common epoch or use object
latitude for three-dimensional placement. Both operations validate requests even
when output is empty. Neither performs astronomy, timezone resolution, version
lookup or resource I/O; the formatters use the caller's catalog.

Composite/Davison charts, transit searches and interpretation remain outside
these operations.
