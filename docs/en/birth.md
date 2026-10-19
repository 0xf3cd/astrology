# Birth records and modern time resolution

[简体中文](../zh-CN/birth.md) · [Documentation](index.md) · [API reference](reference.md)

Keep a civil record separate from its resolved instant. All examples below are
synthetic; these APIs prepare inputs, not charts.

## Preserve what is known

`BirthRecord` stores a proleptic Gregorian `datetime.date`, an optional naive
`datetime.time`, timezone input, location, stated clock precision, and source
metadata. `calendar="gregorian"` is the only admitted calendar; no calendar
conversion, including Julian-calendar conversion, is performed. A missing clock
or location stays `None`.

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import BirthRecord, MissingBirthDataError, prepare_natal_input
>>> unknown = BirthRecord(date(2000, 1, 1))
>>> (unknown.birth_time, unknown.location, unknown.precision)
(None, None, None)
>>> try:
...   prepare_natal_input(unknown)
... except MissingBirthDataError as exc:
...   print(type(exc).__name__)
MissingBirthDataError
```

There is no noon or location substitution. `TimePrecision` records hour, minute,
second, or microsecond precision; smaller clock fields must be zero. `None`
means unstated precision, not an uncertainty interval. An unknown clock cannot
claim clock precision. Pass timezone and fold separately: a recorded clock with
`tzinfo` or `fold=1` is rejected rather than treated as a second input channel.

`Location` uses finite degrees: latitude `[-90, 90]`, longitude `[-180, 180]`,
north/east positive. Values are not wrapped. The poles and both longitude
endpoints are valid *record* values, not promises of available house geometry.

## Choose an ambiguous instant

`IanaTimezone` requires a plain string with nonempty slash-separated segments of
ASCII letters, digits, `_`, `+`, or `-`. Malformed shapes raise `ValueError` at
construction. Resolution checks the exact, case-sensitive identity against the
package's zone-key list; an unknown key raises `ValueError`. IANA data is read explicitly from
the installed, pinned `tzdata` package with `ZoneInfo.from_file`; the system
timezone database and key cache do not select the result.

TZif is the binary timezone-data file format read by `ZoneInfo.from_file`.

```{doctest}
>>> from astrology import (
...   AmbiguousBirthTimeError, IanaTimezone, Location, TimePrecision,
...   resolve_birth_time,
... )
>>> source = {"record": "synthetic"}
>>> record = BirthRecord(
...   date(2026, 4, 5), time(1, 45), IanaTimezone("Australia/Lord_Howe"),
...   Location(0, 0), TimePrecision.MINUTE, source,
... )
>>> source["record"] = "edited by caller"
>>> record.source["record"]
'synthetic'
>>> try:
...   resolve_birth_time(record)
... except AmbiguousBirthTimeError as exc:
...   print(type(exc).__name__)
AmbiguousBirthTimeError
>>> earlier = prepare_natal_input(record, fold=0)
>>> later = prepare_natal_input(record, fold=1)
>>> (earlier.utc.isoformat(), later.utc.isoformat())
('2026-04-04T14:45:00+00:00', '2026-04-04T15:15:00+00:00')
>>> (later.record.birth_time.isoformat(), later.fold, later.timezone_identity)
('01:45:00', 1, 'Australia/Lord_Howe')
```

The resolver round-trips both fold candidates through UTC and deduplicates by UTC
instant. A gap has no valid candidate and raises `NonexistentBirthTimeError`;
an overlap requires `fold=0` (earlier) or `fold=1` (later). Shifts need not be one
hour. A supplied fold for a unique clock or fixed offset is an error. Floats,
booleans, and values other than the integers 0 and 1 are not fold choices.

`ResolvedBirth` retains the original record separately from UTC, the actual
offset, fold choice, IANA key, package version, and IANA release. Its constructor
checks shape and preservation of the recorded clock as UTC plus offset. It does
not load timezone rules to authenticate manually supplied offsets, folds, or
versions. Use `resolve_birth_time` to validate the actual candidate and read its
data versions.

```{doctest}
>>> from importlib import import_module
>>> from importlib.metadata import version
>>> later.timezone_source
'tzdata'
>>> later.tzdata_version == version("tzdata")
True
>>> later.iana_version == import_module("tzdata").IANA_VERSION
True
```

Package and IANA versions are distinct identifiers, taken from
`tzdata.__version__` and `tzdata.IANA_VERSION`. Importing `astrology` does not
read timezone resources or initialize native astronomy.

## Resolve an explicit offset

`FixedOffset` takes a `datetime.timedelta` strictly between -24 and +24 hours.
The offset may include seconds or microseconds. It does not consult or claim an
IANA database. Time resolution itself does not require a location;
`prepare_natal_input` additionally requires a known location.

```{doctest}
>>> from astrology import FixedOffset
>>> fixed = BirthRecord(
...   date(2026, 4, 5), time(0, 15), FixedOffset(timedelta(minutes=345)),
... )
>>> resolved = resolve_birth_time(fixed)
>>> (resolved.utc.isoformat(), resolved.timezone_identity, resolved.timezone_source)
('2026-04-04T18:30:00+00:00', 'UTC+05:45', 'fixed_offset')
>>> (resolved.tzdata_version, resolved.iana_version)
(None, None)
```

## Supported instant and failures

Modern resolution admits UTC at or after `1972-01-01T00:00:00Z`, within Python's
representable datetime range. The cutoff concerns the *resolved instant*, not
the local year: a 1972 local date can resolve into unsupported 1971 UTC, while a
late 1971 local clock can represent the first supported UTC instant. Clocks more
than one day before the cutoff fail without loading IANA data. For IANA resolution,
if the UTC values obtained with `fold=0` and `fold=1` both precede the cutoff,
resolution fails before fold/gap classification. Candidates are never removed to turn an ambiguous
clock into an apparently unique one. The selected instant must meet the cutoff.

Older Gregorian records remain storable. Resolving earlier instants needs a
future explicit historical-time/UT1 contract; this API does not extrapolate UTC,
convert time scales, or accept leap-second labels. A failed UTC conversion beyond
datetime's upper range is an explicit `ValueError`. Astronomy model domains belong
to the future adapter, not this record type.

| Error | Meaning |
|---|---|
| `TypeError` | Wrong runtime type; strings and booleans are not silently converted |
| `ValueError` | Invalid range, shape, precision, calendar or metadata; unknown key; unusable timezone data file; inconsistent `ResolvedBirth` fields; UTC overflow; irrelevant fold |
| `MissingBirthDataError` | A required clock/timezone, or complete-input location, is absent |
| `AmbiguousBirthTimeError` | An explicit fold choice is required |
| `NonexistentBirthTimeError` | The recorded local clock falls in a gap |
| `HistoricalTimeError` | The instant is before the modern UTC contract |

All four named errors subclass `ValueError`. Validation remains active under
`python -O`. Input source metadata is a copied read-only mapping of plain strings;
mutable string subclasses are rejected. Result and input values are frozen.

Environment failures remain separate: a missing `tzdata` package raises an import
error, missing/invalid version metadata raises `RuntimeError`, and resource
I/O failures not otherwise classified, such as permission errors, propagate as
`OSError` subclasses. These are not missing or invalid birth information.

The algorithm follows the [Python zoneinfo data-source contract](https://docs.python.org/3.11/library/zoneinfo.html#data-sources)
and [PEP 495's fold and gap semantics](https://peps.python.org/pep-0495/).
