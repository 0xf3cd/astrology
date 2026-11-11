"""Generate independent solar/lunar references with pinned Moshier crossings.

使用钉版 Moshier 穿越接口生成独立的日月返照参考。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Final, Protocol, cast

_FLAGS: Final = 260
_BIRTH_OFFSET_SECONDS: Final = 64.184
_SEARCH_OFFSET_SECONDS: Final = 69.184
_WRAPPER_VERSION: Final = "2.10.3.2"
_LIBRARY_VERSION: Final = "2.10.03"


class _Swiss(Protocol):
  SUN: int
  MOON: int
  version: str

  def calc(self, jde_tt: float, body: int, flags: int) -> tuple[tuple[float, ...], int]: ...
  def julday(self, year: int, month: int, day: int, hour: float) -> float: ...
  def solcross(self, longitude: float, jde_tt: float, flags: int) -> float: ...
  def mooncross(self, longitude: float, jde_tt: float, flags: int) -> float: ...


def _tt(swe: _Swiss, utc: datetime, offset_seconds: float) -> float:
  hour = utc.hour + utc.minute / 60 + (utc.second + utc.microsecond / 1e6) / 3600
  return swe.julday(utc.year, utc.month, utc.day, hour) + offset_seconds / 86400


def _state(swe: _Swiss, body: int, jde_tt: float) -> tuple[float, float]:
  values, returned = swe.calc(jde_tt, body, _FLAGS)
  if returned != _FLAGS:
    raise RuntimeError("Reference calculation must use explicit Moshier plus speed flags 260")
  longitude, rate = values[0], values[3]
  if not math.isfinite(longitude) or not math.isfinite(rate):
    raise RuntimeError("Reference calculation returned a nonfinite longitude or rate")
  return longitude, rate


def generate_reference(swe: _Swiss, wrapper_version: str) -> dict[str, object]:
  """Generate the fixed synthetic cases without importing astrology or its backend.

  生成固定的合成样例，不导入 astrology 或其天文后端。
  """
  if wrapper_version != _WRAPPER_VERSION or swe.version != _LIBRARY_VERSION:
    raise RuntimeError("Reference generation requires pyswisseph 2.10.3.2 / Swiss 2.10.03")
  epoch = datetime(2000, 1, 1, 12, tzinfo=UTC)
  march_tt = _tt(swe, datetime(2000, 3, 1, tzinfo=UTC), _BIRTH_OFFSET_SECONDS)
  solar_zero = swe.solcross(0, march_tt, _FLAGS)
  lunar_zero = swe.mooncross(0, march_tt, _FLAGS)
  births = (
    ("leap_birth", datetime(2000, 2, 29, 12, tzinfo=UTC)),
    ("year_end", datetime(2000, 12, 31, 23, tzinfo=UTC)),
    ("solar_zero", epoch + timedelta(days=solar_zero - 2451545, seconds=-_BIRTH_OFFSET_SECONDS)),
    ("lunar_zero", epoch + timedelta(days=lunar_zero - 2451545, seconds=-_BIRTH_OFFSET_SECONDS)),
  )
  cases: list[dict[str, object]] = []
  for birth_name, birth in births:
    windows = [
      ("sun", swe.SUN, datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)),
      ("moon", swe.MOON, datetime(2023, 12, 1, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC)),
    ]
    if birth_name == "leap_birth":
      windows.append(
        ("moon", swe.MOON, datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 4, 1, tzinfo=UTC))
      )
    birth_tt = _tt(swe, birth, _BIRTH_OFFSET_SECONDS)
    for body_name, body, start, end in windows:
      level, _ = _state(swe, body, birth_tt)
      start_tt = _tt(swe, start, _SEARCH_OFFSET_SECONDS)
      end_tt = _tt(swe, end, _SEARCH_OFFSET_SECONDS)
      crossing = swe.solcross if body == swe.SUN else swe.mooncross
      instant = crossing(level, start_tt, _FLAGS)
      hits: list[dict[str, float]] = []
      previous = start_tt - 1
      while instant < end_tt:
        if not math.isfinite(instant) or instant < start_tt or instant <= previous:
          raise RuntimeError("Reference crossing times must increase within the interval")
        longitude, rate = _state(swe, body, instant)
        residual = (longitude - level + 180) % 360 - 180
        if abs(residual) >= 1e-6:
          raise RuntimeError("Reference crossing does not satisfy its natal longitude")
        hits.append(
          {
            "jde_tt": instant,
            "longitude_deg": longitude,
            "rate_deg_per_tt_day": rate,
            "residual_deg": residual,
          }
        )
        previous = instant
        instant = crossing(level, instant + 0.001, _FLAGS)
      if not math.isfinite(instant) or not hits:
        raise RuntimeError("The reference window must contain finite crossing times")
      cases.append(
        {
          "name": f"{birth_name}_{body_name}_{start.date()}",
          "body": body_name,
          "birth_utc": birth.isoformat(),
          "birth_jde_tt": birth_tt,
          "natal_longitude_deg": level,
          "start_utc": start.isoformat(),
          "end_utc": end.isoformat(),
          "hits": hits,
        }
      )
  return {
    "source": {
      "pyswisseph_version": wrapper_version,
      "library_version": swe.version,
      "ephemeris": "Moshier analytical, explicitly selected; no Swiss/JPL data-file fallback",
      "requested_flags": _FLAGS,
      "verified_calculation_flags": _FLAGS,
      "coordinates": "apparent geocentric tropical longitude, true equinox/ecliptic of date",
      "time_scale": "TT through solcross/mooncross ET entry points",
      "birth_tt_minus_utc_seconds": _BIRTH_OFFSET_SECONDS,
      "search_tt_minus_utc_seconds": _SEARCH_OFFSET_SECONDS,
      "manual": "https://www.astro.com/swisseph/swephprg.htm",
      "recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    },
    "calibration": {
      "native_version": "1.1.1",
      "maximum_observed_time_difference_seconds": {
        "sun": 1.3446718454360962,
        "moon": 11.77133023738861,
      },
      "fixture_time_tolerance_seconds": {"sun": 5, "moon": 30},
      "scope": "These synthetic 2000 natal instants and 2023-2024 return intervals only; "
      "cross-model agreement is not a general astronomical accuracy bound.",
    },
    "cases": cases,
  }


def main() -> None:
  """Write the independently generated fixture to the selected path.

  将独立生成的参考数据写入指定路径。
  """
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--output", type=Path, default=Path("tests/reference/return_reference.json"))
  args = parser.parse_args()
  swe = cast(_Swiss, importlib.import_module("swisseph"))
  result = generate_reference(swe, version("pyswisseph"))
  args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
  main()
