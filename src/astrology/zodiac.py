"""Tropical zodiac classification over supplied longitudes, without astronomy.

对给定的黄经做热带黄道分类，不涉及天文计算。
"""

from __future__ import annotations

from enum import StrEnum

from astrology._validation import finite_number


class Sign(StrEnum):
  """One of the twelve tropical signs, identified by its 30-degree longitude sector.

  热带黄道十二星座之一，由各自 30° 的黄经区间界定。
  """

  ARIES = "aries"
  TAURUS = "taurus"
  GEMINI = "gemini"
  CANCER = "cancer"
  LEO = "leo"
  VIRGO = "virgo"
  LIBRA = "libra"
  SCORPIO = "scorpio"
  SAGITTARIUS = "sagittarius"
  CAPRICORN = "capricorn"
  AQUARIUS = "aquarius"
  PISCES = "pisces"


_SIGNS = tuple(Sign)
_SECTOR_DEGREES = 30.0
_ARC_SECONDS_PER_DEGREE = 3600


def _longitude(value: float) -> float:
  """Validate a tropical longitude in degrees. 校验以度为单位的热带黄经。"""
  try:
    degrees = finite_number(value, "longitude_deg")
  except ValueError as exc:
    raise ValueError("longitude_deg must be finite and in [0, 360)") from exc
  if not 0.0 <= degrees < 360.0:
    raise ValueError("longitude_deg must be finite and in [0, 360)")
  return degrees


def sign_of(longitude_deg: float) -> Sign:
  """Classify a tropical longitude by half-open [0, 30) degree sectors.

  Boundaries belong to the higher sign: exactly 30° is Taurus, exactly 0° is Aries.

  按半开的 [0, 30) 度区间给热带黄经分星座。区间边界归后一个星座：恰好 30° 是金牛，恰好 0° 是白羊。
  """
  return _SIGNS[int(_longitude(longitude_deg) // _SECTOR_DEGREES)]


def sign_degree(longitude_deg: float) -> float:
  """Return the unrounded degree within its sign, in [0, 30).

  返回黄经在所属星座内的未舍入度数，范围 [0, 30)。
  """
  return _longitude(longitude_deg) % _SECTOR_DEGREES


def truncate_display(longitude_deg: float) -> float:
  """Truncate toward zero at arcsecond resolution; display never crosses a boundary.

  Display rounding must not change a classification. Truncation is the named rule:
  29.9999999° displays as 29°59'59", never as 30°00'00" of the next sign.

  The arcsecond count is floored in exact integer arithmetic on the binary
  fraction, so a value that sits just below a sector boundary cannot be
  rounded up across it by the multiplication.

  向零截断到角秒；显示出来的值不会越过星座边界。显示用的舍入不能改变分类，所以
  采用截断，并把它定为具名规则：29.9999999° 显示为 29°59'59"，不会显示成下一个
  星座的 30°00'00"。角秒数按二进制分数用精确的整数运算向下取整，因此紧贴区间边界
  下方的值，不会因为乘法而被进位到边界的另一侧。
  """
  degrees = _longitude(longitude_deg)
  return _whole_arcseconds(degrees) / _ARC_SECONDS_PER_DEGREE


def _whole_arcseconds(nonnegative_degrees: float) -> int:
  """Truncate a validated finite nonnegative angle without a float multiplication.

  对已校验为有限且非负的角度做截断，不用浮点乘法。
  """
  numerator, denominator = nonnegative_degrees.as_integer_ratio()
  return numerator * _ARC_SECONDS_PER_DEGREE // denominator
