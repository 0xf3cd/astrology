"""Tropical sign sectors and Ashmand's historical sign groups, without astronomy.

热带黄道星座区间与 Ashmand 的历史星座分组，不涉及天文计算。
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType

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


class AshmandSignGroup(StrEnum):
  """One of four sign groups in Ashmand's 1822 edition, Book I, chapter XIV.

  TROPICAL means the two solstitial signs, not the whole tropical zodiac.
  A group label alone gives no chart interpretation or observed-season guarantee.

  Ashmand 1822 年版第一卷第 XIV 章的四种星座分组之一。TROPICAL 指两个至点星座，
  不是整个热带黄道。组别本身不提供命盘解读，也不保证实际季节现象。
  """

  TROPICAL = "tropical"
  EQUINOCTIAL = "equinoctial"
  FIXED = "fixed"
  BICORPOREAL = "bicorporeal"


_ASHMAND_GROUPS = MappingProxyType(
  {
    Sign.ARIES: AshmandSignGroup.EQUINOCTIAL,
    Sign.TAURUS: AshmandSignGroup.FIXED,
    Sign.GEMINI: AshmandSignGroup.BICORPOREAL,
    Sign.CANCER: AshmandSignGroup.TROPICAL,
    Sign.LEO: AshmandSignGroup.FIXED,
    Sign.VIRGO: AshmandSignGroup.BICORPOREAL,
    Sign.LIBRA: AshmandSignGroup.EQUINOCTIAL,
    Sign.SCORPIO: AshmandSignGroup.FIXED,
    Sign.SAGITTARIUS: AshmandSignGroup.BICORPOREAL,
    Sign.CAPRICORN: AshmandSignGroup.TROPICAL,
    Sign.AQUARIUS: AshmandSignGroup.FIXED,
    Sign.PISCES: AshmandSignGroup.BICORPOREAL,
  }
)


def ashmand_sign_group(sign: Sign) -> AshmandSignGroup:
  """Return a sign's group in Ashmand 1822, without a chart or I/O.

  Accept a Sign member; raw strings and unrelated enums raise TypeError.
  In zodiac order, fixed signs immediately follow tropical or equinoctial signs;
  bicorporeal signs immediately follow fixed signs. This expands the source's
  ordering, not a verbatim twelve-sign list. Source: Book I, XIV, printed pp. 34-35;
  knowledge rule: rule.ptolemy_ashmand.sign_groups.

  返回星座在 Ashmand 1822 年版中的分组，不需命盘，也不执行 I/O。只接受 Sign 成员；
  字符串或其他枚举抛出 TypeError。在黄道次序中，固定星座紧接至点星座或分点星座，
  双体星座紧接固定星座。这是按原文次序展开的名单，不是原书逐项列出的十二星座表。
  来源为第一卷第 XIV 章、印刷页 34-35；
  知识规则标识为 rule.ptolemy_ashmand.sign_groups。
  """
  if type(sign) is not Sign:
    raise TypeError("sign must be a Sign")
  return _ASHMAND_GROUPS[sign]


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
