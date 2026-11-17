# Moving-pair events

[简体中文](../zh-CN/moving_events.md) · [API](reference.md#moving-pair-events) · [Exact fixed-source transits](transits.md)

Use `moving_aspect_events` to find exact major aspects between two moving bodies
or named lunar nodes. Searching needs neither a natal chart nor a location.

## Find new and full moons

<!-- usage: moving.events -->

Both longitudes vary. This example requests Sun first and Moon second, so its
relative angle and rate are **Moon minus Sun**:

```{doctest}
>>> from datetime import UTC, datetime
>>> from astrology import (Body, MajorAspect, moving_aspect_events, moving_hit_utc,
...     format_moving_events, load_catalog)
>>> events = moving_aspect_events(
...     pairs=((Body.SUN, Body.MOON),),
...     aspects=(MajorAspect.CONJUNCTION, MajorAspect.OPPOSITION),
...     start_utc=datetime(2024, 1, 1, tzinfo=UTC),
...     end_utc=datetime(2024, 2, 1, tzinfo=UTC))
>>> [(moving_hit_utc(hit).isoformat(timespec="seconds"), hit.aspect.value,
...   hit.direction.value) for hit in events.hits]
[('2024-01-11T11:57:27+00:00', 'conjunction', 'increasing'), ('2024-01-25T17:54:00+00:00', 'opposition', 'increasing')]
>>> table = format_moving_events(events, load_catalog())
>>> print(table.splitlines()[0])
Exact moving-pair events
>>> for row in table.splitlines():
...     if row.startswith(("UTC |", "2024-")):
...         print(" | ".join(row.split(" | ")[:6]))
UTC | First moving object | Second moving object | Aspect | Branch | Relative direction
2024-01-11T11:57:27+00:00 | Sun [sun] | Moon [moon] | Conjunction | 0°00'00" | separation increasing
2024-01-25T17:54:00+00:00 | Sun [sun] | Moon [moon] | Opposition | +180°00'00" | separation increasing
```

<!-- /usage: moving.events -->

The complete table also contains raw TT, relative rate, query bounds, both models
and calculation versions. Pass `language="zh-CN"` for Chinese vocabulary from the
supplied catalog. UTC uses the existing [event-display conversion](transits.md#read-utc-and-format-event-tables),
including its frozen leap offsets, 1972 restriction, microsecond rounding and
whole-second table display. Display precision never changes event membership.

The USNO definition identifies exact new/full moons with Moon-minus-Sun apparent
ecliptic longitude 0°/180°. The example's `(Sun, Moon)` pair uses this
Moon-minus-Sun separation. Swapping the pair order leaves these targets unchanged:
0° stays 0°, and -180° is represented as 180°.
The [knowledge entry](catalog.md), `entry.moving_aspect_events`, records that source
separately from the project's model and search conventions.

## Read the geometry

`pairs` is a nonempty sequence of ordered `(first, second)` identities; `aspects`
is an explicit nonempty selection of `MajorAspect` values. Repeated ordered pairs,
repeated aspects and self-pairs are rejected. A reversed pair is a separate request.
All ten `Body` members and the four named `LunarNode` members are available within
their supported event windows; axes are not moving event sources.
For the other major aspects, select `MajorAspect.SEXTILE`, `MajorAspect.SQUARE`
or `MajorAspect.TRINE`. Each identity uses a calculation model with its own
supported TT window and maximum search span. Read these limits and the model name
from `events.sources`; see [event source records](transits.md#read-and-retain-the-result).

| Result | Meaning |
|---|---|
| `hit.first_object`, `hit.second_object` | Both are moving roles |
| `hit.branch_deg` | Second-minus-first target: one branch for conjunction/opposition, two for the other major aspects |
| `hit.signed_difference_deg` | Unchanged native first-minus-second angle |
| `hit.separation_deg`, `hit.deviation_deg` | Canonical second-minus-first angle and its signed deviation from the branch, in (-180, 180] |
| `hit.first_longitude_deg`, `hit.second_longitude_deg` | Raw apparent geocentric tropical longitudes at the same event TT, in degrees |
| `hit.first_rate_deg_per_tt_day`, `hit.second_rate_deg_per_tt_day` | Raw rates; `relative_rate_deg_per_tt_day` is second minus first |
| `hit.direction` | `RelativeDirection`: separation increasing, decreasing or tangent, not either body's direct/retrograde motion |
| `events.sources` | One `TransitSource` per distinct requested identity, in first-appearance order |

Opposition remains 180° after reversal. At a tangent, the separation reaches the
requested branch without crossing it; the reported relative rate need not be
exactly zero. Hits sort by raw TT, requested pair order, aspect angle and branch.
Two requested pairs that hit at the same TT give two hits. Nearby times returned
by the upstream search are not combined by a tolerance.
Direction follows the continuous (unwrapped) second-minus-first longitude across
wraps, not the absolute value of the canonical separation.

## Empty results and failures

The UTC endpoints must be aware built-in datetimes whose instants, converted to
UTC, are at or after 1972-01-01 UTC.
The search uses their converted **half-open TT interval**, at most 3660 TT days,
within both identities' supported event windows.

Constant mismatch (the relation never holds) is a valid empty result. For example, mean ascending and descending
nodes cannot be conjunct:

```{doctest}
>>> from astrology import LunarNode
>>> empty = moving_aspect_events(
...     pairs=((LunarNode.MEAN_ASCENDING, LunarNode.MEAN_DESCENDING),),
...     aspects=(MajorAspect.CONJUNCTION,),
...     start_utc=events.start_utc, end_utc=events.end_utc)
>>> empty.hits
()
>>> print(format_moving_events(empty, load_catalog()).splitlines()[-1])
No exact moving-pair events in the supplied interval
```

The mean ascending and descending nodes' continuously satisfied opposition raises
`MovingEventDomainError` rather than producing an infinite event list. Invalid types raise
`TypeError`; invalid selections, self-pairs, endpoint order or missing UTC offsets
raise `ValueError`. Pre-1972 UTC raises
`HistoricalTimeError`. Domain/span rejections raise `MovingEventDomainError`,
a `ValueError` subclass,
retaining the operation, both pair identities and TT bounds when available, the
verbatim upstream message and the cause. Native `CelestialError` propagates
unchanged. Any failed pair/branch aborts the entire query, including after earlier
success; failure never becomes an empty or partial result.

Importing the package, querying knowledge, constructing supplied results and
formatting empty results do not start the native astronomy library. Search
initializes it lazily; reading or formatting populated hits initializes only
time conversion.

## Build a chart at an event

Supply a location and chart configuration only when calculating houses:

```{doctest}
>>> from astrology import ChartConfig, HouseSystem, Location, moment_chart
>>> hit = events.hits[0]
>>> chart = moment_chart(hit, Location(0, 0),
...     ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ()))
>>> chart.moment.source_jde_tt == hit.jde_tt
True
>>> chart.moment.utc == moving_hit_utc(hit)
True
```

The [moment-chart domain](moments.md#build-from-a-retained-exact-hit) is separate
from the event domain. A chart failure does not invalidate the retained event.
Source-event TT and the chart's derived calculation TT remain separate.

## Search cost

A one-year Mercury/Sun conjunction query took about 13 seconds in a measured
environment, despite returning only six hits. Cost is not proportional to hit
count, and the measurement is not a response-time guarantee.

For independent numerical fixtures and regeneration, see
[contributing](contributing.md#correctness).
