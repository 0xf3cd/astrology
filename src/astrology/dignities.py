"""William Lilly's 1647 sign rulers and four statuses for seven classical planets.

威廉·利利（William Lilly）1647 年版的星座守护及入庙、擢升、失势、落陷判断，
适用于太阳、月亮、水星、金星、火星、木星和土星。
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from astrology.config import Body
from astrology.zodiac import _SIGNS, Sign

_RULE_ID: Final = "rule.lilly1647.essential_dignities"
_DOMICILES: Final[Mapping[Body, tuple[Sign, ...]]] = MappingProxyType(
  {
    Body.SUN: (Sign.LEO,),
    Body.MOON: (Sign.CANCER,),
    Body.MERCURY: (Sign.GEMINI, Sign.VIRGO),
    Body.VENUS: (Sign.TAURUS, Sign.LIBRA),
    Body.MARS: (Sign.ARIES, Sign.SCORPIO),
    Body.JUPITER: (Sign.SAGITTARIUS, Sign.PISCES),
    Body.SATURN: (Sign.CAPRICORN, Sign.AQUARIUS),
  }
)
_EXALTATIONS: Final[Mapping[Body, Sign]] = MappingProxyType(
  {
    Body.SUN: Sign.ARIES,
    Body.MOON: Sign.TAURUS,
    Body.MERCURY: Sign.VIRGO,
    Body.VENUS: Sign.PISCES,
    Body.MARS: Sign.CAPRICORN,
    Body.JUPITER: Sign.CANCER,
    Body.SATURN: Sign.LIBRA,
  }
)
_RULERS: Final[Mapping[Sign, Body]] = MappingProxyType(
  {sign: body for body, signs in _DOMICILES.items() for sign in signs}
)


class DignityStatus(StrEnum):
  """The four assessed sign-level statuses, without scores. 所判断的四种星座级状态，不计分。"""

  DOMICILE = "domicile"
  EXALTATION = "exaltation"
  DETRIMENT = "detriment"
  FALL = "fall"


def sign_ruler(sign: Sign) -> Body:
  """Return the sign's ruler in Lilly's seven-planet set; a non-Sign raises TypeError.

  按 Lilly 的传统星座守护表返回守护星；非 Sign 输入抛出 TypeError。
  """
  if type(sign) is not Sign:
    raise TypeError("sign must be a Sign")
  return _RULERS[sign]


def essential_dignities(body: Body, sign: Sign) -> tuple[DignityStatus, ...]:
  """Return every match in domicile/exaltation/detriment/fall order, or () for none.

  Wrong enum types raise TypeError; an outer-planet Body raises ValueError.
  Assess the whole sign, not exaltation-degree proximity. See the dignity guide.

  按入庙、擢升、失势、落陷顺序返回全部命中，无命中则为 ()。枚举类型错误抛出 TypeError，
  外行星 Body 抛出 ValueError。判断整个星座，不看离擢升度数多近；详见尊贵指南。
  """
  if type(body) is not Body or type(sign) is not Sign:
    raise TypeError("body and sign must use Body and Sign")
  if body not in _DOMICILES:
    raise ValueError(f"Body outside Lilly's seven-planet rule: {body.value}")
  opposite = _SIGNS[(_SIGNS.index(sign) + 6) % len(_SIGNS)]
  return tuple(
    status
    for status, applies in (
      (DignityStatus.DOMICILE, sign in _DOMICILES[body]),
      (DignityStatus.EXALTATION, sign is _EXALTATIONS[body]),
      (DignityStatus.DETRIMENT, opposite in _DOMICILES[body]),
      (DignityStatus.FALL, opposite is _EXALTATIONS[body]),
    )
    if applies
  )
