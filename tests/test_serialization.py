"""Chart-record preservation, rejection and explicit replay. 命盘记录保真、拒绝与显式重算。"""

import json
import math
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, replace
from datetime import date, time, timedelta
from hashlib import sha256
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import pytest

from astrology import (
  AspectRule,
  BirthRecord,
  Body,
  ChartConfig,
  ChartDomainError,
  ChartRecordError,
  ChartReplayError,
  FixedOffset,
  HouseSystem,
  Location,
  MajorAspect,
  NatalChart,
  OrbCombination,
  dumps_chart,
  loads_chart,
  natal_chart,
  prepare_natal_input,
  recompute_chart,
)

_REFERENCE = Path(__file__).parent / "reference"
_RECORD_TEXT = (_REFERENCE / "chart_record_v1.json").read_text(encoding="utf-8")
_RELEASE_TEXT = (_REFERENCE / "chart_record_v1_v010.json").read_text(encoding="utf-8")


@pytest.fixture(params=[_RECORD_TEXT, _RELEASE_TEXT], ids=["development-000", "release-010"])
def historical_text(request: pytest.FixtureRequest) -> str:
  return str(request.param)


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


def test_historical_fixtures_keep_original_bytes() -> None:
  assert sha256((_REFERENCE / "chart_record_v1.json").read_bytes()).hexdigest() == (
    "ceb3cdf9c42266919a5c6f0aec17ac5a2e3564935bb5645b3aeb7a815b887f5a"
  )
  source = json.loads((_REFERENCE / "chart_record_v1_v010.source.json").read_text())
  assert sha256((_REFERENCE / source["record"]).read_bytes()).hexdigest() == source["sha256"]


def test_historical_record_preservation(historical_text: str) -> None:
  stored = loads_chart(historical_text)
  assert dumps_chart(stored) == historical_text
  original = json.loads(historical_text)
  assert stored.provenance.astrology_version == original["provenance"]["astrology_version"]
  assert stored.provenance.celestial_version == original["provenance"]["celestial_version"]


def test_historical_replay_eligibility(historical_text: str) -> None:
  from astrology.celestial import celestial_version, delta_t_model_id

  stored = loads_chart(historical_text)
  eligible = (
    stored.provenance.astrology_version == version("celestial-astrology")
    and stored.provenance.celestial_version == version("celestial-calendar") == celestial_version()
    and stored.effective.delta_t_model == delta_t_model_id()
  )
  if eligible:
    replayed = recompute_chart(stored)
    assert replayed.resolved == stored.resolved
    assert replayed.requested == stored.requested
    assert replayed.provenance == stored.provenance
  else:
    with pytest.raises(ChartReplayError, match=r"version|model"):
      recompute_chart(stored)
  assert dumps_chart(stored) == historical_text


def test_fresh_calculation_records_current_provenance(historical_text: str) -> None:
  stored = loads_chart(historical_text)
  fresh = natal_chart(stored.resolved, stored.requested)
  assert fresh.resolved == stored.resolved
  assert fresh.requested == stored.requested
  assert fresh.provenance.astrology_version == version("celestial-astrology")
  assert fresh.provenance.celestial_version == version("celestial-calendar")
  assert fresh.effective.delta_t_model == "algo5"
  assert fresh.effective.evaluation == "fixed_fourteen_object_joint_snapshot"
  assert fresh.provenance.position_frame == "apparent_geocentric_true_ecliptic_of_date"
  assert fresh.provenance.ut1_derivation == "delta_t_model_from_civil_utc"
  assert dumps_chart(stored) == historical_text


def test_historical_numerical_regression(historical_text: str) -> None:
  stored = loads_chart(historical_text)
  fresh = natal_chart(stored.resolved, stored.requested)
  assert fresh.resolved == stored.resolved
  assert fresh.requested == stored.requested
  assert fresh.effective == stored.effective
  assert fresh.provenance.position_frame == stored.provenance.position_frame
  assert fresh.provenance.ut1_derivation == stored.provenance.ut1_derivation
  assert fresh.houses.system is stored.houses.system
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
    (("requested", "center"), "heliocentric"),
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


@pytest.mark.parametrize(
  "path,shape",
  [
    (path, shape)
    for path in (
      ("requested", "objects"),
      ("requested", "aspect_objects"),
      ("requested", "aspects"),
      ("requested", "aspects", 0, "object_orbs"),
      ("effective", "aspect_objects"),
      ("positions",),
      ("placements",),
      ("houses", "cusps_deg"),
      ("aspects",),
    )
    for shape in ("object", "string", "empty_string", "null")
    if not (path == ("requested", "aspect_objects") and shape == "null")
  ],
)
def test_record_array_shapes(path: tuple[str | int, ...], shape: str) -> None:
  record: Any = json.loads(_RECORD_TEXT)
  parent = record
  for key in path[:-1]:
    parent = parent[key]
  values = parent[path[-1]]
  assert isinstance(values, list) and values
  if shape == "object":
    parent[path[-1]] = dict.fromkeys(values) if all(isinstance(v, str) for v in values) else {}
  elif shape == "null":
    parent[path[-1]] = None
  else:
    parent[path[-1]] = "sun" if shape == "string" else ""
  with pytest.raises(ChartRecordError, match="Expected a JSON array"):
    loads_chart(json.dumps(record))


@pytest.mark.parametrize(
  "path",
  [
    ("requested", "aspects"),
    ("effective", "aspect_objects"),
    ("aspects",),
    ("requested", "aspects", 0, "object_orbs"),
  ],
)
@pytest.mark.parametrize("value", [{}, "", "sun", None])
def test_empty_record_arrays_reject_other_shapes(
  path: tuple[str | int, ...], value: object
) -> None:
  chart = loads_chart(_RELEASE_TEXT)
  if path[-1] == "object_orbs":
    chart = natal_chart(
      chart.resolved,
      replace(chart.requested, aspects=(AspectRule(MajorAspect.CONJUNCTION, 0),)),
    )
  record: Any = json.loads(dumps_chart(chart))
  parent = record
  for key in path[:-1]:
    parent = parent[key]
  assert parent[path[-1]] == []
  parent[path[-1]] = value
  with pytest.raises(ChartRecordError, match="Expected a JSON array"):
    loads_chart(json.dumps(record))


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
  assert natal_chart(restored.resolved, restored.requested).resolved == resolved


def test_restoration_is_not_native_validation(recorded_chart: NatalChart) -> None:
  polar_record = replace(recorded_chart.resolved.record, location=Location(90, 0))
  chart = replace(recorded_chart, resolved=replace(recorded_chart.resolved, record=polar_record))
  restored = loads_chart(dumps_chart(chart))
  assert restored == chart
  with pytest.raises(ChartDomainError):
    recompute_chart(restored)


@pytest.mark.parametrize("optimized", [False, True])
def test_historical_restore_and_render_block_native_imports(
  historical_text: str, optimized: bool
) -> None:
  program = """
import importlib.abc, json, sys
class Block(importlib.abc.MetaPathFinder):
  def find_spec(self, fullname, path=None, target=None):
    if fullname.startswith(("celestial", "astrology.celestial", "tzdata", "zoneinfo")):
      raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
import astrology
chart = astrology.loads_chart(sys.stdin.read())
catalog = astrology.load_catalog()
tables = {language: astrology.format_chart(chart, catalog, language=language)
          for language in ("en", "zh-CN")}
if any(n.startswith(("celestial", "astrology.celestial", "tzdata", "zoneinfo")) for n in sys.modules):
  raise RuntimeError("Restoration or display imported astronomy/timezone data")
print(json.dumps({"record": astrology.dumps_chart(chart), "tables": tables}))
"""
  result = subprocess.run(
    [sys.executable, *(["-O"] if optimized else []), "-c", program],
    input=historical_text,
    text=True,
    capture_output=True,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  output = json.loads(result.stdout)
  assert output["record"] == historical_text
  original = json.loads(historical_text)
  package_version = original["provenance"]["astrology_version"]
  for language, table in output["tables"].items():
    assert original["input"]["resolved"]["utc"] in table
    assert f"{package_version} / {original['provenance']['celestial_version']}" in table
    assert original["provenance"]["position_frame"] in table
    assert original["provenance"]["ut1_derivation"] in table
    assert original["effective"]["delta_t_model"] in table
    for position in original["positions"]:
      assert f"[{position['identity']}]" in table
    if package_version == "0.0.0":
      row = (
        "Sun [sun] | Aries 14°50'21\" | 9 | D"
        if language == "en"
        else ("太阳 [sun] | 白羊座 14°50'21\" | 9 | D")
      )
    else:
      row = (
        "Sun [sun] | Capricorn 10°22'08\" | 10 | D"
        if language == "en"
        else ("太阳 [sun] | 摩羯座 10°22'08\" | 10 | D")
      )
    assert row in table.splitlines()


def test_public_input_types(recorded_chart: NatalChart) -> None:
  values: tuple[object, ...] = (None, {}, b"{}", 1, True)
  for value in values:
    with pytest.raises(TypeError):
      loads_chart(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
      dumps_chart(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
      recompute_chart(value)  # type: ignore[arg-type]
