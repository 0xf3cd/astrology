# Aspects

[简体中文](../zh-CN/aspects.md) · [Documentation](index.md) · [API reference](reference.md)

`find_aspects` checks for the five major aspects using two objects' ecliptic
longitudes and rates at the same instant. Each result gives the exact angle used
for comparison, the signed deviation from it, the orb limit and the current motion status. The caller
supplies every orb; there is no default. [`natal_chart`](chart.md) calls the same
function to calculate the requested aspects.

For static comparison of two supplied charts, use [cross-chart aspects](cross_aspects.md).
That API keeps left/right ownership and has no motion field.

## Judge aspects from plain values

<!-- usage: aspects.longitudes -->

`find_aspects` needs no chart and does not call the astronomy library. Give it objects with a longitude in
degrees and a rate in degrees per day, and the rules to apply.
Use one instant and coordinate convention for all objects, and the same day unit
for their rates (for example, the TT day). Bare numbers cannot verify those prerequisites.

`AspectObject` accepts any finite longitude, including negative values, values
above 360° and the largest finite float. It stores the supplied float without
wrapping. Aspect calculations reduce each longitude around the circle before
subtraction, so even extreme finite inputs do not overflow. Booleans and
nonnumeric inputs raise `TypeError`; NaN and infinity raise `ValueError`.

```{doctest}
>>> from astrology import (
...   AspectObject, AspectRule, Body, LunarNode, MajorAspect, ObjectOrb,
...   OrbCombination, find_aspects,
... )
>>> sun = AspectObject(Body.SUN, 10.0, 1.0)
>>> mars = AspectObject(Body.MARS, 68.0, 3.0)
>>> sextile = AspectRule(MajorAspect.SEXTILE, 3)
>>> hit = find_aspects([sun, mars], [sextile])[0]
>>> (hit.aspect.value, hit.branch_deg, hit.deviation_deg, hit.motion.value)
('sextile', 60.0, -2.0, 'applying')
```

The separation runs from the first object to the second: 68 minus 10 is 58 degrees.
A sextile is 60 degrees, so the deviation is 58 minus 60, which is -2. It is inside
the orb of 3 degrees. A deviation exactly at the limit also counts as a match.

<!-- /usage: aspects.longitudes -->

## Read the branch and the deviation

A conjunction and an opposition have one exact angle, 0 and 180 degrees. A sextile,
square or trine has two, minus and plus the aspect angle, because the second object
can be ahead of the first or behind it. Each hit records which one it was measured
against as `branch_deg`, and `deviation_deg` is the separation minus that branch,
greater than -180 and up to and including 180.

Swapping the pair keeps the aspect and flips the orientation: the deviation changes
sign, and so does the branch where there are two. The status does not change. A
deviation of exactly 180 stays positive in either order.

```{doctest}
>>> hit = find_aspects([mars, sun], [sextile])[0]
>>> (hit.branch_deg, hit.deviation_deg, hit.motion.value)
(-60.0, 2.0, 'applying')
```

Broad orbs can make one pair match several aspects, or both branches of one aspect.
Every match is returned, in a fixed order: the order of the objects, then the aspect
angle, then the minus branch before the plus branch. Nothing is dropped in favor of
a nearer match.

## Applying, separating and the other statuses

Away from a deviation of 180 degrees, the deviation changes at the second object's
rate minus the first's. When that relative rate and the deviation have opposite
signs the aspect is applying; with the same sign it is separating. This holds for
retrograde motion too.

| Status | When |
|---|---|
| `applying` | The deviation shrinks in size. |
| `separating` | The deviation grows in size. |
| `exact` | The deviation is exactly zero, whatever the rates. |
| `stationary` | The relative rate is exactly zero and the deviation is not. |
| `indeterminate` | A rate is missing, or the deviation is 180 degrees with nonzero relative motion. |

```{doctest}
>>> exact = AspectObject(Body.MARS, 70.0, 1.0)
>>> find_aspects([sun, exact], [sextile])[0].motion.value
'exact'
>>> same_speed = AspectObject(Body.MARS, 68.0, 1.0)
>>> find_aspects([sun, same_speed], [sextile])[0].motion.value
'stationary'
>>> no_rate = AspectObject(Body.MARS, 68.0, None)
>>> find_aspects([sun, no_rate], [sextile])[0].motion.value
'indeterminate'
```

The checks compare floats directly, without a tolerance. `stationary` means no
relative motion, not that either planet has stopped changing longitude (a station).
The status describes this instant only. It does not predict whether an aspect
will become exact; a planet may change direction before that happens.

At a deviation of 180 degrees, the absolute wrapped deviation has a sharp corner and no
two-sided derivative when the relative rate is nonzero, so the status is
`indeterminate` in both object orders. Equal rates still give `stationary`.
This boundary can be a hit only with an orb of at least 180 degrees.

## Combine orbs when objects differ

<!-- usage: aspects.orbs -->

An aspect rule gives one orb for every object. To give an object its own orb, add an
`ObjectOrb` to the rule and choose how the two orbs of a pair combine:

| `OrbCombination` | A pair holds when its deviation is within |
|---|---|
| `EITHER_WITHIN_OWN_ORB` | at least one object's own orb, the larger orb |
| `BOTH_WITHIN_OWN_ORB` | both objects' own orbs, the smaller orb |
| `MEAN_OF_ORBS` | the mean of the two orbs |

When a rule has per-object orbs, you must choose a combination rule. Without
per-object orbs, a chart request rejects a combination rule, while `find_aspects`
accepts it without changing the result. Each hit records the limit it used.

```{doctest}
>>> moon = AspectObject(Body.MOON, 7.0, 13.0)
>>> sun = AspectObject(Body.SUN, 0.0, 1.0)
>>> wide_moon = AspectRule(MajorAspect.CONJUNCTION, 3, [ObjectOrb(Body.MOON, 13)])
>>> for combination in OrbCombination:
...   hits = find_aspects([sun, moon], [wide_moon], combination)
...   print(combination.value, [hit.orb_limit_deg for hit in hits])
either_within_own_orb [13.0]
both_within_own_orb []
mean_of_orbs [8.0]
```

<!-- /usage: aspects.orbs -->

## Choose the objects

In this single-chart evaluation, two lunar nodes never form an aspect with each other. The four node identities are
one pair of nodes under two definitions and two directions, so the ascending and
descending nodes are always exactly opposite. A node can form an aspect with a body.

```{doctest}
>>> nodes = [
...   AspectObject(LunarNode.MEAN_ASCENDING, 10.0, -0.05),
...   AspectObject(LunarNode.MEAN_DESCENDING, 190.0, -0.05),
... ]
>>> find_aspects(nodes, [AspectRule(MajorAspect.OPPOSITION, 3)])
()
```

In a chart request, `aspect_objects` selects requested bodies/nodes and may explicitly
add axes. Left out, all requested bodies/nodes take part, without axes. A node that is
requested but left out of `aspect_objects` still has its position and takes part in
no aspect. A selected axis can pair with a body, node or another axis.

## Aspects in a natal chart

`natal_chart` calculates the requested aspects among the participating objects, using the
positions and rates of the same calculation, and returns them in `chart.aspects`.
`chart.effective` records which objects took part and which combination was used.
The example takes the orbs from the "Hellenistic" drawing style that Astrodienst
publishes: 13 degrees for the Moon, 3 for the Sun and the planets, and no aspects for
the lunar node.

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (
...   BirthRecord, ChartConfig, FixedOffset, HouseSystem, Location, TimePrecision,
...   natal_chart, prepare_natal_input,
... )
>>> record = BirthRecord(
...   date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)),
...   Location(64.15, -21.94), TimePrecision.SECOND, {"record": "synthetic"},
... )
>>> planets = (
...   Body.SUN, Body.MOON, Body.MERCURY, Body.VENUS, Body.MARS, Body.JUPITER, Body.SATURN,
... )
>>> rules = [AspectRule(aspect, 3, [ObjectOrb(Body.MOON, 13)]) for aspect in MajorAspect]
>>> request = ChartConfig(
...   HouseSystem.WHOLE_SIGN, (*planets, LunarNode.MEAN_ASCENDING), rules,
...   aspect_objects=planets,
...   orb_combination=OrbCombination.EITHER_WITHIN_OWN_ORB,
... )
>>> chart = natal_chart(prepare_natal_input(record), request)
>>> for hit in chart.aspects:
...   print(hit.first.value, hit.second.value, hit.aspect.value,
...         round(hit.deviation_deg, 2), hit.motion.value)
moon venus trine 7.42 applying
moon mars conjunction 1.28 applying
moon saturn trine -2.34 separating
>>> len(chart.positions), [value.value for value in chart.effective.aspect_objects][:2]
(8, ['sun', 'moon'])
```

## Select axes explicitly

`Axis.ASCENDANT`, `MIDHEAVEN`, `DESCENDANT` and `IMUM_COELI` identify the Ascendant,
Midheaven, Descendant and Imum Coeli. Chart calculation reads each axis longitude
from `ChartHouses`, without substituting a cusp or deriving it from the opposite axis.
This matters in Whole Sign, where ASC/MC need not be first/tenth cusps.

```{doctest}
>>> from astrology import Axis
>>> axis_request = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,),
...   (AspectRule(MajorAspect.SEXTILE, 3), AspectRule(MajorAspect.TRINE, 3)),
...   aspect_objects=(Axis.IMUM_COELI, Body.SUN, Axis.MIDHEAVEN))
>>> axis_chart = natal_chart(prepare_natal_input(record), axis_request)
>>> [value.value for value in axis_chart.effective.aspect_objects]
['sun', 'midheaven', 'imum_coeli']
>>> [(h.second.value, h.aspect.value, round(h.deviation_deg, 2), h.motion.value)
...  for h in axis_chart.aspects]
[('midheaven', 'trine', 2.47, 'indeterminate'), ('imum_coeli', 'sextile', 2.47, 'indeterminate')]
>>> [p.identity.value for p in axis_chart.positions]
['sun']
```

Chart results have no axis longitude rates (`None`), so a hit involving an axis
has motion status `indeterminate` unless its deviation is zero, which still gives
`exact`. The check compares floats directly: nearly opposite stored values can
have a tiny nonzero deviation. Missing rates are not replaced with zero or a planet's rate. Low-level
`AspectObject` accepts a caller-supplied finite axis rate on the same day basis
as the other objects (for example, the TT day).
Axes have no physical distance, are not listed in `chart.positions`, and are not counted in sign distributions.

Explicitly selected axes can pair with each other, including ASC/DSC and MC/IC.
Opposite axes remain separate identities; all matching aspects/branches are kept.
This is a project pairing policy, not a universal traditional orb or interpretation.
`ObjectOrb` and all three combination rules apply to selected axes unchanged.
The [cross-chart API](cross_aspects.md#select-axes-on-each-side) selects each side independently.

## Check the results

Tests compare aspect angles and orb boundaries with hand-calculated expectations.
They also compare the library's aspects with those derived from JPL Horizons
longitudes. See the [contributing guide](contributing.md#correctness) for the test methods.

## Limits

- Only ecliptic longitude is used. Latitude, declination, minor aspects, whole-sign
  aspects are not evaluated. Axes take part only when explicitly selected.
- The motion status describes this instant only. It does not predict whether an
  aspect will become exact, or describe its meaning or strength.
- The library supplies no default orb. The corpus describes the evaluation as a
  project definition; it makes no claim about any tradition's orbs.

See the [result guide](records.md) for structured results and text output.
