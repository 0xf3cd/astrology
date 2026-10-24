"""Direct result construction enforces domain invariants. 直接构造结果时检查领域约束。"""

from collections.abc import Iterator, Sequence
from dataclasses import replace
from typing import Any

import pytest

from astrology import (
  AspectHit,
  AspectMotion,
  Body,
  HouseSystem,
  LunarNode,
  MajorAspect,
  MissingBirthDataError,
  NatalChart,
  OrbCombination,
)


@pytest.mark.parametrize(
  "first,second,deviation,limit,motion",
  [
    (Body.SUN, Body.SUN, 1.0, 1.0, AspectMotion.APPLYING),
    (LunarNode.MEAN_ASCENDING, LunarNode.MEAN_DESCENDING, 1.0, 1.0, AspectMotion.APPLYING),
    (Body.SUN, Body.MOON, 0.0, 1.0, AspectMotion.SEPARATING),
    (Body.SUN, Body.MOON, 1.0, 1.0, AspectMotion.EXACT),
    (Body.SUN, Body.MOON, 2.0, 1.0, AspectMotion.APPLYING),
  ],
)
def test_direct_aspect_hit_rejects_invalid_invariants(
  first: Body | LunarNode,
  second: Body | LunarNode,
  deviation: float,
  limit: float,
  motion: AspectMotion,
) -> None:
  with pytest.raises(ValueError):
    AspectHit(first, second, MajorAspect.CONJUNCTION, 0.0, deviation, limit, motion)


def test_direct_aspect_hit_accepts_exact_and_inclusive_limit() -> None:
  exact = AspectHit(Body.SUN, Body.MOON, MajorAspect.CONJUNCTION, 0.0, 0.0, 1.0, AspectMotion.EXACT)
  edge = AspectHit(
    Body.SUN, Body.MOON, MajorAspect.CONJUNCTION, 0.0, 1.0, 1.0, AspectMotion.APPLYING
  )
  assert exact.motion is AspectMotion.EXACT
  assert edge.deviation_deg == edge.orb_limit_deg == 1.0


@pytest.mark.parametrize(
  "member,field,value",
  [
    ("times", "jd_ut1", float("nan")),
    ("times", "jde_tt", True),
    ("positions", "identity", "sun"),
    ("positions", "longitude_deg", 10**1000),
    ("positions", "longitude_deg", 360),
    ("positions", "latitude_deg", -91),
    ("positions", "distance_au", None),
    ("positions", "distance_au", 0),
    ("positions", "longitude_rate_deg_per_tt_day", float("inf")),
    ("houses", "system", "equal"),
    ("houses", "cusps_deg", [0] * 12),
    ("houses", "ascendant_deg", 360),
    ("placements", "sign", "aries"),
    ("placements", "house", True),
    ("placements", "house", 13),
    ("placements", "sign_degree_deg", 30),
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
  with pytest.raises(ValueError, match="Effective orb combination differs from the request"):
    replace(
      recorded_chart,
      effective=replace(
        recorded_chart.effective, orb_combination=OrbCombination.EITHER_WITHIN_OWN_ORB
      ),
    )


def test_complete_result_requires_a_birth_location(recorded_chart: NatalChart) -> None:
  resolved = replace(
    recorded_chart.resolved, record=replace(recorded_chart.resolved.record, location=None)
  )
  with pytest.raises(MissingBirthDataError, match="A complete chart requires a birth location"):
    replace(recorded_chart, resolved=resolved)


@pytest.mark.parametrize("field,value", [("latitude_deg", 1), ("distance_au", 1)])
def test_node_results_keep_their_definition(
  recorded_chart: NatalChart, field: str, value: float
) -> None:
  node = next(p for p in recorded_chart.positions if isinstance(p.identity, LunarNode))
  with pytest.raises(ValueError, match="Lunar nodes"):
    replace(node, **{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize(
  "member,field",
  [
    ("effective", "delta_t_model"),
    ("provenance", "astrology_version"),
    ("provenance", "celestial_version"),
  ],
)
@pytest.mark.parametrize("value", ["", " \t\n\u00a0", None, 1])
def test_model_and_version_labels_require_content(
  recorded_chart: NatalChart, member: str, field: str, value: object
) -> None:
  with pytest.raises(ValueError, match="non-whitespace"):
    replace(getattr(recorded_chart, member), **{field: value})


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
  restored = replace(recorded_chart, positions=list(recorded_chart.positions))  # type: ignore[arg-type]
  assert hash(restored) == hash(recorded_chart)
  other_record = replace(
    recorded_chart.resolved.record, source={"record": "another synthetic source"}
  )
  other = replace(recorded_chart, resolved=replace(recorded_chart.resolved, record=other_record))
  assert other != recorded_chart
  assert len({recorded_chart, restored, other}) == 2
  assert {recorded_chart: "original", other: "other"}[other] == "other"


class StringSubclass(str):
  pass


@pytest.mark.parametrize(
  "member,field,expected",
  [
    ("effective", "evaluation", "fixed_fourteen_object_joint_snapshot"),
    ("provenance", "position_frame", "apparent_geocentric_true_ecliptic_of_date"),
    ("provenance", "ut1_derivation", "delta_t_model_from_civil_utc"),
  ],
)
def test_fixed_result_identities_are_plain_exact_strings(
  recorded_chart: NatalChart, member: str, field: str, expected: str
) -> None:
  original = getattr(recorded_chart, member)
  assert type(getattr(original, field)) is str
  assert getattr(original, field) == expected
  assert replace(original, **{field: expected}) == original
  for invalid in (StringSubclass(expected), None, True, 1, "unknown"):
    with pytest.raises(ValueError):
      replace(original, **{field: invalid})
