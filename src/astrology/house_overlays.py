"""Place selected objects from either supplied chart in the other chart's houses.

将两张给定命盘各自选中的对象，分别归入另一张盘的宫位。
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
  """An object's house in the other source, with explicit opposite left/right owners.

  `identity` is a Body, LunarNode or Axis. `house` is an integer in 1..12, not bool.
  Source-relative geometry is checked by CrossChartHouseOverlays, not this row alone.

  一个对象落入另一张源盘的宫位；对象所属侧和宫位所属侧显式区分，须为相反的 left/right。
  identity 为 Body、LunarNode 或 Axis；house 是 1..12 的整数，不接受 bool。
  单条记录不校验源盘几何，由 CrossChartHouseOverlays 校验。
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
  """Immutable sources, effective selections and every directional house placement.

  Sources remain unchanged. Sequences are isolated in tuples; selections follow
  source position order, then ASC/MC/DSC/IC. Placements run left objects in right
  houses, then right objects in left houses. Construction recomputes that complete
  sequence and rejects any difference. It does not authenticate astronomical origin.

  不可变的双侧源盘、实际对象选择及全部双向落宫。源盘保持不变；序列复制为元组。
  选择按源位置顺序排列，再接上升、中天、下降、天底；落宫先列左对象入右宫，再列右对象入左宫。
  构造时重算完整落宫序列，拒绝任何差异；不认证源盘的天文来源。
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
  """Place each side's selected stored longitudes in the other side's supplied houses.

  None selects that side's bodies/nodes, without axes or inherited natal participants.
  Explicit selections may include stored axes; their fields, not cusps or synthesized
  opposites, supply the longitudes. Selections use source order, then ASC/MC/DSC/IC.
  Empty selections are valid and suppress only their own direction. Both sources and
  requests are validated even for empty output. Same-named objects and the same chart
  in both roles are allowed. The result retains both sources and orders left-to-right
  placements before right-to-left placements. A longitude exactly on a cusp belongs
  to the house starting there; angles are degrees, with membership wrapping at 360.

  Sources must match in zodiac, center and position frame; current public constructors
  admit only the tropical/geocentric own-date convention. Different dates, house
  systems, models and versions are retained. This directly compares stored longitudes
  with receiving cusps, without common-epoch conversion or three-dimensional placement.
  Bad types raise TypeError; duplicate/unavailable selections or incompatible sources
  raise ValueError. No astronomy, time resolution, version lookup or I/O is performed.

  将每侧选中的已存黄经归入另一侧的给定宫位。None 选该侧天体和交点，不加入四轴，
  也不继承本命相位参与者。显式选择可含已存轴，读取其字段，不用宫头或合成对轴。
  对象按源顺序排列，再接上升、中天、下降、天底。空选择合法，只取消其自身方向；
  即使输出为空，仍校验双侧源盘和请求。允许同名对象及同一张盘占两侧角色；保留双源，
  先列左对象入右宫，再列右对象入左宫。恰在宫头的黄经归入从该宫头开始的宫；角度以度计，
  落宫跨 360 度回绕。

  双源的黄道、中心和位置坐标约定须一致；当前公开构造器只接纳各自日期的热带地心约定。
  不同日期、宫制、模型和版本均保留。直接比较已存黄经与接收盘宫头，不转换共同历元，
  也不计算三维落宫。类型错误抛出 TypeError；重复或不可用对象、源盘坐标不兼容抛出 ValueError。
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
