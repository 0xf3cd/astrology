"""Tropical sign classification, sign degrees and display rounding.

热带星座归属、座内度数与显示舍入。
"""

import math
import subprocess
import sys

import pytest

from astrology import Sign, sign_degree, sign_of, truncate_display

_SECTOR_STARTS = (
  (0.0, Sign.ARIES),
  (30.0, Sign.TAURUS),
  (60.0, Sign.GEMINI),
  (90.0, Sign.CANCER),
  (120.0, Sign.LEO),
  (150.0, Sign.VIRGO),
  (180.0, Sign.LIBRA),
  (210.0, Sign.SCORPIO),
  (240.0, Sign.SAGITTARIUS),
  (270.0, Sign.CAPRICORN),
  (300.0, Sign.AQUARIUS),
  (330.0, Sign.PISCES),
)


@pytest.mark.parametrize(("longitude", "expected"), _SECTOR_STARTS)
def test_sector_start_belongs_to_its_own_sign(longitude: float, expected: Sign) -> None:
  assert sign_of(longitude) is expected
  assert sign_degree(longitude) == 0.0


@pytest.mark.parametrize(("longitude", "expected"), _SECTOR_STARTS[1:])
def test_value_just_below_a_sector_start_belongs_to_the_previous_sign(
  longitude: float, expected: Sign
) -> None:
  previous = _SECTOR_STARTS[_SECTOR_STARTS.index((longitude, expected)) - 1][1]
  assert sign_of(math.nextafter(longitude, 0.0)) is previous
  assert sign_of(longitude - 1e-7) is previous


def test_last_degree_stays_in_pisces() -> None:
  assert sign_of(359.9999999) is Sign.PISCES
  assert sign_degree(359.9999999) == pytest.approx(29.9999999)


def test_sign_degree_is_unrounded() -> None:
  assert sign_degree(0.0) == 0.0
  assert sign_degree(45.0) == 15.0
  assert sign_degree(30.0) == 0.0
  assert sign_degree(59.5) == 29.5
  assert sign_degree(29.9999999) == 29.9999999


def test_display_truncates_toward_zero_without_crossing_a_boundary() -> None:
  assert truncate_display(29.9999999) == pytest.approx(29 + 59 / 60 + 59 / 3600)
  assert truncate_display(359.9999999) == pytest.approx(359 + 59 / 60 + 59 / 3600)
  assert truncate_display(30.0) == 30.0
  assert truncate_display(0.0) == 0.0
  assert truncate_display(29.9999999) < 30.0
  assert truncate_display(359.9999999) < 360.0


def test_display_never_rounds_up_across_a_sector_boundary() -> None:
  below = math.nextafter(30.0, 0.0)
  assert below < 30.0
  assert truncate_display(below) < 30.0
  assert sign_of(truncate_display(below)) is Sign.ARIES
  assert truncate_display(below) == pytest.approx(29 + 59 / 60 + 59 / 3600)


def test_display_never_changes_the_classification() -> None:
  for longitude in (0.0, 0.0001, 29.9999999, 30.0, 179.9999999, 180.0, 359.9999999):
    assert sign_of(truncate_display(longitude)) is sign_of(longitude)


def test_display_is_monotone_and_never_above_the_input() -> None:
  values = (0.0, 1.0, 29.9999999, 30.0, 100.5, 359.9999999)
  truncated = [truncate_display(value) for value in values]
  assert truncated == sorted(truncated)
  assert all(display <= value for display, value in zip(truncated, values, strict=True))


@pytest.mark.parametrize("value", ["30", None, True, [30.0]])
def test_non_numeric_longitude_is_rejected(value: object) -> None:
  with pytest.raises(TypeError, match="must be a number"):
    sign_of(value)  # type: ignore[arg-type]
  with pytest.raises(TypeError, match="must be a number"):
    sign_degree(value)  # type: ignore[arg-type]
  with pytest.raises(TypeError, match="must be a number"):
    truncate_display(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.0001, 360.0, -30.0, 400.0])
def test_out_of_domain_longitude_is_rejected(value: float) -> None:
  with pytest.raises(ValueError, match=r"\[0, 360\)"):
    sign_of(value)
  with pytest.raises(ValueError, match=r"\[0, 360\)"):
    sign_degree(value)
  with pytest.raises(ValueError, match=r"\[0, 360\)"):
    truncate_display(value)


def test_input_domain_is_checked_in_optimized_mode() -> None:
  code = """
from astrology import sign_degree, sign_of, truncate_display
for call in (sign_of, sign_degree, truncate_display):
    try:
        call(360.0)
    except ValueError:
        continue
    raise RuntimeError('optimized mode skipped the longitude domain check')
try:
    sign_of('30')
except TypeError:
    pass
else:
    raise RuntimeError('optimized mode skipped the longitude type check')
"""
  for mode in ((), ("-O",)):
    result = subprocess.run([sys.executable, *mode, "-c", code], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
