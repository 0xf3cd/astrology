"""Chart-record preservation, rejection and explicit replay. 命盘记录保真、拒绝与显式重算。"""

import json
import math
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, replace
from datetime import date, time, timedelta
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import pytest

from astrology import (
  BirthRecord,
  Body,
  ChartConfig,
  ChartDomainError,
  ChartRecordError,
  ChartReplayError,
  FixedOffset,
  HouseSystem,
  Location,
  NatalChart,
  OrbCombination,
  dumps_chart,
  loads_chart,
  natal_chart,
  prepare_natal_input,
  recompute_chart,
)


def test_complete_round_trip(recorded_chart: NatalChart) -> None:
  packed = dumps_chart(recorded_chart)
  restored = loads_chart(packed)
  assert restored == recorded_chart
  assert dumps_chart(restored) == packed
  assert restored.resolved.record.source == {"record": "synthetic", "note": "双语 source"}
  assert restored.resolved.fold == 1
  assert restored.requested.aspect_objects != restored.effective.aspect_objects
  assert restored.requested.aspects[0].object_orbs
  assert {hit.orb_limit_deg for hit in restored.aspects} == {6.0, 8.0}
  with pytest.raises(FrozenInstanceError):
    restored.resolved = recorded_chart.resolved  # type: ignore[misc]
  with pytest.raises(TypeError):
    restored.resolved.record.source["new"] = "value"  # type: ignore[index]


def test_historical_fixture_restores_and_independent_calculation_retains_numerics() -> None:
  text = (Path(__file__).parent / "reference/chart_record_v1.json").read_text(encoding="utf-8")
  stored = loads_chart(text)
  assert dumps_chart(stored) == text
  assert stored.provenance.astrology_version == "0.0.0"
  with pytest.raises(ChartReplayError, match="astrology version"):
    recompute_chart(stored)
  fresh = natal_chart(stored.resolved, stored.requested)
  assert fresh.resolved == stored.resolved
  assert fresh.requested == stored.requested
  assert fresh.effective == stored.effective
  assert fresh.provenance.astrology_version == version("celestial-astrology")
  assert replace(fresh.provenance, astrology_version="0.0.0") == stored.provenance
  assert fresh.times.jd_ut1 == pytest.approx(stored.times.jd_ut1, abs=1e-8, rel=0)
  assert fresh.times.jde_tt == pytest.approx(stored.times.jde_tt, abs=1e-8, rel=0)
  for actual, expected in zip(fresh.positions, stored.positions, strict=True):
    assert actual.identity is expected.identity
    assert actual.longitude_deg == pytest.approx(expected.longitude_deg, abs=1e-8, rel=0)
    assert actual.latitude_deg == pytest.approx(expected.latitude_deg, abs=1e-8, rel=0)
    assert actual.longitude_rate_deg_per_tt_day == pytest.approx(
      expected.longitude_rate_deg_per_tt_day, abs=1e-9, rel=0
    )
    if expected.distance_au is None:
      assert actual.distance_au is None
    else:
      assert actual.distance_au == pytest.approx(expected.distance_au, abs=1e-9, rel=0)
  for actual_cusp, expected_cusp in zip(
    fresh.houses.cusps_deg, stored.houses.cusps_deg, strict=True
  ):
    assert actual_cusp == pytest.approx(expected_cusp, abs=1e-8, rel=0)
  for field in ("ascendant_deg", "midheaven_deg", "descendant_deg", "imum_coeli_deg"):
    assert getattr(fresh.houses, field) == pytest.approx(
      getattr(stored.houses, field), abs=1e-8, rel=0
    )
  for actual_placement, expected_placement in zip(fresh.placements, stored.placements, strict=True):
    assert (actual_placement.identity, actual_placement.sign, actual_placement.house) == (
      expected_placement.identity,
      expected_placement.sign,
      expected_placement.house,
    )
    assert actual_placement.sign_degree_deg == pytest.approx(
      expected_placement.sign_degree_deg, abs=1e-8, rel=0
    )
  for actual_hit, expected_hit in zip(fresh.aspects, stored.aspects, strict=True):
    assert (
      actual_hit.first,
      actual_hit.second,
      actual_hit.aspect,
      actual_hit.branch_deg,
      actual_hit.motion,
      actual_hit.orb_limit_deg,
    ) == (
      expected_hit.first,
      expected_hit.second,
      expected_hit.aspect,
      expected_hit.branch_deg,
      expected_hit.motion,
      expected_hit.orb_limit_deg,
    )
    assert actual_hit.deviation_deg == pytest.approx(expected_hit.deviation_deg, abs=1e-8, rel=0)


@pytest.mark.parametrize("system", list(HouseSystem))
@pytest.mark.parametrize("combination", list(OrbCombination))
def test_replay_and_all_requested_policies(
  recorded_chart: NatalChart, system: HouseSystem, combination: OrbCombination
) -> None:
  config = replace(recorded_chart.requested, house_system=system, orb_combination=combination)
  chart = natal_chart(recorded_chart.resolved, config)
  restored = loads_chart(dumps_chart(chart))
  assert restored == chart
  assert recompute_chart(restored) == chart


@pytest.mark.parametrize("explicit", [False, True])
def test_requested_omission_stays_distinct(recorded_chart: NatalChart, explicit: bool) -> None:
  config = replace(
    recorded_chart.requested,
    aspect_objects=tuple(recorded_chart.requested.objects) if explicit else None,
  )
  chart = natal_chart(recorded_chart.resolved, config)
  restored = loads_chart(dumps_chart(chart))
  assert restored.requested.aspect_objects == config.aspect_objects
  assert restored.effective.aspect_objects == tuple(config.objects)


def test_fixed_offset_microseconds_signed_zero_and_clock_rollover() -> None:
  source = {"record": "synthetic"}
  record = BirthRecord(
    date(2020, 6, 2),
    time(0, 15, 1, 654321),
    FixedOffset(timedelta(hours=5, minutes=45, microseconds=123)),
    Location(-0.0, -0.0),
    source=source,
  )
  source.clear()
  chart = natal_chart(prepare_natal_input(record), ChartConfig(HouseSystem.EQUAL, (Body.SUN,), ()))
  restored = loads_chart(dumps_chart(chart))
  assert restored == chart
  assert restored.resolved.utc.date() == date(2020, 6, 1)
  assert restored.resolved.utc.microsecond == 654198
  assert restored.resolved.utc_offset.microseconds == 123
  assert restored.resolved.record.precision is None
  site = restored.resolved.record.location
  assert site is not None
  assert math.copysign(1, site.latitude) == -1
  assert math.copysign(1, site.longitude) == -1
  assert dumps_chart(restored) == dumps_chart(chart)


@pytest.mark.parametrize(
  "path,value",
  [
    (("schema_version",), True),
    (("schema_version",), 2),
    (("schema_version",), 1.0),
    (("input", "record", "date"), "20211107"),
    (("input", "record", "time"), "013000"),
    (("input", "record", "time"), None),
    (("input", "record", "calendar"), "julian"),
    (("input", "record", "precision"), "guess"),
    (("input", "record", "location"), None),
    (("input", "record", "location", "latitude"), True),
    (("input", "record", "source"), {"record": []}),
    (("input", "record", "timezone", "kind"), "system"),
    (("input", "resolved", "utc"), "2021-11-07T06:30:00Z"),
    (("input", "resolved", "utc_offset_microseconds"), 0),
    (("input", "resolved", "utc_offset_microseconds"), 10**1000),
    (("input", "resolved", "fold"), True),
    (("input", "resolved", "fold"), 2),
    (("input", "resolved", "timezone_key"), "Europe/London"),
    (("input", "resolved", "tzdata_version"), ""),
    (("requested", "zodiac"), "sidereal"),
    (("requested", "objects", 0), "earth"),
    (("requested", "aspects", 0, "orb_degrees"), -1),
    (("requested", "aspects", 0, "object_orbs", 0, "identity"), "mean_descending_node"),
    (("requested", "orb_combination"), None),
    (("effective", "aspect_objects"), []),
    (("effective", "house_system"), "equal"),
    (("effective", "evaluation"), "independent_positions"),
    (("effective", "orb_combination"), "either_within_own_orb"),
    (("provenance", "position_frame"), "j2000"),
    (("provenance", "ut1_derivation"), "utc_is_ut1"),
    (("provenance", "astrology_version"), ""),
    (("times", "jd_ut1"), True),
    (("times", "jde_tt"), "2450000"),
    (("positions", 0, "identity"), "moon"),
    (("positions", 0, "longitude_deg"), 360),
    (("positions", 0, "latitude_deg"), -91),
    (("positions", 0, "distance_au"), None),
    (("positions", 0, "distance_au"), 0),
    (("positions", 10, "distance_au"), 1),
    (("positions", 10, "latitude_deg"), 1),
    (("positions", 0, "longitude_rate_deg_per_tt_day"), None),
    (("houses", "system"), "whole_sign"),
    (("houses", "cusps_deg"), [0] * 12),
    (("houses", "ascendant_deg"), 360),
    (("placements", 0, "sign"), "virgo"),
    (("placements", 0, "sign_degree_deg"), 30),
    (("placements", 0, "house"), True),
    (("placements", 0, "house"), 13),
    (("aspects", 0, "motion"), "exact"),
    (("aspects", 0, "branch_deg"), 42),
    (("aspects", 0, "orb_limit_deg"), 7),
    (("aspects", 0, "deviation_deg"), -180),
    (("aspects",), []),
  ],
)
def test_malformed_or_inconsistent_fields_rejected(
  recorded_chart: NatalChart, path: tuple[str | int, ...], value: object
) -> None:
  record: Any = json.loads(dumps_chart(recorded_chart))
  parent = record
  for key in path[:-1]:
    parent = parent[key]
  parent[path[-1]] = value
  with pytest.raises(ChartRecordError):
    loads_chart(json.dumps(record))


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("missing", [False, True])
def test_fields_are_explicit(recorded_chart: NatalChart, nested: bool, missing: bool) -> None:
  record = json.loads(dumps_chart(recorded_chart))
  target = record["requested"]["aspects"][0] if nested else record
  if missing:
    target.pop(next(iter(target)))
  else:
    target["unused"] = None
  with pytest.raises(ChartRecordError):
    loads_chart(json.dumps(record))


def numeric_paths(
  value: object, path: tuple[str | int, ...] = ()
) -> Iterator[tuple[str | int, ...]]:
  if type(value) in (int, float):
    yield path
  elif isinstance(value, dict):
    for key, child in value.items():
      yield from numeric_paths(child, (*path, key))
  elif isinstance(value, list):
    for index, child in enumerate(value):
      yield from numeric_paths(child, (*path, index))


_RECORD_TEXT = (Path(__file__).parent / "reference/chart_record_v1.json").read_text(
  encoding="utf-8"
)


@pytest.mark.parametrize("path", tuple(numeric_paths(json.loads(_RECORD_TEXT))))
@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e400", "-1e400"])
def test_nonfinite_json_numbers_rejected(path: tuple[str | int, ...], token: str) -> None:
  record: Any = json.loads(_RECORD_TEXT)
  parent = record
  for key in path[:-1]:
    parent = parent[key]
  parent[path[-1]] = "__nonfinite_token__"
  packed = json.dumps(record).replace('"__nonfinite_token__"', token)
  with pytest.raises(ChartRecordError):
    loads_chart(packed)


@pytest.mark.parametrize("text", ["null", "[]", "{}", "[", "[[]]", "[" * 1500 + "]" * 1500])
def test_bad_json_or_shape(text: str) -> None:
  with pytest.raises(ChartRecordError):
    loads_chart(text)


def test_duplicate_keys_at_root_and_nested(recorded_chart: NatalChart) -> None:
  packed = dumps_chart(recorded_chart)
  for text in (
    packed.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'),
    packed.replace('"record": "synthetic"', '"record": "synthetic", "record": "synthetic"'),
  ):
    with pytest.raises(ChartRecordError, match="Duplicate"):
      loads_chart(text)


@pytest.mark.parametrize("field", ["astrology_version", "celestial_version", "delta_t_model"])
def test_unknown_executable_version_restores_but_cannot_replay(
  recorded_chart: NatalChart, field: str
) -> None:
  record = json.loads(dumps_chart(recorded_chart))
  record["effective" if field == "delta_t_model" else "provenance"][field] = "unavailable"
  restored = loads_chart(json.dumps(record))
  assert "unavailable" in dumps_chart(restored)
  with pytest.raises(ChartReplayError):
    recompute_chart(restored)


@pytest.mark.parametrize("package", ["celestial-astrology", "celestial-calendar"])
def test_missing_metadata_has_replay_contract_and_preserved_cause(
  recorded_chart: NatalChart, monkeypatch: pytest.MonkeyPatch, package: str
) -> None:
  import astrology._distribution as identity
  import astrology.serialization as serialization

  missing = PackageNotFoundError(package)
  original = version

  def lookup(name: str) -> str:
    if name == package:
      raise missing
    return original(name)

  monkeypatch.setattr(identity, "version", lookup)
  monkeypatch.setattr(serialization, "version", lookup)
  with pytest.raises(ChartReplayError, match="metadata") as error:
    recompute_chart(recorded_chart)
  assert error.value.__cause__ is missing
  assert loads_chart(dumps_chart(recorded_chart)) == recorded_chart


def test_calculation_requires_installed_metadata(
  recorded_chart: NatalChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  import astrology._distribution as identity

  def missing(name: str) -> str:
    raise PackageNotFoundError(name)

  monkeypatch.setattr(identity, "version", missing)
  with pytest.raises(PackageNotFoundError, match="celestial-astrology"):
    natal_chart(recorded_chart.resolved, recorded_chart.requested)


def test_native_version_mismatch_is_rejected(
  recorded_chart: NatalChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  celestial = import_module("astrology.celestial")

  monkeypatch.setattr(celestial, "celestial_version", lambda: "unavailable")
  with pytest.raises(ChartReplayError, match="native astronomy version"):
    recompute_chart(recorded_chart)


def test_restore_and_replay_do_not_reresolve_timezone(
  recorded_chart: NatalChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  import astrology.birth as birth

  def forbidden(*args: object) -> None:
    raise AssertionError("Timezone data must not be read")

  monkeypatch.setattr(birth, "_load_iana_zone", forbidden)
  resolved = replace(recorded_chart.resolved, tzdata_version="old", iana_version="old")
  chart = replace(recorded_chart, resolved=resolved)
  restored = loads_chart(dumps_chart(chart))
  assert restored.resolved.tzdata_version == "old"
  assert recompute_chart(restored).resolved == resolved


def test_restoration_is_not_native_validation(recorded_chart: NatalChart) -> None:
  polar_record = replace(recorded_chart.resolved.record, location=Location(90, 0))
  chart = replace(recorded_chart, resolved=replace(recorded_chart.resolved, record=polar_record))
  restored = loads_chart(dumps_chart(chart))
  assert restored == chart
  with pytest.raises(ChartDomainError):
    recompute_chart(restored)


def test_restore_and_render_block_native_imports(recorded_chart: NatalChart) -> None:
  program = """
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.startswith(("celestial", "astrology.celestial", "tzdata", "zoneinfo")):
      raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
import astrology
chart = astrology.loads_chart(sys.stdin.read())
assert astrology.dumps_chart(chart)
catalog = astrology.load_catalog()
assert "本命盘" in astrology.format_chart(chart, catalog, language="zh-CN")
assert not any(n.startswith(("celestial", "astrology.celestial", "tzdata", "zoneinfo")) for n in sys.modules)
"""
  result = subprocess.run(
    [sys.executable, "-c", program],
    input=dumps_chart(recorded_chart),
    text=True,
    capture_output=True,
  )
  assert result.returncode == 0, result.stdout + result.stderr


def test_public_input_types(recorded_chart: NatalChart) -> None:
  values: tuple[object, ...] = (None, {}, b"{}", 1, True)
  for value in values:
    with pytest.raises(TypeError):
      loads_chart(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
      dumps_chart(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
      recompute_chart(value)  # type: ignore[arg-type]
