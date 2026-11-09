"""Fixed-instant geometry and zero-rate reference checks. 固定时刻几何与零速率参考侧校验。"""

import copy
import math
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from astrology import (
  AspectMotion,
  AspectRule,
  Axis,
  Body,
  Location,
  LunarNode,
  MajorAspect,
  MomentChart,
  MomentInput,
  ObjectOrb,
  OrbCombination,
  TransitAspectHit,
  cross_chart_aspects,
  format_transit_aspects,
  load_catalog,
  transit_aspects,
)
from tools.installed_check import _cross_source


def moving_at(*coordinates: tuple[Body | LunarNode, float], rate: float = 1) -> MomentChart:
  source = _cross_source(2000, "moving-geometry", coordinates)
  return MomentChart(
    MomentInput(datetime(2000, 1, 1, tzinfo=UTC), Location(0, 0)),
    source.requested,
    source.effective,
    source.provenance,
    source.times,
    tuple(replace(p, longitude_rate_deg_per_tt_day=rate) for p in source.positions),
    source.houses,
    source.placements,
    source.aspects,
  )


@pytest.mark.parametrize(
  "aspect,first,second,branch,deviation,motion",
  [
    (MajorAspect.CONJUNCTION, 359, 1, 0, 2, AspectMotion.APPLYING),
    (MajorAspect.CONJUNCTION, 1, 359, 0, -2, AspectMotion.SEPARATING),
    (MajorAspect.CONJUNCTION, 10, 10, 0, 0, AspectMotion.EXACT),
    (MajorAspect.SEXTILE, 10, 68, 60, -2, AspectMotion.SEPARATING),
    (MajorAspect.SEXTILE, 10, 312, -60, 2, AspectMotion.APPLYING),
    (MajorAspect.SQUARE, 10, 98, 90, -2, AspectMotion.SEPARATING),
    (MajorAspect.TRINE, 10, 132, 120, 2, AspectMotion.APPLYING),
    (MajorAspect.OPPOSITION, 10, 190, 180, 0, AspectMotion.EXACT),
  ],
)
def test_same_identity_has_hand_worked_geometry_and_local_motion(
  aspect: MajorAspect,
  first: float,
  second: float,
  branch: float,
  deviation: float,
  motion: AspectMotion,
) -> None:
  moving = moving_at((Body.SUN, first))
  natal = _cross_source(2001, "natal-geometry", ((Body.SUN, second),))
  rules = (AspectRule(aspect, 3),)
  (hit,) = transit_aspects(moving, natal, rules).hits
  assert (hit.moving_object, hit.natal_object) == (Body.SUN, Body.SUN)
  assert (hit.branch_deg, hit.deviation_deg, hit.orb_limit_deg, hit.motion) == (
    branch,
    deviation,
    3,
    motion,
  )
  (static,) = cross_chart_aspects(moving, natal, rules).hits
  assert (hit.aspect, hit.branch_deg, hit.deviation_deg, hit.orb_limit_deg) == (
    static.aspect,
    static.branch_deg,
    static.deviation_deg,
    static.orb_limit_deg,
  )


@pytest.mark.parametrize("moving_node", list(LunarNode))
@pytest.mark.parametrize("natal_node", list(LunarNode))
def test_every_cross_node_pair_is_admitted(moving_node: LunarNode, natal_node: LunarNode) -> None:
  result = transit_aspects(
    moving_at((moving_node, 10)),
    _cross_source(2001, "node", ((natal_node, 190),)),
    (AspectRule(MajorAspect.OPPOSITION, 0),),
  )
  assert len(result.hits) == 1 and result.hits[0].motion is AspectMotion.EXACT


def test_natal_stored_rates_are_not_used_and_stationary_is_numeric_zero() -> None:
  moving = moving_at((Body.MERCURY, 68))
  natal = _cross_source(2001, "rate", ((Body.MOON, 70),))
  natal = replace(natal, positions=(replace(natal.positions[0], longitude_rate_deg_per_tt_day=13),))
  rules = (AspectRule(MajorAspect.CONJUNCTION, 3),)
  assert transit_aspects(moving, natal, rules).hits[0].motion is AspectMotion.APPLYING
  assert (
    transit_aspects(moving_at((Body.MERCURY, 68), rate=-1), natal, rules).hits[0].motion
    is AspectMotion.SEPARATING
  )
  assert (
    transit_aspects(moving_at((Body.MERCURY, 68), rate=-0.0), natal, rules).hits[0].motion
    is AspectMotion.STATIONARY
  )
  changed = replace(
    natal, positions=(replace(natal.positions[0], longitude_rate_deg_per_tt_day=-100),)
  )
  assert transit_aspects(moving, natal, rules).hits == transit_aspects(moving, changed, rules).hits


@pytest.mark.parametrize("axis", list(Axis))
def test_all_four_axes_are_explicit_and_moving_rates_remain_absent(axis: Axis) -> None:
  moving = moving_at((Body.SUN, 0))
  natal = _cross_source(2001, "axes", ((Body.SUN, 1),))
  rules = tuple(AspectRule(aspect, 180) for aspect in MajorAspect)
  result = transit_aspects(moving, natal, rules, moving_objects=(axis,), natal_objects=(*Axis,))
  static = cross_chart_aspects(moving, natal, rules, left_objects=(axis,), right_objects=(*Axis,))
  assert [(h.branch_deg, h.deviation_deg, h.orb_limit_deg) for h in result.hits] == [
    (h.branch_deg, h.deviation_deg, h.orb_limit_deg) for h in static.hits
  ]
  assert all(
    h.motion is (AspectMotion.EXACT if h.deviation_deg == 0 else AspectMotion.INDETERMINATE)
    for h in result.hits
  )
  frozen = transit_aspects(moving, natal, rules, moving_objects=(Body.SUN,), natal_objects=(axis,))
  assert all(
    h.motion in (AspectMotion.APPLYING, AspectMotion.SEPARATING)
    or abs(h.deviation_deg) in (0.0, 180.0)
    for h in frozen.hits
  )
  (conjunction,) = (h for h in frozen.hits if h.aspect is MajorAspect.CONJUNCTION)
  expected_motion = {
    Axis.ASCENDANT: AspectMotion.EXACT,
    Axis.MIDHEAVEN: AspectMotion.SEPARATING,
    Axis.IMUM_COELI: AspectMotion.APPLYING,
    Axis.DESCENDANT: AspectMotion.INDETERMINATE,
  }[axis]
  assert conjunction.motion is expected_motion
  assert all(
    not isinstance(h.moving_object, Axis) for h in transit_aspects(moving, natal, rules).hits
  )


@pytest.mark.parametrize("combination", list(OrbCombination))
def test_orb_overrides_membership_and_order_match_static_cross_geometry(
  combination: OrbCombination,
) -> None:
  moving = moving_at((Body.MOON, 359), (Body.SUN, 10))
  natal = _cross_source(2001, "orbs", ((Body.SUN, 1), (Body.MOON, 190)))
  rules = tuple(
    AspectRule(aspect, 3, (ObjectOrb(Body.SUN, 4),)) for aspect in reversed(tuple(MajorAspect))
  )
  result = transit_aspects(moving, natal, rules, combination=combination)
  static = cross_chart_aspects(moving, natal, rules, combination=combination)
  assert [
    (h.moving_object, h.natal_object, h.aspect, h.branch_deg, h.deviation_deg, h.orb_limit_deg)
    for h in result.hits
  ] == [
    (h.left_object, h.right_object, h.aspect, h.branch_deg, h.deviation_deg, h.orb_limit_deg)
    for h in static.hits
  ]


def test_inclusive_raw_orb_boundary_and_subnormal_motion() -> None:
  moving = moving_at((Body.SUN, 0))
  rule = AspectRule(MajorAspect.CONJUNCTION, 3)
  for longitude, expected in (
    (math.nextafter(3, -math.inf), True),
    (3, True),
    (math.nextafter(3, math.inf), False),
  ):
    natal = _cross_source(2001, "orb-boundary", ((Body.SUN, longitude),))
    result = transit_aspects(moving, natal, (rule,))
    assert bool(result.hits) is expected
    if expected:
      assert result.hits[0].deviation_deg == longitude
  tiny = math.nextafter(0, 1)
  natal = _cross_source(2001, "subnormal", ((Body.SUN, tiny),))
  (hit,) = transit_aspects(moving, natal, (AspectRule(MajorAspect.CONJUNCTION, tiny),)).hits
  assert hit.deviation_deg == tiny and hit.motion is AspectMotion.APPLYING


def test_selection_order_overlaps_and_branch_cut_are_preserved() -> None:
  moving = moving_at((Body.MOON, 0), (Body.SUN, 0))
  natal = _cross_source(2001, "order", ((Body.MOON, 180), (Body.SUN, 180)))
  rules = tuple(AspectRule(aspect, 180) for aspect in reversed(tuple(MajorAspect)))
  result = transit_aspects(
    moving,
    natal,
    rules,
    moving_objects=(Axis.MIDHEAVEN, Body.SUN, Body.MOON),
    natal_objects=(Body.SUN, Body.MOON),
  )
  assert result.moving_objects == (Body.MOON, Body.SUN, Axis.MIDHEAVEN)
  assert result.natal_objects == (Body.MOON, Body.SUN)
  pair = tuple(
    h for h in result.hits if h.moving_object is Body.MOON and h.natal_object is Body.MOON
  )
  assert len(pair) == 8
  assert pair[0].aspect is MajorAspect.CONJUNCTION
  assert pair[0].deviation_deg == 180 and pair[0].motion is AspectMotion.INDETERMINATE
  assert pair[-1].aspect is MajorAspect.OPPOSITION and pair[-1].motion is AspectMotion.EXACT
  assert [h.branch_deg for h in pair] == [0, -60, 60, -90, 90, -120, 120, 180]


@pytest.mark.parametrize("field", ["zodiac", "center", "position_frame"])
def test_incompatible_sources_are_rejected_even_for_no_hits(field: str) -> None:
  moving = moving_at((Body.SUN, 10))
  natal = _cross_source(2001, "frame", ((Body.SUN, 11),))
  owner = "provenance" if field == "position_frame" else "requested"
  mutated = copy.copy(getattr(natal, owner))
  object.__setattr__(mutated, field, "future-convention")
  object.__setattr__(natal, owner, mutated)
  with pytest.raises(ValueError, match="matching zodiac, center and position frame"):
    transit_aspects(moving, natal, (), moving_objects=(), natal_objects=())


def test_empty_outputs_still_validate_both_roles_rules_and_selections() -> None:
  moving = moving_at((Body.SUN, 10))
  natal = _cross_source(2001, "empty", ((Body.SUN, 11),))
  rules = (AspectRule(MajorAspect.CONJUNCTION, 3),)
  assert transit_aspects(moving, natal, ()).hits == ()
  assert transit_aspects(moving, natal, rules, moving_objects=()).hits == ()
  assert transit_aspects(moving, natal, rules, natal_objects=()).hits == ()
  for kwargs in (
    {"moving_objects": (Body.SUN, Body.SUN)},
    {"natal_objects": (Body.MOON,)},
    {"combination": OrbCombination.MEAN_OF_ORBS},
  ):
    with pytest.raises(ValueError):
      transit_aspects(moving, natal, (), **cast(Any, kwargs))
  for first, second in ((natal, natal), (moving, moving), (None, natal), (moving, None)):
    with pytest.raises(TypeError):
      transit_aspects(cast(Any, first), cast(Any, second), ())
  with pytest.raises(ValueError):
    transit_aspects(moving, natal, (rules[0], rules[0]))
  with pytest.raises(TypeError):
    transit_aspects(moving, natal, cast(Any, None))


def test_result_isolates_sequences_and_rejects_motion_or_membership_tampering() -> None:
  moving = moving_at((Body.SUN, 10))
  natal = _cross_source(2001, "value", ((Body.SUN, 11),))
  rules = [AspectRule(MajorAspect.CONJUNCTION, 3)]
  result = transit_aspects(moving, natal, rules)
  rules.clear()
  hits = list(result.hits)
  supplied = replace(result, hits=hits)  # type: ignore[arg-type]
  hits.clear()
  assert supplied == result and supplied.moving_chart is moving and supplied.natal_chart is natal
  assert hash(supplied) == hash(result)
  for value in (
    (),
    (*result.hits, *result.hits),
    (replace(result.hits[0], motion=AspectMotion.SEPARATING),),
  ):
    with pytest.raises(ValueError):
      replace(result, hits=value)
  for name, bad in (("hits", [None]), ("moving_chart", natal), ("natal_chart", moving)):
    with pytest.raises(TypeError):
      replace(result, **{name: cast(Any, bad)})
  with pytest.raises(TypeError, match="hits must be a sequence"):
    replace(result, hits=cast(Any, None))


@pytest.mark.parametrize(
  "field,value,error",
  [
    ("moving_object", None, TypeError),
    ("natal_object", "sun", TypeError),
    ("aspect", "conjunction", TypeError),
    ("motion", "applying", TypeError),
    ("deviation_deg", math.nan, ValueError),
    ("orb_limit_deg", True, TypeError),
    ("branch_deg", 1, ValueError),
    ("motion", AspectMotion.EXACT, ValueError),
  ],
)
def test_direct_hit_constructor_checks_fields(
  field: str, value: Any, error: type[Exception]
) -> None:
  hit = TransitAspectHit(
    Body.SUN, Body.SUN, MajorAspect.CONJUNCTION, 0, 1, 3, AspectMotion.APPLYING
  )
  with pytest.raises(error):
    replace(hit, **{field: value})
  assert replace(hit, deviation_deg=-0.0, motion=AspectMotion.EXACT).motion is AspectMotion.EXACT


@pytest.mark.parametrize(
  "language,moving_label,natal_label,motion",
  [("en", "Moving", "Natal (fixed)", "applying"), ("zh-CN", "移动盘", "本命盘（固定）", "入相")],
)
def test_bilingual_output_keeps_roles_motion_escaping_and_unrounded_membership(
  language: Any, moving_label: str, natal_label: str, motion: str
) -> None:
  moving = moving_at((Body.SUN, 10))
  natal = _cross_source(2001, "text", ((Body.SUN, 10 + 1e-8),))
  result = transit_aspects(moving, natal, (AspectRule(MajorAspect.CONJUNCTION, 1),))
  catalog = load_catalog()
  sun = catalog.concept("body.sun")
  custom = replace(
    catalog,
    concepts=tuple(
      replace(c, name=replace(c.name, en="Sun|\\\n", zh="日|\\\n")) if c is sun else c
      for c in catalog.concepts
    ),
  )
  output = format_transit_aspects(result, custom, language=language)
  assert moving_label in output and natal_label in output
  assert motion in output and "0°00'00\"" in output
  assert "\\|\\\\\\n" in output
  assert result.hits[0].deviation_deg != 0 and len(result.hits) == 1
  assert format_transit_aspects(replace(result, hits=(), rules=()), catalog, language=language)
  with pytest.raises(TypeError):
    format_transit_aspects(cast(Any, None), catalog)
  with pytest.raises(ValueError):
    format_transit_aspects(result, catalog, language=cast(Any, "fr"))
  with pytest.raises(TypeError):
    format_transit_aspects(result, cast(Any, None))
