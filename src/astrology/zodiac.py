"""Tropical zodiac classification over supplied longitudes, without astronomy.

对给定黄经做热带黄道分类，不做天文计算。
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite


class Sign(StrEnum):
  """One of the twelve tropical signs, identified by its 30-degree longitude sector.

  热带黄道十二星座之一，由 30 度黄经区间标识。
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
  if type(value) not in (int, float):
    raise TypeError("longitude_deg must be a number")
  degrees = float(value)
  if not isfinite(degrees) or not 0.0 <= degrees < 360.0:
    raise ValueError("longitude_deg must be finite and in [0, 360)")
  return degrees


def sign_of(longitude_deg: float) -> Sign:
  """Classify a tropical longitude by half-open [0, 30) degree sectors.

  Boundaries belong to the higher sign: exactly 30° is Taurus, exactly 0° is Aries.

  按半开区间 [0, 30) 度对热带黄经分类。边界归入后一个星座：恰好 30° 为金牛，恰好 0° 为白羊。
  """
  return _SIGNS[int(_longitude(longitude_deg) // _SECTOR_DEGREES)]


def sign_degree(longitude_deg: float) -> float:
  """Return the unrounded degree within its sign, in [0, 30).

  返回座内未舍入的度数，范围 [0, 30)。
  """
  return _longitude(longitude_deg) % _SECTOR_DEGREES


def truncate_display(longitude_deg: float) -> float:
  """Truncate toward zero at arcsecond resolution; display never crosses a boundary.

  Display rounding must not change a classification. Truncation is the named rule:
  29.9999999° displays as 29°59'59", never as 30°00'00" of the next sign.

  The arcsecond count is floored in exact integer arithmetic on the binary
  fraction, so a value that sits just below a sector boundary cannot be
  rounded up across it by the multiplication.

  向零截断到角秒分辨率；显示值不跨边界。展示舍入不得改变分类，截断是具名规则：
  29.9999999° 显示为 29°59'59"，不会显示成下一星座的 30°00'00"。
  角秒数在二进制分数上以精确整数运算取下整，因此紧贴区间边界之下的值
  不会因乘法而被进位到边界另一侧。
  """
  degrees = _longitude(longitude_deg)
  numerator, denominator = degrees.as_integer_ratio()
  whole_arc_seconds = numerator * _ARC_SECONDS_PER_DEGREE // denominator
  return whole_arc_seconds / _ARC_SECONDS_PER_DEGREE
