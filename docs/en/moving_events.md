# Moving-pair events

[简体中文](../zh-CN/moving_events.md) · [API](reference.md#moving-pair-events) · [Exact fixed-source transits](transits.md)

Use `moving_aspect_events` to find exact major aspects between two moving bodies
or named lunar nodes. Searching needs neither a natal chart nor a location.

## Find new and full moons

<!-- usage: moving.events -->

Both longitudes vary. This example requests Moon first and Sun second, so its
relative angle and rate are **Sun minus Moon**:

```{doctest}
>>> from datetime import UTC, datetime
>>> from astrology import (Body, MajorAspect, moving_aspect_events, moving_hit_utc,
...     format_moving_events, load_catalog)
>>> events = moving_aspect_events(
...     pairs=((Body.MOON, Body.SUN),),
...     aspects=(MajorAspect.CONJUNCTION, MajorAspect.OPPOSITION),
...     start_utc=datetime(2024, 1, 1, tzinfo=UTC),
...     end_utc=datetime(2024, 2, 1, tzinfo=UTC))
>>> [(moving_hit_utc(hit).isoformat(timespec="seconds"), hit.aspect.value,
...   hit.direction.value) for hit in events.hits]
[('2024-01-11T11:57:27+00:00', 'conjunction', 'decreasing'), ('2024-01-25T17:54:00+00:00', 'opposition', 'decreasing')]
>>> table = format_moving_events(events, load_catalog())
>>> print(table.splitlines()[0])
Exact moving-pair events
>>> for row in table.splitlines():
...     if row.startswith("2024-"):
...         print(" | ".join(row.split(" | ")[:6]))
2024-01-11T11:57:27+00:00 | Moon [moon] | Sun [sun] | Conjunction | 0°00'00" | separation decreasing
2024-01-25T17:54:00+00:00 | Moon [moon] | Sun [sun] | Opposition | +180°00'00" | separation decreasing
```

<!-- /usage: moving.events -->

The complete table also contains raw TT, relative rate, query bounds, both models
and calculation versions. Pass `language="zh-CN"` for Chinese vocabulary from the
supplied catalog. UTC uses the existing [event-display conversion](transits.md#read-utc-and-format-event-tables),
including its frozen leap offsets, 1972 restriction, microsecond rounding and
whole-second table display. Display precision never changes event membership.

The USNO definition identifies exact new/full moons with Moon-minus-Sun apparent
ecliptic longitude 0°/180°. These two targets are unchanged by reversal.
The [knowledge entry](catalog.md), `entry.moving_aspect_events`, records that source
separately from the project's model and search conventions.

## Read the geometry

`pairs` is a nonempty sequence of ordered `(first, second)` identities; `aspects`
is an explicit nonempty selection of `MajorAspect` values. Repeated ordered pairs,
repeated aspects and self-pairs are rejected. A reversed pair is a separate request.
All ten `Body` members and the four named `LunarNode` members are available where
their providers admit the query; axes are not moving event providers.

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

Opposition remains 180° after reversal. Tangent retains the provider's two-sided
contact classification; it does not require identical rates. Hits sort by raw TT,
requested pair order, aspect angle and branch. Coincident roles and distinct
provider times are not merged by a tolerance.
Direction follows the continuous (unwrapped) second-minus-first longitude across
wraps, not the absolute value of the canonical separation.

## Empty results and failures

The UTC endpoints must be aware built-in datetimes at or after 1972-01-01 UTC.
The search uses their converted **half-open TT interval**, at most 3660 TT days,
within both providers' event domains.

Constant mismatch is a valid empty result. For example, mean ascending and descending
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

Their continuously satisfied opposition is rejected rather than represented by
an infinite event list. Domain/span rejections raise `MovingEventDomainError`,
retaining the operation, both pair identities and TT bounds when available, the
verbatim upstream message and the cause. Native `CelestialError` propagates
unchanged. Any failed pair/branch aborts the entire query, including after earlier
success; failure never becomes an empty or partial result.

Importing the package, querying knowledge, constructing supplied results and formatting
empty results are native-free. Search initializes native astronomy lazily; reading
or formatting populated hits initializes only time conversion. Constructors copy
nested pairs and validate consistency and provider windows, not astronomical origin
or completeness of caller-supplied hits.

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

Independent numerical fixtures and regeneration are described in
[contributing](contributing.md#correctness).

## Search cost

On one Linux environment with Python 3.14.9 and celestial-calendar 1.1.1, complete
queries had the following median wall times over three runs after an initial query:

| Pair / aspects | UTC interval | Hits | Median |
|---|---|---:|---:|
| Moon/Sun, all five aspects | 2024-01-01 to 2024-02-01 | 9 | 0.66 s |
| Moon/Sun, conjunction/opposition | 2024-01-01 to 2025-01-01 | 25 | 1.89 s |
| Mercury/Sun, conjunction | 2024-01-01 to 2025-01-01 | 6 | 12.80 s |

These are selected-query measurements, not latency guarantees. Relative extrema
can make a small event list expensive; query cost is not proportional to hit count.
