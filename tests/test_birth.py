"""Directed birth-record, time-resolution, and provenance cases."""

import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, time, timedelta, timezone
from importlib import import_module, metadata
from typing import Any, cast

import pytest

from astrology import (
  AmbiguousBirthTimeError,
  BirthRecord,
  FixedOffset,
  HistoricalTimeError,
  IanaTimezone,
  Location,
  MissingBirthDataError,
  NonexistentBirthTimeError,
  TimePrecision,
  prepare_natal_input,
  resolve_birth_time,
)


def birth_at(text: str, zone: IanaTimezone | FixedOffset) -> BirthRecord:
  wall = datetime.fromisoformat(text)
  return BirthRecord(wall.date(), wall.time(), zone, Location(12.5, -45.25))


def test_unknown_fields_and_copied_metadata() -> None:
  source = {"record": "synthetic", "precision_note": "unstated"}
  record = BirthRecord(date(1950, 1, 1), source=source)
  source["record"] = "changed"
  assert record.source["record"] == "synthetic"
  assert record.birth_time is None
  assert record.timezone is None
  assert record.location is None
  assert record.precision is None
  with pytest.raises(TypeError):
    cast(Any, record.source)["record"] = "changed"
  with pytest.raises(FrozenInstanceError):
    cast(Any, record).birth_time = time(12)
  with pytest.raises(MissingBirthDataError):
    resolve_birth_time(record)


def test_mutable_string_subclasses_do_not_enter_frozen_records() -> None:
  class MutableText(str):
    tags: list[str]

  text = MutableText("synthetic")
  text.tags = []
  for source in ({"record": text}, {text: "record"}):
    with pytest.raises(TypeError):
      BirthRecord(date(2026, 1, 1), source=cast(Any, source))
  with pytest.raises(TypeError):
    IanaTimezone(MutableText("UTC"))
  with pytest.raises(TypeError):
    BirthRecord(date(2026, 1, 1), calendar=cast(Any, MutableText("gregorian")))


@pytest.mark.parametrize("latitude,longitude", [(90, 180), (-90, -180), (0, 0), (-12.5, 45.25)])
def test_location_retains_geographic_values(latitude: float, longitude: float) -> None:
  location = Location(latitude, longitude)
  assert location.latitude == latitude
  assert location.longitude == longitude
  assert type(location.latitude) is float
  assert type(location.longitude) is float


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 91, -91, 10**1000])
def test_invalid_latitude(value: float) -> None:
  with pytest.raises(ValueError, match="latitude"):
    Location(value, 0)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 181, -181])
def test_invalid_longitude(value: float) -> None:
  with pytest.raises(ValueError, match="longitude"):
    Location(0, value)


@pytest.mark.parametrize("value", [True, "1", None])
def test_coordinate_types_are_not_coerced(value: object) -> None:
  with pytest.raises(TypeError):
    Location(cast(Any, value), 0)
  with pytest.raises(TypeError):
    Location(0, cast(Any, value))


@pytest.mark.parametrize("offset", [timedelta(days=1), -timedelta(days=1), timedelta(days=2)])
def test_offset_range(offset: timedelta) -> None:
  with pytest.raises(ValueError, match="24"):
    FixedOffset(offset)


@pytest.mark.parametrize("offset", [True, 3600, "UTC", None])
def test_offset_type(offset: object) -> None:
  with pytest.raises(TypeError):
    FixedOffset(cast(Any, offset))


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(minutes=345), timedelta(seconds=-2670)])
def test_fixed_offsets_preserve_input_and_have_no_database_provenance(offset: timedelta) -> None:
  record = birth_at("2026-04-05T00:15:00", FixedOffset(offset))
  result = resolve_birth_time(record)
  expected = datetime(2026, 4, 5, 0, 15, tzinfo=timezone(offset)).astimezone(UTC)
  assert result.utc == expected
  assert result.utc_offset == offset
  assert result.record is record
  assert result.record.birth_date == date(2026, 4, 5)
  assert result.record.birth_time == time(0, 15)
  assert result.timezone_source == "fixed_offset"
  assert result.timezone_identity == timezone(offset).tzname(None)
  assert result.timezone_key is None
  assert result.fold is None
  assert result.tzdata_version is None
  assert result.iana_version is None


def test_fixed_quarter_hour_offset_changes_utc_date() -> None:
  result = resolve_birth_time(birth_at("2026-04-05T00:15:00", FixedOffset(timedelta(minutes=345))))
  assert result.utc == datetime(2026, 4, 4, 18, 30, tzinfo=UTC)


@pytest.mark.parametrize(
  "key,wall,earlier,later",
  [
    (
      "Australia/Lord_Howe",
      "2026-04-05T01:45:00",
      "2026-04-04T14:45:00+00:00",
      "2026-04-04T15:15:00+00:00",
    ),
    (
      "America/New_York",
      "2026-11-01T01:30:00",
      "2026-11-01T05:30:00+00:00",
      "2026-11-01T06:30:00+00:00",
    ),
  ],
)
def test_folds_require_choice_and_preserve_two_utc_instants(
  key: str, wall: str, earlier: str, later: str
) -> None:
  record = birth_at(wall, IanaTimezone(key))
  with pytest.raises(AmbiguousBirthTimeError):
    resolve_birth_time(record)
  first = resolve_birth_time(record, fold=0)
  second = resolve_birth_time(record, fold=1)
  assert first.utc == datetime.fromisoformat(earlier)
  assert second.utc == datetime.fromisoformat(later)
  assert first.utc < second.utc
  assert first.fold == 0
  assert second.fold == 1
  assert first.record is second.record is record
  assert first.timezone_key == key
  assert first.timezone_identity == key
  assert first.timezone_source == "tzdata"
  assert first.tzdata_version == metadata.version("tzdata")
  assert first.iana_version == import_module("tzdata").IANA_VERSION


@pytest.mark.parametrize(
  "key,wall",
  [
    ("Australia/Lord_Howe", "2026-10-04T02:15:00"),
    ("America/New_York", "2026-03-08T02:30:00"),
  ],
)
@pytest.mark.parametrize("fold", [None, 0, 1])
def test_gaps_are_never_resolved(key: str, wall: str, fold: int | None) -> None:
  with pytest.raises(NonexistentBirthTimeError):
    resolve_birth_time(birth_at(wall, IanaTimezone(key)), fold=cast(Any, fold))


@pytest.mark.parametrize(
  "wall,expected",
  [
    ("2026-04-05T12:00:00", "2026-04-05T01:30:00+00:00"),
    ("2026-04-05T00:15:00", "2026-04-04T13:15:00+00:00"),
  ],
)
def test_unique_iana_time_and_rollover(wall: str, expected: str) -> None:
  result = resolve_birth_time(birth_at(wall, IanaTimezone("Australia/Lord_Howe")))
  assert result.utc == datetime.fromisoformat(expected)
  assert result.fold is None


@pytest.mark.parametrize("zone", [IanaTimezone("Australia/Lord_Howe"), FixedOffset(timedelta(0))])
@pytest.mark.parametrize("fold", [0, 1])
def test_irrelevant_fold_is_rejected(zone: IanaTimezone | FixedOffset, fold: int) -> None:
  with pytest.raises(ValueError, match="not applicable"):
    resolve_birth_time(birth_at("2026-04-05T12:00:00", zone), fold=cast(Any, fold))


@pytest.mark.parametrize("fold", [-1, 2, 1.0, True, False, "0"])
def test_invalid_fold_type_or_value(fold: object) -> None:
  with pytest.raises((ValueError, TypeError)):
    resolve_birth_time(
      birth_at("2026-04-05T01:45:00", IanaTimezone("Australia/Lord_Howe")),
      fold=cast(Any, fold),
    )


@pytest.mark.parametrize("key", ["", "/UTC", "../UTC", "UTC/..", "UTC//UTC", "C:UTC", "Etc\\UTC"])
def test_iana_key_rejects_non_relative_or_unsafe_shapes(key: str) -> None:
  with pytest.raises(ValueError):
    IanaTimezone(key)


def test_timezone_key_type_and_unknown_identity() -> None:
  with pytest.raises(TypeError):
    IanaTimezone(cast(Any, 42))
  unknown = IanaTimezone("Not/A_Zone")
  with pytest.raises(ValueError, match="Unknown IANA"):
    resolve_birth_time(birth_at("2026-01-01T12:00:00", unknown))
  directory = IanaTimezone("America")
  with pytest.raises(ValueError, match="Unknown IANA"):
    resolve_birth_time(birth_at("2026-01-01T12:00:00", directory))


@pytest.mark.parametrize("key", ["UTC/Child", "x" * 5000])
def test_unknown_zone_path_errors_are_input_errors(key: str) -> None:
  with pytest.raises(ValueError, match="Unknown IANA"):
    resolve_birth_time(birth_at("2026-01-01T12:00:00", IanaTimezone(key)))


def test_iana_resolution_bypasses_default_zone_constructor(monkeypatch: pytest.MonkeyPatch) -> None:
  import zoneinfo

  original = zoneinfo.ZoneInfo

  class ExplicitOnly:
    from_file = staticmethod(original.from_file)

    def __init__(self, *args: object, **kwargs: object) -> None:
      raise AssertionError("The default ZoneInfo constructor must not supply pinned data")

  monkeypatch.setattr(zoneinfo, "ZoneInfo", ExplicitOnly)
  result = resolve_birth_time(birth_at("2026-04-05T12:00:00", IanaTimezone("Australia/Lord_Howe")))
  assert result.utc == datetime(2026, 4, 5, 1, 30, tzinfo=UTC)
  assert result.tzdata_version == metadata.version("tzdata")


@pytest.mark.parametrize(
  "wall,zone",
  [
    ("1972-01-01T00:00:00", FixedOffset(timedelta(hours=14))),
    ("1971-12-31T23:59:59.999999", FixedOffset(timedelta(0))),
    ("1972-01-01T00:30:00", IanaTimezone("Etc/GMT-1")),
    ("1950-04-30T01:30:00", IanaTimezone("America/Los_Angeles")),
  ],
)
def test_pre_modern_utc_is_not_resolved(wall: str, zone: IanaTimezone | FixedOffset) -> None:
  with pytest.raises(HistoricalTimeError):
    resolve_birth_time(birth_at(wall, zone))


@pytest.mark.parametrize(
  "wall,zone",
  [
    ("1972-01-01T00:00:00", FixedOffset(timedelta(0))),
    ("1971-12-31T23:00:00", FixedOffset(timedelta(hours=-1))),
    ("1971-12-31T16:00:00", IanaTimezone("America/Los_Angeles")),
  ],
)
def test_modern_boundary_is_inclusive_and_uses_utc(
  wall: str, zone: IanaTimezone | FixedOffset
) -> None:
  result = resolve_birth_time(birth_at(wall, zone))
  assert result.utc == datetime(1972, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize("zone", [FixedOffset(timedelta(hours=-1)), IanaTimezone("Etc/GMT+1")])
def test_unrepresentable_utc_fails_explicitly(zone: IanaTimezone | FixedOffset) -> None:
  record = BirthRecord(date.max, time.max, zone)
  with pytest.raises(ValueError, match="representable"):
    resolve_birth_time(record)


def test_time_resolution_does_not_require_location_but_natal_preparation_does() -> None:
  record = BirthRecord(date(2026, 1, 1), time(12), FixedOffset(timedelta(0)))
  assert resolve_birth_time(record).utc.hour == 12
  with pytest.raises(MissingBirthDataError):
    prepare_natal_input(record)
  known = replace(record, location=Location(90, 180))
  assert prepare_natal_input(known).record is known


@pytest.mark.parametrize("field", ["birth_time", "timezone", "location"])
def test_each_missing_complete_input_field_fails(field: str) -> None:
  record = birth_at("2026-04-05T12:00:00", FixedOffset(timedelta(0)))
  with pytest.raises(MissingBirthDataError):
    prepare_natal_input(replace(record, **cast(Any, {field: None})))


def test_missing_timezone_fails_time_resolution() -> None:
  with pytest.raises(MissingBirthDataError):
    resolve_birth_time(BirthRecord(date(2026, 1, 1), time(12)))


@pytest.mark.parametrize("function", [resolve_birth_time, prepare_natal_input])
def test_entry_points_require_birth_record(function: Any) -> None:
  with pytest.raises(TypeError):
    function("2026-01-01")


@pytest.mark.parametrize(
  "field,value",
  [
    ("birth_date", datetime(2026, 1, 1)),
    ("birth_date", "2026-01-01"),
    ("birth_time", "12:00"),
    ("birth_time", time(12, tzinfo=UTC)),
    ("birth_time", time(12, fold=1)),
    ("timezone", "UTC"),
    ("location", (0, 0)),
    ("precision", "minute"),
    ("calendar", "julian"),
    ("calendar", 42),
    ("source", []),
    ("source", {"key": []}),
    ("source", {42: "value"}),
    ("source", {"": "value"}),
  ],
)
def test_record_rejects_unsupported_shapes(field: str, value: object) -> None:
  with pytest.raises((TypeError, ValueError)):
    BirthRecord(**cast(Any, {"birth_date": date(2026, 1, 1), field: value}))


@pytest.mark.parametrize(
  "precision,clock",
  [
    (TimePrecision.HOUR, time(12)),
    (TimePrecision.MINUTE, time(12, 30)),
    (TimePrecision.SECOND, time(12, 30, 15)),
    (TimePrecision.MICROSECOND, time(12, 30, 15, 123)),
  ],
)
def test_stated_precision_is_retained(precision: TimePrecision, clock: time) -> None:
  record = BirthRecord(date(2026, 1, 1), clock, precision=precision)
  assert record.precision is precision
  assert record.birth_time == clock


@pytest.mark.parametrize(
  "precision,clock",
  [
    (TimePrecision.HOUR, time(12, 1)),
    (TimePrecision.MINUTE, time(12, 0, 1)),
    (TimePrecision.SECOND, time(12, 0, 0, 1)),
    (TimePrecision.MINUTE, None),
  ],
)
def test_precision_does_not_discard_smaller_fields(
  precision: TimePrecision, clock: time | None
) -> None:
  with pytest.raises(ValueError, match="precision"):
    BirthRecord(date(2026, 1, 1), clock, precision=precision)


@pytest.mark.parametrize(
  "field,value",
  [
    ("record", "record"),
    ("utc", "2026-01-01"),
    ("utc", datetime(2026, 4, 5, 12)),
    ("utc", datetime(2026, 4, 5, 12, tzinfo=UTC, fold=1)),
    ("utc", datetime(2026, 4, 5, 13, tzinfo=UTC)),
    ("utc_offset", timedelta(hours=1)),
    ("timezone_key", "UTC"),
    ("fold", 0),
    ("tzdata_version", "invented"),
    ("iana_version", "invented"),
  ],
)
def test_resolved_value_consistency(field: str, value: object) -> None:
  result = resolve_birth_time(birth_at("2026-04-05T12:00:00", FixedOffset(timedelta(0))))
  with pytest.raises((TypeError, ValueError)):
    replace(result, **cast(Any, {field: value}))


def test_resolved_iana_requires_matching_key_and_both_versions() -> None:
  result = resolve_birth_time(birth_at("2026-04-05T12:00:00", IanaTimezone("Australia/Lord_Howe")))
  for changes in ({"timezone_key": "UTC"}, {"tzdata_version": None}, {"iana_version": ""}):
    with pytest.raises(ValueError):
      replace(result, **cast(Any, changes))


def test_resolved_value_rejects_missing_clock_and_inconsistent_offset() -> None:
  result = resolve_birth_time(birth_at("2026-04-05T12:00:00", FixedOffset(timedelta(0))))
  with pytest.raises(MissingBirthDataError):
    replace(result, record=BirthRecord(date(2026, 4, 5)))
  with pytest.raises(ValueError, match="explicit input offset"):
    replace(result, utc=result.utc - timedelta(hours=1), utc_offset=timedelta(hours=1))
  with pytest.raises(ValueError, match="representable"):
    replace(result, utc=datetime.max.replace(tzinfo=UTC), utc_offset=timedelta(hours=1))


def test_missing_iana_version_is_not_fabricated(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(import_module("tzdata"), "IANA_VERSION", None)
  with pytest.raises(RuntimeError, match="package and IANA versions"):
    resolve_birth_time(birth_at("2026-04-05T12:00:00", IanaTimezone("Australia/Lord_Howe")))


def test_import_alone_does_not_load_timezone_data_or_astronomy() -> None:
  code = """
import importlib.resources
import sys
def forbidden(*args, **kwargs):
  raise RuntimeError('Resource lookup during package import')
importlib.resources.files = forbidden
import astrology
if 'tzdata' in sys.modules or 'zoneinfo' in sys.modules:
  raise RuntimeError('Timezone initialization during package import')
if any(name == 'celestial_calendar' or name.startswith('celestial_calendar.') for name in sys.modules):
  raise RuntimeError('Native astronomy initialization during package import')
"""
  subprocess.run([sys.executable, "-c", code], check=True)
