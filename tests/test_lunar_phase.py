"""Hand cases and independent integer-ratio checks for lunar phase. 月相手算及独立整数比值核验。"""

import math
import random
import struct
import sys
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
from typing import Any

import pytest

from astrology import LunarPhaseResult, LunationType, lunar_phase

# Rudhyar, Your Lunation Birthday, Part Four: the eight Soli-Lunar Arc headings.
# Rudhyar 的 Your Lunation Birthday 第四部分八个 Soli-Lunar Arc 标题。
_RANGES = (
  (0, 45, LunationType.NEW_MOON),
  (45, 90, LunationType.CRESCENT_MOON),
  (90, 135, LunationType.FIRST_QUARTER),
  (135, 180, LunationType.GIBBOUS_MOON),
  (180, 225, LunationType.FULL_MOON),
  (225, 270, LunationType.DISSEMINATING_MOON),
  (270, 315, LunationType.LAST_QUARTER),
  (315, 360, LunationType.BALSAMIC_MOON),
)


@pytest.mark.parametrize("lower,upper,phase", _RANGES)
def test_every_interval_and_both_boundary_sides(
  lower: int, upper: int, phase: LunationType
) -> None:
  assert lunar_phase(0, lower).phase is phase
  assert lunar_phase(0, (lower + upper) / 2).phase is phase
  assert lunar_phase(0, math.nextafter(float(lower), math.inf)).phase is phase
  assert lunar_phase(0, math.nextafter(float(upper), -math.inf)).phase is phase
  next_type = _RANGES[(lower // 45 + 1) % 8][2]
  assert lunar_phase(0, upper).phase is next_type
  assert lunar_phase(0, math.nextafter(float(upper), math.inf)).phase is next_type
  previous = _RANGES[(lower // 45 - 1) % 8][2]
  assert lunar_phase(0, math.nextafter(float(lower), -math.inf)).phase is previous


@pytest.mark.parametrize(
  "sun,moon,angle,direction",
  [
    (350, 10, 20, "waxing"),
    (10, 350, 340, "waning"),
    (20, 20, 0, "turning"),
    (20, 110, 90, "waxing"),
    (20, 200, 180, "turning"),
    (20, 290, 270, "waning"),
    (-360, 720, 0, "turning"),
    (sys.float_info.max, -sys.float_info.max, 104, "waxing"),
  ],
)
def test_sun_first_keywords_wrap_quarters_and_extremes(
  sun: float, moon: float, angle: float, direction: str
) -> None:
  result = lunar_phase(sun, moon)
  assert result == lunar_phase(moon_longitude_deg=moon, sun_longitude_deg=sun)
  assert result.elongation_deg == angle
  assert result.direction == direction
  assert result.rule_id == "rule.lunation.rudhyar1950"


@pytest.mark.parametrize("rotation", [-1080, -90, 0, 45, 360, 720])
def test_exactly_representable_rotations_and_swapped_direction(rotation: float) -> None:
  result = lunar_phase(12.5, 80.25)
  assert lunar_phase(12.5 + rotation, 80.25 + rotation) == result
  reverse = lunar_phase(80.25, 12.5)
  assert reverse.elongation_deg == 360 - result.elongation_deg
  assert result.direction == "waxing" and reverse.direction == "waning"


def test_nonexact_input_rotation_has_explicit_tolerance() -> None:
  assert lunar_phase(360, 360.1).elongation_deg == pytest.approx(
    lunar_phase(0, 0.1).elongation_deg, abs=1e-12
  )


def integer_oracle(sun: float, moon: float) -> tuple[int, bool, float]:
  sn, sd = sun.as_integer_ratio()
  mn, md = moon.as_integer_ratio()
  denominator = sd * md
  remainder = (mn * sd - sn * md) % (360 * denominator)
  with localcontext() as context:
    context.prec = 1200
    nearest = float(Decimal(remainder) / Decimal(denominator))
  return remainder // (45 * denominator), remainder in (0, 180 * denominator), nearest


def test_independent_ratio_oracle_including_subnormal_boundary_cancellation() -> None:
  tiny = math.ulp(0.0)
  pairs = [(tiny, 0.0), (0.0, -tiny), (tiny, 45.0), (-tiny, 180.0)]
  for boundary in range(0, 361, 45):
    for moon in (
      math.nextafter(float(boundary), -math.inf),
      float(boundary),
      math.nextafter(float(boundary), math.inf),
    ):
      pairs.extend((sun, moon) for sun in (-tiny, 0.0, tiny))
  rng = random.Random(47_51)
  for _ in range(2000):
    sun, moon = (struct.unpack("!d", rng.getrandbits(64).to_bytes(8, "big"))[0] for _ in range(2))
    if math.isfinite(sun) and math.isfinite(moon):
      pairs.append((sun, moon))
  for sun, moon in pairs:
    sector, turning, nearest = integer_oracle(sun, moon)
    result = lunar_phase(sun, moon)
    assert 0 <= result.elongation_deg < 360
    assert result.phase is _RANGES[sector][2]
    assert (result.direction == "turning") is turning
    assert int(result.elongation_deg // 45) == sector
    assert result.elongation_deg in (
      nearest,
      math.nextafter(nearest, -math.inf),
      math.nextafter(nearest, math.inf),
    )
  assert lunar_phase(tiny, 0).elongation_deg == math.nextafter(360.0, 0.0)
  assert lunar_phase(tiny, 45).elongation_deg == math.nextafter(45.0, 0.0)
  assert lunar_phase(-tiny, 180).elongation_deg == math.nextafter(180.0, math.inf)


@pytest.mark.parametrize("bad", [None, True, False, "12", [], object(), LunationType.NEW_MOON])
def test_wrong_scalar_types(bad: Any) -> None:
  with pytest.raises(TypeError):
    lunar_phase(bad, 0)
  with pytest.raises(TypeError):
    lunar_phase(0, bad)
  with pytest.raises(TypeError):
    LunarPhaseResult(bad)


@pytest.mark.parametrize("bad", [math.inf, -math.inf, math.nan, 10**1000])
def test_nonfinite_scalars(bad: Any) -> None:
  with pytest.raises(ValueError):
    lunar_phase(bad, 0)
  with pytest.raises(ValueError):
    lunar_phase(0, bad)


@pytest.mark.parametrize("bad", [-1, 360, math.inf, math.nan])
def test_result_construction_requires_normalized_finite_angle(bad: float) -> None:
  with pytest.raises(ValueError):
    LunarPhaseResult(bad)


def test_result_labels_cannot_be_forged_or_mutated() -> None:
  result = LunarPhaseResult(45)
  assert type(result.elongation_deg) is float
  assert result.phase is LunationType.CRESCENT_MOON
  assert replace(result, elongation_deg=180).direction == "turning"
  assert hash(result) == hash(LunarPhaseResult(45))
  with pytest.raises(FrozenInstanceError):
    result.elongation_deg = 0  # type: ignore[misc]
  with pytest.raises(TypeError):
    LunarPhaseResult(45, phase=LunationType.NEW_MOON)  # type: ignore[call-arg]
