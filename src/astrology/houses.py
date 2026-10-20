"""House placement over supplied cusp geometry, without calculating positions.

按给定的宫头判断落在哪一宫，不计算天体位置。
"""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

_HOUSES = 12
_FULL_TURN = 360.0


def _cusps(cusps_deg: Sequence[float]) -> tuple[float, ...]:
  """Validate twelve finite cyclically ordered cusps in [0, 360).

  校验十二个宫头：都是有限数，落在 [0, 360) 内，并按循环顺序严格递增。

  Cyclic order is judged on the given angles: one wrap across 0/360 and eleven
  strict rises. Offsets from the first cusp can round two distinct cusps onto each
  other, so they are not used.

  循环顺序直接按给定的角度判断：整圈恰有一次越过 0/360 的回落，其余十一次都是严格
  上升。不用相对首宫头的偏移，因为它可能把两个不同的宫头舍入成同一个值。
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
  following = (*cusps[1:], cusps[0])
  ascents = sum(left < right for left, right in zip(cusps, following, strict=True))
  descents = sum(left > right for left, right in zip(cusps, following, strict=True))
  if ascents != _HOUSES - 1 or descents != 1:
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

  返回该热带黄经所在的宫（1 至 12）。每个区间都是半开的 [宫头, 下一宫头)：恰好落在
  宫头上的黄经，归从这个宫头开始的那一宫；区间可以跨过 0/360。本函数只看给定的宫头表，
  上升点等轴是否与第一宫头重合，由宫制决定，与本函数无关。

  区间直接按给定的角度比较。如果先减去同一个起点，紧贴宫头下方的黄经会被舍入到宫头上，
  错判成下一宫。
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
