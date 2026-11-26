"""Generate independent ten-body post-natal returns with pinned Moshier crossings.

使用钉版 Moshier 星历生成十体本命后返照候选，不导入 astrology 或其天文后端。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Any

import swisseph as swe  # type: ignore[import-not-found]

FLAGS = 260
TT_MINUS_UTC_SECONDS = 69.184
BIRTH = datetime(2024, 12, 1, tzinfo=UTC)
END = datetime(2026, 1, 1, tzinfo=UTC)


def julian_day(instant: datetime) -> float:
  if instant.tzinfo is not UTC:
    raise ValueError("Reference civil inputs must use UTC")
  hour = instant.hour + instant.minute / 60 + (instant.second + instant.microsecond / 1e6) / 3600
  return float(
    swe.julday(instant.year, instant.month, instant.day, hour) + TT_MINUS_UTC_SECONDS / 86400
  )


def utc_from_julian_day(value: float) -> datetime:
  year, month, day, hour = swe.revjul(value - TT_MINUS_UTC_SECONDS / 86400)
  whole_seconds = round(hour * 3600, 6)
  seconds, microseconds = divmod(round(whole_seconds * 1e6), 1_000_000)
  hours, seconds = divmod(seconds, 3600)
  minutes, seconds = divmod(seconds, 60)
  if hours >= 24:
    raise RuntimeError("Reference UTC conversion carried into the following day")
  return datetime(year, month, day, hours, minutes, seconds, microseconds, tzinfo=UTC)


def state(body: int, instant: float) -> tuple[float, float]:
  values, returned = swe.calc(instant, body, FLAGS)
  if returned != FLAGS:
    raise RuntimeError("Reference calculation must use explicit Moshier plus speed flags 260")
  longitude, rate = values[0], values[3]
  if not math.isfinite(longitude) or not math.isfinite(rate):
    raise RuntimeError("Reference calculation returned a nonfinite longitude or rate")
  return longitude, rate


def bisect(function: Callable[[float], float], left: float, right: float) -> float:
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


def crossings(body: int, level: float, start: float, end: float) -> list[dict[str, Any]]:
  def deviation(instant: float) -> float:
    return (state(body, instant)[0] - level + 180) % 360 - 180

  hits: list[dict[str, Any]] = []
  left = start
  while left < end:
    right = min(left + 0.0625, end)
    first, last = deviation(left), deviation(right)
    if first * last < 0 and abs(first - last) < 180:
      instant = bisect(deviation, left, right)
      longitude, rate = state(body, instant)
      hits.append(
        {
          "jde_tt": instant,
          "longitude_deg": longitude,
          "rate_deg_per_tt_day": rate,
          "direction": "increasing" if rate > 0 else "decreasing",
          "residual_deg": (longitude - level + 180) % 360 - 180,
          "bracket_jde_tt": [left, right],
        }
      )
    left = right
  if hits != sorted(hits, key=lambda hit: hit["jde_tt"]):
    raise RuntimeError("Reference crossings must be in increasing TT order")
  return hits


def case(
  name: str,
  body: int,
  birth: datetime,
  start: datetime,
  end: datetime,
  level: float | None = None,
  hit_limit: int | None = 1,
) -> dict[str, Any]:
  birth_tt = julian_day(birth)
  natal_level = state(body, birth_tt)[0] if level is None else level
  hits = [
    hit
    for hit in crossings(body, natal_level, birth_tt + 1 / 86400, julian_day(end))
    if hit["jde_tt"] > birth_tt
  ]
  if not hits:
    raise RuntimeError(f"Reference case has no post-natal hit: {name}")
  if hit_limit is not None:
    hits = hits[:hit_limit]
    end = utc_from_julian_day(hits[-1]["jde_tt"]) + timedelta(days=1)
  return {
    "name": name,
    "body": swe.get_planet_name(body).lower(),
    "birth_utc": birth.isoformat(),
    "birth_jde_tt": birth_tt,
    "natal_longitude_deg": natal_level,
    "start_utc": start.isoformat(),
    "start_jde_tt": julian_day(start),
    "end_utc": end.isoformat(),
    "end_jde_tt": julian_day(end),
    "hits": hits,
  }


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--output", type=Path, required=True)
  args = parser.parse_args()
  if version("pyswisseph") != "2.10.3.2" or swe.version != "2.10.03":
    raise RuntimeError("Reference generation requires pyswisseph 2.10.3.2 / Swiss 2.10.03")
  specifications = {body: (BIRTH, END) for body in range(10)}
  specifications[3] = (BIRTH, datetime(2026, 4, 1, tzinfo=UTC))
  specifications[6] = (datetime(2025, 6, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC))
  specifications[9] = (datetime(2025, 4, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC))
  cases = [
    case(
      f"post_natal_{swe.get_planet_name(body).lower()}",
      body,
      birth,
      birth + timedelta(days=1),
      end,
      hit_limit=2 if body in (4, 6, 9) else 1,
    )
    for body, (birth, end) in specifications.items()
  ]

  triple_start = datetime(2024, 3, 1, tzinfo=UTC)
  triple_end = datetime(2024, 6, 1, tzinfo=UTC)
  earlier = crossings(2, 20, julian_day(datetime(2022, 1, 1, tzinfo=UTC)), julian_day(triple_start))
  birth_tt = earlier[-1]["jde_tt"]
  if not isinstance(birth_tt, float):
    raise TypeError("Reference crossing time must be a float")
  triple_birth = utc_from_julian_day(birth_tt)
  triple = case(
    "mercury_retrograde_triple", 2, triple_birth, triple_start, triple_end, level=20, hit_limit=None
  )
  directions = [hit["direction"] for hit in triple["hits"]]
  if directions != ["increasing", "decreasing", "increasing"]:
    raise RuntimeError(
      f"Mercury reference must preserve three crossing directions, got {directions}"
    )
  cases.append(triple)

  result = {
    "generated_utc": datetime.now(UTC).isoformat(),
    "source": {
      "pyswisseph_version": version("pyswisseph"),
      "library_version": swe.version,
      "ephemeris": "Moshier analytical, explicitly selected; no Swiss/JPL data-file fallback",
      "requested_flags": FLAGS,
      "verified_calculation_flags": FLAGS,
      "coordinates": "apparent geocentric tropical longitude, true equinox/ecliptic of date",
      "time_scale": "TT; fixed TT minus UTC offset of 69.184 seconds applies to every civil input in these 2022-2026 cases",
      "algorithm": "signed-longitude sign changes on 0.0625 TT-day partitions, refined by 60 bisection iterations; these positive cases do not seek stationary tangencies or adjacent double crossings inside one partition and are not a complete event oracle",
      "manual": "https://www.astro.com/swisseph/swephprg.htm",
      "recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    },
    "cases": cases,
  }
  args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
  for item in cases:
    print(
      item["name"], item["birth_utc"], len(item["hits"]), [hit["direction"] for hit in item["hits"]]
    )


if __name__ == "__main__":
  main()
