"""Fixed-instant aspects from a moving moment chart to frozen natal degrees.

计算移动时刻盘与固定本命黄经在给定时刻的相位。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from astrology._comparison import _require_comparable_sources, _selection_for_chart
from astrology.aspects import (
  AspectMotion,
  AspectObject,
  _geometry_values,
  _motion,
  _pair_geometry,
  aspect_angle,
)
from astrology.chart import MomentChart, NatalChart, _aspect_positions, _selected_longitudes
from astrology.config import AspectRule, MajorAspect, OrbCombination
from astrology.cross_aspects import _rules
from astrology.objects import ChartObject, _is_chart_object


@dataclass(frozen=True, slots=True)
class TransitAspectHit:
  """One fixed-instant hit with moving/natal roles and local motion.

  Angles and inclusive orb limits are degrees, with the same oriented branch and
  signed deviation as CrossAspectHit. Identical identities and node-node pairs
  are allowed. Motion is checked against the retained sources by TransitAspects.

  给定时刻的一条命中，区分移动与本命角色，保留局部运动。角度与包含等号的容许度上限
  以度计，有向分支及带符号偏差与 CrossAspectHit 相同。允许同名及交点间配对；
  运动状态由 TransitAspects 根据保留的来源校验。
  """

  moving_object: ChartObject
  natal_object: ChartObject
  aspect: MajorAspect
  branch_deg: float
  deviation_deg: float
  orb_limit_deg: float
  motion: AspectMotion

  def __post_init__(self) -> None:
    if not _is_chart_object(self.moving_object) or not _is_chart_object(self.natal_object):
      raise TypeError("Transit-aspect endpoints must be Body, LunarNode or Axis values")
    if type(self.aspect) is not MajorAspect:
      raise TypeError("aspect must be a MajorAspect")
    if type(self.motion) is not AspectMotion:
      raise TypeError("motion must be an AspectMotion")
    values = _geometry_values(self.aspect, self.branch_deg, self.deviation_deg, self.orb_limit_deg)
    for name, value in zip(("branch_deg", "deviation_deg", "orb_limit_deg"), values, strict=True):
      object.__setattr__(self, name, value)
    if (self.deviation_deg == 0.0) != (self.motion is AspectMotion.EXACT):
      raise ValueError("Zero deviation requires EXACT motion, and EXACT requires zero deviation")


@dataclass(frozen=True, slots=True)
class TransitAspects:
  """Retain a moving MomentChart, fixed NatalChart, explicit rules and every matching hit.

  Sequences are copied into tuples; selections follow source order, then axes.
  Construction checks the complete hit sequence, including local motion, by pure
  recomputation. Coordinate and zero-rate conventions are in entry.transit_aspects.

  保留移动 MomentChart、固定 NatalChart、显式规则及全部命中。序列复制为元组，
  选择按源盘顺序排列，四轴随后。构造时以纯规则重算完整命中序列，包括局部运动。
  坐标与零速率约定见 entry.transit_aspects。
  """

  moving_chart: MomentChart
  natal_chart: NatalChart
  moving_objects: tuple[ChartObject, ...]
  natal_objects: tuple[ChartObject, ...]
  rules: tuple[AspectRule, ...]
  combination: OrbCombination | None
  hits: tuple[TransitAspectHit, ...]

  def __post_init__(self) -> None:
    if type(self.moving_chart) is not MomentChart or type(self.natal_chart) is not NatalChart:
      raise TypeError("moving_chart must be a MomentChart and natal_chart a NatalChart")
    _require_comparable_sources(self.moving_chart, self.natal_chart)
    moving = _selection_for_chart(self.moving_chart, self.moving_objects, "moving_objects")
    natal = _selection_for_chart(self.natal_chart, self.natal_objects, "natal_objects")
    rules = _rules(self.rules, self.combination, (*moving, *natal))
    if not isinstance(self.hits, Sequence) or isinstance(self.hits, (str, bytes)):
      raise TypeError("hits must be a sequence of TransitAspectHit values")
    hits = tuple(self.hits)
    if any(type(hit) is not TransitAspectHit for hit in hits):
      raise TypeError("hits must contain only TransitAspectHit values")
    for name, value in (
      ("moving_objects", moving),
      ("natal_objects", natal),
      ("rules", rules),
      ("hits", hits),
    ):
      object.__setattr__(self, name, value)
    if hits != _hits(self.moving_chart, self.natal_chart, moving, natal, rules, self.combination):
      raise ValueError("Transit aspects differ from complete pure derivation")


def _hits(
  moving_chart: MomentChart,
  natal_chart: NatalChart,
  moving_objects: tuple[ChartObject, ...],
  natal_objects: tuple[ChartObject, ...],
  rules: tuple[AspectRule, ...],
  combination: OrbCombination | None,
) -> tuple[TransitAspectHit, ...]:
  ordered = sorted(rules, key=lambda rule: aspect_angle(rule.aspect))
  moving = _aspect_positions(moving_chart.positions, moving_chart.houses, moving_objects)
  natal = tuple(
    AspectObject(identity, longitude, 0.0)
    for identity, longitude in _selected_longitudes(
      natal_chart.positions, natal_chart.houses, natal_objects
    )
  )
  return tuple(
    TransitAspectHit(
      first.identity,
      second.identity,
      aspect,
      branch,
      deviation,
      limit,
      _motion(deviation, first, second),
    )
    for first in moving
    for second in natal
    for aspect, branch, deviation, limit in _pair_geometry(
      first.identity,
      first.longitude_deg,
      second.identity,
      second.longitude_deg,
      ordered,
      combination,
    )
  )


def transit_aspects(
  moving_chart: MomentChart,
  natal_chart: NatalChart,
  rules: Sequence[AspectRule],
  *,
  moving_objects: Sequence[ChartObject] | None = None,
  natal_objects: Sequence[ChartObject] | None = None,
  combination: OrbCombination | None = None,
) -> TransitAspects:
  """Compare a moment's moving objects with frozen natal degrees at that instant.

  Explicit rules, selections, orb combinations and ordering follow cross_chart_aspects;
  default selections use each source's bodies/nodes without axes. Empty selections
  and rules, same identities and node-node pairs are allowed. Raw geometry is
  identical to that static comparison for the same ordered pairs.

  Local motion uses the moment's rates against zero natal motion, including natal
  axes. Moving axes have no supplied rate: their non-exact hits are INDETERMINATE,
  while zero deviation remains EXACT. A local applying label does not promise a later
  exact event. Stored own-date longitudes are compared without common-epoch conversion.
  Sources are unchanged; no astronomy or time resolution is performed. Invalid source
  types raise TypeError; invalid selections/rules or incompatible frames raise ValueError.

  在给定时刻比较时刻盘的移动对象与固定本命黄经。显式规则、选择、容许度合成及排序沿用
  cross_chart_aspects；默认选择各源盘的天体和交点，不含四轴。允许空选择、空规则、同名
  对象与交点间配对；对相同有序配对，原始几何与静态比较完全相同。

  局部运动使用时刻盘速率，本命侧含四轴均为零速率。移动四轴没有提供速率，其非精确命中
  为 INDETERMINATE，偏差为零仍为 EXACT。局部入相不保证之后会有精确事件。
  比较各自日期的已存黄经，不转换共同历元。来源保持不变，不进行天文计算或时刻解析。
  来源类型错误抛出 TypeError；选择、规则非法或坐标约定不兼容时抛出 ValueError。
  """
  if type(moving_chart) is not MomentChart or type(natal_chart) is not NatalChart:
    raise TypeError("moving_chart must be a MomentChart and natal_chart a NatalChart")
  _require_comparable_sources(moving_chart, natal_chart)
  moving = _selection_for_chart(
    moving_chart,
    moving_chart.requested.objects if moving_objects is None else moving_objects,
    "moving_objects",
  )
  natal = _selection_for_chart(
    natal_chart,
    natal_chart.requested.objects if natal_objects is None else natal_objects,
    "natal_objects",
  )
  selected_rules = _rules(rules, combination, (*moving, *natal))
  return TransitAspects(
    moving_chart,
    natal_chart,
    moving,
    natal,
    selected_rules,
    combination,
    _hits(moving_chart, natal_chart, moving, natal, selected_rules, combination),
  )
