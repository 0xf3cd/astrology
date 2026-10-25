# Static cross-chart aspects

[简体中文](../zh-CN/cross_aspects.md) · [Documentation](index.md) · [API](reference.md)

`cross_chart_aspects` compares two existing in-memory `NatalChart` results.
A Sun in the left chart and a Sun in the right chart remain separate endpoints;
no renaming or chart merging is needed. Comparing supplied results performs no
astronomy, timezone resolution, version lookup or I/O.

This API is in the current source, not the published v0.1.0. Use the
[source installation instructions](../../README.md#install-from-source).

## Compare two synthetic birth records

Calculate the source charts first. Their own natal aspect rules can be empty:
the comparison takes its rules explicitly.

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
>>> left, right = source_chart(2003), source_chart(2004)
>>> rules = [AspectRule(MajorAspect.CONJUNCTION, 3)]
>>> result = cross_chart_aspects(left, right, rules)
>>> [(h.left_object.value, h.right_object.value, h.aspect.value) for h in result.hits]
[('sun', 'sun', 'conjunction')]
>>> result.left is left, result.right is right
(True, True)
>>> result.left.resolved.utc.year, result.right.resolved.utc.year
(2003, 2004)
>>> hit = result.hits[0]
>>> abs(hit.deviation_deg) <= hit.orb_limit_deg == 3
True
```

Both complete charts remain available as `result.left` and `result.right`,
including original/resolved birth inputs, positions, requested/effective choices
and provenance. `rules` and `combination` record the fresh comparison request;
neither chart's natal rules or participants are inherited.

## Choose pairs and orbs

`left_objects` and `right_objects` select each side independently. `None` selects
all positions on that side, even if its natal aspects used a smaller subset.
Selections follow source position order, not the order of the selection argument.
Every selected left object is paired with every selected right object. This
includes same-named objects, all named cross-chart node pairs, and the same chart
in both roles. These are project geometry choices, not traditional interpretations.
The [single-chart node exclusion](aspects.md#choose-the-objects) remains unchanged.

Object-orb overrides use the existing `Body` or `LunarNode` identity on either
side. A Sun override applies to both Suns; there is no left-Sun/right-Sun override
mechanism. An override must name a selected object from at least one side.
Choose an `OrbCombination` exactly when a rule has overrides; without overrides,
leave `combination=None`. The [three combination rules](aspects.md#combine-orbs-when-objects-differ)
and inclusive limits are the same arithmetic as for a natal pair.

```{doctest}
>>> own_sun = [AspectRule(MajorAspect.CONJUNCTION, 1, [ObjectOrb(Body.SUN, 5)])]
>>> adjusted = cross_chart_aspects(left, right, own_sun,
...   combination=OrbCombination.MEAN_OF_ORBS)
>>> adjusted.hits[0].orb_limit_deg
5.0
>>> cross_chart_aspects(left, right, rules, left_objects=[]).hits
()
>>> cross_chart_aspects(left, right, ()).rules
()
```

Empty selections, empty rules and no matches all yield empty hits; their recorded
selections/rules distinguish them. Invalid requests still fail: duplicate or
unavailable participants, duplicate aspect identities, unused override identities
and an inappropriate or missing combination are rejected even with no pairs.
Caller-owned sequences are copied into immutable tuples.

## Read static geometry

Each hit has `left_object`, `right_object`, `aspect`, `branch_deg`,
`deviation_deg` and `orb_limit_deg`. The [branch/deviation definitions](aspects.md#read-the-branch-and-the-deviation)
apply unchanged, in degrees. Every matching branch is returned, ordered by left
position, right position, ascending aspect angle, then negative before positive
branch. Broad orbs may admit several aspects or both branches; no nearest-only
selection or display rounding is applied.

There is no motion field, including no applying/separating label. Rates at two
birth instants do not describe a shared time evolution. Zero deviation still
identifies exact static geometry, without predicting a later event.

The sources must use matching zodiac, center and position-frame conventions.
The current source types admit tropical/geocentric positions on the true ecliptic
and equinox of each chart's own date. Those longitudes are compared directly;
there is no common-epoch conversion or claim of a simultaneous spatial angle.
Different dates, locations, house systems, models and software labels are retained
and do not by themselves cause rejection. Constructor checks validate pure result
consistency, not the authenticity of supplied astronomical values or labels.

Composite/Davison charts, house overlays, transit searches and interpretation
remain outside this API. It provides no chart persistence or separate text formatter.
