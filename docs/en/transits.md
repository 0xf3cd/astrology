# Exact transit hits

[简体中文](../zh-CN/transits.md) · [Documentation](index.md) · [API](reference.md)

`transit_hits` finds every selected exact aspect to an existing chart within a
supplied UTC interval, converted to TT for membership. It returns a `TransitHits`
result with the original chart, search inputs, model provenance, and each crossing
or contact. Hit times are JDE(TT): Julian Dates on the TT time scale, not UTC clock
readings.

(event-provider-en)=
The event provider is the selected celestial-calendar longitude-event search
implementation.

For the natal-only ten-body convenience `return_hits` and a chart at a chosen
hit/location, see [planetary returns](returns.md).

## Search an interval

The fixed source may also be a `MomentChart`; `natal_objects` names its
fixed-reference role, not its birth-input kind. `TransitHits.epoch_policy` keeps
`fixed_natal_degree_against_moving_of_date_longitude` for both source types because
the longitude convention is unchanged. The genuine source type/input remains in
`result.chart`. For building and reading a moment chart, see [moment charts](moments.md).

<!-- usage: transits.hits -->

This synthetic birth example calculates one stored natal Sun. The moving side
needs only an object selection and an interval, with no birthplace or houses.
Both endpoints must be timezone-aware built-in `datetime` values at or after
1972-01-01 UTC. Local offsets are normalized to UTC; naive values are rejected.

```{doctest}
>>> from datetime import UTC, date, datetime, time, timedelta
>>> from astrology import (
...   BirthRecord, Body, ChartConfig, FixedOffset, HouseSystem, Location,
...   MajorAspect, natal_chart, prepare_natal_input, transit_hits,
... )
>>> record = BirthRecord(date(2000, 4, 10), time(12), FixedOffset(timedelta(0)),
...   Location(0, 0), source={"example": "synthetic"})
>>> chart = natal_chart(prepare_natal_input(record),
...   ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ()))
>>> result = transit_hits(chart,
...   start_utc=datetime(2024, 3, 1, tzinfo=UTC),
...   end_utc=datetime(2024, 6, 1, tzinfo=UTC),
...   moving_objects=(Body.MERCURY,), natal_objects=(Body.SUN,),
...   aspects=(MajorAspect.CONJUNCTION,))
>>> for hit in result.hits:
...   print(f"{hit.moving_object.value} {hit.aspect.value} {hit.natal_object.value} "
...         f"{hit.jde_tt:.5f} {hit.direction.value} {hit.longitude_rate_deg_per_tt_day:+.3f}")
mercury conjunction sun 2460392.23731 increasing +1.208
mercury conjunction sun 2460414.61236 decreasing -0.744
mercury conjunction sun 2460437.45999 increasing +0.812
```

Mercury reaches the fixed natal Sun degree three times: once while its longitude
increases, once during retrograde motion, and once after it increases again.
Rates are degrees per TT day, copied from the upstream event. A `tangent` event
touches the requested longitude without crossing it; its reported rate need not
be exactly zero.

<!-- /usage: transits.hits -->

## Read UTC and format event tables

Use `transit_hit_utc` for a location-free UTC readout, and `format_transit_hits`
for an English or Chinese table. The table keeps the moving and fixed-source roles,
aspect and oriented branch, direction, raw TT, and the model/version context:

```{doctest}
>>> from astrology import format_transit_hits, load_catalog, transit_hit_utc
>>> displayed = transit_hit_utc(result.hits[0])
>>> displayed.isoformat(timespec="microseconds")
'2024-03-22T17:40:34.047537+00:00'
>>> displayed.isoformat(timespec="seconds")
'2024-03-22T17:40:34+00:00'
>>> catalog = load_catalog()
>>> print(format_transit_hits(result, catalog))
Exact transit hits
Supplied UTC interval [start, end): [2024-03-01T00:00:00+00:00, 2024-06-01T00:00:00+00:00)
Converted TT interval [start, end): [2460370.500800741, 2460462.500800741)
Event models: Mercury [mercury]: position_source/3
astrology / celestial-calendar versions: 0.5.0 / 1.1.1
<BLANKLINE>
UTC | Moving object | Fixed source | Aspect | Branch | Direction | JDE(TT)
2024-03-22T17:40:34+00:00 | Mercury [mercury] | Sun [sun] | Conjunction | 0°00'00" | increasing | 2460392.2373059206
2024-04-14T02:40:38+00:00 | Mercury [mercury] | Sun [sun] | Conjunction | 0°00'00" | decreasing | 2460414.612359507
2024-05-06T23:01:13+00:00 | Mercury [mercury] | Sun [sun] | Conjunction | 0°00'00" | increasing | 2460437.459988502
```

The three times have different jobs: `start_utc` and `end_utc` are the supplied
civil endpoints, `start_jde_tt` and `end_jde_tt` determine search membership, and
each derived event UTC is only a display. Keep raw `jde_tt` as the event authority.
Conversion to `datetime` rounds the day fraction to microseconds; the table then
truncates rather than rounds to whole seconds. This display loses precision and
does not change the hit or its order.

The upstream uses a frozen leap-offset table and retains its final offset after
the last entry. It does not predict future leap seconds. Python `datetime` cannot
represent a leap second, and a UTC-to-TT-to-UTC round trip need not recover the
original civil fields. At the 2016 leap boundary, direct TT offsets of +68.400,
+69.100 and +69.200 seconds from JDE(TT) `2457754.5` display respectively as
`2017-01-01T00:00:00.215991+00:00`, `00:00:00.916007+00:00` and
`00:00:00.015987+00:00`. Display can therefore enter the next year, repeat a
second, reverse order, or appear outside the supplied UTC interval. Raw TT still
determines membership, ordering and classification. The adjacent representable
floating-point JDE(TT) values immediately below and above the leap start can also
display on different civil dates.

The upstream converter accepts JDE(TT) in `[1867522.5, 13689325.5)`. Display is
further limited to converted civil dates at or after 1972-01-01 and values Python
`datetime` can represent (through year 9999, including any rounding carry).
If conversion yields the upstream pre-1972 UT1 substitute, `transit_hit_utc` raises
`EventDisplayError` rather than labeling it ordinary UTC. Range and Python datetime
construction failures use the same display-specific error and retain the source TT,
operation, upstream message and original cause. Native `CelestialError` propagates
unchanged. The 1972 model seam and leap steps are not exact inverses.

Calling either formatter with no hits returns a meaningful empty table without
initializing native astronomy. Populated tables lazily call only `jde_to_utc` for
each row: they do not search again, call `utc_to_jde`, calculate houses, construct
a chart, or use chart-specific `moment_utc`. Package import and field reads remain
native-free. `format_return_hits` additionally validates a post-natal same-body
`NatalChart` result; see [planetary returns](returns.md#read-utc-and-format-event-tables).

## Select targets and aspects

- `moving_objects` selects bodies or named lunar nodes, in the given order.
  They need not be present on the natal chart. Axes cannot move in this query.
- `natal_objects` selects stored bodies/nodes and may explicitly add `Axis`
  members. Selections follow the source's stored position order, then
  Ascendant, Midheaven, Descendant and Imum Coeli. Axes use their own stored fields.
- `aspects` selects `MajorAspect` identities, not `AspectRule` orbs. Nothing is
  inherited from the natal chart's aspect rules. Each selection must be nonempty
  and duplicate-free; unavailable natal objects are rejected. Retained aspects
  are normalized to ascending angle order.

For example, `natal_objects=(Axis.ASCENDANT,)` searches the source chart's stored
Ascendant degree instead of its Sun. Import `Axis` from `astrology` and replace
the `natal_objects` argument in the call above. Every `NatalChart` stores its axes,
regardless of the selected bodies; this example's axis query returns no hits in
the displayed interval. A natal target stays fixed even when its stored position
includes a longitude rate.

Conjunction and opposition each have one branch. The other major aspects search
both oriented branches. `hit.branch_deg` is the signed angle added to the natal
degree: 0° for conjunction, 180° for opposition, and ± the aspect angle for the
others. `hit.query_longitude_deg` is that sum reduced to [0°, 360°), the moving
longitude the search solves for. `hit.longitude_deg` preserves the raw event
longitude, which can differ by a small numerical residual or lie on the other
side of 0°/360°. See the {ref}`rule and coordinate limits
<catalog-en-rule-project-exact-transit-hits>` for the own-date longitude convention.

## Search cost

The number of upstream interval scans is:

`moving objects × natal targets × total oriented aspect branches`

All five major aspects have eight branches in total, not five. Narrow each
selection to the question you need, and start with a short interval. The call
provides no progress callback and returns only after every selected scan succeeds;
it does not return partial results.

Measurements on 2026-11-07 with celestial-calendar 1.1.1 and Python 3.14.9 on a
16-core Linux machine give approximate costs, not timing guarantees. One longitude
scan over 365 TT days took about 2–11 seconds for Jupiter, Uranus, Venus, Saturn,
Mars and Mercury; Mercury was slowest. Sun and Moon each took less than 0.1 second.
A separate one-year search of Saturn and Jupiter against natal Sun, Moon and
Ascendant, selecting conjunction, square and opposition, took about 74 seconds:
`2 × 3 × (1 + 2 + 1) = 24` scans.

Ten moving bodies against ten natal bodies plus four axes, with all five aspects,
require `10 × 14 × 8 = 1120` scans. Extrapolating each moving body's measured scan
time equally across all natal targets and branches gives roughly an hour for that
one-year request; the complete request was not timed. Costs depend on the target,
interval, machine and load; do not assume that they scale linearly with interval
length from these samples.

## Read and retain the result

```{doctest}
>>> result.chart is chart
True
>>> result.start_utc.isoformat()
'2024-03-01T00:00:00+00:00'
>>> result.sources[0].model_kind, result.sources[0].model_identity
('position_source', 3)
>>> result.celestial_version
'1.1.1'
```

`('position_source', 3)` is the effective upstream model key for this Mercury
search; `result.sources[0].model_description` gives its name and description.
Tables write this key as `model_kind/model_identity`, here `position_source/3`.

`start_jde_tt` and `end_jde_tt` retain the converted search interval. Each
`TransitSource` identifies the effective moving model, its event-domain bounds,
maximum span and upstream descriptions. The result also retains the astrology
version and explicit time, position-frame and epoch policies. These versions
describe the current transit calculation; `result.chart.provenance` describes
the original natal calculation and may record different versions.

Hits are sorted by TT time, moving selection order, natal source order, ascending
aspect angle and then negative before positive branch. Different identities at
the same time remain separate. Close crossings are not merged by a tolerance.
Timestamps are reported as multiples of 2^-30 day; that numerical resolution is
not an astronomical accuracy bound.

Sequences are isolated as immutable tuples. Constructing or reading a supplied
result does not load native astronomy. See the [constructor validation contract](architecture.md#reproducibility)
for the checks performed on caller-supplied results.

## Limits and failures

The search interval is **half-open**, including its TT start and excluding its TT
end. Its maximum duration is **3660 TT days**, and every selected moving source
must admit the whole interval. The limit applies after UTC-to-TT conversion:
leap-second changes can make a civil interval of 3660 days exceed the TT cap.
This is separate from the natal snapshot's joint
domain: selecting the Sun alone can search dates unavailable to Pluto. UTC
conversion uses the upstream's fixed leap-second table, so its final offset is
retained after the last entry; it does not predict future leap seconds. A known
leap step can make the TT duration differ from the civil elapsed duration.

| Failure | Exception |
|---|---|
| Wrong Python or enum type | `TypeError` |
| Missing UTC offset, invalid order, empty/duplicate/unavailable selection or normalization overflow | `ValueError` |
| Normalized UTC before 1972 | `HistoricalTimeError` |
| UTC conversion, converted TT span or selected rate domain rejected upstream | `TransitDomainError` |
| Native computation/resource/internal failure | Upstream `CelestialError`, unchanged |
| Missing installed distribution metadata | `importlib.metadata.PackageNotFoundError` |

`TransitDomainError` is a `ValueError` with `operation`, the moving identity and
TT endpoints when available, `upstream_message`, and the original exception as
its cause. A failed provider aborts the whole call; no partial list is returned.
An empty successful hit tuple means the complete selected search found no event.

An endpoint uses the offset returned by its `datetime.utcoffset()`, including its
`fold` setting. This function does not detect or reject nonexistent or ambiguous
local clock readings. Resolve daylight-saving gaps or overlaps before supplying
an endpoint; see the [birth-time explanation](birth.md).

This operation finds
exact moving-to-fixed hits. It does not calculate a fixed-instant transit chart,
orb-entry windows, moving-to-moving events or interpretation.
For aspects at one chosen instant with local motion, use [moment_chart and
transit_aspects](moments.md). [Static cross-chart aspects](cross_aspects.md#compare-two-example-charts)
remain available when no motion is wanted; both compare own-date stored longitudes
under the [source-compatibility convention](cross_aspects.md#source-compatibility-and-calculation-boundaries).
