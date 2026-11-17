"""Generate independent moving-pair crossings, scan audits and calibration states.

生成独立的移动对象对穿越、扫描核对及校准位置样本。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import swisseph as swe  # type: ignore[import-not-found]

FLAGS = 260
BODIES = {"sun": 0, "moon": 1, "mercury": 2, "mars": 4, "jupiter": 5, "saturn": 6}
CASES = (
  *(
    (f"moon_sun_{int(angle)}", "moon", "sun", angle, "2024-01-01", "2024-02-02")
    for angle in (0.0, 60.0, 90.0, 120.0, 180.0)
  ),
  ("mercury_sun_conjunctions", "mercury", "sun", 0.0, "2024-01-01", "2025-01-01"),
  ("jupiter_saturn_squares", "jupiter", "saturn", 90.0, "2024-01-01", "2025-03-01"),
  ("mars_jupiter_conjunction", "mars", "jupiter", 0.0, "2024-07-01", "2024-09-01"),
)


def julian_day(instant: datetime) -> float:
  hour = instant.hour + instant.minute / 60 + instant.second / 3600
  return float(swe.julday(instant.year, instant.month, instant.day, hour) + 69.184 / 86400)


def state(body: str, jde_tt: float) -> tuple[float, float]:
  values, flags = swe.calc(jde_tt, BODIES[body], FLAGS)
  if flags != FLAGS or not all(math.isfinite(values[index]) for index in (0, 3)):
    raise RuntimeError("Expected finite Moshier longitude/speed with returned flags 260")
  return float(values[0]), float(values[3])


def bisect(function: Callable[[float], float], left: float, right: float) -> float:
  before = function(left)
  if before * function(right) >= 0:
    raise ValueError("Expected a strict sign-changing bracket")
  for _ in range(80):
    middle = (left + right) / 2
    if middle in (left, right):
      break
    value = function(middle)
    if value * before < 0:
      right = middle
    else:
      left, before = middle, value
  return (left + right) / 2


def crossings(
  case: dict[str, Any], step: float
) -> tuple[list[dict[str, Any]], list[dict[str, float]]]:
  first, second = case["first"], case["second"]
  angle = case["aspect_deg"]
  branches = (angle,) if angle in (0, 180) else (-angle, angle)

  def separation(instant: float) -> float:
    return state(second, instant)[0] - state(first, instant)[0]

  def rate(instant: float) -> float:
    return state(second, instant)[1] - state(first, instant)[1]

  hits, extrema = [], []
  left = case["start_jde_tt"]
  initial_angle, initial_rate = separation(left), rate(left)
  while left < case["end_jde_tt"]:
    right = min(left + step, case["end_jde_tt"])
    final_angle, final_rate = separation(right), rate(right)
    for branch in branches:
      initial, final = (
        math.remainder(initial_angle - branch, 360),
        math.remainder(final_angle - branch, 360),
      )
      if initial * final < 0 and abs(initial - final) < 180:

        def residual(value: float, selected: float = branch) -> float:
          return math.remainder(separation(value) - selected, 360)

        instant = bisect(residual, left, right)
        first_longitude, first_rate = state(first, instant)
        second_longitude, second_rate = state(second, instant)
        relative_rate = second_rate - first_rate
        if relative_rate == 0:
          raise RuntimeError("Sign-change scans cannot establish tangent contact")
        hits.append(
          {
            "jde_tt": instant,
            "branch_deg": branch,
            "first_longitude_deg": first_longitude,
            "second_longitude_deg": second_longitude,
            "first_rate_deg_per_tt_day": first_rate,
            "second_rate_deg_per_tt_day": second_rate,
            "relative_rate_deg_per_tt_day": relative_rate,
            "direction": "increasing" if relative_rate > 0 else "decreasing",
            "residual_deg": math.remainder(separation(instant) - branch, 360),
          }
        )
    if initial_rate * final_rate < 0:
      instant = bisect(rate, left, right)
      extrema.append(
        {
          "jde_tt": instant,
          "distance_from_requested_branch_deg": min(
            abs(math.remainder(separation(instant) - branch, 360)) for branch in branches
          ),
        }
      )
    left, initial_angle, initial_rate = right, final_angle, final_rate
  hits.sort(key=lambda hit: (hit["jde_tt"], hit["branch_deg"]))
  return hits, extrema


def generate_reference() -> dict[str, Any]:
  if version("pyswisseph") != "2.10.3.2" or swe.version != "2.10.03":
    raise RuntimeError("Reference requires pyswisseph 2.10.3.2 / Swiss 2.10.03")
  swe.set_ephe_path("")
  cases = []
  for name, first, second, angle, start_date, end_date in CASES:
    start_utc, end_utc = (
      datetime.fromisoformat(start_date).replace(tzinfo=UTC),
      datetime.fromisoformat(end_date).replace(tzinfo=UTC),
    )
    case: dict[str, Any] = {
      "name": name,
      "first": first,
      "second": second,
      "aspect_deg": angle,
      "start_utc": start_utc.isoformat(),
      "end_utc": end_utc.isoformat(),
      "start_jde_tt": julian_day(start_utc),
      "end_jde_tt": julian_day(end_utc),
    }
    coarse, _ = crossings(case, 1 / 16)
    fine, extrema = crossings(case, 1 / 256)
    if not coarse or coarse != fine:
      raise RuntimeError(f"Coarse/fine crossing audit differs or is empty: {name}")
    case["hits"], case["relative_extrema"] = coarse, extrema
    cases.append(case)
  start = julian_day(datetime(2024, 1, 1, tzinfo=UTC))
  end = julian_day(datetime(2025, 3, 1, tzinfo=UTC))
  times = {start + 7 * index for index in range(int((end - start) / 7) + 1)}
  times.add(end)
  times.update(
    hit["jde_tt"] + offset for case in cases for hit in case["hits"] for offset in (-1, 0, 1)
  )
  samples = []
  for instant in sorted(times):
    for body in sorted(BODIES):
      longitude, rate = state(body, instant)
      samples.append(
        {"jde_tt": instant, "body": body, "longitude_deg": longitude, "rate_deg_per_tt_day": rate}
      )
  return {
    "generated_utc": datetime.now(UTC).isoformat(),
    "source": {
      "pyswisseph_version": version("pyswisseph"),
      "library_version": swe.version,
      "requested_flags": FLAGS,
      "verified_returned_flags": FLAGS,
      "coordinates": "Apparent geocentric tropical longitude, true ecliptic/equinox of date",
      "ephemeris": "Explicit Moshier plus speed; no ephemeris data-file fallback",
      "time_scale": "TT; TT-UTC=69.184 seconds for these 2024-2025 inputs",
      "separation": "second-minus-first",
      "algorithm": "1/16- and 1/256-TT-day sign-change scans, bisection and relative-rate sign-change extrema. Numerical selected-window audit, not a complete event or tangency oracle; adjacent double sign changes inside a partition are not certified.",
      "selection": "Eight fixed ordinary-crossing cases selected before native comparison; all retained",
      "manual": "https://www.astro.com/swisseph/swephprg.htm",
      "recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    },
    "cases": cases,
    "calibration_states": samples,
    "calibration_time_count": len(times),
  }


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--output", required=True, type=Path)
  args = parser.parse_args()
  args.output.write_text(json.dumps(generate_reference(), indent=2) + "\n")
  print(args.output)


if __name__ == "__main__":
  main()
