"""Oriented longitude difference and Rudhyar's eight lunation types, without astronomy.

有向黄经差与 Rudhyar 八种月相类型，不调用天文库。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from math import inf, nextafter
from typing import Literal

from astrology._validation import finite_number


class LunationType(StrEnum):
  """Rudhyar's eight angular categories; each name denotes a range, not an exact event.

  Rudhyar 的八种角度分类；每个名称表示一段区间，不表示精确天象事件。
  """

  NEW_MOON = "new_moon"
  CRESCENT_MOON = "crescent_moon"
  FIRST_QUARTER = "first_quarter"
  GIBBOUS_MOON = "gibbous_moon"
  FULL_MOON = "full_moon"
  DISSEMINATING_MOON = "disseminating_moon"
  LAST_QUARTER = "last_quarter"
  BALSAMIC_MOON = "balsamic_moon"


_RULE_ID = "rule.lunation.rudhyar1950"
_SECTOR_DEGREES = 45
_INTERVALS = tuple(
  (phase, index * _SECTOR_DEGREES, (index + 1) * _SECTOR_DEGREES)
  for index, phase in enumerate(LunationType)
)


@dataclass(frozen=True, slots=True)
class LunarPhaseResult:
  """A normalized Moon-minus-Sun angle in degrees, with derived type, direction and rule ID.

  Construction requires a finite angle in [0, 360); invalid types/ranges raise
  TypeError/ValueError. Labels derive from this angle, never from rounded display.
  This is neither a 3D phase angle nor an illuminated fraction or event search.

  归一化的月减日角度（度），附由角度推导的类型、盈亏方向和规则标识。构造要求有限的
  [0, 360) 内角度；类型或范围非法时抛出 TypeError 或 ValueError。标签从此角度推导，不由
  显示舍入值决定。这不是三维相角、照亮比例或事件搜索。
  """

  elongation_deg: float

  def __post_init__(self) -> None:
    angle = finite_number(self.elongation_deg, "elongation_deg")
    if not 0 <= angle < 360:
      raise ValueError("elongation_deg must be in [0, 360)")
    object.__setattr__(self, "elongation_deg", angle)

  @property
  def phase(self) -> LunationType:
    """Return the type in half-open 45° sectors. 返回半开 45° 区间对应的类型。"""
    return _INTERVALS[int(self.elongation_deg // _SECTOR_DEGREES)][0]

  @property
  def direction(self) -> Literal["waxing", "waning", "turning"]:
    """Label strict (0, 180) as waxing, (180, 360) as waning, and 0/180 as turning.

    严格 (0, 180) 为盈、(180, 360) 为亏，0 和 180 为转折点。
    """
    if self.elongation_deg in (0, 180):
      return "turning"
    return "waxing" if self.elongation_deg < 180 else "waning"

  @property
  def rule_id(self) -> str:
    """Return the stable classification rule ID. 返回稳定的分类规则标识。"""
    return _RULE_ID


def lunar_phase(sun_longitude_deg: float, moon_longitude_deg: float) -> LunarPhaseResult:
  """Return (Moon minus Sun) modulo 360 and its Rudhyar lunation type.

  Supply finite degrees, Sun first; whole turns are allowed. The caller must
  ensure the same instant and coordinate convention. Wrong types (including bool)
  raise TypeError; nonfinite values raise ValueError. The angle is a float
  approximation in [0, 360). Sources, boundary policies and numerical details
  are in the :doc:`summary guide <summaries>`.

  返回（月亮减太阳）模 360 的角度及 Rudhyar 月相类型。输入依次为太阳、月亮黄经，
  单位为有限度数，可包含整圈；调用方须保证同一时刻和坐标约定。类型非法（包括 bool）
  抛出 TypeError，非有限值抛出 ValueError。返回角度为 [0, 360) 内的浮点近似值。
  来源、边界约定及数值细节见 :doc:`摘要指南 <summaries>`。
  """
  sun = finite_number(sun_longitude_deg, "sun_longitude_deg")
  moon = finite_number(moon_longitude_deg, "moon_longitude_deg")
  exact = (Fraction(moon) - Fraction(sun)) % 360
  sector = int(exact // _SECTOR_DEGREES)
  _, lower, upper = _INTERVALS[sector]
  angle = float(exact)
  # Preserve the interval side and exact turning points when float conversion rounds to a boundary.
  # 转为浮点时若舍入到边界，保留区间一侧及精确转折点的区别。
  if angle == lower and exact > lower:
    angle = nextafter(angle, inf)
  elif angle >= upper:
    angle = nextafter(float(upper), float(lower))
  return LunarPhaseResult(angle)
