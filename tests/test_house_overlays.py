"""Directional overlays against hand-worked houses and immutable-source contracts.

用手算宫位及不可变源盘合同验证双向落宫。
"""

import copy
import math
from dataclasses import FrozenInstanceError, fields, replace
from typing import Any, cast

import pytest

from astrology import (
  AspectRule,
  Axis,
  Body,
  CrossChartHouseOverlays,
  HouseOverlay,
  HouseSystem,
  LunarNode,
  MajorAspect,
  cross_chart_house_overlays,
)
from astrology.objects import ChartObject
from tools.installed_check import _cross_source, acceptance_house_overlays


def test_hand_worked_bidirectional_placements_include_actual_axis_fields() -> None:
  result = acceptance_house_overlays()
  assert [(p.object_owner, p.house_owner, p.identity, p.house) for p in result.placements] == [
    ("left", "right", Body.SUN, 1),
    ("left", "right", Body.VENUS, 7),
    ("left", "right", LunarNode.MEAN_ASCENDING, 12),
    ("left", "right", Axis.ASCENDANT, 1),
    ("left", "right", Axis.MIDHEAVEN, 4),
    ("left", "right", Axis.DESCENDANT, 7),
    ("left", "right", Axis.IMUM_COELI, 10),
    ("right", "left", Body.SUN, 12),
    ("right", "left", Body.VENUS, 1),
    ("right", "left", LunarNode.MEAN_ASCENDING, 2),
  ]
  assert result.chart_left.houses.system is HouseSystem.WHOLE_SIGN
  assert result.chart_right.houses.system is HouseSystem.EQUAL
  assert {field.name for field in fields(HouseOverlay)} == {
    "object_owner",
    "house_owner",
    "identity",
    "house",
  }


def test_swapping_sources_swaps_owners_and_direction_blocks() -> None:
  result = acceptance_house_overlays()
  swapped = cross_chart_house_overlays(
    result.chart_right,
    result.chart_left,
    left_objects=result.right_objects,
    right_objects=result.left_objects,
  )
  expected = tuple(
    replace(p, object_owner=p.house_owner, house_owner=p.object_owner)
    for p in (
      *result.placements[len(result.left_objects) :],
      *result.placements[: len(result.left_objects)],
    )
  )
  assert swapped.placements == expected
  assert swapped.chart_left is result.chart_right
  assert swapped.chart_right is result.chart_left


def test_same_chart_keeps_both_roles_and_same_named_objects() -> None:
  chart = acceptance_house_overlays().chart_left
  result = cross_chart_house_overlays(chart, chart)
  expected = [p.house for p in chart.placements]
  assert [p.house for p in result.placements] == expected + expected
  assert [p.object_owner for p in result.placements] == ["left"] * 3 + ["right"] * 3
  assert result.chart_left is result.chart_right is chart


def test_defaults_ignore_natal_participants_and_do_not_add_axes() -> None:
  chart = acceptance_house_overlays().chart_left
  chart = replace(
    chart,
    requested=replace(
      chart.requested,
      aspects=(AspectRule(MajorAspect.CONJUNCTION, 0),),
      aspect_objects=(Axis.MIDHEAVEN,),
    ),
    effective=replace(chart.effective, aspect_objects=(Axis.MIDHEAVEN,)),
  )
  result = cross_chart_house_overlays(chart, chart)
  assert result.left_objects == result.right_objects == chart.requested.objects
  assert all(not isinstance(p.identity, Axis) for p in result.placements)


def test_selections_use_source_order_then_axis_order_not_argument_order() -> None:
  source = acceptance_house_overlays()
  selected = (Axis.IMUM_COELI, Body.VENUS, Axis.ASCENDANT, Body.SUN)
  result = cross_chart_house_overlays(
    source.chart_left, source.chart_right, left_objects=selected, right_objects=(Body.VENUS,)
  )
  assert result.left_objects == (Body.SUN, Body.VENUS, Axis.ASCENDANT, Axis.IMUM_COELI)
  assert result.right_objects == (Body.VENUS,)
  assert len(result.placements) == 5


@pytest.mark.parametrize("left_empty,right_empty", [(True, False), (False, True), (True, True)])
def test_empty_selections_affect_only_their_direction(left_empty: bool, right_empty: bool) -> None:
  source = acceptance_house_overlays()
  result = cross_chart_house_overlays(
    source.chart_left,
    source.chart_right,
    left_objects=() if left_empty else None,
    right_objects=() if right_empty else None,
  )
  assert result.left_objects == (() if left_empty else source.chart_left.requested.objects)
  assert result.right_objects == (() if right_empty else source.chart_right.requested.objects)
  assert len(result.placements) == (0 if left_empty else 3) + (0 if right_empty else 3)
  assert all(p.object_owner != "left" for p in result.placements) is left_empty
  assert all(p.object_owner != "right" for p in result.placements) is right_empty


def test_all_admitted_identities_are_available_without_changing_natal_admission() -> None:
  astronomical = (*Body, *LunarNode)
  chart = _cross_source(
    2000, "all", tuple((identity, float(5 + 10 * n)) for n, identity in enumerate(astronomical))
  )
  objects: tuple[ChartObject, ...] = (*reversed(tuple(Axis)), *reversed(astronomical))
  result = cross_chart_house_overlays(chart, chart, left_objects=objects, right_objects=objects)
  assert result.left_objects == result.right_objects == (*astronomical, *Axis)
  assert len(result.placements) == 2 * len(objects)
  assert chart.requested.objects == astronomical


@pytest.mark.parametrize("index", range(12))
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_exact_cusps_and_adjacent_floats_keep_receiving_house(index: int, offset: int) -> None:
  cusps = (300.0, 330.0, 0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0)
  cusp = cusps[index]
  if offset < 0:
    longitude = math.nextafter(cusp, -math.inf) if cusp else math.nextafter(360.0, 0.0)
  elif offset > 0:
    longitude = math.nextafter(cusp, math.inf)
  else:
    longitude = cusp
  left = _cross_source(2000, "object", ((Body.SUN, longitude),))
  right = _cross_source(2001, "houses", ((Body.SUN, 0),), cusps_deg=cusps)
  result = cross_chart_house_overlays(left, right, right_objects=())
  expected = (index or 12) if offset < 0 else index + 1
  assert result.placements == (HouseOverlay("left", "right", Body.SUN, expected),)


@pytest.mark.parametrize("longitude,expected", [(5, 3), (13, 4), (320, 1), (270, 12)])
def test_nonuniform_receiving_cusps(longitude: float, expected: int) -> None:
  cusps = (300.0, 322.0, 351.0, 13.0, 41.0, 68.0, 97.0, 129.0, 164.0, 201.0, 237.0, 269.0)
  left = _cross_source(2000, "object", ((Body.SUN, longitude),))
  right = _cross_source(2001, "houses", ((Body.SUN, 0),), cusps_deg=cusps)
  assert cross_chart_house_overlays(left, right, right_objects=()).placements[0].house == expected


@pytest.mark.parametrize("side", ["left_objects", "right_objects"])
@pytest.mark.parametrize(
  "bad,exception",
  [
    ("sun", TypeError),
    (["sun"], TypeError),
    ([MajorAspect.CONJUNCTION], TypeError),
    ([Body.SUN, Body.SUN], ValueError),
    ([Body.PLUTO], ValueError),
    (iter([Body.SUN]), TypeError),
  ],
)
def test_invalid_selection_even_when_other_direction_is_empty(
  side: str, bad: object, exception: type[Exception]
) -> None:
  chart = _cross_source(2000, "one", ((Body.SUN, 0),))
  kwargs = {"left_objects": (), "right_objects": (), side: cast(Any, bad)}
  with pytest.raises(exception):
    cross_chart_house_overlays(chart, chart, **kwargs)


@pytest.mark.parametrize("side", ["chart_left", "chart_right"])
def test_wrong_source_types_are_rejected_even_for_empty_output(side: str) -> None:
  chart = _cross_source(2000, "one", ((Body.SUN, 0),))
  kwargs = {"chart_left": chart, "chart_right": chart, side: cast(Any, None)}
  with pytest.raises(TypeError, match="must be NatalChart"):
    cross_chart_house_overlays(**kwargs, left_objects=(), right_objects=())


@pytest.mark.parametrize("field", ["zodiac", "center", "position_frame"])
def test_instrumented_future_convention_mismatch_rejects_empty_output(field: str) -> None:
  """Inject future conventions, not legal values admitted by current constructors.

  人工注入未来的坐标差异，不冒充当前构造器接纳的合法值。
  """
  left = _cross_source(2000, "one", ((Body.SUN, 0),))
  right = copy.copy(left)
  owner = "provenance" if field == "position_frame" else "requested"
  changed = copy.copy(getattr(right, owner))
  object.__setattr__(changed, field, "future-convention")
  object.__setattr__(right, owner, changed)
  with pytest.raises(ValueError, match="matching zodiac, center and position frame"):
    cross_chart_house_overlays(left, right, left_objects=(), right_objects=())


def test_selections_rows_and_birth_source_mapping_are_isolated() -> None:
  source = acceptance_house_overlays()
  record_source = {"record": "synthetic", "side": "before"}
  left = replace(
    source.chart_left,
    resolved=replace(
      source.chart_left.resolved,
      record=replace(source.chart_left.resolved.record, source=record_source),
    ),
  )
  selected: list[ChartObject] = [Body.SUN, Axis.MIDHEAVEN]
  result = cross_chart_house_overlays(left, source.chart_right, left_objects=selected)
  rows = list(result.placements)
  reconstructed = CrossChartHouseOverlays(
    result.chart_left,
    result.chart_right,
    cast(Any, selected),
    result.right_objects,
    cast(Any, rows),
  )
  before = repr(result)
  selected.clear()
  rows.clear()
  record_source["side"] = "after"
  assert repr(result) == before
  assert reconstructed == result and hash(reconstructed) == hash(result)
  assert result.chart_left is left and result.chart_right is source.chart_right
  assert result.chart_left.resolved.record.source["side"] == "before"
  with pytest.raises(FrozenInstanceError):
    cast(Any, result).placements = ()
  with pytest.raises(FrozenInstanceError):
    cast(Any, result.placements[0]).house = 2


@pytest.mark.parametrize("field", ["object_owner", "house_owner"])
@pytest.mark.parametrize(
  "bad,exception", [(None, TypeError), (True, TypeError), ("other", ValueError)]
)
def test_overlay_row_rejects_invalid_owner(
  field: str, bad: object, exception: type[Exception]
) -> None:
  kwargs = {"object_owner": "left", "house_owner": "right", field: cast(Any, bad)}
  with pytest.raises(exception):
    HouseOverlay(**kwargs, identity=Body.SUN, house=1)


@pytest.mark.parametrize("side", ["left", "right"])
def test_overlay_row_requires_opposite_owners(side: Any) -> None:
  with pytest.raises(ValueError, match="opposite sides"):
    HouseOverlay(side, side, Body.SUN, 1)


@pytest.mark.parametrize("house", [True, 1.0, "1", None])
def test_overlay_row_rejects_noninteger_house(house: Any) -> None:
  with pytest.raises(TypeError, match="integer, not bool"):
    HouseOverlay("left", "right", Body.SUN, house)


@pytest.mark.parametrize("house", [-1, 0, 13])
def test_overlay_row_rejects_out_of_range_house(house: int) -> None:
  with pytest.raises(ValueError, match=r"\[1, 12\]"):
    HouseOverlay("left", "right", Body.SUN, house)


def test_overlay_row_rejects_nonobject_identity() -> None:
  with pytest.raises(TypeError, match="Body, LunarNode or Axis"):
    HouseOverlay("left", "right", cast(Any, MajorAspect.CONJUNCTION), 1)


@pytest.mark.parametrize("bad", [None, "rows", iter(()), [Body.SUN]])
def test_result_constructor_rejects_invalid_row_sequence(bad: object) -> None:
  source = acceptance_house_overlays()
  with pytest.raises(TypeError, match="placements must"):
    replace(source, placements=cast(Any, bad))


@pytest.mark.parametrize("defect", ["missing", "extra", "order", "house", "owners", "identity"])
def test_result_constructor_rejects_incomplete_or_changed_derivation(defect: str) -> None:
  result = acceptance_house_overlays()
  rows = result.placements
  if defect == "missing":
    rows = rows[:-1]
  elif defect == "extra":
    rows = (*rows, rows[0])
  elif defect == "order":
    rows = tuple(reversed(rows))
  elif defect == "house":
    rows = (replace(rows[0], house=2), *rows[1:])
  elif defect == "owners":
    rows = (replace(rows[0], object_owner="right", house_owner="left"), *rows[1:])
  else:
    rows = (replace(rows[0], identity=Body.VENUS), *rows[1:])
  with pytest.raises(ValueError, match="complete pure derivation"):
    replace(result, placements=rows)
