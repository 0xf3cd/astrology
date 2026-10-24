"""Project-calculated numerical regression cases. 项目计算的数值回归案例。"""

import json
from dataclasses import replace
from datetime import date, time, timedelta
from hashlib import sha256
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
  NatalChart,
  ObjectOrb,
  OrbCombination,
  TimePrecision,
  natal_chart,
  prepare_natal_input,
)

_REFERENCE = json.loads(
  (Path(__file__).parent / "reference/chart_regression.json").read_text(encoding="utf-8")
)
_CASES = _REFERENCE["cases"]


def test_reference_values_and_extraction_provenance_are_unchanged() -> None:
  canonical = json.dumps(_REFERENCE, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
  assert sha256(canonical.encode("utf-8")).hexdigest() == (
    "da230aa43bc8b32be363a0d2130d866c5997cd11893f73c1cba212a612604fbc"
  )


@pytest.fixture(params=["lord-howe-2026", "j2000-two-bodies"])
def regression_chart(request: pytest.FixtureRequest) -> NatalChart:
  if request.param == "lord-howe-2026":
    record = BirthRecord(
      date(2026, 4, 5),
      time(1, 45),
      IanaTimezone("Australia/Lord_Howe"),
      Location(0, 0),
      TimePrecision.MINUTE,
      {"record": "synthetic"},
    )
    config = ChartConfig(
      HouseSystem.WHOLE_SIGN,
      (*Body, LunarNode.MEAN_ASCENDING),
      tuple(AspectRule(a, 6, (ObjectOrb(Body.SUN, 10),)) for a in MajorAspect),
      aspect_objects=tuple(reversed(tuple(Body))),
      orb_combination=OrbCombination.MEAN_OF_ORBS,
    )
    return natal_chart(prepare_natal_input(record, fold=0), config)
  record = BirthRecord(
    date(2000, 1, 1),
    time(12, 0),
    FixedOffset(timedelta(0)),
    Location(0, 0),
    TimePrecision.MINUTE,
    {"example": "synthetic"},
  )
  return natal_chart(
    prepare_natal_input(record),
    ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ()),
  )


def assert_regression(chart: NatalChart, expected: dict[str, Any]) -> None:
  """Compare numeric fields and conventions, independently of package-version labels.

  比较数值字段和计算约定，不以包版本标签决定是否比较。
  """
  conventions = expected["conventions"]
  assert chart.effective.delta_t_model == conventions["delta_t_model"]
  assert chart.effective.evaluation == conventions["evaluation"]
  assert chart.effective.house_system.value == conventions["house_system"]
  assert [p.value for p in chart.effective.aspect_objects] == conventions["aspect_objects"]
  combination = chart.effective.orb_combination
  assert (None if combination is None else combination.value) == conventions["orb_combination"]
  for field in ("position_frame", "ut1_derivation"):
    assert getattr(chart.provenance, field) == expected["origin"]["provenance"][field]
  for field in ("jd_ut1", "jde_tt"):
    assert getattr(chart.times, field) == pytest.approx(expected["times"][field], abs=1e-8, rel=0)
  for actual, reference in zip(chart.positions, expected["positions"], strict=True):
    assert actual.identity.value == reference["identity"]
    for field, tolerance in (
      ("longitude_deg", 1e-8),
      ("latitude_deg", 1e-8),
      ("distance_au", 1e-9),
      ("longitude_rate_deg_per_tt_day", 1e-9),
    ):
      value = reference[field]
      if value is None:
        assert getattr(actual, field) is None
      else:
        assert getattr(actual, field) == pytest.approx(value, abs=tolerance, rel=0)
  assert chart.houses.system.value == expected["houses"]["system"]
  for actual_cusp, reference_cusp in zip(
    chart.houses.cusps_deg, expected["houses"]["cusps_deg"], strict=True
  ):
    assert actual_cusp == pytest.approx(reference_cusp, abs=1e-8, rel=0)
  for field in ("ascendant_deg", "midheaven_deg", "descendant_deg", "imum_coeli_deg"):
    assert getattr(chart.houses, field) == pytest.approx(expected["houses"][field], abs=1e-8, rel=0)
  for placement, reference in zip(chart.placements, expected["placements"], strict=True):
    assert (placement.identity.value, placement.sign.value, placement.house) == (
      reference["identity"],
      reference["sign"],
      reference["house"],
    )
    assert placement.sign_degree_deg == pytest.approx(reference["sign_degree_deg"], abs=1e-8, rel=0)
  for hit, reference in zip(chart.aspects, expected["aspects"], strict=True):
    assert (
      hit.first.value,
      hit.second.value,
      hit.aspect.value,
      hit.branch_deg,
      hit.motion.value,
      hit.orb_limit_deg,
    ) == (
      reference["first"],
      reference["second"],
      reference["aspect"],
      reference["branch_deg"],
      reference["motion"],
      reference["orb_limit_deg"],
    )
    assert hit.deviation_deg == pytest.approx(reference["deviation_deg"], abs=1e-8, rel=0)


def test_project_numerical_regression(regression_chart: NatalChart) -> None:
  index = 0 if len(regression_chart.positions) == 11 else 1
  assert_regression(regression_chart, _CASES[index])


@pytest.mark.parametrize("field", ["astrology_version", "celestial_version"])
def test_numerical_regression_ignores_version_only_changes(
  regression_chart: NatalChart, field: str
) -> None:
  provenance = (
    replace(regression_chart.provenance, astrology_version="another-version")
    if field == "astrology_version"
    else replace(regression_chart.provenance, celestial_version="another-version")
  )
  changed = replace(regression_chart, provenance=provenance)
  index = 0 if len(changed.positions) == 11 else 1
  assert_regression(changed, _CASES[index])


def test_numerical_regression_rejects_valid_raw_drift(regression_chart: NatalChart) -> None:
  position = replace(
    regression_chart.positions[0], latitude_deg=regression_chart.positions[0].latitude_deg + 1e-6
  )
  changed = replace(regression_chart, positions=(position, *regression_chart.positions[1:]))
  index = 0 if len(changed.positions) == 11 else 1
  with pytest.raises(AssertionError):
    assert_regression(changed, _CASES[index])
