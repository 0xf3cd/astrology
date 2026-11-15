# Planetary returns

[简体中文](../zh-CN/returns.md) · [Moment charts](moments.md) · [API](reference.md)

Use `return_hits` to find any of the ten `Body` identities at its stored natal
longitude after the natal TT, within an explicit UTC interval. It returns a
`TransitHits` result with the search provenance and the retained post-natal hits.
Build a chart at a chosen event with `moment_chart`. The examples on this page
continue in order.

## Find every return in an interval

<!-- usage: returns.search -->

The natal chart must contain the selected body. This synthetic example stores the
Sun, Moon and Mercury, then finds three lunar returns and one return each for the
other two bodies in January through March 2024:

```{doctest}
>>> from datetime import UTC, date, datetime, time, timedelta
>>> from astrology import (
...     BirthRecord, Body, ChartConfig, FixedOffset, HouseSystem, Location,
...     moment_chart, natal_chart, prepare_natal_input, return_hits,
... )
>>> birthplace = Location(0, 0)
>>> config = ChartConfig(
...     HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON, Body.MERCURY), ()
... )
>>> record = BirthRecord(date(2000, 2, 29), time(12), FixedOffset(timedelta(0)), birthplace)
>>> natal = natal_chart(prepare_natal_input(record), config)
>>> start = datetime(2024, 1, 1, tzinfo=UTC)
>>> end = datetime(2024, 4, 1, tzinfo=UTC)
>>> events = return_hits(natal, Body.MOON, start_utc=start, end_utc=end)
>>> type(events).__name__, len(events.hits)
('TransitHits', 3)
>>> events.chart is natal
True
>>> events.moving_objects == events.natal_objects == (Body.MOON,)
True
>>> solar = return_hits(natal, Body.SUN, start_utc=start, end_utc=end)
>>> len(solar.hits)
1
>>> mercury = return_hits(natal, Body.MERCURY, start_utc=start, end_utc=end)
>>> len(mercury.hits)
1
```

<!-- /usage: returns.search -->

The supplied interval is `[start_utc, end_utc)` and is converted to TT for event
membership. All retained hits are returned in raw-TT order. Direct, retrograde and
tangent events admitted by the {ref}`event provider <event-provider-en>` are
preserved; a short retrograde recrossing is a return and does not require a
complete orbital cycle. An interval
with no post-natal return has `hits == ()`. No birthday, calendar month,
nearest-return window or complete-cycle assumption is inferred. A calendar-year
search can find one solar return near each end of the year, and a leap-day birth
needs no substitute anniversary date.

The reference is the selected body's **stored natal apparent geocentric tropical
longitude**, compared with the moving longitude at its own date under the
[exact-transit convention](transits.md#select-targets-and-aspects). `return_hits`
makes one same-body conjunction query, then retains only hits whose raw `jde_tt`
is strictly later than `natal.times.jde_tt`:

```{doctest}
>>> from astrology import MajorAspect, transit_hits
>>> explicit = transit_hits(
...     natal, start_utc=start, end_utc=end, moving_objects=(Body.MOON,),
...     natal_objects=(Body.MOON,), aspects=(MajorAspect.CONJUNCTION,),
... )
>>> events.hits == tuple(
...     hit for hit in explicit.hits if hit.jde_tt > natal.times.jde_tt
... )
True
```

Pre-natal hits and a hit exactly at natal TT do not count. Distinct events are
not merged by a time tolerance. The numerical search can report a separate hit
just after natal TT, which a birth-inclusive interval can retain. To omit this
near-natal hit, choose an interval around the later return of interest. The rest
of the result retains the original chart, supplied UTC and converted TT bounds,
selected body, effective models, domains and versions.

## Read UTC and format event tables

Use `transit_hit_utc` to read a retained hit as an aware UTC `datetime`; no
location or chart construction is needed. `format_return_hits` renders the
validated return result in English or Chinese and includes the supplied UTC and
converted TT intervals, model identity and versions. For the model identifier
format, see [retained model provenance](transits.md#read-and-retain-the-result):

```{doctest}
>>> from astrology import format_return_hits, load_catalog, transit_hit_utc
>>> catalog = load_catalog()
>>> transit_hit_utc(mercury.hits[0]).isoformat(timespec="seconds")
'2024-03-01T02:18:31+00:00'
>>> print(format_return_hits(mercury, catalog))
Planetary returns
Supplied UTC interval [start, end): [2024-01-01T00:00:00+00:00, 2024-04-01T00:00:00+00:00)
Converted TT interval [start, end): [2460310.500800741, 2460401.500800741)
Event models: Mercury [mercury]: position_source/3
astrology / celestial-calendar versions: 0.5.0 / 1.1.1
<BLANKLINE>
UTC | Returning body | Direction | JDE(TT)
2024-03-01T02:18:31+00:00 | Mercury [mercury] | increasing | 2460370.5969953192
>>> print(format_return_hits(mercury, catalog, language="zh-CN"))
行星返照
给定 UTC 区间 [start, end): [2024-01-01T00:00:00+00:00, 2024-04-01T00:00:00+00:00)
转换后 TT 区间 [start, end): [2460310.500800741, 2460401.500800741)
事件模型: 水星 [mercury]: position_source/3
astrology / celestial-calendar 版本: 0.5.0 / 1.1.1
<BLANKLINE>
UTC | 返照星体 | 方向 | JDE(TT)
2024-03-01T02:18:31+00:00 | 水星 [mercury] | 黄经增大 | 2460370.5969953192
```

Seconds are truncated after conversion to a microsecond-precision `datetime`.
The raw TT remains authoritative for membership, ordering and classification.
Displayed UTC inside a leap second can repeat a second, cross a civil-date
boundary or reverse order. Display errors,
conversion effects and empty-table behavior are described under
[event UTC and tables](transits.md#read-utc-and-format-event-tables).

The same formatter provides an annual solar-return table. In the leap-day example:

```{doctest}
>>> print(format_return_hits(solar, catalog).splitlines()[-1])
2024-02-29T07:39:12+00:00 | Sun [sun] | increasing | 2460369.819691605
```

## Choose an event and an explicit location

<!-- usage: returns.chart -->

`events.hits` contains event times as JDE(TT), not UTC clock readings. Pass a hit
directly to `moment_chart`; it converts the time at the chart boundary and retains
the original in `moment.source_jde_tt`.

```{doctest}
>>> hit = events.hits[0]
>>> site = Location(40, 100)
>>> returned = moment_chart(hit, site, config)
>>> type(returned).__name__
'MomentChart'
>>> returned.moment.source_jde_tt == hit.jde_tt
True
>>> returned.moment.location == site
True
>>> at_birthplace = moment_chart(hit, birthplace, config)
>>> returned.positions == at_birthplace.positions
True
>>> returned.times == at_birthplace.times
True
>>> returned.houses == at_birthplace.houses
False
```

<!-- /usage: returns.chart -->

Changing location leaves the geocentric event and positions unchanged but changes
local axes and houses. To use the birthplace, pass it explicitly as above; no
current location is inferred. Supply the chart configuration too. It may differ
from the natal configuration and need not contain the returning body; the search
still retains the selected body and its stored natal longitude. No objects are
added and the house system is not replaced.

Keep **both `events` and `returned`** for the complete calculation. `events`
retains the natal chart, selected body, interval, event models, versions and every
post-natal hit. `returned` retains its location, requested/effective chart
configuration, provenance and source event TT separately from normalized UTC and
derived `ChartTimes`. Source TT need not equal the chart calculation's derived TT;
see [time conversion](moments.md#build-from-a-retained-exact-hit).

## Read or compare the return chart

The result is an ordinary `MomentChart`, with no fabricated birth record. Existing
chart consumers work directly with it. The returning Moon falls in the natal
chart's eighth house in this example:

```{doctest}
>>> from astrology import (
...     AspectRule, HouseRulers, chart_dispositors, chart_sign_distribution,
...     cross_chart_aspects, cross_chart_house_overlays, format_chart,
...     transit_aspects,
... )
>>> rules = (AspectRule(MajorAspect.CONJUNCTION, 1),)
>>> comparison = cross_chart_aspects(
...     returned, natal, rules, left_objects=(Body.MOON,), right_objects=(Body.MOON,),
... )
>>> len(comparison.hits)
1
>>> overlays = cross_chart_house_overlays(
...     returned, natal, left_objects=(Body.MOON,), right_objects=(),
... )
>>> overlays.placements[0].identity is Body.MOON
True
>>> overlays.placements[0].house
8
>>> len(transit_aspects(returned, natal, rules,
...     moving_objects=(Body.MOON,), natal_objects=(Body.MOON,)).hits)
1
>>> len(HouseRulers(returned).houses)
12
>>> chart_dispositors(returned, objects=(Body.MOON,)).chart is returned
True
>>> chart_sign_distribution(returned, objects=(Body.MOON,)).total
1
>>> format_chart(returned, catalog).splitlines()[0]
'Tropical geocentric moment chart'
```

Static cross-chart aspects and fixed-instant transits have different motion
semantics; see [moment comparisons](moments.md#compare-moving-objects-with-a-natal-chart).
These calls describe geometry and text, not a return interpretation.

## Errors and sources

- `natal` must be a `NatalChart`, not a `MomentChart`; `body` must be a `Body`.
  Wrong types raise `TypeError`. A selected body missing from the natal chart
  raises `ValueError`; its message lists the bodies available on that chart.
- Aware endpoints, modern UTC, maximum span, model domains and computation
  failures follow [transit search](transits.md#limits-and-failures). In particular,
  `TransitDomainError` retains an upstream rejection; it is not an empty result.
- Finding an event does not ensure its chart can be calculated. Missing location
  raises `TypeError`; unavailable house geometry raises `ChartDomainError`, without
  a fallback. Event conversion and the chart's calculation domain follow
  [moment-chart input contracts](moments.md#calculate-at-an-instant).
- UTC display can raise `EventDisplayError`, including when conversion yields the
  upstream pre-1972 UT1 substitute. It does not change the retained raw TT.

`entry.solar_lunar_returns` in the [catalog](catalog.md) keeps its stable identity
while covering the ten-body project convention. It records the general return
definitions, short quotations with separate Chinese translations, location
practices and post-natal filtering. It does not
define node returns or supply ten separate interpretive traditions. The entry is
available without a chart or native astronomy:

```{doctest}
>>> entry = catalog.entry("entry.solar_lunar_returns")
>>> entry.prerequisite_status.value, entry.output_eligibility.value, entry.chart_applicability
('complete', 'reference_only', 'not_assessed')
>>> len(catalog.citations(entry.identifier))
5
```

`complete` means the entry states its prerequisites; `reference_only` makes it
reference material, and `not_assessed` means retrieving the entry does not assess
a chart against those prerequisites. These are
[separate editorial states](knowledge.md#status-has-several-dimensions).
