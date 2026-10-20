# Natal charts

[简体中文](../zh-CN/chart.md) · [Documentation](index.md) · [API reference](reference.md)

`natal_chart` is the single entry point for a modern tropical, geocentric natal
chart. It takes a resolved birth instant and a requested configuration and
returns an immutable result that keeps the requested choices, the effective
choices, the astronomical values and their provenance apart.

## Calculate one chart

Prepare the input first. A chart needs a known clock, an explicit timezone and
a location; the [birth guide](birth.md) explains that preparation.

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (
...   Body, BirthRecord, ChartConfig, FixedOffset, HouseSystem, Location,
...   TimePrecision, natal_chart, prepare_natal_input,
... )
>>> record = BirthRecord(
...   date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)),
...   Location(64.15, -21.94), TimePrecision.SECOND, {"record": "synthetic"},
... )
>>> resolved = prepare_natal_input(record)
>>> request = ChartConfig(HouseSystem.PLACIDUS, (Body.SUN, Body.MOON), ())
>>> chart = natal_chart(resolved, request)
>>> chart.requested.house_system.value
'placidus'
>>> chart.effective.house_system.value
'placidus'
```

Positions are apparent geocentric ecliptic longitudes and latitudes of date.
The result keeps the unrounded values; the derived sign and house follow from
them.

```{doctest}
>>> sun, moon = chart.positions
>>> round(sun.longitude_deg, 4), round(moon.longitude_deg, 4)
(114.2565, 337.8942)
>>> placements = chart.placements
>>> (placements[0].sign, placements[0].house)
(<Sign.CANCER: 'cancer'>, 12)
>>> (placements[1].sign, placements[1].house)
(<Sign.PISCES: 'pisces'>, 9)
>>> round(placements[0].sign_degree_deg, 4)
24.2565
```

## Keep the models and the conventions

The requested configuration and the effective configuration are separate
values. The adapter fixes the ΔT model; it is not a caller request, and the
result names it anyway.

```{doctest}
>>> chart.effective.delta_t_model
'algo5'
>>> chart.effective.evaluation
'fixed_fourteen_object_joint_snapshot'
>>> chart.provenance.celestial_version
'0.8.0'
>>> chart.provenance.position_frame
'apparent_geocentric_true_ecliptic_of_date'
>>> chart.provenance.ut1_derivation
'delta_t_model_from_civil_utc'
```

`position_frame` states that the values are apparent geocentric positions on the
true ecliptic and equinox of date. `ut1_derivation` states that UT1 is derived
from civil UTC through the ΔT model, not observed as DUT1. The lunar nodes are
referred to the same true equinox, so they already carry the nutation in
longitude. `ChartTimes` records the UT1-based Julian Day and the TT-based
Julian Ephemeris Day of the instant.

```{doctest}
>>> chart.times.jde_tt > chart.times.jd_ut1
True
```

Positions do not depend on the location; the house geometry does.

```{doctest}
>>> elsewhere = natal_chart(
...   prepare_natal_input(BirthRecord(
...     date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)),
...     Location(-33.87, 151.21), TimePrecision.SECOND, {"record": "synthetic"},
...   )),
...   request,
... )
>>> elsewhere.positions == chart.positions
True
>>> elsewhere.houses == chart.houses
False
```

## Read the house system as it is

Whole Sign, Equal and Placidus are different geometries, not different labels
for one result. Under Whole Sign the Ascendant is not the first cusp, and the
Midheaven is not the tenth cusp; the chart keeps the axes and the cusps apart.

```{doctest}
>>> whole = natal_chart(
...   resolved, ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ())
... )
>>> whole.houses.cusps_deg[0]
120.0
>>> round(whole.houses.ascendant_deg, 4)
127.7431
>>> whole.houses.ascendant_deg != whole.houses.cusps_deg[0]
True
>>> from astrology import house_of
>>> house_of(whole.houses.ascendant_deg, whole.houses.cusps_deg)
1
```

A house interval is half-open: a longitude exactly on a cusp belongs to the
house that starts there. `house_of` works on any supplied cusp table and never
consults the Ascendant.

```{doctest}
>>> from astrology import house_of
>>> house_of(120.0, whole.houses.cusps_deg)
1
>>> house_of(150.0, whole.houses.cusps_deg)
2
>>> house_of(0.0, whole.houses.cusps_deg)
9
>>> house_of(359.999999, whole.houses.cusps_deg)
8
```

## Read a sign from a longitude

Sign sectors are half-open: exactly 30 degrees is Taurus, exactly 0 degrees is
Aries. The degree within the sign is unrounded, and the display rule is
truncation, so a displayed value never shows the next sign.

```{doctest}
>>> from astrology import Sign, sign_degree, sign_of, truncate_display
>>> sign_of(0.0), sign_of(30.0)
(<Sign.ARIES: 'aries'>, <Sign.TAURUS: 'taurus'>)
>>> sign_degree(45.0)
15.0
>>> truncate_display(29.9999999)
29.99972222222222
>>> sign_of(truncate_display(29.9999999)) is sign_of(29.9999999)
True
```

## Fail explicitly

The adapter rejects input it can judge before the astronomy library is asked,
and reports an upstream failure without inventing a substitute. Nothing is
returned partially, and the requested house system is never replaced.

```{doctest}
>>> from astrology import ChartDomainError, MissingBirthDataError
>>> polar = BirthRecord(
...   date(2003, 7, 17), time(12, 0), FixedOffset(timedelta(0)),
...   Location(90.0, 0.0), TimePrecision.SECOND, {"record": "synthetic"},
... )
>>> try:
...   natal_chart(prepare_natal_input(polar), request)
... except ChartDomainError as error:
...   (type(error).__name__, error.house_system.value)
('ChartDomainError', 'placidus')
```

A missing location is missing information, not a domain error, and is reported
as such.

```{doctest}
>>> without_location = BirthRecord(
...   date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)), None,
...   TimePrecision.SECOND, {"record": "synthetic"},
... )
>>> from astrology import resolve_birth_time
>>> try:
...   natal_chart(resolve_birth_time(without_location), request)
... except MissingBirthDataError as error:
...   type(error).__name__
'MissingBirthDataError'
```

| Situation | Reported as |
|---|---|
| No location on the record | `MissingBirthDataError` |
| Latitude at a pole | `ChartDomainError`, no upstream detail |
| Civil year 2100 or later | `ChartDomainError`, no upstream detail |
| Instant outside the supported ephemeris range | `ChartDomainError` with the upstream operation |
| Requested geometry undefined at this latitude | `ChartDomainError` with the requested house system |

The classification never depends on reading the upstream message. A failure
raised before the library is called carries no upstream detail; a failure
raised by the library carries the operation and the recording status.

```{doctest}
>>> high = prepare_natal_input(BirthRecord(
...   date(1990, 6, 21), time(0, 0), FixedOffset(timedelta(0)),
...   Location(69.65, 0.0), TimePrecision.SECOND, {"record": "synthetic"},
... ))
>>> try:
...   natal_chart(high, ChartConfig(HouseSystem.PLACIDUS, (Body.SUN,), ()))
... except ChartDomainError as error:
...   (error.house_system.value, error.operation, error.recorded)
('placidus', 'chart_snapshot', True)
>>> natal_chart(high, ChartConfig(HouseSystem.EQUAL, (Body.SUN,), ())).houses.system.value
'equal'
```

## Select objects without widening the domain

The astronomy library evaluates the fourteen-object snapshot and the house
geometry together. Selecting fewer objects filters that output; it does not
narrow the evaluated domain, and the result says so.

```{doctest}
>>> one = natal_chart(resolved, ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ()))
>>> len(one.positions)
1
>>> one.effective.evaluation
'fixed_fourteen_object_joint_snapshot'
```

## Check the result against an independent reference

The reference cases in `tests/reference/natal_reference.json` compare two
instants, one per hemisphere, with JPL Horizons. Under matched conventions the
checks require agreement within 3 arcseconds for the Sun and the planets, 15 for
the Moon, 1 arcsecond in latitude (3 for the Moon) and 0.001 degrees for the
axes. The Placidus cusps 2, 3, 11 and 12 are held to the same 0.001 degrees
against the Placidus definition, evaluated at the Horizons sidereal time. The
node check reimplements the Meeus chapter 47 formulas that the library also
uses, and the leap-second relation `JDE(TT) - JD(UTC)` is exact. The
[contributing guide](contributing.md#correctness) records what each reference
can and cannot detect.

## Limits

- Aspect angles, orbs and applying or separating motion are not calculated
  here; see the [configuration guide](configuration.md).
- Results are not serialized and have no text output yet.
- The repository keeps no external reference values for Placidus cusps. Cusps 2, 3, 11 and 12 are checked
  against the definition, which the check and the library read alike; cusps 5, 6,
  8 and 9 are checked only as the exact opposites.
- The astronomy library supports civil years 1885 to 2099 and, for UTC input,
  instants from 1972-01-01; the ephemeris range is narrower than the civil
  range, and an instant outside it fails explicitly.
- Installs need a platform with a celestial-calendar wheel; see
  [contributing](contributing.md#run-the-checks).
