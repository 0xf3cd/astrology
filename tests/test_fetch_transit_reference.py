"""Offline checks for reference flags, bracketing and wrap handling.

参考星历标志、夹根及环绕处理的离线检查。
"""

import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import celestial_calendar as native
import pytest

from tools import fetch_transit_reference as reference


def test_reference_flags_reject_silent_ephemeris_substitution() -> None:
  class WrongEphemeris:
    def calc(self, *args: Any) -> tuple[tuple[float, ...], int]:
      return (1, 2, 3, 4, 5, 6), 258

  with pytest.raises(RuntimeError, match="without a fallback"):
    reference._state(cast(reference._Swiss, WrongEphemeris()), 0, 2451545)


def test_reference_brackets_resolve_roots_but_not_a_wrap_discontinuity() -> None:
  assert reference._bisect(lambda instant: instant - 0.3, 0, 1) == pytest.approx(0.3)
  with pytest.raises(ValueError, match="not bracketed"):
    reference._bisect(lambda instant: instant + 1, 0, 1)
  hits = reference._crossings(lambda instant: ((359.1 + instant * 2) % 360, 2), 0, 0, 1)
  assert len(hits) == 1 and hits[0]["direction"] == "increasing"
  assert float(cast(float, hits[0]["jde_tt"])) == pytest.approx(0.45)
  assert reference._crossings(lambda instant: ((179.1 + instant * 2) % 360, 2), 0, 0, 1) == []


def test_recipe_rejects_a_mislabelled_optional_package(
  monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
  monkeypatch.setattr(sys, "argv", ["recipe", "--output", str(tmp_path / "reference.json")])
  monkeypatch.setattr(reference, "version", lambda name: "wrong-version")
  with pytest.raises(RuntimeError, match=r"pyswisseph 2\.10\.3\.2"):
    reference.main()
  assert not (tmp_path / "reference.json").exists()


def test_generator_success_shape_and_main_write_without_optional_packages(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  names = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
  )

  class SyntheticSwiss:
    version = "synthetic-reference"

    def julday(self, year: int, month: int, day: int, hour: float) -> float:
      return (
        2451544.5
        + (datetime(year, month, day, tzinfo=UTC) - datetime(2000, 1, 1, tzinfo=UTC)).days
        + hour / 24
      )

    def get_planet_name(self, body: int) -> str:
      return names[body]

    def calc(self, instant: float, body: int, flags: int) -> tuple[tuple[float, ...], int]:
      if body == 2:
        delta = instant - self.julday(2024, 4, 2, 12)
        longitude, rate = (20.1 - 0.01 * delta**2) % 360, -0.02 * delta
      else:
        longitude, rate = (instant * (body + 1)) % 360, float(body + 1)
      return (longitude, 0, 1, rate, 0, 0), flags

  swe = SyntheticSwiss()

  def positions(targets: tuple[native.Target, ...], instant: float) -> tuple[SimpleNamespace, ...]:
    return tuple(
      SimpleNamespace(
        longitude_deg=swe.calc(instant, names.index(target.value.title()), 260)[0][0] + 1e-6
      )
      for target in targets
    )

  monkeypatch.setattr(native, "positions", positions)
  generated = reference._generate(swe)
  calibration = cast(dict[str, Any], generated["calibration"])
  cases = cast(list[dict[str, Any]], generated["cases"])
  assert calibration["sample_count"] == 1830
  assert set(calibration["maximum_difference_deg"]) == {name.lower() for name in names}
  assert all(
    calibration["angular_tolerance_deg"][name] >= maximum
    for name, maximum in calibration["maximum_difference_deg"].items()
  )
  assert len(cases) == 17
  assert [case["name"] for case in cases[-7:]] == [
    "mercury_triple_2024",
    "mercury_near_station_2024",
    "sun_wrap_2025",
    "mean_ascending",
    "mean_descending",
    "meeus_five_term_true_ascending",
    "meeus_five_term_true_descending",
  ]
  source = cast(dict[str, Any], generated["source"])
  assert source["library_version"] == "synthetic-reference"
  assert source["requested_flags"] == source["returned_flags"] == 260
  assert len(source["recipe_sha256"]) == len(source["node_reference_sha256"]) == 64
  output = tmp_path / "reference.json"
  monkeypatch.setattr(sys, "argv", ["recipe", "--output", str(output)])
  monkeypatch.setattr(reference, "version", lambda name: "2.10.3.2")
  monkeypatch.setattr(importlib, "import_module", lambda name: swe)
  monkeypatch.setattr(reference, "_generate", lambda selected: generated)
  reference.main()
  assert json.loads(output.read_text()) == generated
