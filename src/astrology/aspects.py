"""Major aspects between ecliptic longitudes at one instant, with local motion status.

An aspect is a signed deviation of the oriented longitude separation from an exact
angle. Orientation is kept: the separation runs from the first object to the second,
and each hit records which exact angle (branch) it was measured against. The status
comes from the rate of that deviation at the instant and says nothing about a later
station. Nothing here depends on astronomy or on the chart.

某一时刻黄经之间的主要相位，以及局部运动状态。相位是有向黄经间距相对精确角度的带符号偏差。
方向保留：间距从第一个对象指向第二个，每次命中都记录它相对哪个精确角度（分支）度量。状态
来自该时刻偏差的变化率，不预言之后的留。这里不依赖天文计算，也不依赖命盘。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite, remainder
from typing import cast

from astrology.config import AspectRule, Body, LunarNode, MajorAspect, OrbCombination

_ANGLES: dict[MajorAspect, float] = {
  MajorAspect.CONJUNCTION: 0.0,
  MajorAspect.SEXTILE: 60.0,
  MajorAspect.SQUARE: 90.0,
  MajorAspect.TRINE: 120.0,
  MajorAspect.OPPOSITION: 180.0,
}


class AspectMotion(StrEnum):
  """Local motion of an aspect at the instant, from the sign of the deviation and its rate.

  The relative longitude rate is the second object's rate minus the first's. The
  deviation shrinks in magnitude when the relative rate and the deviation have
  opposite signs (applying) and grows when they have the same sign (separating).
  Statuses compare exact floats, with no
  hidden tolerance. `STATIONARY` means the relative rate is exactly zero, which is not
  a planet's own station. `INDETERMINATE` means a rate is missing.

  某一时刻相位的局部运动，由偏差的符号及其变化率得出。相对黄经速率是第二个对象的速率减去
  第一个的速率。相对速率与偏差异号时，偏差的绝对值在缩小（入相）；同号时在增大（离相）。
  各状态比较的是确切的浮点数，没有隐含的容差。`STATIONARY` 指相对速率恰为零，不是某颗行星自己的留。
  `INDETERMINATE` 指缺少速率。
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
  another object. All objects must use the same day, such as the TT day.

  一个对象的黄经（度）及其速率（度每日，若有）。没有有意义的运动时速率可为 None；
  绝不借用别的对象的速率。所有对象必须用同一种日，例如 TT 日。
  """

  identity: Body | LunarNode
  longitude_deg: float
  longitude_rate_deg_per_day: float | None

  def __post_init__(self) -> None:
    if not isinstance(self.identity, (Body, LunarNode)):
      raise TypeError("identity must be a Body or LunarNode")
    object.__setattr__(self, "longitude_deg", _finite(self.longitude_deg, "longitude_deg"))
    if self.longitude_rate_deg_per_day is not None:
      object.__setattr__(
        self,
        "longitude_rate_deg_per_day",
        _finite(self.longitude_rate_deg_per_day, "longitude_rate_deg_per_day"),
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

  两个对象之间的一次相位；保留配对的顺序和分支。`branch_deg` 是间距所对照的、从第一个对象
  指向第二个的有向精确角度：六分、四分、三分相取相位角的负值或正值，合相和对分相只有
  0 或 180 这一个角度。`deviation_deg` 是间距减去分支，取值在 (-180, 180]。交换配对时，
  偏差反号（180 是自己的镜像，不变），有两个分支的相位分支也反号；状态不变。
  """

  first: Body | LunarNode
  second: Body | LunarNode
  aspect: MajorAspect
  branch_deg: float
  deviation_deg: float
  orb_limit_deg: float
  motion: AspectMotion


def _finite(value: object, name: str) -> float:
  if type(value) not in (int, float):
    raise TypeError(f"{name} must be a number, not bool")
  try:
    number = float(cast("int | float", value))
  except OverflowError as exc:
    raise ValueError(f"{name} must be finite") from exc
  if not isfinite(number):
    raise ValueError(f"{name} must be finite")
  return number


def _signed(angle: float) -> float:
  """Reduce an angle to (-180, 180] without losing small values. 把角度化到 (-180, 180]，不丢小量。"""
  value = remainder(angle, 360.0)
  return 180.0 if value == -180.0 else value


def _deviation(separation: float, branch: float) -> float:
  """Separation minus branch in (-180, 180], so that swapping a pair negates it exactly.

  For the branch 180, `remainder` of a sum near -360 rounds to zero while the mirrored
  pair stays a few ulps away, which would make the two orders disagree on the status.
  Adding or subtracting 180 by the sign of the separation keeps both exact near zero.

  间距减去分支，取值在 (-180, 180]，使交换配对后正好变号。分支为 180 时，接近 -360 的和经
  `remainder` 可能舍入成零，而镜像那一对仍差几个 ulp，两种顺序对状态的判断就会不一致。
  按间距的正负加或减 180，两边在接近零处都是精确的。
  """
  if branch == 180.0:
    return separation - 180.0 if separation > 0.0 else separation + 180.0
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


def _limit(
  rule: AspectRule,
  first: Body | LunarNode,
  second: Body | LunarNode,
  combination: OrbCombination | None,
) -> float:
  own = {entry.identity: entry.orb_degrees for entry in rule.object_orbs}
  first_orb = own.get(first, rule.orb_degrees)
  second_orb = own.get(second, rule.orb_degrees)
  if combination is OrbCombination.BOTH_WITHIN_OWN_ORB:
    return min(first_orb, second_orb)
  if combination is OrbCombination.MEAN_OF_ORBS:
    low, high = sorted((first_orb, second_orb))
    return low + (high - low) / 2.0
  return max(first_orb, second_orb)


def _motion(deviation: float, first: AspectObject, second: AspectObject) -> AspectMotion:
  if deviation == 0.0:
    return AspectMotion.EXACT
  if first.longitude_rate_deg_per_day is None or second.longitude_rate_deg_per_day is None:
    return AspectMotion.INDETERMINATE
  relative = second.longitude_rate_deg_per_day - first.longitude_rate_deg_per_day
  if relative == 0.0:
    return AspectMotion.STATIONARY
  return AspectMotion.SEPARATING if (deviation > 0.0) == (relative > 0.0) else AspectMotion.APPLYING


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
  definitions and two directions.

  按固定顺序返回对象两两之间成立的所有相位。顺序是：配对按 `objects` 的顺序，再按相位角，
  再按分支（负的在前），所以是全序。凡是成立的相位和分支都会返回：容许度较宽时，一对对象可能有
  多个命中，也不会为了取更近的而丢弃别的。偏差的绝对值不超过限度时成立，限度本身包含在内。
  限度是规则的容许度；规则带按对象的容许度时，是两个对象容许度的合成结果，此时必须给出
  `combination`。两个月交点之间不构成相位：四个标识只是同一对交点的两种定义和两个方向。
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
      separation = _signed(_signed(second.longitude_deg) - _signed(first.longitude_deg))
      for rule in by_angle:
        limit = _limit(rule, first.identity, second.identity, combination)
        for branch in _branches(_ANGLES[rule.aspect]):
          deviation = _deviation(separation, branch)
          if abs(deviation) <= limit:
            hits.append(
              AspectHit(
                first.identity,
                second.identity,
                rule.aspect,
                branch,
                deviation,
                limit,
                _motion(deviation, first, second),
              )
            )
  return tuple(hits)
