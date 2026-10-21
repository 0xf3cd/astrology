"""Complete charts against independent Swiss states and separate arithmetic.

用独立 Swiss 状态与另写的算术核对完整命盘。
"""

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest

from astrology import (
  AspectRule,
  BirthRecord,
  Body,
  ChartConfig,
  FixedOffset,
  HouseSystem,
  IanaTimezone,
  Location,
  LunarNode,
  MajorAspect,
  ObjectOrb,
  OrbCombination,
  natal_chart,
  prepare_natal_input,
)

_REFERENCE: dict[str, Any] = json.loads(
  (Path(__file__).parent / "reference/complete_chart_reference.json").read_text(encoding="utf-8")
)


def difference_arcsec(first: float, second: float) -> float:
  return abs((first - second + 180.0) % 360.0 - 180.0) * 3600.0


def reference_house_candidates(
  longitude: float, cusps: list[float], expected_house: int, tolerance_arcsec: float
) -> set[int]:
  adjoining: set[int] = set()
  for index, cusp in enumerate(cusps):
    if difference_arcsec(longitude, cusp) <= tolerance_arcsec:
      adjoining.update((index + 1, (index - 1) % 12 + 1))
  return adjoining or {expected_house}


@pytest.mark.parametrize("case", _REFERENCE["cases"], ids=lambda case: case["identifier"])
@pytest.mark.parametrize("system", list(HouseSystem))
def test_complete_independent_chart(case: dict[str, Any], system: HouseSystem) -> None:
  year, month, day, hour, minute, second = case["utc"]
  site = Location(case["latitude"], case["longitude"])
  if case["identifier"].startswith("fold-"):
    record = BirthRecord(date(2021, 11, 7), time(1, 30), IanaTimezone("America/New_York"), site)
    resolved = prepare_natal_input(record, fold=1 if case["identifier"].endswith("second") else 0)
  else:
    record = BirthRecord(
      date(year, month, day), time(hour, minute, second), FixedOffset(timedelta()), site
    )
    resolved = prepare_natal_input(record)
  assert resolved.utc == datetime(year, month, day, hour, minute, second, tzinfo=UTC)
  config = ChartConfig(
    system,
    (*Body, LunarNode.MEAN_ASCENDING),
    tuple(AspectRule(aspect, 6, (ObjectOrb(Body.SUN, 10),)) for aspect in MajorAspect),
    aspect_objects=tuple(reversed(tuple(Body))),
    orb_combination=OrbCombination.MEAN_OF_ORBS,
  )
  chart = natal_chart(resolved, config)
  tolerances = _REFERENCE["tolerances"]
  assert abs(chart.times.jde_tt - case["jde_tt"]) * 86400 < tolerances["tt_seconds"]
  assert abs(chart.times.jd_ut1 - case["jd_ut1"]) * 86400 < tolerances["ut1_seconds"]
  for actual, expected in zip(chart.positions, case["positions"], strict=True):
    assert actual.identity.value == expected["identity"]
    assert expected["flags"] == _REFERENCE["source"]["calc_flags"] == 260
    limits = tolerances["positions"][actual.identity.value]
    assert (
      difference_arcsec(actual.longitude_deg, expected["longitude_deg"])
      < limits["longitude_arcsec"]
    )
    assert (
      abs(actual.longitude_rate_deg_per_tt_day - expected["longitude_rate_deg_per_tt_day"])
      < limits["rate_deg_per_tt_day"]
    )
    if isinstance(actual.identity, LunarNode):
      assert actual.distance_au is None
      assert expected["distance_au"] > 0
      assert actual.latitude_deg == expected["latitude_deg"] == 0.0
    else:
      assert abs(actual.latitude_deg - expected["latitude_deg"]) * 3600 < limits["latitude_arcsec"]
      assert actual.distance_au is not None
      assert abs(actual.distance_au - expected["distance_au"]) < limits["distance_au"]
  geometry = next(house for house in case["houses"] if house["system"] == system.value)
  assert (
    difference_arcsec(chart.houses.ascendant_deg, geometry["ascendant_deg"])
    < tolerances["axes_cusps_arcsec"]
  )
  assert (
    difference_arcsec(chart.houses.midheaven_deg, geometry["midheaven_deg"])
    < tolerances["axes_cusps_arcsec"]
  )
  assert (
    difference_arcsec(chart.houses.descendant_deg, (geometry["ascendant_deg"] + 180) % 360)
    < tolerances["axes_cusps_arcsec"]
  )
  assert (
    difference_arcsec(chart.houses.imum_coeli_deg, (geometry["midheaven_deg"] + 180) % 360)
    < tolerances["axes_cusps_arcsec"]
  )
  for cusp, expected_cusp in zip(chart.houses.cusps_deg, geometry["cusps_deg"], strict=True):
    assert difference_arcsec(cusp, expected_cusp) < tolerances["axes_cusps_arcsec"]
  for placement, expected, raw in zip(
    chart.placements, geometry["placements"], case["positions"], strict=True
  ):
    assert (placement.identity.value, placement.sign.value) == (
      expected["identity"],
      expected["sign"],
    )
    longitude_tolerance = tolerances["positions"][placement.identity.value]["longitude_arcsec"]
    assert (
      min(expected["sign_degree_deg"], 30.0 - expected["sign_degree_deg"]) * 3600
      > longitude_tolerance
    )
    candidates = reference_house_candidates(
      raw["longitude_deg"],
      geometry["cusps_deg"],
      expected["house"],
      longitude_tolerance + tolerances["axes_cusps_arcsec"],
    )
    assert expected["house"] in candidates
    assert placement.house in candidates
    assert (
      abs(placement.sign_degree_deg - expected["sign_degree_deg"]) * 3600
      < tolerances["positions"][placement.identity.value]["longitude_arcsec"]
    )
  actual_hits = {
    (hit.first.value, hit.second.value, hit.aspect.value, hit.branch_deg): hit
    for hit in chart.aspects
  }
  expected_hits = {
    (hit["first"], hit["second"], hit["aspect"], hit["branch_deg"]): hit for hit in case["aspects"]
  }
  assert actual_hits.keys() == expected_hits.keys()
  for key, hit in actual_hits.items():
    expected = expected_hits[key]
    tolerance = (
      sum(tolerances["positions"][identity]["longitude_arcsec"] for identity in key[:2]) / 3600
    )
    assert abs(hit.deviation_deg - expected["deviation_deg"]) < tolerance
    assert hit.orb_limit_deg == expected["orb_limit_deg"]
    assert hit.motion.value == expected["motion"]
    assert abs(expected["deviation_deg"]) > tolerance
    assert abs(abs(expected["deviation_deg"]) - expected["orb_limit_deg"]) > tolerance


def test_reference_definitions_and_coverage() -> None:
  assert {hit["aspect"] for case in _REFERENCE["cases"] for hit in case["aspects"]} == {
    aspect.value for aspect in MajorAspect
  }
  assert _REFERENCE["source"]["data_files"] == []
  assert _REFERENCE["source"]["backend"] == "Moshier, explicitly requested"
  assert len(_REFERENCE["calibration"]["inputs"]) == 14


def test_reference_house_ambiguity_is_explicit_and_limited() -> None:
  uncertain = []
  for case in _REFERENCE["cases"]:
    for geometry in case["houses"]:
      for position, placement in zip(case["positions"], geometry["placements"], strict=True):
        limits = _REFERENCE["tolerances"]
        candidates = reference_house_candidates(
          position["longitude_deg"],
          geometry["cusps_deg"],
          placement["house"],
          limits["positions"][position["identity"]]["longitude_arcsec"]
          + limits["axes_cusps_arcsec"],
        )
        if len(candidates) > 1:
          uncertain.append(
            (case["identifier"], geometry["system"], position["identity"], sorted(candidates))
          )
  assert uncertain == [("fold-2021-first", "equal", "mean_ascending_node", [9, 10])]
