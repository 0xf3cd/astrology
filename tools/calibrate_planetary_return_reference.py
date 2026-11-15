"""Calibrate independent return candidates through the current native composition.

通过当前原生组合校准独立返照候选；原生观察只作同后端证据，不充当独立数值参考。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import celestial_calendar as native

from astrology import (
  BirthRecord,
  Body,
  ChartConfig,
  FixedOffset,
  HouseSystem,
  Location,
  MajorAspect,
  natal_chart,
  prepare_natal_input,
  transit_hits,
)

SITE = Location(0, 0)


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--candidates", type=Path, required=True)
  parser.add_argument(
    "--transit-reference", type=Path, default=Path("tests/reference/transit_reference.json")
  )
  parser.add_argument("--output", type=Path, required=True)
  parser.add_argument("--observations", type=Path, required=True)
  args = parser.parse_args()

  reference = json.loads(args.candidates.read_text())
  transit_reference = json.loads(args.transit_reference.read_text())
  angular = transit_reference["calibration"]["angular_tolerance_deg"]
  observations = []
  maxima = {body.value: 0.0 for body in Body}
  for case in reference["cases"]:
    body = Body(case["body"])
    birth = datetime.fromisoformat(case["birth_utc"])
    chart = natal_chart(
      prepare_natal_input(BirthRecord(birth.date(), birth.time(), FixedOffset(timedelta(0)), SITE)),
      ChartConfig(HouseSystem.WHOLE_SIGN, (body,), ()),
    )
    result = transit_hits(
      chart,
      start_utc=datetime.fromisoformat(case["start_utc"]),
      end_utc=datetime.fromisoformat(case["end_utc"]),
      moving_objects=(body,),
      natal_objects=(body,),
      aspects=(MajorAspect.CONJUNCTION,),
    )
    natal_hits = [hit for hit in result.hits if hit.jde_tt <= chart.times.jde_tt]
    retained = [hit for hit in result.hits if hit.jde_tt > chart.times.jde_tt]
    if len(retained) != len(case["hits"]):
      raise RuntimeError(f"Native hit count differs for {case['name']}")
    natal_longitude = next(p.longitude_deg for p in chart.positions if p.identity is body)
    rows = []
    for hit, independent in zip(retained, case["hits"], strict=True):
      difference = (hit.jde_tt - independent["jde_tt"]) * 86400
      tolerance = max(
        2.0, 2 * angular[body.value] / abs(independent["rate_deg_per_tt_day"]) * 86400
      )
      if abs(difference) >= tolerance:
        raise RuntimeError(f"Native time difference exceeds tolerance for {case['name']}")
      independent["time_tolerance_seconds"] = tolerance
      actual = native.positions((native.Target(body.value),), hit.jde_tt)[0].longitude_deg
      residual = (actual - natal_longitude + 180) % 360 - 180
      if abs(residual) >= 1e-6:
        raise RuntimeError(f"Native root residual exceeds tolerance for {case['name']}")
      maxima[body.value] = max(maxima[body.value], abs(difference))
      rows.append(
        {
          "reference_jde_tt": independent["jde_tt"],
          "native_jde_tt": hit.jde_tt,
          "signed_difference_seconds": difference,
          "time_tolerance_seconds": tolerance,
          "native_direction": hit.direction.value,
          "same_model_residual_deg": residual,
        }
      )
    observations.append(
      {
        "name": case["name"],
        "chart_jde_tt": chart.times.jde_tt,
        "reference_birth_jde_tt": case["birth_jde_tt"],
        "natal_hits_excluded_for_post_natal_comparison": [hit.jde_tt for hit in natal_hits],
        "retained_hits": rows,
        "source": {
          "model_identity": result.sources[0].model_identity,
          "domain_start_jde_tt": result.sources[0].domain_start_jde_tt,
          "domain_end_jde_tt": result.sources[0].domain_end_jde_tt,
        },
      }
    )
    print(case["name"], "natal_excluded=", len(natal_hits), "post_natal=", len(retained))

  reference["calibrated_utc"] = datetime.now(UTC).isoformat()
  reference["calibration"] = {
    "native_version": native.__version__,
    "transit_reference_sha256": hashlib.sha256(args.transit_reference.read_bytes()).hexdigest(),
    "calibration_recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "angular_tolerance_deg": angular,
    "time_tolerance": "max(2 seconds, 2 * angular_tolerance_deg / abs(reference_rate) * 86400), stored independently for each hit",
    "maximum_observed_absolute_time_difference_seconds": maxima,
    "scope": "The angular bounds reuse the 1,830-point 2021-2022 Moshier/native calibration. Native observations here are same-backend composition checks for the selected 2023-2026 return cases, not independent numerical references or general accuracy bounds.",
    "native_observations_sha256": "",
  }
  observation_payload = {
    "native_version": native.__version__,
    "purpose": "same-backend composition and tolerance calibration only",
    "cases": observations,
  }
  args.observations.write_text(json.dumps(observation_payload, indent=2) + "\n", encoding="utf-8")
  reference["calibration"]["native_observations_sha256"] = hashlib.sha256(
    args.observations.read_bytes()
  ).hexdigest()
  args.output.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
  main()
