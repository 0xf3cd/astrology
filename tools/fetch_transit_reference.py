"""Generate independent transit references with an explicitly selected Moshier ephemeris.

在独立环境中显式使用 Moshier 星历，生成行运参考数据。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from importlib.metadata import version
from pathlib import Path
from typing import Protocol, cast

from tests.test_reference import NODE_TOLERANCE_ARCSEC, _meeus_nodes


class _Swiss(Protocol):
  version: str

  def calc(self, jde_tt: float, body: int, flags: int) -> tuple[tuple[float, ...], int]: ...
  def julday(self, year: int, month: int, day: int, hour: float) -> float: ...
  def get_planet_name(self, body: int) -> str: ...


def _state(swe: _Swiss, body: int, instant: float) -> tuple[float, float]:
  values, returned = swe.calc(instant, body, 260)
  if returned != 260:
    raise RuntimeError("The reference must use Moshier plus speed, without a fallback")
  return values[0], values[3]


def _bisect(function: Callable[[float], float], left: float, right: float) -> float:
  first = function(left)
  if first * function(right) > 0:
    raise ValueError("Reference root is not bracketed")
  for _ in range(60):
    middle = (left + right) / 2
    if middle in (left, right):
      break
    value = function(middle)
    if first * value <= 0:
      right = middle
    else:
      left, first = middle, value
  return (left + right) / 2


def _crossings(
  position: Callable[[float], tuple[float, float]], level: float, start: float, end: float
) -> list[dict[str, object]]:
  def deviation(instant: float) -> float:
    return (position(instant)[0] - level + 180) % 360 - 180

  hits: list[dict[str, object]] = []
  left = start
  while left < end:
    right = min(left + 0.0625, end)
    first, last = deviation(left), deviation(right)
    if first * last < 0 and abs(first - last) < 180:
      instant = _bisect(deviation, left, right)
      longitude, rate = position(instant)
      hits.append(
        {
          "jde_tt": instant,
          "longitude_deg": longitude,
          "longitude_rate_deg_per_tt_day": rate,
          "direction": "increasing" if rate > 0 else "decreasing",
          "bracket_jde_tt": [left, right],
        }
      )
    left = right
  return hits


def _node(instant: float, true: bool, descending: bool) -> tuple[float, float]:
  def longitude(jde_tt: float) -> float:
    mean, five_term, nutation = _meeus_nodes(jde_tt)
    return ((five_term if true else mean) + nutation + (180 if descending else 0)) % 360

  rate = ((longitude(instant + 0.001) - longitude(instant - 0.001) + 180) % 360 - 180) / 0.002
  return longitude(instant), rate


def _generate(swe: _Swiss) -> dict[str, object]:
  import celestial_calendar as celestial

  if celestial.__version__ != "1.1.1":
    raise RuntimeError("This calibration recipe requires celestial-calendar 1.1.1")
  maxima: dict[str, float] = {}
  calibration_rows: list[tuple[str, float, float, float]] = []
  for body in range(10):
    name = swe.get_planet_name(body).lower()
    differences = []
    for offset in range(0, 730, 4):
      instant = swe.julday(2021, 1, 1, 0) + offset
      reference, _ = _state(swe, body, instant)
      native = celestial.positions((celestial.Target(name),), instant)[0].longitude_deg
      differences.append(abs((native - reference + 180) % 360 - 180))
      calibration_rows.append((name, instant, reference, native))
    maxima[name] = max(differences)
  bounds = {name: math.ceil(2 * maximum * 1e6) / 1e6 for name, maximum in maxima.items()}
  bounds.update(sun=0.0002, mercury=0.0002)
  calibration = {
    "native_version": celestial.__version__,
    "sample_count": len(calibration_rows),
    "interval": "2021-01-01 through 2022-12-30, every fourth TT day",
    "maximum_difference_deg": maxima,
    "angular_tolerance_deg": bounds,
    "rows_sha256": hashlib.sha256(json.dumps(calibration_rows).encode()).hexdigest(),
    "time_tolerance": "max(2 seconds, 2 * angular_tolerance_deg / abs(reference_rate) * 86400)",
  }
  cases: list[dict[str, object]] = []

  def add(
    name: str,
    body: str,
    level: float,
    start: float,
    end: float,
    position: Callable[[float], tuple[float, float]],
    tolerance: float,
  ) -> None:
    cases.append(
      {
        "name": name,
        "moving_object": body,
        "query_longitude_deg": level,
        "start_jde_tt": start,
        "end_jde_tt": end,
        "angular_tolerance_deg": tolerance,
        "hits": _crossings(position, level, start, end),
      }
    )

  for body in range(10):
    name = swe.get_planet_name(body).lower()
    center = max(
      (abs(_state(swe, body, instant)[1]), instant)
      for instant in (swe.julday(2024, month, 15, 0) for month in range(1, 13))
    )[1]
    level = round(_state(swe, body, center)[0], 2) % 360
    add(
      f"{name}_regular_2024",
      name,
      level,
      center - 10,
      center + 10,
      partial(_state, swe, body),
      bounds[name],
    )

  def mercury(instant: float) -> tuple[float, float]:
    return _state(swe, 2, instant)

  station = _bisect(
    lambda instant: mercury(instant)[1], swe.julday(2024, 4, 1, 0), swe.julday(2024, 4, 4, 0)
  )
  add(
    "mercury_triple_2024",
    "mercury",
    20,
    swe.julday(2024, 3, 1, 0),
    swe.julday(2024, 6, 1, 0),
    mercury,
    bounds["mercury"],
  )
  add(
    "mercury_near_station_2024",
    "mercury",
    mercury(station)[0] - 0.01,
    station - 1,
    station + 1,
    mercury,
    bounds["mercury"],
  )
  add(
    "sun_wrap_2025",
    "sun",
    0,
    swe.julday(2025, 3, 15, 0),
    swe.julday(2025, 3, 25, 0),
    lambda instant: _state(swe, 0, instant),
    bounds["sun"],
  )
  for true in (False, True):
    for descending in (False, True):
      name = ("meeus_five_term_true" if true else "mean") + (
        "_descending" if descending else "_ascending"
      )
      add(
        name,
        name + "_node",
        240 if descending else 60,
        2459215.5,
        2459945.5,
        partial(_node, true=true, descending=descending),
        NODE_TOLERANCE_ARCSEC / 3600,
      )
  return {
    "generated_utc": datetime.now(UTC).isoformat(),
    "source": {
      "pyswisseph_version": "2.10.3.2",
      "library_version": swe.version,
      "ephemeris": "Moshier analytical, explicitly selected; not Swiss/JPL data files",
      "requested_flags": 260,
      "returned_flags": 260,
      "coordinates": "apparent geocentric tropical longitude, true equinox/ecliptic of date",
      "time_scale": "TT",
      "manual": "https://www.astro.com/swisseph/swephprg.htm",
      "node_reference": "tests.test_reference._meeus_nodes: Meeus ch.47 plus ch.22 low-accuracy nutation",
      "node_reference_sha256": hashlib.sha256(
        (Path(__file__).parents[1] / "tests/test_reference.py").read_bytes()
      ).hexdigest(),
      "recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    },
    "calibration": calibration,
    "cases": cases,
  }


def main() -> None:
  """Write the requested reference file; optional reference packages are loaded here.

  写入指定参考文件；仅在此处加载可选的参考计算包。
  """
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--output", type=Path, required=True)
  destination = parser.parse_args().output
  if version("pyswisseph") != "2.10.3.2":
    raise RuntimeError("This reference recipe requires pyswisseph 2.10.3.2")
  swe = cast(_Swiss, importlib.import_module("swisseph"))
  destination.write_text(json.dumps(_generate(swe), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
  main()
