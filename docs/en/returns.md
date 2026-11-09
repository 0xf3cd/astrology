# Solar and lunar returns

[简体中文](../zh-CN/returns.md) · [Moment charts](moments.md) · [API](reference.md)

Use `return_hits` to find the Sun or Moon at its stored natal longitude within an
explicit UTC interval. It returns `TransitHits`, the same result as an exact
same-body conjunction search. Build a chart at a chosen event with `moment_chart`.
The examples on this page continue in order.

## Find every return in an interval

<!-- usage: returns.search -->

The natal chart must contain the selected luminary. This synthetic example stores
both, then finds three lunar returns in January through March 2024:

```{doctest}
>>> from datetime import UTC, date, datetime, time, timedelta
>>> from astrology import (
...     BirthRecord, Body, ChartConfig, FixedOffset, HouseSystem, Location,
...     moment_chart, natal_chart, prepare_natal_input, return_hits,
... )
>>> birthplace = Location(0, 0)
>>> config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ())
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
```

<!-- /usage: returns.search -->

The interval is `[start_utc, end_utc)`: a hit at the start is included, one at the
end is excluded. All hits are returned in time order. An interval with no return
has `hits == ()`. Choose the interval yourself; no birthday, calendar month or
nearest-return window is inferred. In the interval above, the leap-day example has
one solar return.
For a birth near the turn of a year, a calendar-year search can find one solar
return near each end of the year; both are retained. A leap-day birth needs no
substitute anniversary date.

The reference is the selected body's **stored natal apparent geocentric tropical
longitude**. It is compared with the moving longitude at its own date, following
the [exact-transit convention](transits.md#select-targets-and-aspects). `return_hits` makes
one same-body conjunction query and returns its complete result unchanged:

```{doctest}
>>> from astrology import MajorAspect, transit_hits
>>> explicit = transit_hits(
...     natal, start_utc=start, end_utc=end, moving_objects=(Body.MOON,),
...     natal_objects=(Body.MOON,), aspects=(MajorAspect.CONJUNCTION,),
... )
>>> events == explicit
True
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
hit. `returned` retains its location, requested/effective chart configuration,
provenance and source event TT separately from normalized UTC and derived
`ChartTimes`. Source TT need not equal the chart calculation's derived TT; see
[time conversion](moments.md#build-from-a-retained-exact-hit).

## Read or compare the return chart

The result is an ordinary `MomentChart`, with no fabricated birth record. Existing
chart consumers work directly with it:

```{doctest}
>>> from astrology import (
...     AspectRule, HouseRulers, chart_dispositors, chart_sign_distribution,
...     cross_chart_aspects, cross_chart_house_overlays, format_chart,
...     load_catalog, transit_aspects,
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
>>> len(overlays.placements)
1
>>> len(transit_aspects(returned, natal, rules,
...     moving_objects=(Body.MOON,), natal_objects=(Body.MOON,)).hits)
1
>>> len(HouseRulers(returned).houses)
12
>>> chart_dispositors(returned, objects=(Body.MOON,)).chart is returned
True
>>> chart_sign_distribution(returned, objects=(Body.MOON,)).total
1
>>> catalog = load_catalog()
>>> format_chart(returned, catalog).splitlines()[0]
'Tropical geocentric moment chart'
```

Static cross-chart aspects and fixed-instant transits have different motion
semantics; see [moment comparisons](moments.md#compare-moving-objects-with-a-natal-chart).
These calls describe geometry and text, not a return interpretation.

## Errors and sources

- `natal` must be a `NatalChart`, not a `MomentChart`; `body` must be a `Body`.
  Wrong types raise `TypeError`; bodies other than `SUN` or `MOON` raise `ValueError`.
  A missing natal luminary also raises `ValueError`.
- Aware endpoints, modern UTC, maximum span, model domains and computation
  failures follow [transit search](transits.md#limits-and-failures). In particular,
  `TransitDomainError` retains an upstream rejection; it is not an empty result.
- Finding an event does not ensure its chart can be calculated. Missing location
  raises `TypeError`; unavailable house geometry raises `ChartDomainError`, without
  a fallback. Event conversion and the chart's calculation domain follow
  [moment-chart input contracts](moments.md#calculate-at-an-instant).

`entry.solar_lunar_returns` in the [catalog](catalog.md) records the definitions,
short quotations with separate Chinese translations, location practices and
project conventions. It is available without a chart or native astronomy:

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
