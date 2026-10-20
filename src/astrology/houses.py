"""House placement over supplied cusp geometry, without calculating positions.

对给定宫头几何求落宫，不计算天体位置。
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise
from math import isfinite

_HOUSES = 12
_FULL_TURN = 360.0


def _cusps(cusps_deg: Sequence[float]) -> tuple[float, ...]:
  """Validate twelve finite cyclically ordered cusps in [0, 360).

  校验十二个有限、按循环顺序递增、范围 [0, 360) 的宫头。
  """
  if not isinstance(cusps_deg, Sequence) or isinstance(cusps_deg, (str, bytes)):
    raise TypeError("cusps_deg must be a sequence of twelve numbers")
  values = tuple(cusps_deg)
  if len(values) != _HOUSES:
    raise ValueError("cusps_deg must contain exactly twelve cusps")
  if any(type(value) not in (int, float) for value in values):
    raise TypeError("cusps_deg must contain only numbers")
  cusps = tuple(float(value) for value in values)
  if any(not isfinite(value) or not 0.0 <= value < _FULL_TURN for value in cusps):
    raise ValueError("cusps_deg must be finite and in [0, 360)")
  rotated = tuple((value - cusps[0]) % _FULL_TURN for value in cusps)
  if rotated[0] != 0.0 or any(left >= right for left, right in pairwise(rotated)):
    raise ValueError("cusps_deg must be strictly increasing in cyclic order from the first cusp")
  return cusps


def house_of(longitude_deg: float, cusps_deg: Sequence[float]) -> int:
  """Return the house 1-12 containing a tropical longitude.

  Intervals are half-open [cusp, next cusp): a longitude exactly on a cusp
  belongs to the house that starts there. Membership wraps across 0/360. This
  uses the supplied cusp list only; whether an axis such as the Ascendant
  coincides with the first cusp is a property of the house system, not of this
  function.

  The intervals are compared in the given angles. Rotating them by a common
  origin would round a longitude that sits just below a cusp onto the cusp
  itself and hand it to the next house.

  返回包含该热带黄经的宫（1-12）。区间为半开 [宫头, 下一宫头)：恰好落在宫头上的黄经
  归属于从该宫头开始的宫。成员关系跨 0/360 环绕。本函数只使用给定宫头表；上升点等轴
  是否与第一宫头重合是宫制的性质，不是本函数的性质。
  区间按给定角度直接比较：按共同原点旋转会把紧贴宫头下方的黄经舍入到宫头上，交给下一宫。
  """
  cusps = _cusps(cusps_deg)
  if type(longitude_deg) not in (int, float):
    raise TypeError("longitude_deg must be a number")
  longitude = float(longitude_deg)
  if not isfinite(longitude) or not 0.0 <= longitude < _FULL_TURN:
    raise ValueError("longitude_deg must be finite and in [0, 360)")
  for index in range(_HOUSES):
    start = cusps[index]
    end = cusps[(index + 1) % _HOUSES]
    inside = start <= longitude < end if start < end else longitude >= start or longitude < end
    if inside:
      return index + 1
  raise ValueError("cusps_deg does not cover the circle")
