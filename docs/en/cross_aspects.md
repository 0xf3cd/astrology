# Static cross-chart aspects

[简体中文](../zh-CN/cross_aspects.md) · [Documentation](index.md) · [API](reference.md)

`cross_chart_aspects` compares two existing in-memory `NatalChart` results.
A Sun in the left chart and a Sun in the right chart remain separate endpoints;
no renaming or chart merging is needed. Comparing supplied results performs no
astronomy, timezone resolution, version lookup or I/O.

This API is available from 0.2.0, which is still in development. Use the
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

Both complete charts remain available as `result.chart_left` and `result.chart_right`,
including original/resolved birth inputs, positions, requested/effective choices
and provenance. `rules` and `combination` record the fresh comparison request;
neither chart's natal rules or participants are inherited.

## Choose pairs and orbs

`left_objects` and `right_objects` select each side independently. `None` selects
all bodies/nodes on that side and no axes, even if its natal aspects used a smaller subset.
Selections follow source position order, not the order of the selection argument.
Every selected left object is paired with every selected right object. This
includes same-named objects and every selected node identity on one side with
every selected node identity on the other. The same chart can occupy both roles.
These are project geometry choices, not traditional interpretations.
The [single-chart node exclusion](aspects.md#choose-the-objects) remains unchanged.

Object-orb overrides use the `Body`, `LunarNode` or `Axis` identity on either
side. A Sun override applies to both Suns; there is no left-Sun/right-Sun override
mechanism. An override must name a selected object from at least one side.
Choose an `OrbCombination` exactly when a rule has overrides; without overrides,
leave `combination=None`. The [three combination rules](aspects.md#combine-orbs-when-objects-differ)
and inclusive limits are the same arithmetic as for a natal pair.

```{doctest}
>>> own_sun = [AspectRule(MajorAspect.CONJUNCTION, 1, [ObjectOrb(Body.SUN, 5)])]
>>> adjusted = cross_chart_aspects(chart_left, chart_right, own_sun,
...   combination=OrbCombination.MEAN_OF_ORBS)
>>> adjusted.hits[0].orb_limit_deg
5.0
>>> cross_chart_aspects(chart_left, chart_right, rules, left_objects=[]).hits
()
>>> cross_chart_aspects(chart_left, chart_right, ()).rules
()
```

Empty selections, empty rules and no matches all yield empty hits; their recorded
selections/rules distinguish them. These requests raise `ValueError` even with no
pairs: duplicate participants within one side's selection, unavailable participants,
duplicate aspect identities, unused override identities, a combination given
without overrides, or overrides without a combination.
Caller-owned sequences are copied into immutable tuples.

## Select axes on each side

Explicit `left_objects`/`right_objects` may include any stored axis from that
source, independently of its natal participants. Body/node order is preserved;
selected axes follow in ASC/MC/DSC/IC order. Each side uses its actual axis fields,
not its cusps or the other chart's axes. Axis-axis pairs, same-named axes and
opposite axes are admitted without folding their identities or removing hits.
An axis override applies by identity to both sides, like a body override.

```{doctest}
>>> from astrology import Axis
>>> axes = cross_chart_aspects(chart_left, chart_left, rules,
...   left_objects=(Axis.ASCENDANT,), right_objects=(Axis.ASCENDANT,))
>>> [(h.left_object.value, h.right_object.value, h.deviation_deg) for h in axes.hits]
[('ascendant', 'ascendant', 0.0)]
>>> hasattr(axes.hits[0], 'motion')
False
```

No native calculation is performed by this comparison, and axes do not acquire
distance or motion fields. See [natal axis selection](aspects.md#select-axes-explicitly).

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

The sources must use matching zodiac, center and position-frame conventions;
a mismatch raises `ValueError`. Current public constructors admit only one such
convention: tropical/geocentric positions on the true ecliptic
and equinox of each chart's own date. Different dates therefore use different
equinox references: a hit compares the stored longitudes, not the angle between
two positions at one moment. There is no common-epoch conversion.
Different dates, locations, house systems, models and software labels are retained
and do not by themselves cause rejection. Construction recomputes all hits from
the sources, selections and rules and rejects any difference. It does not
authenticate the supplied astronomical values or provenance labels.

Composite/Davison charts, house overlays, transit searches and interpretation
remain outside this API. It provides no separate text formatter.
