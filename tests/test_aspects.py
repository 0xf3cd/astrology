"""Aspect classification against hand-computed longitudes, rates and orbs."""

import math
from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from astrology import (
  AspectHit,
  AspectMotion,
  AspectObject,
  AspectRule,
  Body,
  LunarNode,
  MajorAspect,
  ObjectOrb,
  OrbCombination,
  aspect_angle,
  find_aspects,
)

SUN = Body.SUN
MOON = Body.MOON
MARS = Body.MARS


def obj(identity: Body | LunarNode, longitude: float, rate: float | None = 1.0) -> AspectObject:
  return AspectObject(identity, longitude, rate)


def rule(aspect: MajorAspect, orb: float, *entries: ObjectOrb) -> AspectRule:
  return AspectRule(aspect, orb, entries)


def only(hits: tuple[AspectHit, ...]) -> AspectHit:
  assert len(hits) == 1, hits
  return hits[0]


def test_aspect_angles_cover_every_aspect_exactly() -> None:
  expected = {
    MajorAspect.CONJUNCTION: 0.0,
    MajorAspect.SEXTILE: 60.0,
    MajorAspect.SQUARE: 90.0,
    MajorAspect.TRINE: 120.0,
    MajorAspect.OPPOSITION: 180.0,
  }
  assert {aspect: aspect_angle(aspect) for aspect in MajorAspect} == expected


@pytest.mark.parametrize("value", ["sextile", None, 60])
def test_aspect_angle_requires_an_aspect_identity(value: object) -> None:
  with pytest.raises(TypeError):
    aspect_angle(cast(Any, value))


# Separation s = second - first, wrapped to (-180, 180]; deviation = s - branch.
def test_sextile_selects_the_plus_branch_when_the_second_object_is_ahead() -> None:
  hit = only(find_aspects([obj(SUN, 10.0), obj(MARS, 68.0)], [rule(MajorAspect.SEXTILE, 3.0)]))
  assert (hit.first, hit.second, hit.aspect) == (SUN, MARS, MajorAspect.SEXTILE)
  assert (hit.branch_deg, hit.deviation_deg, hit.orb_limit_deg) == (60.0, -2.0, 3.0)


def test_sextile_selects_the_minus_branch_when_the_second_object_is_behind() -> None:
  hit = only(find_aspects([obj(SUN, 10.0), obj(MARS, 312.0)], [rule(MajorAspect.SEXTILE, 3.0)]))
  assert (hit.branch_deg, hit.deviation_deg) == (-60.0, 2.0)


@pytest.mark.parametrize(
  "aspect,second,branch,deviation",
  [
    (MajorAspect.SQUARE, 98.0, 90.0, -2.0),
    (MajorAspect.SQUARE, 282.0, -90.0, 2.0),
    (MajorAspect.TRINE, 128.0, 120.0, -2.0),
    (MajorAspect.TRINE, 252.0, -120.0, 2.0),
  ],
)
def test_square_and_trine_have_two_oriented_branches(
  aspect: MajorAspect, second: float, branch: float, deviation: float
) -> None:
  hit = only(find_aspects([obj(SUN, 10.0), obj(MARS, second)], [rule(aspect, 3.0)]))
  assert (hit.branch_deg, hit.deviation_deg) == (branch, deviation)


@pytest.mark.parametrize(
  "first,second,aspect,branch,deviation",
  [
    (359.0, 1.0, MajorAspect.CONJUNCTION, 0.0, 2.0),
    (1.0, 359.0, MajorAspect.CONJUNCTION, 0.0, -2.0),
    (725.0, 3.0, MajorAspect.CONJUNCTION, 0.0, -2.0),
    (10.0, 188.0, MajorAspect.OPPOSITION, 180.0, -2.0),
    (10.0, 192.0, MajorAspect.OPPOSITION, 180.0, 2.0),
  ],
)
def test_separation_wraps_across_zero_and_180(
  first: float, second: float, aspect: MajorAspect, branch: float, deviation: float
) -> None:
  hit = only(find_aspects([obj(SUN, first), obj(MARS, second)], [rule(aspect, 3.0)]))
  assert (hit.branch_deg, hit.deviation_deg) == (branch, deviation)


@pytest.mark.parametrize("first,second", [(10.0, 190.0), (190.0, 10.0), (350.0, 170.0)])
def test_opposition_exact_on_either_side_of_180(first: float, second: float) -> None:
  hit = only(
    find_aspects([obj(SUN, first), obj(MARS, second)], [rule(MajorAspect.OPPOSITION, 0.0)])
  )
  assert (hit.branch_deg, hit.deviation_deg, hit.motion) == (180.0, 0.0, AspectMotion.EXACT)


@pytest.mark.parametrize(
  "first_rate,second_rate,expected",
  [
    (1.0, 2.0, AspectMotion.APPLYING),
    (2.0, 1.0, AspectMotion.SEPARATING),
    (-1.5, -0.5, AspectMotion.APPLYING),
    (-0.5, -1.5, AspectMotion.SEPARATING),
    (-1.0, 1.0, AspectMotion.APPLYING),
    (1.0, -1.0, AspectMotion.SEPARATING),
    (0.0, 1.0, AspectMotion.APPLYING),
    (1.0, 1.0, AspectMotion.STATIONARY),
    (-0.25, -0.25, AspectMotion.STATIONARY),
    (None, 1.0, AspectMotion.INDETERMINATE),
    (1.0, None, AspectMotion.INDETERMINATE),
    (None, None, AspectMotion.INDETERMINATE),
  ],
)
def test_motion_status_from_deviation_and_relative_rate(
  first_rate: float | None, second_rate: float | None, expected: AspectMotion
) -> None:
  # Separation 58 against the +60 branch: deviation -2, so a positive relative rate applies.
  hit = only(
    find_aspects(
      [obj(SUN, 10.0, first_rate), obj(MARS, 68.0, second_rate)], [rule(MajorAspect.SEXTILE, 3.0)]
    )
  )
  assert hit.deviation_deg == -2.0
  assert hit.motion is expected


@pytest.mark.parametrize("rates", [(1.0, 2.0), (1.0, 1.0), (None, 1.0), (None, None)])
def test_exact_aspect_is_exact_whatever_the_rates(rates: tuple[float | None, float | None]) -> None:
  hit = only(
    find_aspects(
      [obj(SUN, 10.0, rates[0]), obj(MARS, 70.0, rates[1])], [rule(MajorAspect.SEXTILE, 3.0)]
    )
  )
  assert (hit.deviation_deg, hit.motion) == (0.0, AspectMotion.EXACT)


def test_conjunction_motion_across_zero() -> None:
  hit = only(
    find_aspects([obj(SUN, 359.0, 1.0), obj(MARS, 1.0, 0.0)], [rule(MajorAspect.CONJUNCTION, 3.0)])
  )
  assert (hit.deviation_deg, hit.motion) == (2.0, AspectMotion.APPLYING)
  hit = only(
    find_aspects([obj(SUN, 1.0, 0.0), obj(MARS, 359.0, 1.0)], [rule(MajorAspect.CONJUNCTION, 3.0)])
  )
  assert (hit.deviation_deg, hit.motion) == (-2.0, AspectMotion.APPLYING)


def test_orb_limit_is_inclusive_and_a_float_beyond_it_is_not() -> None:
  conjunction = [rule(MajorAspect.CONJUNCTION, 3.0)]
  assert len(find_aspects([obj(SUN, 0.0), obj(MARS, 3.0)], conjunction)) == 1
  assert len(find_aspects([obj(SUN, 0.0), obj(MARS, 357.0)], conjunction)) == 1
  assert not find_aspects([obj(SUN, 0.0), obj(MARS, math.nextafter(3.0, 4.0))], conjunction)
  assert not find_aspects([obj(SUN, 0.0), obj(MARS, 356.9)], conjunction)


def test_zero_orb_admits_only_the_exact_aspect() -> None:
  zero = [rule(MajorAspect.CONJUNCTION, 0.0)]
  assert len(find_aspects([obj(SUN, 5.0), obj(MARS, 5.0)], zero)) == 1
  assert not find_aspects([obj(SUN, 5.0), obj(MARS, 5.0 + 1e-9)], zero)


def test_a_deviation_below_float_resolution_of_180_is_not_lost() -> None:
  objects = [obj(SUN, 0.0, 0.0), obj(MARS, 1e-300, 1.0)]
  hit = only(find_aspects(objects, [rule(MajorAspect.CONJUNCTION, 1.0)]))
  assert hit.deviation_deg == 1e-300
  assert hit.motion is AspectMotion.SEPARATING
  assert not find_aspects(objects, [rule(MajorAspect.CONJUNCTION, 0.0)])


@pytest.mark.parametrize("first,second", [(0.0, 180.0), (180.0, 0.0)])
def test_a_deviation_of_180_is_its_own_mirror_and_is_reported_as_plus_180(
  first: float, second: float
) -> None:
  hit = only(
    find_aspects([obj(SUN, first), obj(MARS, second)], [rule(MajorAspect.CONJUNCTION, 180.0)])
  )
  assert (hit.branch_deg, hit.deviation_deg) == (0.0, 180.0)


def test_both_branches_are_returned_in_a_fixed_order() -> None:
  hits = find_aspects([obj(SUN, 0.0), obj(MARS, 0.0)], [rule(MajorAspect.SEXTILE, 60.0)])
  assert [(hit.branch_deg, hit.deviation_deg) for hit in hits] == [(-60.0, 60.0), (60.0, -60.0)]


def test_overlapping_orbs_report_every_aspect_by_angle_whatever_the_rule_order() -> None:
  rules = [rule(MajorAspect.SEXTILE, 30.0), rule(MajorAspect.CONJUNCTION, 35.0)]
  hits = find_aspects([obj(SUN, 0.0), obj(MARS, 30.0)], rules)
  assert [(hit.aspect, hit.branch_deg, hit.deviation_deg) for hit in hits] == [
    (MajorAspect.CONJUNCTION, 0.0, 30.0),
    (MajorAspect.SEXTILE, 60.0, -30.0),
  ]


def test_pairs_follow_the_object_order_then_the_aspect_angle() -> None:
  objects = [obj(SUN, 0.0), obj(MOON, 1.0), obj(MARS, 61.0)]
  rules = [rule(MajorAspect.SEXTILE, 2.0), rule(MajorAspect.CONJUNCTION, 2.0)]
  hits = find_aspects(objects, rules)
  assert [(hit.first, hit.second, hit.aspect) for hit in hits] == [
    (SUN, MOON, MajorAspect.CONJUNCTION),
    (SUN, MARS, MajorAspect.SEXTILE),
    (MOON, MARS, MajorAspect.SEXTILE),
  ]


@pytest.mark.parametrize(
  "aspect,second,deviation",
  [
    (MajorAspect.CONJUNCTION, 12.0, 2.0),
    (MajorAspect.SEXTILE, 68.0, -2.0),
    (MajorAspect.SQUARE, 98.0, -2.0),
    (MajorAspect.TRINE, 128.0, -2.0),
    (MajorAspect.OPPOSITION, 188.0, -2.0),
  ],
)
def test_swapping_the_pair_keeps_the_aspect_and_flips_orientation(
  aspect: MajorAspect, second: float, deviation: float
) -> None:
  rules = [rule(aspect, 3.0)]
  forward = only(find_aspects([obj(SUN, 10.0, 1.0), obj(MARS, second, 3.0)], rules))
  backward = only(find_aspects([obj(MARS, second, 3.0), obj(SUN, 10.0, 1.0)], rules))
  assert (forward.first, forward.second) == (SUN, MARS)
  assert (backward.first, backward.second) == (MARS, SUN)
  assert forward.aspect is backward.aspect is aspect
  assert forward.deviation_deg == deviation
  assert backward.deviation_deg == -deviation
  if aspect in (MajorAspect.CONJUNCTION, MajorAspect.OPPOSITION):
    assert backward.branch_deg == forward.branch_deg
  else:
    assert backward.branch_deg == -forward.branch_deg
  assert forward.motion is backward.motion
  assert forward.orb_limit_deg == backward.orb_limit_deg


@pytest.mark.parametrize("ulps", [1, 2, 3, 10, 1000])
@pytest.mark.parametrize("side", [1.0, -1.0])
def test_swapping_an_opposition_a_few_ulps_from_exact_keeps_the_status(
  ulps: int, side: float
) -> None:
  gap = 180.0
  for _ in range(ulps):
    gap = math.nextafter(gap, 0.0)
  rules = [rule(MajorAspect.OPPOSITION, 1.0)]
  forward = only(find_aspects([obj(SUN, 0.0, 1.0), obj(MARS, side * gap, 2.0)], rules))
  backward = only(find_aspects([obj(MARS, side * gap, 2.0), obj(SUN, 0.0, 1.0)], rules))
  expected = AspectMotion.APPLYING if side > 0 else AspectMotion.SEPARATING
  assert forward.deviation_deg != 0.0
  assert backward.deviation_deg == -forward.deviation_deg
  assert forward.motion is expected
  assert backward.motion is expected


def test_two_lunar_nodes_never_form_an_aspect() -> None:
  nodes = [
    obj(LunarNode.MEAN_ASCENDING, 10.0, -0.05),
    obj(LunarNode.MEAN_DESCENDING, 190.0, -0.05),
    obj(LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING, 10.5, -0.14),
  ]
  rules = [rule(aspect, 5.0) for aspect in MajorAspect]
  assert not find_aspects(nodes, rules)


def test_a_node_aspects_a_body_like_any_other_object() -> None:
  hits = find_aspects(
    [obj(LunarNode.MEAN_ASCENDING, 10.0, -0.05), obj(SUN, 11.0, 1.0)],
    [rule(MajorAspect.CONJUNCTION, 3.0)],
  )
  hit = only(hits)
  assert (hit.first, hit.second, hit.deviation_deg) == (LunarNode.MEAN_ASCENDING, SUN, 1.0)
  assert hit.motion is AspectMotion.SEPARATING


def moon_hits(
  separation: float,
  combination: OrbCombination,
  *,
  sun_orb: float | None = None,
  moon_first: bool = False,
) -> tuple[AspectHit, ...]:
  entries = [ObjectOrb(MOON, 13.0)]
  if sun_orb is not None:
    entries.append(ObjectOrb(SUN, sun_orb))
  rules = [AspectRule(MajorAspect.CONJUNCTION, 3.0, entries)]
  pair = [obj(SUN, 0.0), obj(MOON, separation)]
  return find_aspects(pair[::-1] if moon_first else pair, rules, combination)


@pytest.mark.parametrize(
  "separation,either,both,mean",
  [
    (3.0, True, True, True),
    (7.0, True, False, True),
    (8.0, True, False, True),
    (8.5, True, False, False),
    (13.0, True, False, False),
    (13.5, False, False, False),
  ],
)
def test_orb_combination_with_a_wide_orb_for_the_moon(
  separation: float, either: bool, both: bool, mean: bool
) -> None:
  assert bool(moon_hits(separation, OrbCombination.EITHER_WITHIN_OWN_ORB)) is either
  assert bool(moon_hits(separation, OrbCombination.BOTH_WITHIN_OWN_ORB)) is both
  assert bool(moon_hits(separation, OrbCombination.MEAN_OF_ORBS)) is mean


def test_orb_combination_reports_the_limit_it_used() -> None:
  limits = {
    combination: only(moon_hits(2.0, combination)).orb_limit_deg for combination in OrbCombination
  }
  assert limits == {
    OrbCombination.EITHER_WITHIN_OWN_ORB: 13.0,
    OrbCombination.BOTH_WITHIN_OWN_ORB: 3.0,
    OrbCombination.MEAN_OF_ORBS: 8.0,
  }
  both_wide = {
    combination: only(moon_hits(2.0, combination, sun_orb=5.0)).orb_limit_deg
    for combination in OrbCombination
  }
  assert both_wide == {
    OrbCombination.EITHER_WITHIN_OWN_ORB: 13.0,
    OrbCombination.BOTH_WITHIN_OWN_ORB: 5.0,
    OrbCombination.MEAN_OF_ORBS: 9.0,
  }


@pytest.mark.parametrize("combination", list(OrbCombination))
@pytest.mark.parametrize("separation", [2.0, 7.0, 8.5])
def test_orb_combination_does_not_depend_on_the_object_order(
  combination: OrbCombination, separation: float
) -> None:
  for sun_orb in (None, 5.0):
    forward = moon_hits(separation, combination, sun_orb=sun_orb)
    backward = moon_hits(separation, combination, sun_orb=sun_orb, moon_first=True)
    assert [hit.orb_limit_deg for hit in backward] == [hit.orb_limit_deg for hit in forward]
    assert len(backward) == len(forward)


@pytest.mark.parametrize("combination", list(OrbCombination))
def test_objects_without_an_override_use_the_rule_orb(combination: OrbCombination) -> None:
  rules = [AspectRule(MajorAspect.CONJUNCTION, 3.0, [ObjectOrb(MOON, 13.0)])]
  objects = [obj(SUN, 0.0), obj(MARS, 3.0), obj(Body.VENUS, 3.5), obj(MOON, 100.0)]
  hits = find_aspects(objects, rules, combination)
  assert [(hit.first, hit.second, hit.orb_limit_deg) for hit in hits] == [
    (SUN, MARS, 3.0),
    (MARS, Body.VENUS, 3.0),
  ]


def test_a_combination_without_object_orbs_changes_nothing() -> None:
  objects = [obj(SUN, 0.0), obj(MARS, 3.0)]
  rules = [rule(MajorAspect.CONJUNCTION, 3.0)]
  baseline = find_aspects(objects, rules)
  for combination in OrbCombination:
    assert find_aspects(objects, rules, combination) == baseline


def test_object_orbs_without_a_combination_are_rejected() -> None:
  rules = [AspectRule(MajorAspect.CONJUNCTION, 3.0, [ObjectOrb(MOON, 13.0)])]
  with pytest.raises(ValueError, match="combination is required"):
    find_aspects([obj(SUN, 0.0), obj(MOON, 1.0)], rules)


@pytest.mark.parametrize(
  "objects,rules,combination,error",
  [
    ("sun", [], None, TypeError),
    (None, [], None, TypeError),
    ([(SUN, 0.0, 1.0)], [], None, TypeError),
    ([obj(SUN, 0.0), obj(SUN, 1.0)], [], None, ValueError),
    ([], "conjunction", None, TypeError),
    ([], [MajorAspect.CONJUNCTION], None, TypeError),
    ([], [rule(MajorAspect.TRINE, 1.0), rule(MajorAspect.TRINE, 2.0)], None, ValueError),
    ([], [], "mean_of_orbs", TypeError),
  ],
)
def test_find_aspects_rejects_invalid_arguments(
  objects: object, rules: object, combination: object, error: type[Exception]
) -> None:
  with pytest.raises(error):
    find_aspects(cast(Any, objects), cast(Any, rules), cast(Any, combination))


def test_aspect_object_keeps_values_and_allows_a_missing_rate() -> None:
  value = AspectObject(SUN, 10, 2)
  assert (value.longitude_deg, value.longitude_rate_deg_per_day) == (10.0, 2.0)
  assert type(value.longitude_deg) is float
  assert AspectObject(SUN, 10.0, None).longitude_rate_deg_per_day is None
  with pytest.raises(FrozenInstanceError):
    cast(Any, value).longitude_deg = 1.0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), 10**400])
def test_aspect_object_rejects_non_finite_numbers(bad: float) -> None:
  with pytest.raises(ValueError):
    AspectObject(SUN, bad, 1.0)
  with pytest.raises(ValueError):
    AspectObject(SUN, 1.0, bad)


@pytest.mark.parametrize("bad", [True, "1", 1j])
def test_aspect_object_rejects_non_numbers(bad: object) -> None:
  with pytest.raises(TypeError):
    AspectObject(SUN, cast(Any, bad), 1.0)
  with pytest.raises(TypeError):
    AspectObject(SUN, 1.0, cast(Any, bad))


@pytest.mark.parametrize("identity", ["sun", None, MajorAspect.TRINE])
def test_aspect_object_requires_an_object_identity(identity: object) -> None:
  with pytest.raises(TypeError):
    AspectObject(cast(Any, identity), 1.0, 1.0)


def test_a_hit_is_immutable() -> None:
  hit = only(find_aspects([obj(SUN, 0.0), obj(MARS, 1.0)], [rule(MajorAspect.CONJUNCTION, 3.0)]))
  with pytest.raises(FrozenInstanceError):
    cast(Any, hit).deviation_deg = 0.0
