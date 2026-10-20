"""House membership over supplied cusp geometry, including boundary and wrap cases.

基于给定宫头几何的落宫成员关系，含边界与回绕用例。
"""

import math
import subprocess
import sys

import pytest

from astrology import house_of

# A table that starts at 300 degrees, so houses 3 and 12 cross the 0/360 seam.
_CUSPS = (300.0, 330.0, 0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0)
# The same cyclic table expressed from another starting cusp.
_ROTATED = (120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 330.0, 0.0, 30.0, 60.0, 90.0)


def test_a_longitude_on_a_cusp_belongs_to_the_house_starting_there() -> None:
  for index, cusp in enumerate(_CUSPS):
    assert house_of(cusp, _CUSPS) == index + 1


def test_a_longitude_just_below_a_cusp_belongs_to_the_previous_house() -> None:
  for index, cusp in enumerate(_CUSPS):
    previous = 12 if index == 0 else index
    assert house_of((cusp - 1e-6) % 360.0, _CUSPS) == previous


def test_adjacent_representable_values_keep_their_cusp_ownership() -> None:
  # The value one representable step below a cusp stays in the house that ends
  # there; a rotation by a common origin used to round it onto the cusp.
  for index, cusp in enumerate(_CUSPS):
    previous = 12 if index == 0 else index
    below = math.nextafter(cusp, 0.0) if cusp > 0.0 else math.nextafter(360.0, 0.0)
    assert house_of(below, _CUSPS) == previous
    assert house_of(cusp, _CUSPS) == index + 1


def test_adjacent_representable_values_keep_their_side_in_a_rotated_table() -> None:
  below = math.nextafter(30.0, 0.0)
  assert house_of(below, _ROTATED) == 9
  assert house_of(30.0, _ROTATED) == 10
  assert house_of(math.nextafter(360.0, 0.0), _ROTATED) == 8
  assert house_of(0.0, _ROTATED) == 9


def test_membership_wraps_across_zero_degrees() -> None:
  assert house_of(359.999999, _CUSPS) == 2
  assert house_of(0.0, _CUSPS) == 3
  assert house_of(0.000001, _CUSPS) == 3
  assert house_of(299.999999, _CUSPS) == 12
  assert house_of(300.0, _CUSPS) == 1


def test_every_house_is_reachable() -> None:
  reached = {house_of(cusp + 15.0, _CUSPS) for cusp in _CUSPS}
  assert reached == set(range(1, 13))


def test_membership_uses_only_the_cusp_table() -> None:
  # The Ascendant is not an argument: a table whose first cusp differs from an
  # Ascendant still decides membership. 宫头表之外没有上升点参数。
  assert house_of(305.0, _CUSPS) == 1
  assert house_of(295.0, _CUSPS) == 12


@pytest.mark.parametrize(
  "cusps",
  [
    (),
    (0.0, 30.0, 60.0),
    tuple(float(value) for value in range(0, 330, 30)),
    (0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 300.0),
    (0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 30.0),
    (0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 360.0),
    (0.0, 30.0, 60.0, float("nan"), 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 330.0),
    (-30.0, 0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0),
  ],
)
def test_invalid_cusp_tables_are_rejected(cusps: tuple[float, ...]) -> None:
  with pytest.raises(ValueError, match="cusps"):
    house_of(10.0, cusps)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.5, 360.0])
def test_out_of_domain_longitude_is_rejected(value: float) -> None:
  with pytest.raises(ValueError, match=r"\[0, 360\)"):
    house_of(value, _CUSPS)


@pytest.mark.parametrize("value", ["30", None, True])
def test_non_numeric_longitude_is_rejected(value: object) -> None:
  with pytest.raises(TypeError, match="must be a number"):
    house_of(value, _CUSPS)  # type: ignore[arg-type]


@pytest.mark.parametrize("cusps", ["not cusps", 30.0, [30.0] * 11 + ["x"]])
def test_non_numeric_cusps_are_rejected(cusps: object) -> None:
  with pytest.raises((TypeError, ValueError), match="cusp"):
    house_of(10.0, cusps)  # type: ignore[arg-type]


def test_input_domain_is_checked_in_optimized_mode() -> None:
  code = """
from astrology import house_of
try:
    house_of(10.0, (0.0, 30.0))
except ValueError:
    pass
else:
    raise RuntimeError('optimized mode skipped the cusp count check')
try:
    house_of(400.0, tuple(float(v) for v in range(0, 360, 30)))
except ValueError:
    pass
else:
    raise RuntimeError('optimized mode skipped the longitude domain check')
"""
  for mode in ((), ("-O",)):
    result = subprocess.run([sys.executable, *mode, "-c", code], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
