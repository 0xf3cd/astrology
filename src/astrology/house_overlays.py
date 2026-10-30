"""Find which houses in one chart contain the other chart's selected objects.

查询一张盘中选定的对象落入另一张盘的哪一宫。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from astrology.chart import (
  NatalChart,
  _require_comparable_sources,
  _selected_longitudes,
  _selection_for_chart,
)
from astrology.houses import _require_house_number, house_of
from astrology.objects import ChartObject, _is_chart_object


@dataclass(frozen=True, slots=True)
class HouseOverlay:
  """An object's house in the other chart.

  object_owner identifies the chart the object comes from; house_owner identifies
  the chart whose houses are used. One must be "left" and the other "right".
  identity is a Body, LunarNode or Axis. house is an integer from 1 to 12, not bool.
  CrossChartHouseOverlays checks the house against the charts; this record alone
  does not have the geometry needed for that check.

  一个对象落入另一张盘的宫位。object_owner 表示对象来自哪张盘，house_owner 表示使用哪张盘的宫位，
  两者必须一个为 "left"、另一个为 "right"。identity 为 Body、LunarNode 或 Axis；
  house 是 1 到 12 的整数，不接受 bool。单条记录没有校验落宫所需的几何数据，
  由 CrossChartHouseOverlays 根据两张盘检查宫号是否正确。
  """

  object_owner: Literal["left", "right"]
  house_owner: Literal["left", "right"]
  identity: ChartObject
  house: int

  def __post_init__(self) -> None:
    for name in ("object_owner", "house_owner"):
      value = getattr(self, name)
      if type(value) is not str:
        raise TypeError(f"{name} must be a string")
      if value not in ("left", "right"):
        raise ValueError(f"{name} must be left or right")
    if self.object_owner == self.house_owner:
      raise ValueError("Object owner and house owner must be opposite sides")
    if not _is_chart_object(self.identity):
      raise TypeError("identity must be a Body, LunarNode or Axis value")
    _require_house_number(self.house)


@dataclass(frozen=True, slots=True)
class CrossChartHouseOverlays:
  """An immutable result containing both charts, selected objects and all placements.

  Both charts remain unchanged. Input sequences are copied into tuples. Selected
  bodies and nodes follow each chart's position order, then selected axes follow
  in ASC/MC/DSC/IC order. Placements list left objects in right houses, then right
  objects in left houses. Construction recomputes the complete placement sequence
  and rejects any difference; it does not authenticate the charts' astronomical origin.

  不可变的结果，包含两张命盘、所选对象和全部落宫记录。两张盘保持不变，传入的序列复制为元组。
  所选天体和交点按各盘的位置记录顺序排列，所选四轴随后按上升、中天、下降、天底排列。
  落宫记录先列左盘对象在右盘的落宫，再列右盘对象在左盘的落宫。
  构造时会重新计算完整落宫序列，拒绝与它不同的记录；这些检查不证明命盘的天文来源真实。
  """

  chart_left: NatalChart
  chart_right: NatalChart
  left_objects: tuple[ChartObject, ...]
  right_objects: tuple[ChartObject, ...]
  placements: tuple[HouseOverlay, ...]

  def __post_init__(self) -> None:
    _require_comparable_sources(self.chart_left, self.chart_right)
    left_objects = _selection_for_chart(self.chart_left, self.left_objects, "left_objects")
    right_objects = _selection_for_chart(self.chart_right, self.right_objects, "right_objects")
    if not isinstance(self.placements, Sequence) or isinstance(self.placements, (str, bytes)):
      raise TypeError("placements must be a sequence of HouseOverlay values")
    placements = tuple(self.placements)
    if any(type(value) is not HouseOverlay for value in placements):
      raise TypeError("placements must contain only HouseOverlay values")
    object.__setattr__(self, "left_objects", left_objects)
    object.__setattr__(self, "right_objects", right_objects)
    object.__setattr__(self, "placements", placements)
    if placements != _placements(self.chart_left, self.chart_right, left_objects, right_objects):
      raise ValueError("House overlays differ from complete pure derivation")


def _placements(
  chart_left: NatalChart,
  chart_right: NatalChart,
  left_objects: tuple[ChartObject, ...],
  right_objects: tuple[ChartObject, ...],
) -> tuple[HouseOverlay, ...]:
  left = tuple(
    HouseOverlay("left", "right", identity, house_of(longitude, chart_right.houses.cusps_deg))
    for identity, longitude in _selected_longitudes(
      chart_left.positions, chart_left.houses, left_objects
    )
  )
  right = tuple(
    HouseOverlay("right", "left", identity, house_of(longitude, chart_left.houses.cusps_deg))
    for identity, longitude in _selected_longitudes(
      chart_right.positions, chart_right.houses, right_objects
    )
  )
  return (*left, *right)


def cross_chart_house_overlays(
  chart_left: NatalChart,
  chart_right: NatalChart,
  *,
  left_objects: Sequence[ChartObject] | None = None,
  right_objects: Sequence[ChartObject] | None = None,
) -> CrossChartHouseOverlays:
  """Find the house of each selected object in the other chart.

  left_objects and right_objects select objects from their respective charts.
  None selects all bodies and nodes in that chart, without axes, independently of
  its natal aspect selection. Explicit selections may include stored axes. Their
  longitudes come from the actual axis fields, not cusps or calculated opposites.
  Bodies and nodes follow chart order, then selected axes follow in ASC/MC/DSC/IC order.

  An empty selection skips placements of that chart's objects, but its houses are
  still used for the other chart's objects. Both charts and selections are checked
  even when output is empty. Same-named objects and the same chart on both sides
  are allowed. The result retains both charts and lists left objects in right
  houses before right objects in left houses.

  Placement compares stored longitudes with the other chart's cusps, in degrees,
  wrapping at 360. A longitude exactly on a cusp belongs to the house starting
  there. The charts must use the same zodiac, center and position frame. Current
  public constructors accept only tropical, geocentric positions on the true
  ecliptic and equinox of each chart's own date. Different dates, house systems,
  models and versions are retained. There is no common-epoch conversion or
  three-dimensional placement.

  Invalid types raise TypeError. Duplicate or unavailable selections and incompatible
  coordinates raise ValueError. No astronomy, time resolution, version lookup or I/O
  is performed.

  查询每个所选对象落入另一张盘的哪一宫。left_objects 和 right_objects 分别选择左右盘的对象。
  None 表示该盘的全部天体和交点，不含四轴，也不沿用本命相位的对象选择。显式选择可以包含已存轴，
  黄经从实际轴字段读取，不用宫头或计算出的对轴代替。天体和交点按盘中顺序排列，
  所选四轴随后按上升、中天、下降、天底排列。

  空选择表示不查该盘对象的落宫，但仍用它的宫位判断另一张盘对象的落宫。即使输出为空，
  两张盘和对象选择仍会接受检查。允许同名对象，也可以把同一张盘传给两边。结果保留两张盘，
  先列左盘对象在右盘的落宫，再列右盘对象在左盘的落宫。

  落宫直接比较已存黄经与另一张盘的宫头，角度以度计，跨 360 度回绕。
  黄经恰好等于宫头时，归入从该宫头开始的宫。两张盘的黄道、中心和位置坐标约定必须一致。
  当前公开构造器只接受热带地心位置，以各盘自身日期的真黄道和真春分点为基准。
  不同日期、宫制、模型和版本均保留，不转换到共同历元，也不计算三维落宫。

  类型错误抛出 TypeError；重复选择、选择盘中没有的对象或坐标约定不一致时，抛出 ValueError。
  不执行天文计算、时刻解析、版本查询或 I/O。
  """
  _require_comparable_sources(chart_left, chart_right)
  selected_left = _selection_for_chart(
    chart_left,
    chart_left.requested.objects if left_objects is None else left_objects,
    "left_objects",
  )
  selected_right = _selection_for_chart(
    chart_right,
    chart_right.requested.objects if right_objects is None else right_objects,
    "right_objects",
  )
  return CrossChartHouseOverlays(
    chart_left,
    chart_right,
    selected_left,
    selected_right,
    _placements(chart_left, chart_right, selected_left, selected_right),
  )
