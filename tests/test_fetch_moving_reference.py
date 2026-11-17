"""Offline checks of moving-reference scans and calibration guards.

移动参考扫描及校准检查的离线测试。
"""

import importlib.util
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import celestial_calendar as native
import pytest

from tools import calibrate_moving_reference as calibration


@pytest.fixture
def reference(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
  swiss = ModuleType("swisseph")

  def julday(year: int, month: int, day: int, hour: float) -> float:
    return datetime(year, month, day).toordinal() + hour / 24.0

  vars(swiss).update(
    {
      "version": "2.10.03",
      "julday": julday,
      "set_ephe_path": lambda path: None,
      "calc": lambda *args: ((0, 0, 1, 1, 0, 0), 260),
    }
  )
  monkeypatch.setitem(sys.modules, "swisseph", swiss)
  path = Path(__file__).parents[1] / "tools/fetch_moving_reference.py"
  spec = importlib.util.spec_from_file_location("synthetic_moving_reference", path)
  assert spec is not None and spec.loader is not None
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  monkeypatch.setattr(module, "version", lambda name: "2.10.3.2")
  return module


def _case() -> dict[str, Any]:
  return {
    "first": "sun",
    "second": "moon",
    "aspect_deg": 0.0,
    "start_jde_tt": 0.0,
    "end_jde_tt": 1.0,
  }


def test_scan_finds_a_crossing_but_not_a_wrap_discontinuity(
  reference: ModuleType,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def state(body: str, instant: float) -> tuple[float, float]:
    return (0, 0) if body == "sun" else (instant - 0.73, 1)

  monkeypatch.setattr(reference, "state", state)
  hits, extrema = reference.crossings(_case(), 1 / 16)
  assert len(hits) == 1 and not extrema
  assert hits[0]["jde_tt"] == pytest.approx(0.73)
  assert hits[0]["direction"] == "increasing"

  def wrapped(body: str, instant: float) -> tuple[float, float]:
    return (0, 0) if body == "sun" else (179.1 + instant * 2, 2)

  monkeypatch.setattr(reference, "state", wrapped)
  assert reference.crossings(_case(), 1 / 16) == ([], [])
  assert reference.bisect(lambda instant: instant - 0.73, 0, 1) == pytest.approx(0.73)
  with pytest.raises(ValueError, match="bracket"):
    reference.bisect(lambda instant: instant + 1, 0, 1)


def test_scan_records_a_relative_extremum(
  reference: ModuleType,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def state(body: str, instant: float) -> tuple[float, float]:
    return (0, 0) if body == "sun" else ((instant - 0.73) ** 2 + 5, 2 * (instant - 0.73))

  monkeypatch.setattr(reference, "state", state)
  hits, extrema = reference.crossings(_case(), 1 / 16)
  assert not hits and len(extrema) == 1
  assert extrema[0]["jde_tt"] == pytest.approx(0.73)
  assert extrema[0]["distance_from_requested_branch_deg"] == pytest.approx(5)


def test_generator_rejects_versions_flags_and_failed_scan_audits(
  reference: ModuleType,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(reference, "version", lambda name: "wrong")
  with pytest.raises(RuntimeError, match="Reference requires"):
    reference.generate_reference()
  monkeypatch.setattr(reference, "version", lambda name: "2.10.3.2")
  monkeypatch.setattr(reference.swe, "calc", lambda *args: ((0, 0, 1, 1, 0, 0), 258))
  with pytest.raises(RuntimeError, match="flags 260"):
    reference.state("sun", 0)
  monkeypatch.setattr(reference, "crossings", lambda case, step: ([{"jde_tt": step}], []))
  with pytest.raises(RuntimeError, match="Coarse/fine"):
    reference.generate_reference()
  monkeypatch.setattr(reference, "crossings", lambda case, step: ([], []))
  with pytest.raises(RuntimeError, match="Coarse/fine"):
    reference.generate_reference()


def _candidates() -> dict[str, Any]:
  case = _case()
  case.update(
    {
      "name": "synthetic",
      "hits": [
        {
          "jde_tt": 0.73,
          "branch_deg": 0.0,
          "direction": "decreasing",
          "relative_rate_deg_per_tt_day": -1.0,
        }
      ],
      "relative_extrema": [],
    }
  )
  return {
    "generated_utc": "synthetic",
    "source": {},
    "calibration_time_count": 1,
    "calibration_states": [
      {"body": body, "jde_tt": 0.5, "longitude_deg": 0.0} for body in ("sun", "moon")
    ],
    "cases": [case],
  }


@pytest.fixture
def native_values(
  monkeypatch: pytest.MonkeyPatch,
) -> Callable[
  [native.Target, native.Target, float, float, float], tuple[native.LongitudeDifferenceEvent, ...]
]:
  def positions(targets: tuple[native.Target, ...], instant: float) -> tuple[SimpleNamespace, ...]:
    return tuple(
      SimpleNamespace(longitude_deg=0.0001 if target is native.Target.SUN else 0.0002)
      for target in targets
    )

  def events(
    first: native.Target,
    second: native.Target,
    level: float,
    start: float,
    end: float,
  ) -> tuple[native.LongitudeDifferenceEvent, ...]:
    return (
      native.LongitudeDifferenceEvent(
        0.73,
        0,
        0,
        2,
        1,
        0,
        native.EventDirection.INCREASING,
      ),
    )

  monkeypatch.setattr(native, "positions", positions)
  monkeypatch.setattr(native, "longitude_difference_events", events)
  return events


def test_calibration_uses_both_bounds_and_records_shift_controls(
  native_values: Callable[..., tuple[native.LongitudeDifferenceEvent, ...]],
) -> None:
  fixture, observations = calibration.calibrate(_candidates())
  assert fixture["calibration"]["angular_tolerance_deg"] == {"sun": 0.0002, "moon": 0.0004}
  assert fixture["cases"][0]["hits"][0]["time_tolerance_seconds"] == pytest.approx(103.68)
  assert observations["controls"][0]["shifted_time_rejected"] is True
  assert "candidate_sha256" not in fixture["calibration"]
  assert "native_observations_sha256" not in fixture["calibration"]


@pytest.mark.parametrize(
  "defect,expected",
  [
    ("count", "count"),
    ("branch", "branch"),
    ("direction", "direction"),
    ("time", "tolerance"),
    ("extremum", "extremum"),
    ("shift", "sanity control"),
  ],
)
def test_calibration_rejects_inconsistent_reference_inputs(
  monkeypatch: pytest.MonkeyPatch,
  native_values: Callable[..., tuple[native.LongitudeDifferenceEvent, ...]],
  defect: str,
  expected: str,
) -> None:
  candidates = _candidates()
  if defect == "count":
    candidates["cases"][0]["hits"] = []
  elif defect == "branch":
    candidates["cases"][0]["hits"][0]["branch_deg"] = 60
  elif defect == "direction":
    candidates["cases"][0]["hits"][0]["direction"] = "increasing"
  elif defect == "time":
    candidates["cases"][0]["hits"][0]["jde_tt"] = 0.1
  elif defect == "extremum":
    candidates["cases"][0]["relative_extrema"] = [{"distance_from_requested_branch_deg": 0.0001}]
  else:
    monkeypatch.setattr(calibration, "time_tolerance_seconds", lambda *args: 0)
  with pytest.raises(RuntimeError, match=expected):
    calibration.calibrate(candidates)
