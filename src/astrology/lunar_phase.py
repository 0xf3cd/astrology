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
  """Classify (Moon minus Sun) modulo 360 under Rudhyar's eight-type convention.

  Arguments are Sun first, Moon second, in finite degrees, with any number of
  turns. The caller must supply the same instant and coordinate convention;
  bare numbers cannot authenticate either. Wrong types (including bool) raise
  TypeError; nonfinite values raise ValueError. Inputs use finite_number's float
  conversion. Exact ratios of those binary values avoid overflow and determine
  the boundary side before float conversion. If nearest conversion erases that
  side, adjust by one adjacent float. The result is in [0, 360), not an exact
  real-valued angle. Rotating inputs can itself introduce input-rounding error.

  Source: Your Lunation Birthday, Part Four, online archival transcription,
  reporting January 1950 publication. The project assigns exact multiples of
  45° to the following interval. Whole categories are not exact lunar events;
  direction describes the supplied arc, not a prediction from motion rates.

  按 Rudhyar 八分型对（月亮减太阳）模 360 分类。参数依次为太阳、月亮，单位为有限的度数，
  可包含任意整圈。调用方须保证同一时刻和坐标约定；裸数值无法核实这两项。类型非法（包括
  bool）抛出 TypeError，非有限值抛出 ValueError。输入按 finite_number 转为浮点值，再以
  这些二进制值的精确比值避免溢出，并在转回浮点前判断边界一侧；若最近浮点值抹去该侧，
  则移到相邻浮点值。结果在 [0, 360)，不是精确实数角度；旋转输入本身可能引入输入舍入误差。
  来源为 Your Lunation Birthday 第四部分的在线档案转录，页面自述发表于 1950 年 1 月。
  项目把恰好 45° 的整数倍归后段。整个类别不是精确月相事件；方向描述给定弧，不根据速率预测运动。
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
