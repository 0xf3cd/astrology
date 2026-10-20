"""The same result invariants apply to direct construction and restoration.

直接构造和恢复遵守同一套结果约束。
"""

from collections.abc import Iterator, Sequence
from dataclasses import replace
from typing import Any

import pytest

from astrology import HouseSystem, NatalChart, dumps_chart, loads_chart
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


class MutableStandIn:
  def __init__(self) -> None:
    self.payload: list[str] = []

  def __eq__(self, other: object) -> bool:
    return True


class ChangingList(list[object]):
  def __init__(self, original: Sequence[object], changed: Sequence[object]) -> None:
    super().__init__(original)
    self.changed = changed
    self.iterations = 0

  def __iter__(self) -> Iterator[object]:
    self.iterations += 1
    return super().__iter__() if self.iterations == 1 else iter(self.changed)


@pytest.mark.parametrize("field", ["positions", "placements", "aspects"])
def test_result_sequences_validate_the_single_stored_snapshot(
  recorded_chart: NatalChart, field: str
) -> None:
  original = getattr(recorded_chart, field)
  stand_ins = [MutableStandIn() for _ in original]
  sequence = ChangingList(original, stand_ins)
  result = replace(recorded_chart, **{field: sequence})  # type: ignore[arg-type]
  assert sequence.iterations == 1
  assert all(type(member) is type(original[0]) for member in getattr(result, field))
  stand_ins[0].payload.append("outside mutation")
  assert result == recorded_chart
  with pytest.raises(TypeError):
    replace(recorded_chart, **{field: ChangingList(stand_ins, original)})  # type: ignore[arg-type]


def test_chart_hashing_preserves_equality_and_distinct_birth_metadata(
  recorded_chart: NatalChart,
) -> None:
  restored = loads_chart(dumps_chart(recorded_chart))
  assert hash(restored) == hash(recorded_chart)
  other_record = replace(
    recorded_chart.resolved.record, source={"record": "another synthetic source"}
  )
  other = replace(recorded_chart, resolved=replace(recorded_chart.resolved, record=other_record))
  assert other != recorded_chart
  assert len({recorded_chart, restored, other}) == 2
  assert {recorded_chart: "original", other: "other"}[other] == "other"


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
