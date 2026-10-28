"""Static major aspects between two supplied natal results, without astronomy or motion.

对两张给定本命盘结果判断静态主要相位，不调用天文库，也不判断运动状态。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from astrology.aspects import _geometry_values, _pair_geometry, aspect_angle
from astrology.chart import NatalChart, _aspect_positions
from astrology.config import AspectRule, MajorAspect, OrbCombination
from astrology.objects import Axis, ChartObject, _is_chart_object


@dataclass(frozen=True, slots=True)
class CrossAspectHit:
  """A static hit with distinct left/right roles, even when the object identities match.

  Angles are degrees. Branch and signed deviation follow `AspectHit` geometry;
  `orb_limit_deg` is the inclusive limit actually used. There is no motion field:
  rates at separate birth instants do not define a shared time evolution.

  一条静态相位命中，保留左右角色，即使两侧对象标识相同。角度单位为度；分支与带符号偏差
  遵循 `AspectHit` 的几何定义，`orb_limit_deg` 是实际采用且包含等号的上限。不设运动字段：
  两次出生时刻的速率不能定义共同的时间演化。
  """

  left_object: ChartObject
  right_object: ChartObject
  aspect: MajorAspect
  branch_deg: float
  deviation_deg: float
  orb_limit_deg: float

  def __post_init__(self) -> None:
    if not _is_chart_object(self.left_object) or not _is_chart_object(self.right_object):
      raise TypeError("Cross-aspect endpoints must be Body, LunarNode or Axis values")
    if type(self.aspect) is not MajorAspect:
      raise TypeError("aspect must be a MajorAspect")
    values = _geometry_values(self.aspect, self.branch_deg, self.deviation_deg, self.orb_limit_deg)
    for name, value in zip(("branch_deg", "deviation_deg", "orb_limit_deg"), values, strict=True):
      object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class CrossChartAspects:
  """Immutable sources, effective selections, explicit rules and all static cross hits.

  `chart_left` and `chart_right` retain the complete source charts unchanged.
  Sequences are isolated in tuples; selections follow their source's position order,
  then selected axes in ASC/MC/DSC/IC order.
  Construction recomputes all hits from the two sources, selections and rules and rejects any difference.
  It does not authenticate the sources' astronomical values or provenance labels.

  不可变的双侧来源、实际参与对象、显式规则与全部静态交叉命中。`chart_left` 与 `chart_right`
  保留两张完整源盘，不改变它们。
  序列复制为元组；天体和交点按各自源盘的位置顺序排列，所选四轴按上升、中天、下降、天底顺序追加。
  构造时按两侧来源、选择和规则重算全部命中，拒绝任何差异，
  不认证源盘的天文值或来源标签是否真实。
  """

  chart_left: NatalChart
  chart_right: NatalChart
  left_objects: tuple[ChartObject, ...]
  right_objects: tuple[ChartObject, ...]
  rules: tuple[AspectRule, ...]
  combination: OrbCombination | None
  hits: tuple[CrossAspectHit, ...]

  def __post_init__(self) -> None:
    _sources(self.chart_left, self.chart_right)
    left_objects = _selection(self.chart_left, self.left_objects, "left_objects")
    right_objects = _selection(self.chart_right, self.right_objects, "right_objects")
    rules = _rules(self.rules, self.combination, (*left_objects, *right_objects))
    if not isinstance(self.hits, Sequence) or isinstance(self.hits, (str, bytes)):
      raise TypeError("hits must be a sequence of CrossAspectHit values")
    hits = tuple(self.hits)
    if any(type(hit) is not CrossAspectHit for hit in hits):
      raise TypeError("hits must contain only CrossAspectHit values")
    for name, value in (
      ("left_objects", left_objects),
      ("right_objects", right_objects),
      ("rules", rules),
      ("hits", hits),
    ):
      object.__setattr__(self, name, value)
    if hits != _hits(
      self.chart_left, self.chart_right, left_objects, right_objects, rules, self.combination
    ):
      raise ValueError("Cross hits differ from complete pure derivation")


def _sources(chart_left: NatalChart, chart_right: NatalChart) -> None:
  if type(chart_left) is not NatalChart or type(chart_right) is not NatalChart:
    raise TypeError("chart_left and chart_right must be NatalChart values")
  if (
    chart_left.requested.zodiac != chart_right.requested.zodiac
    or chart_left.requested.center != chart_right.requested.center
    or chart_left.provenance.position_frame != chart_right.provenance.position_frame
  ):
    raise ValueError("Cross charts must use matching zodiac, center and position frame")


def _selection(
  chart: NatalChart, objects: Sequence[ChartObject], name: str
) -> tuple[ChartObject, ...]:
  if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
    raise TypeError(f"{name} must be a sequence of Body, LunarNode or Axis values")
  selected = tuple(objects)
  if any(not _is_chart_object(value) for value in selected):
    raise TypeError(f"{name} must contain Body, LunarNode or Axis values")
  if len(set(selected)) != len(selected):
    raise ValueError(f"{name} must not contain duplicate identities")
  available: tuple[ChartObject, ...] = (*[position.identity for position in chart.positions], *Axis)
  if not set(selected) <= set(available):
    raise ValueError(f"{name} must name only objects available in its source chart")
  return tuple(identity for identity in available if identity in selected)


def _rules(
  rules: Sequence[AspectRule],
  combination: OrbCombination | None,
  participants: tuple[ChartObject, ...],
) -> tuple[AspectRule, ...]:
  if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes)):
    raise TypeError("rules must be a sequence of AspectRule values")
  snapshot = tuple(rules)
  if any(type(rule) is not AspectRule for rule in snapshot):
    raise TypeError("rules must contain only AspectRule values")
  if len({rule.aspect for rule in snapshot}) != len(snapshot):
    raise ValueError("rules must not repeat an aspect identity")
  if combination is not None and type(combination) is not OrbCombination:
    raise TypeError("combination must be an OrbCombination or None")
  has_overrides = any(rule.object_orbs for rule in snapshot)
  if has_overrides and combination is None:
    raise ValueError("combination is required when rules have object orbs")
  if not has_overrides and combination is not None:
    raise ValueError("combination requires rules with object orbs")
  if any(entry.identity not in participants for rule in snapshot for entry in rule.object_orbs):
    raise ValueError("object orbs may name only selected objects from either chart")
  return snapshot


def _hits(
  chart_left: NatalChart,
  chart_right: NatalChart,
  left_objects: tuple[ChartObject, ...],
  right_objects: tuple[ChartObject, ...],
  rules: tuple[AspectRule, ...],
  combination: OrbCombination | None,
) -> tuple[CrossAspectHit, ...]:
  ordered = sorted(rules, key=lambda rule: aspect_angle(rule.aspect))
  left_positions = _aspect_positions(chart_left.positions, chart_left.houses, left_objects)
  right_positions = _aspect_positions(chart_right.positions, chart_right.houses, right_objects)
  return tuple(
    CrossAspectHit(first.identity, second.identity, aspect, branch, deviation, limit)
    for first in left_positions
    for second in right_positions
    for aspect, branch, deviation, limit in _pair_geometry(
      first.identity,
      first.longitude_deg,
      second.identity,
      second.longitude_deg,
      ordered,
      combination,
    )
  )


def cross_chart_aspects(
  chart_left: NatalChart,
  chart_right: NatalChart,
  rules: Sequence[AspectRule],
  *,
  left_objects: Sequence[ChartObject] | None = None,
  right_objects: Sequence[ChartObject] | None = None,
  combination: OrbCombination | None = None,
) -> CrossChartAspects:
  """Compare each selected left position with every selected right position, without motion.

  None selects all bodies/nodes on that side and no axes, independently of natal participants;
  explicit selections may include any of its stored axes, even if absent from natal
  aspects. Read the actual axis fields, never cusps or synthesized opposite axes.
  an empty selection or rule sequence is valid. Same identities, node-node pairs
  and the same chart in both roles are allowed. Rules are explicit and never
  inherited. Object-orb overrides apply by identity on either side and may name
  only selected objects; a combination is required exactly when overrides exist.
  Duplicate rules/participants and unavailable objects are rejected.

  Selected axes follow bodies/nodes in ASC/MC/DSC/IC order. Axis-axis and opposite-axis
  pairs are retained, not folded. Every matching branch is returned, ordered by left position, right position,
  ascending aspect angle, then negative before positive branch. The inclusive
  limits and signed deviations are in degrees. Both charts must have matching
  zodiac, center and position frame. Their own-date tropical longitudes are
  compared without common-epoch conversion or a simultaneous spatial-angle claim.
  Different dates, locations, house systems, models and version labels are kept,
  not automatically rejected. No I/O, time resolution, version lookup or native
  astronomy is performed; source charts are retained unchanged.

  将每个所选左盘位置与每个所选右盘位置比较，不判断运动状态。None 选该侧全部天体和交点，不加入四轴；
  显式选择可含该盘任一已存轴，即使未参与本命相位。直接读取轴字段，不使用宫头或合成对轴。
  不继承本命相位参与者；空选择和空规则合法。允许同名对象、跨盘交点配对及同一张盘占两个角色。
  规则须显式给出，不继承源盘规则。对象容许度按标识作用于两侧，只能指向所选对象；有覆盖时
  必须给合成方式，无覆盖时不能给。拒绝重复规则、重复参与对象及源盘没有的对象。
  所选四轴在天体和交点之后按上升、中天、下降、天底顺序排列。保留轴间及对轴配对，不折叠身份。
  返回全部命中分支，按左位置、右位置、相位角升序及负分支在前排序。容许度包含等号，
  带符号偏差和上限以度计。两盘的黄道、中心和位置坐标约定须一致；比较各自日期的热带黄经，
  不转换共同历元，也不声称是同时刻的空间角。保留不同日期、地点、宫制、模型和版本标签，
  不因此自动拒绝。不执行 I/O、时刻解析、版本查询或原生天文；源盘保持不变。
  """
  _sources(chart_left, chart_right)
  selected_left = _selection(
    chart_left,
    chart_left.requested.objects if left_objects is None else left_objects,
    "left_objects",
  )
  selected_right = _selection(
    chart_right,
    chart_right.requested.objects if right_objects is None else right_objects,
    "right_objects",
  )
  requested_rules = _rules(rules, combination, (*selected_left, *selected_right))
  hits = _hits(chart_left, chart_right, selected_left, selected_right, requested_rules, combination)
  return CrossChartAspects(
    chart_left, chart_right, selected_left, selected_right, requested_rules, combination, hits
  )
