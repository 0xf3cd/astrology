"""Compare independent moving-pair candidates with native states and derive case tolerances.

将独立移动对象对候选与原生状态比较，并导出各用例容差。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import celestial_calendar as native


def time_tolerance_seconds(first_bound: float, second_bound: float, relative_rate: float) -> float:
  """Use both angular bounds and the independent relative rate.

  使用两侧角误差界及独立的相对速率。
  """
  if abs(relative_rate) < 0.1:
    raise ValueError("Reference relative rate must be at least 0.1 degree/TT day")
  tolerance = max(2.0, 2 * (first_bound + second_bound) / abs(relative_rate) * 86400)
  if tolerance > 300:
    raise ValueError("Reference time tolerance exceeds 300 seconds")
  return tolerance


def calibrate(candidates: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
  maxima = {sample["body"]: 0.0 for sample in candidates["calibration_states"]}
  for sample in candidates["calibration_states"]:
    position = native.positions((native.Target(sample["body"]),), sample["jde_tt"])[0]
    maxima[sample["body"]] = max(
      maxima[sample["body"]],
      abs(math.remainder(position.longitude_deg - sample["longitude_deg"], 360)),
    )
  bounds = {body: math.ceil(2 * error * 1e6) / 1e6 for body, error in maxima.items()}
  observations: dict[str, Any] = {"native_version": native.__version__, "cases": [], "controls": []}
  for case in candidates["cases"]:
    first_bound, second_bound = bounds[case["first"]], bounds[case["second"]]
    for extremum in case["relative_extrema"]:
      if extremum["distance_from_requested_branch_deg"] <= first_bound + second_bound:
        raise RuntimeError("Reference extremum lies inside the bilateral angular budget")
    angle = case["aspect_deg"]
    branches = (angle,) if angle in (0, 180) else (-angle, angle)
    events = []
    for branch in branches:
      level = 180.0 if branch == 180 else -branch
      for event in native.longitude_difference_events(
        native.Target(case["first"]),
        native.Target(case["second"]),
        level,
        case["start_jde_tt"],
        case["end_jde_tt"],
      ):
        events.append({"branch_deg": branch, "event": asdict(event)})
    events.sort(key=lambda item: (item["event"]["jde_tt"], item["branch_deg"]))
    if len(events) != len(case["hits"]):
      raise RuntimeError("Selected native/reference event count differs")
    for actual, expected in zip(events, case["hits"], strict=True):
      event = actual["event"]
      direction = {"increasing": "decreasing", "decreasing": "increasing", "tangent": "tangent"}[
        event["direction"]
      ]
      if actual["branch_deg"] != expected["branch_deg"] or direction != expected["direction"]:
        raise RuntimeError("Selected native/reference branch or relative direction differs")
      tolerance = time_tolerance_seconds(
        first_bound, second_bound, expected["relative_rate_deg_per_tt_day"]
      )
      delta = abs(event["jde_tt"] - expected["jde_tt"]) * 86400
      if delta > tolerance:
        raise RuntimeError("Selected native event exceeds the independent case tolerance")
      expected["time_tolerance_seconds"] = tolerance
      shifted = expected["jde_tt"] + 2 * tolerance / 86400
      if abs(event["jde_tt"] - shifted) * 86400 <= tolerance:
        raise RuntimeError("Shifted reference sanity control unexpectedly passed")
      observations["controls"].append(
        {
          "case": case["name"],
          "tolerance_seconds": tolerance,
          "native_delta_seconds": delta,
          "shifted_time_rejected": True,
        }
      )
    observations["cases"].append({"name": case["name"], "events": events})
  fixture = {
    "generated_utc": candidates["generated_utc"],
    "source": candidates["source"],
    "cases": candidates["cases"],
    "calibration": {
      "calibrated_utc": datetime.now(UTC).isoformat(),
      "native_version": native.__version__,
      "sample_count": len(candidates["calibration_states"]),
      "time_count": candidates["calibration_time_count"],
      "maximum_observed_angular_error_deg": maxima,
      "angular_tolerance_deg": bounds,
      "bound_recipe": "Twice the selected-epoch observed maximum, rounded upward to 0.000001 degree",
      "time_tolerance": "max(2 seconds, 2*(first_bound+second_bound)/abs(reference_relative_rate)*86400)",
      "relative_rate_floor_deg_per_tt_day": 0.1,
      "time_tolerance_ceiling_seconds": 300,
      "scope": "Weekly samples over 2024-01-01 to 2025-03-01 plus all hit times and +/-1 TT-day neighbors. Empirical acceptance bounds, not global accuracy bounds; timing errors within each recorded tolerance can pass. Shifted-time controls are comparator sanity checks, not mutation tests.",
      "recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    },
  }
  return fixture, observations


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--candidates", required=True, type=Path)
  parser.add_argument("--output", required=True, type=Path)
  parser.add_argument("--observations", required=True, type=Path)
  args = parser.parse_args()
  content = args.candidates.read_bytes()
  fixture, observations = calibrate(json.loads(content))
  observed_bytes = (json.dumps(observations, indent=2) + "\n").encode()
  args.observations.write_bytes(observed_bytes)
  args.output.write_text(json.dumps(fixture, indent=2) + "\n")
  print(args.output)


if __name__ == "__main__":
  main()
