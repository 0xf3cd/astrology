"""Static cross-chart contracts against hand-worked geometry. 静态双盘合同与独立手算几何。"""

import copy
import math
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, fields, replace
from typing import Any, cast

import pytest

from astrology import (
  AspectObject,
  AspectRule,
  Body,
  ChartConfig,
  CrossAspectHit,
  CrossChartAspects,
  HouseSystem,
  Location,
  LunarNode,
  MajorAspect,
  NatalChart,
  ObjectOrb,
  OrbCombination,
  cross_chart_aspects,
  find_aspects,
)
from tools.installed_check import _cross_source, acceptance_cross_aspects

SUN, MOON = Body.SUN, Body.MOON
NODE = LunarNode.MEAN_ASCENDING


def chart_at(*coordinates: tuple[Body | LunarNode, float]) -> NatalChart:
  return _cross_source(2000, "unit", coordinates)


def test_chart_keywords_and_result_fields_keep_the_same_source_roles() -> None:
  chart_left = _cross_source(2000, "left", ((SUN, 10),))
  chart_right = _cross_source(2001, "right", ((MOON, 68),))
  rules = (AspectRule(MajorAspect.SEXTILE, 3),)
  result = cross_chart_aspects(chart_right=chart_right, rules=rules, chart_left=chart_left)
  assert result.chart_left is chart_left and result.chart_right is chart_right
  assert {f.name for f in fields(result)} == {
    "chart_left",
    "chart_right",
    "left_objects",
    "right_objects",
    "rules",
    "combination",
    "hits",
  }
  assert result.hits == (CrossAspectHit(SUN, MOON, MajorAspect.SEXTILE, 60, -2, 3),)
  assert (
    CrossChartAspects(
      chart_right=chart_right,
      chart_left=chart_left,
      left_objects=(SUN,),
      right_objects=(MOON,),
      rules=rules,
      combination=None,
      hits=result.hits,
    )
    == result
  )


def natal_policy(chart: NatalChart, aspect: MajorAspect, orb: float, object_: Body) -> NatalChart:
  config = ChartConfig(
    chart.requested.house_system,
    chart.requested.objects,
    (AspectRule(aspect, orb),),
    aspect_objects=(object_,),
  )
  members = [
    AspectObject(p.identity, p.longitude_deg, p.longitude_rate_deg_per_tt_day)
    for p in chart.positions
    if p.identity in config.aspect_participants()
  ]
  return replace(
    chart,
    requested=config,
    effective=replace(chart.effective, aspect_objects=config.aspect_participants()),
    aspects=find_aspects(members, config.aspects),
  )


@pytest.mark.parametrize(
  "aspect,left,right,branch,deviation",
  [
    (MajorAspect.CONJUNCTION, 359, 1, 0, 2),
    (MajorAspect.CONJUNCTION, 1, 359, 0, -2),
    (MajorAspect.CONJUNCTION, 10, 10, 0, 0),
    (MajorAspect.SEXTILE, 10, 68, 60, -2),
    (MajorAspect.SEXTILE, 10, 312, -60, 2),
    (MajorAspect.SQUARE, 10, 98, 90, -2),
    (MajorAspect.SQUARE, 10, 282, -90, 2),
    (MajorAspect.TRINE, 10, 128, 120, -2),
    (MajorAspect.TRINE, 10, 252, -120, 2),
    (MajorAspect.OPPOSITION, 10, 190, 180, 0),
    (MajorAspect.OPPOSITION, 190, 10, 180, 0),
    (MajorAspect.OPPOSITION, 10, 188, 180, -2),
  ],
)
def test_same_named_pair_uses_hand_worked_angles(
  aspect: MajorAspect, left: float, right: float, branch: float, deviation: float
) -> None:
  first, second = chart_at((SUN, left)), chart_at((SUN, right))
  rules = [AspectRule(aspect, 3)]
  (hit,) = cross_chart_aspects(first, second, rules).hits
  assert (hit.left_object, hit.right_object, hit.aspect) == (SUN, SUN, aspect)
  assert (hit.branch_deg, hit.deviation_deg, hit.orb_limit_deg) == (branch, deviation, 3)
  (mirror,) = cross_chart_aspects(second, first, rules).hits
  assert mirror.deviation_deg == -deviation
  assert mirror.branch_deg == (branch if branch in (0, 180) else -branch)


@pytest.mark.parametrize("left_node", list(LunarNode))
@pytest.mark.parametrize("right_node", list(LunarNode))
def test_every_named_node_definition_and_direction_can_pair_across_charts(
  left_node: LunarNode, right_node: LunarNode
) -> None:
  left, right = chart_at((left_node, 10)), chart_at((right_node, 190))
  (hit,) = cross_chart_aspects(left, right, [AspectRule(MajorAspect.OPPOSITION, 0)]).hits
  assert (hit.left_object, hit.right_object, hit.branch_deg, hit.deviation_deg) == (
    left_node,
    right_node,
    180,
    0,
  )
  members = [AspectObject(left_node, 10, 1), AspectObject(right_node, 190, 1)]
  if left_node is right_node:
    with pytest.raises(ValueError, match="duplicate"):
      find_aspects(members, [AspectRule(MajorAspect.OPPOSITION, 0)])
  else:
    assert find_aspects(members, [AspectRule(MajorAspect.OPPOSITION, 0)]) == ()


def test_same_source_in_both_roles_returns_full_cartesian_product_and_all_branches() -> None:
  source = chart_at((MOON, 90), (SUN, 0), (NODE, 180))
  rules = [AspectRule(aspect, 180) for aspect in reversed(tuple(MajorAspect))]
  result = cross_chart_aspects(source, source, rules)
  expected_branches = [
    (MajorAspect.CONJUNCTION, 0),
    (MajorAspect.SEXTILE, -60),
    (MajorAspect.SEXTILE, 60),
    (MajorAspect.SQUARE, -90),
    (MajorAspect.SQUARE, 90),
    (MajorAspect.TRINE, -120),
    (MajorAspect.TRINE, 120),
    (MajorAspect.OPPOSITION, 180),
  ]
  assert len(result.hits) == 3 * 3 * 8
  assert [(h.left_object, h.right_object, h.aspect, h.branch_deg) for h in result.hits] == [
    (left, right, aspect, branch)
    for left in (MOON, SUN, NODE)
    for right in (MOON, SUN, NODE)
    for aspect, branch in expected_branches
  ]
  assert result.chart_left is result.chart_right is source
  assert result.rules == tuple(rules)


@pytest.mark.parametrize("side", ["left", "right"])
def test_selection_is_side_specific_and_follows_source_order(side: str) -> None:
  source = chart_at((MOON, 0), (NODE, 0), (SUN, 0))
  result = cross_chart_aspects(
    source,
    source,
    [AspectRule(MajorAspect.CONJUNCTION, 0)],
    **{side + "_objects": cast(Any, [SUN, MOON])},
  )
  assert getattr(result, side + "_objects") == (MOON, SUN)
  assert len(result.hits) == 6
  other = "right" if side == "left" else "left"
  assert getattr(result, other + "_objects") == (MOON, NODE, SUN)


def test_natal_participants_and_rules_are_not_inherited() -> None:
  left = natal_policy(chart_at((MOON, 0), (SUN, 0), (NODE, 180)), MajorAspect.CONJUNCTION, 1, SUN)
  right = natal_policy(chart_at((SUN, 7), (MOON, 7), (NODE, 187)), MajorAspect.SQUARE, 2, MOON)
  fresh = [AspectRule(MajorAspect.CONJUNCTION, 10)]
  result = cross_chart_aspects(left, right, fresh)
  assert result.left_objects == (MOON, SUN, NODE)
  assert result.right_objects == (SUN, MOON, NODE)
  assert all(hit.orb_limit_deg == 10 for hit in result.hits)
  assert any((h.left_object, h.right_object, h.deviation_deg) == (SUN, SUN, 7) for h in result.hits)
  assert result.rules == tuple(fresh)
  assert not left.aspects and not right.aspects


@pytest.mark.parametrize(
  "combination,limit",
  [
    (OrbCombination.EITHER_WITHIN_OWN_ORB, 13.0),
    (OrbCombination.BOTH_WITHIN_OWN_ORB, 3.0),
    (OrbCombination.MEAN_OF_ORBS, 8.0),
  ],
)
@pytest.mark.parametrize("overridden", [MOON, *LunarNode])
def test_asymmetric_orbs_and_nextafter_boundaries(
  combination: OrbCombination, limit: float, overridden: Body | LunarNode
) -> None:
  rule = AspectRule(MajorAspect.CONJUNCTION, 3, [ObjectOrb(overridden, 13)])
  for longitude, admitted in ((limit, True), (math.nextafter(limit, math.inf), False)):
    left, right = chart_at((SUN, 0)), chart_at((overridden, longitude))
    for first, second in ((left, right), (right, left)):
      result = cross_chart_aspects(first, second, [rule], combination=combination)
      assert bool(result.hits) is admitted
      if admitted:
        assert result.hits[0].orb_limit_deg == limit
        assert abs(result.hits[0].deviation_deg) == limit


@pytest.mark.parametrize("combination", list(OrbCombination))
@pytest.mark.parametrize("identity", [SUN, *LunarNode])
def test_same_identity_override_applies_on_both_sides(
  combination: OrbCombination, identity: Body | LunarNode
) -> None:
  rule = AspectRule(MajorAspect.CONJUNCTION, 1, [ObjectOrb(identity, 5)])
  (hit,) = cross_chart_aspects(
    chart_at((identity, 0)), chart_at((identity, 5)), [rule], combination=combination
  ).hits
  assert hit.orb_limit_deg == hit.deviation_deg == 5


def test_a_subnormal_deviation_is_not_rounded_to_exact() -> None:
  left, right = chart_at((SUN, 0)), chart_at((SUN, 1e-300))
  (hit,) = cross_chart_aspects(left, right, [AspectRule(MajorAspect.CONJUNCTION, 1)]).hits
  assert hit.deviation_deg == 1e-300
  assert not cross_chart_aspects(left, right, [AspectRule(MajorAspect.CONJUNCTION, 0)]).hits


@pytest.mark.parametrize(
  "aspect,branch,longitude",
  [
    (MajorAspect.CONJUNCTION, 0, 180),
    (MajorAspect.SEXTILE, -60, 120),
    (MajorAspect.SEXTILE, 60, 240),
    (MajorAspect.SQUARE, -90, 90),
    (MajorAspect.SQUARE, 90, 270),
    (MajorAspect.TRINE, -120, 60),
    (MajorAspect.TRINE, 120, 300),
    (MajorAspect.OPPOSITION, 180, 0),
  ],
)
def test_branch_antipodes_remain_positive_180_when_endpoints_exchange(
  aspect: MajorAspect, branch: float, longitude: float
) -> None:
  left, right = chart_at((SUN, 0)), chart_at((SUN, longitude))
  rules = [AspectRule(aspect, 180)]
  for first, second, target in (
    (left, right, branch),
    (right, left, branch if branch in (0, 180) else -branch),
  ):
    hit = next(h for h in cross_chart_aspects(first, second, rules).hits if h.branch_deg == target)
    assert hit.deviation_deg == 180


def test_overlapping_aspects_are_not_reduced_to_the_nearest_match() -> None:
  result = cross_chart_aspects(
    chart_at((SUN, 0)),
    chart_at((SUN, 30)),
    [AspectRule(MajorAspect.SEXTILE, 30), AspectRule(MajorAspect.CONJUNCTION, 35)],
  )
  assert [(h.aspect, h.branch_deg, h.deviation_deg) for h in result.hits] == [
    (MajorAspect.CONJUNCTION, 0, 30),
    (MajorAspect.SEXTILE, 60, -30),
  ]


def test_static_hits_have_no_motion_and_do_not_consume_natal_rates(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  left, right = chart_at((SUN, 10)), chart_at((MOON, 68))

  def forbidden(*args: object) -> None:
    raise AssertionError("Cross geometry must not evaluate natal motion")

  monkeypatch.setattr("astrology.aspects._motion", forbidden)
  changed = replace(
    right, positions=(replace(right.positions[0], longitude_rate_deg_per_tt_day=-100),)
  )
  original = cross_chart_aspects(left, right, [AspectRule(MajorAspect.SEXTILE, 3)])
  assert cross_chart_aspects(left, changed, original.rules).hits == original.hits
  assert {f.name for f in fields(CrossAspectHit)} == {
    "left_object",
    "right_object",
    "aspect",
    "branch_deg",
    "deviation_deg",
    "orb_limit_deg",
  }


def test_identical_geometry_keeps_distinct_source_ownership() -> None:
  left = _cross_source(2000, "left", ((SUN, 10),))
  right = _cross_source(2001, "right", ((SUN, 10),))
  result = cross_chart_aspects(left, right, [AspectRule(MajorAspect.CONJUNCTION, 0)])
  assert result.chart_left is left and result.chart_right is right
  assert result.chart_left.resolved != result.chart_right.resolved
  assert result.chart_left.provenance != result.chart_right.provenance
  assert result.hits[0].deviation_deg == 0


def test_sources_and_geometrically_irrelevant_differences_are_retained() -> None:
  result = acceptance_cross_aspects()
  source = {"record": "another synthetic source"}
  right = replace(
    result.chart_right,
    resolved=replace(
      result.chart_right.resolved,
      record=replace(result.chart_right.resolved.record, location=Location(23, 45), source=source),
    ),
    provenance=replace(
      result.chart_right.provenance, celestial_version="other", astrology_version="other"
    ),
    effective=replace(
      result.chart_right.effective, delta_t_model="other", house_system=HouseSystem.EQUAL
    ),
    times=replace(result.chart_right.times, jd_ut1=2460000, jde_tt=2460001),
    requested=replace(result.chart_right.requested, house_system=HouseSystem.EQUAL),
    houses=replace(result.chart_right.houses, system=HouseSystem.EQUAL),
  )
  changed = cross_chart_aspects(
    result.chart_left, right, result.rules, combination=result.combination
  )
  source.clear()
  assert changed.hits == result.hits
  assert changed.chart_left is result.chart_left and changed.chart_right is right
  assert changed.chart_right.resolved.record.source["record"] == "another synthetic source"
  assert changed.chart_right.requested.house_system is HouseSystem.EQUAL
  assert changed.chart_right.provenance.astrology_version == "other"
  assert changed.chart_right.effective.delta_t_model == "other"
  assert changed != result


@pytest.mark.parametrize("field", ["zodiac", "center", "position_frame"])
def test_incompatible_conventions_are_rejected_with_disclosed_instrumentation(field: str) -> None:
  # Current constructors admit one convention; instrument a future mismatch, not a legal current chart.
  # 当前构造器只接纳一种坐标约定；这里人工注入未来的不一致，不冒充当前合法命盘。
  left = chart_at((SUN, 0))
  right = copy.copy(left)
  owner = "provenance" if field == "position_frame" else "requested"
  changed = copy.copy(getattr(right, owner))
  object.__setattr__(changed, field, "different-convention")
  object.__setattr__(right, owner, changed)
  with pytest.raises(ValueError, match="matching zodiac, center and position frame"):
    cross_chart_aspects(left, right, ())


@pytest.mark.parametrize("side", ["left_objects", "right_objects"])
@pytest.mark.parametrize("bad", [None, "sun", ["sun"], [SUN, SUN], [MOON], iter([SUN])])
def test_invalid_explicit_selections_are_rejected(side: str, bad: object) -> None:
  source = chart_at((SUN, 0))
  if bad is None:
    assert getattr(cross_chart_aspects(source, source, (), **{side: None}), side) == (SUN,)
  else:
    with pytest.raises((TypeError, ValueError)):
      cross_chart_aspects(source, source, (), **{side: cast(Any, bad)})


@pytest.mark.parametrize("bad", [None, "conjunction", [MajorAspect.CONJUNCTION], iter(())])
def test_invalid_rule_sequences_are_rejected(bad: object) -> None:
  source = chart_at((SUN, 0))
  with pytest.raises(TypeError):
    cross_chart_aspects(source, source, cast(Any, bad))


def test_request_validation_is_not_skipped_for_empty_outputs() -> None:
  source = chart_at((SUN, 0))
  duplicate = [AspectRule(MajorAspect.CONJUNCTION, 1), AspectRule(MajorAspect.CONJUNCTION, 2)]
  override = [AspectRule(MajorAspect.CONJUNCTION, 1, [ObjectOrb(MOON, 2)])]
  with pytest.raises(ValueError, match="repeat"):
    cross_chart_aspects(source, source, duplicate, left_objects=[])
  with pytest.raises(ValueError, match="required"):
    cross_chart_aspects(source, source, override, left_objects=[])
  with pytest.raises(ValueError, match="only selected"):
    cross_chart_aspects(source, source, override, combination=OrbCombination.MEAN_OF_ORBS)
  with pytest.raises(ValueError, match="requires"):
    cross_chart_aspects(source, source, (), combination=OrbCombination.MEAN_OF_ORBS)
  with pytest.raises(TypeError, match="combination"):
    cross_chart_aspects(source, source, (), combination=cast(Any, "mean_of_orbs"))
  for left, right in ((None, source), (source, None)):
    with pytest.raises(TypeError, match="NatalChart"):
      cross_chart_aspects(cast(Any, left), cast(Any, right), ())


@pytest.mark.parametrize("selected_side", [None, "left", "right"])
def test_override_identity_must_be_selected_on_at_least_one_side(
  selected_side: str | None,
) -> None:
  left = chart_at((SUN, 0), (NODE, 10))
  right = chart_at((SUN, 5), (NODE, 5))
  rules = [AspectRule(MajorAspect.CONJUNCTION, 1, [ObjectOrb(NODE, 13)])]
  assert NODE in left.requested.objects and NODE in right.requested.objects
  options: dict[str, Any] = {
    "left_objects": [SUN],
    "right_objects": [SUN],
    "combination": OrbCombination.MEAN_OF_ORBS,
  }
  if selected_side is None:
    with pytest.raises(ValueError, match="only selected"):
      cross_chart_aspects(left, right, rules, **options)
  else:
    options[selected_side + "_objects"] = [SUN, NODE]
    result = cross_chart_aspects(left, right, rules, **options)
    (hit,) = result.hits
    assert (hit.left_object, hit.right_object) == (
      (NODE, SUN) if selected_side == "left" else (SUN, NODE)
    )
    assert hit.orb_limit_deg == 7 and abs(hit.deviation_deg) == 5


@pytest.mark.parametrize("side,identity", [("left", NODE), ("right", MOON)])
def test_selection_cannot_borrow_an_object_from_the_other_source(
  side: str, identity: Body | LunarNode
) -> None:
  left = chart_at((SUN, 0), (MOON, 1))
  right = chart_at((SUN, 2), (NODE, 3))
  selected, opposite = (left, right) if side == "left" else (right, left)
  assert identity not in selected.requested.objects
  assert identity in opposite.requested.objects
  with pytest.raises(ValueError, match=side + "_objects must name only objects available"):
    cross_chart_aspects(left, right, (), **{side + "_objects": cast(Any, [identity])})


def test_empty_rules_selections_and_no_matches_are_valid_and_distinguishable() -> None:
  left, right = chart_at((SUN, 0)), chart_at((SUN, 20))
  rule = [AspectRule(MajorAspect.CONJUNCTION, 1)]
  empty_rules = cross_chart_aspects(left, right, ())
  empty_left = cross_chart_aspects(left, right, rule, left_objects=[])
  empty_right = cross_chart_aspects(left, right, rule, right_objects=[])
  no_match = cross_chart_aspects(left, right, rule)
  assert all(result.hits == () for result in (empty_rules, empty_left, empty_right, no_match))
  assert empty_rules.rules == () and empty_rules.left_objects == (SUN,)
  assert empty_left.left_objects == () and empty_left.rules == tuple(rule)
  assert empty_right.right_objects == ()
  assert no_match.left_objects == no_match.right_objects == (SUN,)


@pytest.mark.parametrize(
  "field,bad",
  [
    ("left_object", "sun"),
    ("right_object", MajorAspect.CONJUNCTION),
    ("aspect", "conjunction"),
    ("branch_deg", 42),
    ("deviation_deg", -180),
    ("deviation_deg", 181),
    ("orb_limit_deg", -1),
    ("deviation_deg", 4),
  ],
)
def test_direct_hit_construction_checks_all_geometric_contracts(field: str, bad: object) -> None:
  hit = CrossAspectHit(SUN, SUN, MajorAspect.CONJUNCTION, 0, 1, 3)
  with pytest.raises((TypeError, ValueError)):
    replace(hit, **{field: cast(Any, bad)})


@pytest.mark.parametrize("field", ["branch_deg", "deviation_deg", "orb_limit_deg"])
@pytest.mark.parametrize("bad", [True, "1", float("nan"), float("inf"), 10**400])
def test_hit_numeric_fields_reject_invalid_numbers(field: str, bad: object) -> None:
  with pytest.raises((TypeError, ValueError)):
    replace(CrossAspectHit(SUN, NODE, MajorAspect.CONJUNCTION, 0, 0, 3), **{field: cast(Any, bad)})


@pytest.mark.parametrize(
  "field,bad",
  [
    ("chart_left", None),
    ("chart_right", {}),
    ("left_objects", None),
    ("right_objects", "sun"),
    ("rules", None),
    ("hits", None),
    ("hits", [{}]),
    ("hits", []),
    ("combination", "mean_of_orbs"),
  ],
)
def test_direct_result_construction_rejects_invalid_fields(field: str, bad: object) -> None:
  with pytest.raises((TypeError, ValueError)):
    replace(acceptance_cross_aspects(), **{field: cast(Any, bad)})


def test_result_requires_complete_correctly_ordered_hits() -> None:
  result = acceptance_cross_aspects()
  for hits in (result.hits[:-1], result.hits[::-1], (*result.hits, result.hits[0])):
    with pytest.raises(ValueError, match="complete pure derivation"):
      replace(result, hits=hits)
  changed = replace(result.hits[0], deviation_deg=-1)
  with pytest.raises(ValueError, match="complete pure derivation"):
    replace(result, hits=(changed, *result.hits[1:]))


class Once(list[Any]):
  def __init__(self, values: object) -> None:
    super().__init__(cast(Any, values))
    self.iterations = 0

  def __iter__(self) -> Iterator[Any]:
    self.iterations += 1
    if self.iterations > 1:
      raise AssertionError("Caller-owned sequence iterated more than once")
    return super().__iter__()


def test_entry_snapshots_rules_and_selections_once_and_isolates_them() -> None:
  source = chart_at((SUN, 0))
  rules = Once([AspectRule(MajorAspect.CONJUNCTION, 1)])
  left, right = Once([SUN]), Once([SUN])
  result = cross_chart_aspects(source, source, rules, left_objects=left, right_objects=right)
  for values in (rules, left, right):
    assert values.iterations == 1
    values.clear()
  assert len(result.rules) == len(result.hits) == 1
  assert result.left_objects == result.right_objects == (SUN,)


@pytest.mark.parametrize("field", ["left_objects", "right_objects", "rules", "hits"])
def test_result_snapshots_each_sequence_once(field: str) -> None:
  result = acceptance_cross_aspects()
  values = Once(getattr(result, field))
  other = replace(result, **{field: cast(Any, values)})
  assert values.iterations == 1
  values.clear()
  assert other == result and hash(other) == hash(result)
  with pytest.raises(FrozenInstanceError):
    cast(Any, other).hits = ()
  with pytest.raises(FrozenInstanceError):
    cast(Any, other.hits[0]).deviation_deg = 0


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_fresh_process_comparison_blocks_native_time_and_metadata_calls(
  mode: tuple[str, ...],
) -> None:
  source = """
import builtins
import importlib.metadata as metadata
import sys
original_import = builtins.__import__
def forbidden(*args, **kwargs):
  raise RuntimeError('Pure cross comparison reached an effectful boundary')
def guarded(name, *args, **kwargs):
  if name == 'astrology.celestial' or name.startswith(('celestial_calendar', 'tzdata', 'zoneinfo')):
    forbidden()
  return original_import(name, *args, **kwargs)
builtins.__import__ = guarded
metadata.version = metadata.distribution = forbidden
import astrology
import astrology.birth as birth
birth.resolve_birth_time = birth.prepare_natal_input = forbidden
astrology.natal_chart = forbidden
from tools.installed_check import acceptance_cross_aspects, _check_cross_chart
result = acceptance_cross_aspects()
_check_cross_chart()
if len(result.hits) != 5 or any(hasattr(h, 'motion') for h in result.hits):
  raise RuntimeError('Static result changed')
try:
  astrology.cross_chart_aspects(chart_left=result.chart_left, chart_right=result.chart_right,
    rules=[result.rules[0], result.rules[0]])
except ValueError:
  pass
else:
  raise RuntimeError('Duplicate rule validation disappeared')
if any(n.startswith(('celestial_calendar', 'astrology.celestial', 'tzdata', 'zoneinfo')) for n in sys.modules):
  raise RuntimeError('Pure comparison initialized machinery')
"""
  result = subprocess.run([sys.executable, *mode, "-c", source], capture_output=True, text=True)
  assert result.returncode == 0, result.stdout + result.stderr
