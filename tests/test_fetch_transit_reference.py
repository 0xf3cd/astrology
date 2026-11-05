"""Offline checks for reference flags, bracketing and wrap handling.

参考星历标志、夹根及环绕处理的离线检查。
"""

import sys
from pathlib import Path
from typing import Any, cast

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
