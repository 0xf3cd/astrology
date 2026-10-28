"""Find major aspects from longitudes and rates at a given instant.

Each result records the angle measured from the first object to the second, the
exact aspect angle used for comparison (the branch), and the signed difference.
The motion status tells whether the magnitude of that difference is shrinking or growing.
It does not predict later changes in motion or whether the aspect will become
exact. This module needs no chart and does not call the astronomy library.

根据同一时刻的黄经和速率判断主要相位。每条结果记录从第一个对象到第二个对象的角度、
用来对照的精确相位角（分支），以及两者的带符号偏差。运动状态说明偏差的绝对值此刻在缩小还是增大，
不预测之后的运动变化，也不预测相位之后会不会变得精确。本模块不需要命盘，也不调用天文库。
"""

from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import remainder

from astrology._validation import finite_number
from astrology.config import AspectRule, MajorAspect, OrbCombination
from astrology.objects import ChartObject, LunarNode, _is_chart_object

_HALF_MAXIMUM = sys.float_info.max / 2.0

_ANGLES: dict[MajorAspect, float] = {
  MajorAspect.CONJUNCTION: 0.0,
  MajorAspect.SEXTILE: 60.0,
  MajorAspect.SQUARE: 90.0,
  MajorAspect.TRINE: 120.0,
  MajorAspect.OPPOSITION: 180.0,
}


class AspectMotion(StrEnum):
  """Whether an aspect is approaching or moving away from its exact angle at this instant.

  The relative longitude rate is the second object's rate minus the first's. Away
  from a deviation of 180 degrees, the deviation shrinks in magnitude when the
  relative rate and the deviation have opposite signs (applying) and grows when
  they have the same sign (separating). Statuses compare exact floats, with no
  tolerance. `STATIONARY` means the relative rate is exactly zero, not that either
  planet has stopped changing longitude (a station). `INDETERMINATE` means a rate
  is missing, or the deviation is 180 degrees with nonzero relative motion:
  its magnitude has no two-sided derivative there.

  相位此刻在接近还是远离精确角度。相对黄经速率是第二个对象的速率减去第一个的速率。
  偏差不为 180 度时，相对速率与偏差异号，偏差的绝对值在缩小（入相）；同号时在增大（离相）。
  直接比较浮点数，不使用容差。`STATIONARY` 指相对速率恰为零，
  不表示某颗行星的黄经速率为零（占星术语中的“留”）。
  `INDETERMINATE` 指缺少速率，或偏差恰为 180 度且存在相对运动，此时偏差的绝对值没有双侧导数。
  """

  APPLYING = "applying"
  SEPARATING = "separating"
  EXACT = "exact"
  STATIONARY = "stationary"
  INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class AspectObject:
  """One object's longitude in degrees and its rate in degrees per day, if it has one.

  The rate may be None where no meaningful motion exists; it is never borrowed from
  another object. All rates must use the same day unit, such as the TT day.

  一个对象的黄经（度）及其速率（度/日，可为 None）。若无法给出有意义的速率，就用 None，
  不借用其他对象的速率。所有速率必须采用相同的日作为时间单位，例如 TT 日。
  """

  identity: ChartObject
  longitude_deg: float
  longitude_rate_deg_per_day: float | None

  def __post_init__(self) -> None:
    if not _is_chart_object(self.identity):
      raise TypeError("identity must be a Body, LunarNode or Axis")
    object.__setattr__(self, "longitude_deg", finite_number(self.longitude_deg, "longitude_deg"))
    if self.longitude_rate_deg_per_day is not None:
      object.__setattr__(
        self,
        "longitude_rate_deg_per_day",
        finite_number(self.longitude_rate_deg_per_day, "longitude_rate_deg_per_day"),
      )


@dataclass(frozen=True, slots=True)
class AspectHit:
  """One aspect between two objects; the order of the pair and the branch are kept.

  `branch_deg` is the exact oriented angle from the first object to the second that
  the separation was measured against: minus or plus the aspect angle for a sextile,
  square or trine, and the single angle 0 or 180 for a conjunction or opposition.
  `deviation_deg` is the separation minus the branch, in (-180, 180]. Swapping the
  pair flips the deviation, except that 180 is its own mirror, and flips the branch
  where there are two; the status does not change.

  两个对象之间符合规则的一条相位结果，保留对象顺序和分支。`branch_deg` 是用来对照间距的
  精确角度，方向从第一个对象指向第二个：六分、四分、三分相取相位角的负值或正值，合相和对分相只有
  0 或 180 这一个角度。`deviation_deg` 是间距减去分支，取值在 (-180, 180]。交换配对时，
  偏差反号，但 180 仍记为 180；有两个分支时，分支也反号。运动状态不变。
  """

  first: ChartObject
  second: ChartObject
  aspect: MajorAspect
  branch_deg: float
  deviation_deg: float
  orb_limit_deg: float
  motion: AspectMotion

  def __post_init__(self) -> None:
    if not _is_chart_object(self.first) or not _is_chart_object(self.second):
      raise TypeError("Aspect endpoints must be Body, LunarNode or Axis values")
    if self.first == self.second or (
      isinstance(self.first, LunarNode) and isinstance(self.second, LunarNode)
    ):
      raise ValueError("An aspect needs distinct endpoints, not two lunar nodes")
    if type(self.aspect) is not MajorAspect or type(self.motion) is not AspectMotion:
      raise TypeError("aspect and motion must use their owning enum types")
    values = _geometry_values(self.aspect, self.branch_deg, self.deviation_deg, self.orb_limit_deg)
    for name, value in zip(("branch_deg", "deviation_deg", "orb_limit_deg"), values, strict=True):
      object.__setattr__(self, name, value)
    if (self.deviation_deg == 0.0) != (self.motion is AspectMotion.EXACT):
      raise ValueError("Only a zero deviation has exact motion status")


def _signed(angle: float) -> float:
  """Wrap an angle to (-180, 180], preserving small values near zero.

  将角度折回 (-180, 180]，保留接近零的小角度。
  """
  value = remainder(angle, 360.0)
  return 180.0 if value == -180.0 else value


def _deviation(separation: float, branch: float) -> float:
  """Separation minus branch in (-180, 180], with 180 as its own mirror.

  For the branch 180, `remainder` of a sum near -360 rounds to zero while the mirrored
  pair stays a few ulps away, which would make the two orders disagree on the status.
  Adding or subtracting 180 by the sign of the separation keeps both exact near zero.

  间距减去分支，结果折回 (-180, 180]；交换对象后，180 仍记为正值。
  分支为 180 时，直接相减再用 `remainder` 可能把接近 -360 的结果舍入成零，
  交换对象后却仍差几个 ulp，导致两种顺序的运动状态不同。
  按间距的正负选择加或减 180，可以保留两种顺序下接近零的偏差。
  """
  if branch == 180.0:
    return _signed(separation - 180.0 if separation > 0.0 else separation + 180.0)
  return _signed(separation - branch)


def aspect_angle(aspect: MajorAspect) -> float:
  """Return the exact angle of an aspect in degrees: 0, 60, 90, 120 or 180.

  返回相位的精确角度（度）：0、60、90、120 或 180。
  """
  if not isinstance(aspect, MajorAspect):
    raise TypeError("aspect must be a MajorAspect")
  return _ANGLES[aspect]


def _branches(angle: float) -> tuple[float, ...]:
  if angle in (0.0, 180.0):
    return (angle,)
  return (-angle, angle)


def _geometry_values(
  aspect: MajorAspect, branch_deg: float, deviation_deg: float, orb_limit_deg: float
) -> tuple[float, float, float]:
  """Validate the shared geometric fields of an aspect hit. 校验相位命中共用的几何字段。"""
  branch = finite_number(branch_deg, "branch_deg")
  deviation = finite_number(deviation_deg, "deviation_deg")
  limit = finite_number(orb_limit_deg, "orb_limit_deg")
  if branch not in _branches(aspect_angle(aspect)):
    raise ValueError("branch_deg does not belong to the aspect")
  if not -180.0 < deviation <= 180.0:
    raise ValueError("deviation_deg must be in (-180, 180]")
  if limit < 0.0 or abs(deviation) > limit:
    raise ValueError("The aspect deviation must be within its nonnegative orb limit")
  return branch, deviation, limit


def _mean(first: float, second: float) -> float:
  """Return the correctly rounded mean of two finite nonnegative numbers, never infinite.

  `(first + second) / 2` rounds once, even into the subnormal range, as long as the sum
  does not overflow. When either number is above half the largest float the sum might
  overflow, so both are halved first; a number that large has a rounding step so coarse
  that halving a tiny partner cannot change the result.

  返回两个有限非负数正确舍入后的平均值，结果不会是无穷。只要和不溢出，`(first + second) / 2`
  只舍入一次，次正规数范围内也是如此。任一数大于最大浮点数的一半时，和可能溢出，就先各自除以
  2；这么大的数，相邻浮点值之间的间隔也很大，另一个很小的数除以 2 不会改变结果。
  """
  if first > _HALF_MAXIMUM or second > _HALF_MAXIMUM:
    return first / 2.0 + second / 2.0
  return (first + second) / 2.0


def _limit(
  rule: AspectRule,
  first: ChartObject,
  second: ChartObject,
  combination: OrbCombination | None,
) -> float:
  own = {entry.identity: entry.orb_degrees for entry in rule.object_orbs}
  first_orb = own.get(first, rule.orb_degrees)
  second_orb = own.get(second, rule.orb_degrees)
  if combination is OrbCombination.BOTH_WITHIN_OWN_ORB:
    return min(first_orb, second_orb)
  if combination is OrbCombination.MEAN_OF_ORBS:
    return _mean(first_orb, second_orb)
  return max(first_orb, second_orb)


def _motion(deviation: float, first: AspectObject, second: AspectObject) -> AspectMotion:
  if deviation == 0.0:
    return AspectMotion.EXACT
  if first.longitude_rate_deg_per_day is None or second.longitude_rate_deg_per_day is None:
    return AspectMotion.INDETERMINATE
  relative = second.longitude_rate_deg_per_day - first.longitude_rate_deg_per_day
  if relative == 0.0:
    return AspectMotion.STATIONARY
  if deviation == 180.0:
    return AspectMotion.INDETERMINATE
  return AspectMotion.SEPARATING if (deviation > 0.0) == (relative > 0.0) else AspectMotion.APPLYING


def _pair_geometry(
  first: ChartObject,
  first_longitude_deg: float,
  second: ChartObject,
  second_longitude_deg: float,
  ordered_rules: Sequence[AspectRule],
  combination: OrbCombination | None,
) -> Iterator[tuple[MajorAspect, float, float, float]]:
  """Yield matching geometry in supplied rule order; eligibility and motion belong to callers.

  按传入的规则顺序产出几何命中；配对准入与运动状态由调用方负责。
  """
  separation = _signed(_signed(second_longitude_deg) - _signed(first_longitude_deg))
  for rule in ordered_rules:
    limit = _limit(rule, first, second, combination)
    for branch in _branches(_ANGLES[rule.aspect]):
      deviation = _deviation(separation, branch)
      if abs(deviation) <= limit:
        yield rule.aspect, branch, deviation, limit


def find_aspects(
  objects: Sequence[AspectObject],
  rules: Sequence[AspectRule],
  combination: OrbCombination | None = None,
) -> tuple[AspectHit, ...]:
  """Return every aspect that holds between pairs of objects, in a fixed order.

  Pairs follow the order of `objects`, then the aspect angle, then the branch (minus
  before plus), so the order is total. Every matching aspect and branch is returned:
  broad orbs may give one pair several hits, and none is dropped in favor of a nearer
  one. A hit holds when the deviation's magnitude is at most the limit, with the limit
  itself included. The limit is the rule's orb, or the combination of the two objects'
  orbs when the rule has per-object orbs, which then requires `combination`. Two lunar
  nodes never form an aspect: the four identities are one pair of nodes under two
  definitions and two directions. Axes may pair with any other distinct identity,
  including an opposite axis; their identities and all matching branches remain separate.

  按固定顺序返回对象两两之间符合规则的所有相位。配对按 `objects` 的顺序排列，再按相位角排序，
  同一相位的负分支排在正分支之前。容许度较宽时，同一对对象可能符合多个相位或分支，都会返回，
  不会只保留偏差最小的一个。偏差的绝对值不超过容许度上限就算符合，等于上限也算。
  上限通常是规则的容许度；规则给对象单独设置容许度时，上限由两个对象的容许度合成，
  此时必须给出 `combination`。两个月交点之间不构成相位：四个标识表示同一对交点的两种定义和两个方向。
  四轴可与任一不同身份配对，包括其对轴；各身份及全部命中分支分别保留。
  """
  if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
    raise TypeError("objects must be a sequence of AspectObject values")
  members = tuple(objects)
  if any(type(member) is not AspectObject for member in members):
    raise TypeError("objects must contain only AspectObject values")
  if len({member.identity for member in members}) != len(members):
    raise ValueError("objects must not contain duplicate identities")
  if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes)):
    raise TypeError("rules must be a sequence of AspectRule values")
  ordered = tuple(rules)
  if any(type(rule) is not AspectRule for rule in ordered):
    raise TypeError("rules must contain only AspectRule values")
  if len({rule.aspect for rule in ordered}) != len(ordered):
    raise ValueError("rules must not repeat an aspect identity")
  if combination is not None and not isinstance(combination, OrbCombination):
    raise TypeError("combination must be an OrbCombination")
  if combination is None and any(rule.object_orbs for rule in ordered):
    raise ValueError("combination is required when rules have object orbs")

  by_angle = sorted(ordered, key=lambda rule: _ANGLES[rule.aspect])
  hits: list[AspectHit] = []
  for index, first in enumerate(members):
    for second in members[index + 1 :]:
      if isinstance(first.identity, LunarNode) and isinstance(second.identity, LunarNode):
        continue
      for aspect, branch, deviation, limit in _pair_geometry(
        first.identity,
        first.longitude_deg,
        second.identity,
        second.longitude_deg,
        by_angle,
        combination,
      ):
        hits.append(
          AspectHit(
            first.identity,
            second.identity,
            aspect,
            branch,
            deviation,
            limit,
            _motion(deviation, first, second),
          )
        )
  return tuple(hits)
