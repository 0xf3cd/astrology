# Moment charts and fixed-instant transits

[简体中文](../zh-CN/moments.md) · [Charts](chart.md) · [Exact transit search](transits.md)

Use `moment_chart` for a supplied instant and location. It returns a `MomentChart`,
with no birth record or inferred location. Use `transit_aspects` to compare that
moment's moving objects with an existing natal chart's frozen degrees.
The examples on this page continue in order.

## Calculate at an instant

<!-- usage: chart.moment -->

Supply an aware built-in `datetime`, a `Location` and a `ChartConfig`. Offsets are
normalized to UTC. The input and calculated times are separate records:

```{doctest}
>>> from datetime import UTC, date, datetime, time, timedelta
>>> from astrology import Body, ChartConfig, HouseSystem, Location, moment_chart
>>> site = Location(0, 0)
>>> config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON, Body.MERCURY), ())
>>> moving = moment_chart(datetime(2024, 3, 22, 18, tzinfo=UTC), site, config)
>>> type(moving).__name__
'MomentChart'
>>> moving.moment.utc.isoformat()
'2024-03-22T18:00:00+00:00'
>>> moving.moment.location == site and moving.moment.source_jde_tt is None
True
>>> len(moving.positions)
3
>>> round(moving.positions[0].longitude_deg, 6)
2.60136
>>> moving.placements[0].sign.name, moving.placements[0].house
('ARIES', 7)
```

`moving.moment` holds the normalized UTC, location and optional source-event TT.
`moving.times` holds the calculated JD(UT1) and JDE(TT). Positions, houses,
placements, intra-chart aspects, configuration and provenance follow the
[structured result guide](records.md#read-the-structured-result).
This example requests no intra-chart aspects.

<!-- /usage: chart.moment -->

The [joint snapshot domain](chart.md#select-objects-without-widening-the-domain) and
explicit house-system choice still apply. A smaller body selection filters the
fourteen-object snapshot; it does not narrow its calculation domain. Naive
datetimes are rejected, and the normalized UTC must be at or after 1972-01-01.

## Compare moving objects with a natal chart

<!-- usage: transits.fixed -->

Build the natal source from a synthetic birth record. Choose the fixed-instant
rules and each side's objects explicitly; rules are not inherited from either chart:

```{doctest}
>>> from astrology import (AspectRule, BirthRecord, FixedOffset, MajorAspect,
...     format_transit_aspects, load_catalog, natal_chart, prepare_natal_input, transit_aspects)
>>> record = BirthRecord(date(2000, 4, 10), time(12), FixedOffset(timedelta(0)), site)
>>> natal = natal_chart(prepare_natal_input(record), config)
>>> rules = (AspectRule(MajorAspect.CONJUNCTION, 3),)
>>> fixed = transit_aspects(moving, natal, rules,
...     moving_objects=(Body.MERCURY,), natal_objects=(Body.SUN,))
>>> [(hit.moving_object.value, hit.natal_object.value, hit.motion.value) for hit in fixed.hits]
[('mercury', 'sun', 'separating')]
>>> catalog = load_catalog()
>>> print(format_transit_aspects(fixed, catalog).splitlines()[0])
Fixed-instant transit-to-natal aspects
>>> print(next(line for line in format_transit_aspects(fixed, catalog).splitlines()
...     if line.startswith('Mercury [mercury] |')))
Mercury [mercury] | Sun [sun] | Conjunction | 0°00'00" | -0°00'58" | 3°00'00" | separating
```

The row retains the moving/natal identities, aspect, [oriented branch and signed
deviation](aspects.md#read-the-branch-and-the-deviation), inclusive orb limit and
[motion status](aspects.md#applying-separating-and-the-other-statuses). The original unrounded values
remain in `fixed.hits`; whole-arcsecond display truncation changes neither hit
membership nor motion, even when a nonzero deviation displays as zero.

<!-- /usage: transits.fixed -->

`None` selections use each source's stored bodies/nodes without axes. Explicit
selections may include any of the four `Axis` members. Empty selections or rules
produce no hits; invalid inputs are still checked. Same-identity and axis-axis
pairs are allowed, as is every combination of the nodes selected on each side.
Ordering and per-object orb
combinations follow [cross-chart aspects](cross_aspects.md).

The moving side must be a `MomentChart`, the fixed side a `NatalChart`. Each pair's
raw branch, deviation and orb limit exactly match `cross_chart_aspects` with the
moment chart on the left, the natal chart on the right and the same object selections.
Motion uses moving rates against **zero natal motion**,
including fixed natal axes; it never uses the natal positions' stored birth-time
rates. Moving axes have no supplied rate: non-exact hits are indeterminate, while
zero deviation is exact. Applying describes a local derivative, not a promise of
a later exact event. Both sides retain their own-date tropical longitudes without
common-epoch conversion or a simultaneous spatial-angle claim.

## Build from a retained exact hit

<!-- usage: chart.hit_moment -->

Pass a retained `TransitHit` directly to `moment_chart`; no upstream converter
import is needed. The explicit location determines the new chart's houses:

```{doctest}
>>> from astrology import transit_hits
>>> events = transit_hits(natal, start_utc=datetime(2024, 3, 1, tzinfo=UTC),
...     end_utc=datetime(2024, 6, 1, tzinfo=UTC), moving_objects=(Body.MERCURY,),
...     natal_objects=(Body.SUN,), aspects=(MajorAspect.CONJUNCTION,))
>>> at_hit = moment_chart(events.hits[0], site, config)
>>> at_hit.moment.source_jde_tt == events.hits[0].jde_tt
True
>>> at_hit.moment.utc.isoformat(timespec='seconds')
'2024-03-22T17:40:34+00:00'
```

The retained `source_jde_tt` is the source event's original JDE(TT).
`at_hit.times.jde_tt` comes from a new snapshot at the converted Python UTC
datetime. These times can differ: the fixed upstream leap table and datetime's
microsecond representation do not guarantee an exact inverse round trip.

<!-- /usage: chart.hit_moment -->

Python cannot represent an inserted leap second. At the first 1972 leap step the
converted snapshot can be about one second later than its source event. At the
1972 model boundary a source time can convert to pre-1972 UTC, which raises
`HistoricalTimeError`; admission is checked on the converted instant. Conversion
also rounds to datetime precision, possibly carrying into the next day/year.
The resulting UTC must satisfy the snapshot domain. A valid event in the wider
event-search domain does not guarantee a valid full chart. Conversion/domain
failures raise `ChartDomainError` with the requested house system and available
upstream diagnostics. See the [transit time limits](transits.md#limits-and-failures)
for the fixed leap table's future-offset behavior.

## Use existing consumers

Comparisons, house overlays, house rulers, dispositors, sign distributions,
interval transit searches and chart text accept moment charts. Continuing with
the supplied charts above:

```{doctest}
>>> from astrology import (Dispositors, HouseRulers, chart_sign_distribution,
...     cross_chart_aspects, cross_chart_house_overlays, format_chart)
>>> cross = cross_chart_aspects(moving, natal, rules,
...     left_objects=(Body.MERCURY,), right_objects=(Body.SUN,))
>>> cross.hits[0].deviation_deg == fixed.hits[0].deviation_deg
True
>>> cross_chart_house_overlays(natal, moving).chart_right is moving
True
>>> len(HouseRulers(moving).houses)
12
>>> Dispositors(moving, (Body.SUN,)).chart is moving
True
>>> chart_sign_distribution(moving, objects=config.objects).total
3
>>> print(format_chart(moving, catalog).splitlines()[0])
Tropical geocentric moment chart
>>> print(next(line for line in format_chart(moving, catalog).splitlines()
...     if line.startswith('Sun [sun] |')))
Sun [sun] | Aries 2°36'04" | 7 | D
```

Moment text shows supplied UTC/location and, when present, source-event TT; it
does not add a recorded birth clock, timezone identity or tzdata/fold provenance.
`natal_lunar_phase` remains natal-specific; use `lunar_phase` with a moment chart's
stored Sun/Moon longitudes. For interval `transit_hits`, `natal_objects` names the
fixed-reference role even when the supplied source is a moment chart; the existing
recorded epoch-policy value is explained in the [transit guide](transits.md).

The project definitions and their scope are recorded under `entry.moment_charts`
and `entry.transit_aspects` in the [knowledge catalog](catalog.md).
