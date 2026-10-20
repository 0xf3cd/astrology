"""The same result invariants apply to direct construction and restoration.

直接构造和恢复遵守同一套结果约束。
"""

from dataclasses import replace
from typing import Any

import pytest

from astrology import HouseSystem, NatalChart
from tools import check, installed_check


@pytest.mark.parametrize(
  "member,field,value",
  [
    ("times", "jd_ut1", float("nan")),
    ("times", "jde_tt", True),
    ("positions", "identity", "sun"),
    ("positions", "longitude_deg", 10**1000),
    ("positions", "longitude_rate_deg_per_tt_day", float("inf")),
    ("houses", "system", "equal"),
    ("houses", "cusps_deg", [0] * 12),
    ("placements", "sign", "aries"),
    ("placements", "house", True),
    ("effective", "delta_t_model", {}),
    ("effective", "aspect_objects", ["sun"]),
    ("effective", "aspect_objects", None),
    ("effective", "evaluation", "unknown"),
    ("provenance", "celestial_version", 1),
    ("provenance", "position_frame", {}),
    ("aspects", "first", "sun"),
    ("aspects", "second", "moon"),
    ("aspects", "motion", "applying"),
    ("aspects", "deviation_deg", 181),
    ("aspects", "orb_limit_deg", -1),
  ],
)
def test_leaf_result_validation(
  recorded_chart: NatalChart, member: str, field: str, value: object
) -> None:
  instance: Any = getattr(recorded_chart, member)
  if isinstance(instance, tuple):
    instance = instance[0]
  with pytest.raises((TypeError, ValueError)):
    replace(instance, **{field: value})


@pytest.mark.parametrize(
  "field,value",
  [
    ("resolved", None),
    ("requested", {}),
    ("effective", []),
    ("provenance", None),
    ("times", None),
    ("houses", None),
    ("positions", [{}]),
    ("placements", []),
    ("aspects", None),
  ],
)
def test_composition_validation(recorded_chart: NatalChart, field: str, value: object) -> None:
  with pytest.raises((TypeError, ValueError)):
    replace(recorded_chart, **{field: value})  # type: ignore[arg-type]


def test_cross_domain_consistency(recorded_chart: NatalChart) -> None:
  with pytest.raises(ValueError, match="house systems"):
    replace(
      recorded_chart, effective=replace(recorded_chart.effective, house_system=HouseSystem.EQUAL)
    )
  with pytest.raises(ValueError, match="Position identities"):
    replace(recorded_chart, positions=tuple(reversed(recorded_chart.positions)))
  with pytest.raises(ValueError, match="participants"):
    replace(recorded_chart, effective=replace(recorded_chart.effective, aspect_objects=()))


def test_result_sequences_are_isolated(recorded_chart: NatalChart) -> None:
  positions = list(recorded_chart.positions)
  placements = list(recorded_chart.placements)
  aspects = list(recorded_chart.aspects)
  restored = replace(recorded_chart, positions=positions, placements=placements, aspects=aspects)  # type: ignore[arg-type]
  positions.clear()
  placements.clear()
  aspects.clear()
  assert restored == recorded_chart


@pytest.mark.parametrize(
  "modules",
  [
    installed_check.MODULES[:-1],
    (*installed_check.MODULES, "invented"),
    (*installed_check.MODULES, installed_check.MODULES[0]),
  ],
)
def test_consumer_module_guard_rejects_missing_extra_and_duplicate(
  monkeypatch: pytest.MonkeyPatch, modules: tuple[str, ...]
) -> None:
  monkeypatch.setattr(installed_check, "MODULES", modules)
  with pytest.raises(ValueError, match="module coverage"):
    check.check_package_files()
