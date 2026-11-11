"""Offline checks for return-reference provenance and crossing validation.

返照参考来源及穿越校验的离线检查。
"""

import importlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from tools import fetch_return_reference as reference


class SyntheticSwiss:
  SUN = 0
  MOON = 1
  version = "2.10.03"

  def julday(self, year: int, month: int, day: int, hour: float) -> float:
    return (
      2451544.5
      + (datetime(year, month, day, tzinfo=UTC) - datetime(2000, 1, 1, tzinfo=UTC)).days
      + hour / 24
    )

  def calc(self, instant: float, body: int, flags: int) -> tuple[tuple[float, ...], int]:
    rate = 1.0 if body == self.SUN else 13.0
    return ((instant * rate) % 360, 0, 1, rate, 0, 0), flags

  def solcross(self, longitude: float, instant: float, flags: int) -> float:
    return instant + ((longitude - instant) % 360)

  def mooncross(self, longitude: float, instant: float, flags: int) -> float:
    return instant + ((longitude - instant * 13) % 360) / 13


def test_reference_generation_and_explicit_output(
  monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
  swe = SyntheticSwiss()
  generated = reference.generate_reference(swe, "2.10.3.2")
  cases = cast(list[dict[str, object]], generated["cases"])
  source = cast(dict[str, object], generated["source"])
  assert len(cases) == 9
  assert source["requested_flags"] == source["verified_calculation_flags"] == 260
  assert {case["body"] for case in cases} == {"sun", "moon"}
  assert all(case["hits"] for case in cases)
  assert all("+00:00" in str(case["birth_utc"]) for case in cases)
  output = tmp_path / "returns.json"
  monkeypatch.setattr(sys, "argv", ["recipe", "--output", str(output)])
  monkeypatch.setattr(importlib, "import_module", lambda name: swe)
  monkeypatch.setattr(reference, "version", lambda name: "2.10.3.2")
  reference.main()
  assert json.loads(output.read_text()) == generated


@pytest.mark.parametrize("wrapper", ["wrong", "2.10.3.1"])
def test_wrapper_version_is_pinned(wrapper: str) -> None:
  with pytest.raises(RuntimeError, match=r"pyswisseph 2\.10\.3\.2"):
    reference.generate_reference(SyntheticSwiss(), wrapper)


def test_library_version_is_pinned() -> None:
  swe = SyntheticSwiss()
  swe.version = "wrong"
  with pytest.raises(RuntimeError, match=r"Swiss 2\.10\.03"):
    reference.generate_reference(swe, "2.10.3.2")


def test_reference_rejects_a_silent_ephemeris_fallback() -> None:
  class WrongFlags(SyntheticSwiss):
    def calc(self, instant: float, body: int, flags: int) -> tuple[tuple[float, ...], int]:
      return super().calc(instant, body, flags)[0], 258

  with pytest.raises(RuntimeError, match="Moshier"):
    reference.generate_reference(WrongFlags(), "2.10.3.2")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_reference_rejects_nonfinite_states(value: float) -> None:
  class Nonfinite(SyntheticSwiss):
    def calc(self, instant: float, body: int, flags: int) -> tuple[tuple[float, ...], int]:
      return (value, 0, 1, 1, 0, 0), flags

  with pytest.raises(RuntimeError, match="nonfinite"):
    reference.generate_reference(Nonfinite(), "2.10.3.2")


def test_reference_rejects_nonprogressing_crossings() -> None:
  class Stuck(SyntheticSwiss):
    saved: float | None = None

    def solcross(self, longitude: float, instant: float, flags: int) -> float:
      if longitude == 0:
        return super().solcross(longitude, instant, flags)
      if self.saved is None:
        self.saved = super().solcross(longitude, instant, flags)
      return self.saved

  with pytest.raises(RuntimeError, match="must increase"):
    reference.generate_reference(Stuck(), "2.10.3.2")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_reference_rejects_nonfinite_crossings(value: float) -> None:
  class InvalidCrossing(SyntheticSwiss):
    def solcross(self, longitude: float, instant: float, flags: int) -> float:
      if longitude == 0:
        return super().solcross(longitude, instant, flags)
      return value

  with pytest.raises(RuntimeError, match=r"finite|increase"):
    reference.generate_reference(InvalidCrossing(), "2.10.3.2")


def test_reference_rechecks_the_solved_longitude() -> None:
  class WrongRoot(SyntheticSwiss):
    def calc(self, instant: float, body: int, flags: int) -> tuple[tuple[float, ...], int]:
      values, returned = super().calc(instant, body, flags)
      if instant > 2455000:
        values = (values[0] + 1, *values[1:])
      return values, returned

  with pytest.raises(RuntimeError, match="natal longitude"):
    reference.generate_reference(WrongRoot(), "2.10.3.2")
