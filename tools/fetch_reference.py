"""Fetch JPL Horizons reference data for two natal-chart reference cases.

Reuses the exact query shape validated by the batch-2 plan review:
apparent geocentric ecliptic lon/lat (QUANTITIES=31, DE440/441, TIME_TYPE=TT at
the upstream jde_tt) and local apparent sidereal time at the site (QUANTITIES=7,
TIME_TYPE=UT). Writes tests/reference/natal_reference.json; compares northern
case B against the plan-review raw files kept in .review/probes/.

Stdlib only; no key required. Run: python3 tools/fetch_reference.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import TypedDict

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
BODIES = {
  "sun": "10",
  "moon": "301",
  "mercury": "199",
  "venus": "299",
  "mars": "499",
  "jupiter": "599",
  "saturn": "699",
  "uranus": "799",
  "neptune": "899",
  "pluto": "999",
}
# TT - UTC = 32.184 s + delta AT; leap seconds from IERS UTC-TAI history.


class _Body(TypedDict):
  """One body's apparent ecliptic coordinates. 单个天体的视黄道坐标。"""

  longitude_deg: float
  latitude_deg: float


class _Case(TypedDict):
  """A reference case request. 一个参考案例的请求参数。"""

  identifier: str
  utc: str
  delta_at_seconds: float
  delta_at_source: str
  location: dict[str, float]
  house_system: str


class _CaseResult(TypedDict):
  """A fetched reference case. 取回的参考案例。"""

  identifier: str
  utc: str
  location: dict[str, float]
  house_system: str
  delta_at_seconds: float
  delta_at_source: str
  jde_tt: float
  ephemeris_sources: dict[str, str]
  center_source: str
  queries: dict[str, str]
  bodies: dict[str, _Body]
  local_apparent_sidereal_time_deg: float


CASES: tuple[_Case, ...] = (
  {
    "identifier": "north-2003-64n",
    "utc": "2003-07-17T05:37:13Z",
    "delta_at_seconds": 32.0,
    "delta_at_source": "IERS leap-second history: delta AT = 32 s from 1999-01-01 until 2006-01-01",
    "location": {"latitude": 64.15, "longitude": -21.94},
    "house_system": "placidus",
  },
  {
    "identifier": "south-2020-34s",
    "utc": "2020-06-01T12:00:00Z",
    "delta_at_seconds": 37.0,
    "delta_at_source": "IERS leap-second history: delta AT = 37 s from 2017-01-01 onward",
    "location": {"latitude": -33.87, "longitude": 151.21},
    "house_system": "placidus",
  },
)


def jd_utc(instant: datetime) -> float:
  """Julian Day of a UTC datetime (Gregorian civil-to-days since 1970-01-01, +2440587.5)."""
  year, month, day = instant.year, instant.month, instant.day
  if month <= 2:
    year, month = year - 1, month + 12
  era = year // 400
  yoe = year - era * 400
  doy = (153 * (month - 3) + 2) // 5 + day - 1
  doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
  days = era * 146097 + doe - 719468
  fraction = (
    instant.hour * 3600 + instant.minute * 60 + instant.second + instant.microsecond / 1e6
  ) / 86400
  return days + 2440587.5 + fraction


def query(parameters: dict[str, str]) -> tuple[str, str]:
  """GET the Horizons API; return (response text, full URL used).

  `format=text` returns the ephemeris as plain text; a malformed request still
  comes back as a JSON object with an `error` member.
  """
  url = f"{API}?{urllib.parse.urlencode(parameters)}"
  request = urllib.request.Request(url, headers={"User-Agent": "astrology-reference-fetch"})
  with urllib.request.urlopen(request, timeout=60) as response:
    text = response.read().decode("utf-8")
  try:
    payload = json.loads(text)
  except ValueError:
    return text, url
  if "error" in payload:
    raise RuntimeError(f"Horizons error for {parameters}: {payload['error']}")
  return str(payload.get("result", text)), url


def rows(result: str) -> list[list[str]]:
  """Split a CSV ephemeris result into data rows between $$SOE/$$EOE."""
  if "$$SOE" not in result:
    raise RuntimeError(f"No ephemeris data in Horizons response: {result[:300]}")
  block = result.partition("$$SOE")[2].partition("$$EOE")[0]
  return [
    [field.strip() for field in line.split(",")]
    for line in block.strip().splitlines()
    if line.strip()
  ]


def source_marker(result: str, body_line: str) -> str:
  """Extract the ephemeris kernel from the named header line.

  Horizons names the kernel that provided a body's data on its own line; the
  target line names the body's kernel, the center line the geocenter's.
  Horizons 在各自的一行里写出所用的星历核：目标行是该天体的核，地心行是地心的核。
  """
  for line in result.splitlines():
    if line.strip().startswith(body_line) and "{source: " in line:
      return line.partition("{source: ")[2].rstrip("}")
  raise RuntimeError(f"No source marker for {body_line} in Horizons header")


def fetch_case(case: _Case) -> _CaseResult:
  """Fetch one case's body positions and local apparent sidereal time."""
  instant = datetime.fromisoformat(case["utc"].replace("Z", "+00:00")).astimezone(UTC)
  tt_jd = jd_utc(instant) + (32.184 + case["delta_at_seconds"]) / 86400
  location = case["location"]
  latitude, longitude = location["latitude"], location["longitude"]

  bodies: dict[str, _Body] = {}
  query_urls: dict[str, str] = {}
  sources: dict[str, str] = {}
  center_source = ""
  for name, command in BODIES.items():
    result, url = query(
      {
        "format": "text",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "TLIST": f"'{tt_jd:.10f}'",
        "TLIST_TYPE": "'JD'",
        "TIME_TYPE": "'TT'",
        "QUANTITIES": "'31'",
        "ANG_FORMAT": "'DEG'",
        "EXTRA_PREC": "'YES'",
        "CSV_FORMAT": "'YES'",
      }
    )
    row = rows(result)[0]
    bodies[name] = {"longitude_deg": float(row[3]), "latitude_deg": float(row[4])}
    query_urls[name] = url
    sources[name] = source_marker(result, "Target body name:")
    center = source_marker(result, "Center body name:")
    if not center_source:
      center_source = center

  result, url = query(
    {
      "format": "text",
      "COMMAND": "'10'",
      "OBJ_DATA": "'NO'",
      "MAKE_EPHEM": "'YES'",
      "EPHEM_TYPE": "'OBSERVER'",
      "CENTER": "'coord@399'",
      "COORD_TYPE": "'GEODETIC'",
      "SITE_COORD": f"'{longitude},{latitude},0'",
      "TLIST": f"'{instant.strftime('%Y-%m-%d %H:%M:%S')}'",
      "TIME_TYPE": "'UT'",
      "QUANTITIES": "'7'",
      "ANG_FORMAT": "'DEG'",
      "EXTRA_PREC": "'YES'",
      "CSV_FORMAT": "'YES'",
    }
  )
  last_row = rows(result)[0]
  last_hours = float(last_row[3])
  query_urls["local_apparent_sidereal_time"] = url

  return {
    "identifier": case["identifier"],
    "utc": case["utc"],
    "location": {"latitude": latitude, "longitude": longitude},
    "house_system": case["house_system"],
    "delta_at_seconds": case["delta_at_seconds"],
    "delta_at_source": case["delta_at_source"],
    "jde_tt": tt_jd,
    "ephemeris_sources": sources,
    "center_source": center_source,
    "queries": query_urls,
    "bodies": bodies,
    "local_apparent_sidereal_time_deg": last_hours * 15.0,
  }


def main() -> None:
  """Fetch every case, write the fixture and check it against the plan-review fetch."""
  root = pathlib.Path(__file__).resolve().parents[1]
  cases = [fetch_case(case) for case in CASES]
  fixture = {
    "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    "api": API,
    "conventions": {
      "positions": (
        "Apparent geocentric ecliptic longitude/latitude of date, geocenter 500@399, "
        "TIME_TYPE=TT at the instant's JDE(TT), QUANTITIES=31; Horizons reports the "
        "IAU76/80 ecliptic of date with light-time, gravitational deflection of light "
        "and stellar aberration"
      ),
      "axis": (
        "Local apparent sidereal time at the site (QUANTITIES=7, TIME_TYPE=UT) converted "
        "to RAMC degrees; Asc/MC derived test-side from RAMC and the Meeus mean "
        "obliquity plus the low-accuracy nutation in obliquity"
      ),
      "tt_utc": "JDE(TT) - JD(UTC) = (32.184 + delta AT) / 86400 exactly",
      "center_source": (
        "The geocenter kernel is taken from the center line of the first body query; "
        "Horizons echoes the requested kernel on that line for some targets"
      ),
    },
    "cases": cases,
  }
  target = root / "tests" / "reference" / "natal_reference.json"
  target.parent.mkdir(parents=True, exist_ok=True)
  target.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
  digest = hashlib.sha256(target.read_bytes()).hexdigest()
  print(f"wrote {target} sha256={digest}")

  # Consistency: northern case against the plan-review raw fetch kept in .review/probes.
  probes = root / ".review" / "probes"
  north = cases[0]
  if probes.is_dir():
    for name, command in BODIES.items():
      raw = (probes / f"horizons_{command}.txt").read_text(encoding="utf-8")
      row = rows(raw)[0]
      old = (float(row[3]), float(row[4]))
      new = (north["bodies"][name]["longitude_deg"], north["bodies"][name]["latitude_deg"])
      if old != new:
        raise RuntimeError(f"Northern {name} differs from plan-review raw data: {old} vs {new}")
    raw_last = rows((probes / "horizons_last.txt").read_text(encoding="utf-8"))[0]
    if float(raw_last[3]) * 15.0 != north["local_apparent_sidereal_time_deg"]:
      raise RuntimeError("Northern LAST differs from plan-review raw data")
    print("northern case matches plan-review raw fetch bit for bit")


if __name__ == "__main__":
  main()
