"""Agreement with independent JPL Horizons references and definition-level node references.

与 JPL Horizons 独立参考及定义级交点参考的一致性。
"""

import json
import math
from datetime import datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import TypedDict, cast

import pytest

from astrology import (
  BirthRecord,
  Body,
  ChartConfig,
  FixedOffset,
  HouseSystem,
  Location,
  LunarNode,
  NatalChart,
  ResolvedBirth,
  TimePrecision,
  natal_chart,
  prepare_natal_input,
)


class _Body(TypedDict):
  """One reference body's apparent ecliptic coordinates. 一个参考天体的视黄道坐标。"""

  longitude_deg: float
  latitude_deg: float


class _Location(TypedDict):
  """A reference site's geographic position. 参考地点的地理位置。"""

  latitude: float
  longitude: float


class _Case(TypedDict):
  """One reference case. 一个参考案例。"""

  identifier: str
  utc: str
  location: _Location
  house_system: str
  delta_at_seconds: float
  delta_at_source: str
  jde_tt: float
  ephemeris_sources: dict[str, str]
  queries: dict[str, str]
  bodies: dict[str, _Body]
  local_apparent_sidereal_time_deg: float


class _Fixture(TypedDict):
  """The reference file as a whole. 整个参考文件。"""

  retrieved_utc: str
  api: str
  conventions: dict[str, str]
  cases: list[_Case]


# The fixture is a project file, not a package resource.
FIXTURE = Path(__file__).resolve().parent / "reference" / "natal_reference.json"

# Tolerances, in arcseconds unless stated otherwise. 容差，除注明外均以角秒计。
LONGITUDE_TOLERANCE_ARCSEC = 3.0
MOON_LONGITUDE_TOLERANCE_ARCSEC = 10.0
LATITUDE_TOLERANCE_ARCSEC = 1.0
NODE_TOLERANCE_ARCSEC = 1.0
# The Ascendant and Midheaven depend on UT1, which the library models rather
# than observes; the bound covers the modelled-versus-observed difference.
# 上升点与中天依赖 UT1，本库用模型推得而非观测值，容差覆盖模型与观测之差。
AXIS_TOLERANCE_DEGREES = 0.005
# JDE(TT) - JD(UTC) is an exact leap-second relation, not an approximation.
TIME_TOLERANCE_DAYS = 1e-9


def _fixture() -> _Fixture:
  return cast(_Fixture, json.loads(FIXTURE.read_text(encoding="utf-8")))


def _cases() -> tuple[_Case, ...]:
  return tuple(_fixture()["cases"])


def _julian_day_utc(instant: tuple[int, int, int, int, int, int]) -> float:
  """Julian Day of a UTC calendar instant. UTC 历日时刻的儒略日。"""
  year, month, day, hour, minute, second = instant
  if month <= 2:
    year, month = year - 1, month + 12
  era = year // 400
  year_of_era = year - era * 400
  day_of_year = (153 * (month - 3) + 2) // 5 + day - 1
  day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
  days = era * 146097 + day_of_era - 719468
  return days + 2440587.5 + (hour * 3600 + minute * 60 + second) / 86400


def _obliquity(jde_tt: float) -> float:
  """True obliquity in radians: Meeus ch. 22 mean obliquity plus low-accuracy nutation.

  真黄赤交角（弧度）：Meeus 第 22 章平黄赤交角加低精度章动项。
  """
  t = (jde_tt - 2451545.0) / 36525
  mean = 23.4392911111 - (46.8150 * t + 0.00059 * t**2 - 0.001813 * t**3) / 3600
  omega = math.radians(125.04452 - 1934.136261 * t)
  sun = math.radians(280.4665 + 36000.7698 * t)
  moon = math.radians(218.3165 + 481267.8813 * t)
  nutation = (
    9.20 * math.cos(omega)
    + 0.57 * math.cos(2 * sun)
    + 0.10 * math.cos(2 * moon)
    - 0.09 * math.cos(2 * omega)
  ) / 3600
  return math.radians(mean + nutation)


def _axes(ramc_deg: float, latitude_deg: float, obliquity_rad: float) -> tuple[float, float]:
  """Ascendant and Midheaven ecliptic longitudes from the meridian's right ascension.

  由子午圈赤经求上升点与中天的黄经。子午圈赤经取当地真恒星时。
  """
  ramc = math.radians(ramc_deg)
  latitude = math.radians(latitude_deg)
  midheaven = (
    math.degrees(math.atan2(math.sin(ramc), math.cos(ramc) * math.cos(obliquity_rad))) % 360
  )
  ascendant = (
    math.degrees(
      math.atan2(
        math.cos(ramc),
        -(math.sin(ramc) * math.cos(obliquity_rad) + math.tan(latitude) * math.sin(obliquity_rad)),
      )
    )
    % 360
  )
  return ascendant, midheaven


def _meeus_nodes(jde_tt: float) -> tuple[float, float, float]:
  """Mean node, five-term true node and nutation in longitude, in degrees.

  Meeus ch. 47 mean-node and five-term true-node series with the ch. 22
  low-accuracy nutation in longitude. 平交点、五项真交点及黄经章动（度）。
  """
  t = (jde_tt - 2451545.0) / 36525
  elongation = (
    297.8501921 + 445267.1114034 * t - 0.0018819 * t**2 + t**3 / 545868 - t**4 / 113065000
  )
  sun_anomaly = 357.5291092 + 35999.0502909 * t - 0.0001536 * t**2 + t**3 / 24490000
  moon_anomaly = (
    134.9633964 + 477198.8675055 * t + 0.0087414 * t**2 + t**3 / 69699 - t**4 / 14712000
  )
  latitude_argument = (
    93.2720950 + 483202.0175233 * t - 0.0036539 * t**2 - t**3 / 3526000 + t**4 / 863310000
  )
  mean = (125.0445479 - 1934.1362891 * t + 0.0020754 * t**2 + t**3 / 467441 - t**4 / 60616000) % 360
  true = (
    mean
    - 1.4979 * math.sin(math.radians(2 * (elongation - latitude_argument)))
    - 0.1500 * math.sin(math.radians(sun_anomaly))
    - 0.1226 * math.sin(math.radians(2 * elongation))
    + 0.1176 * math.sin(math.radians(2 * latitude_argument))
    - 0.0801 * math.sin(math.radians(2 * (moon_anomaly - latitude_argument)))
  ) % 360
  sun = 280.4665 + 36000.7698 * t
  moon = 218.3165 + 481267.8813 * t
  nutation = (
    -17.20 * math.sin(math.radians(mean))
    - 1.32 * math.sin(math.radians(2 * sun))
    - 0.23 * math.sin(math.radians(2 * moon))
    + 0.21 * math.sin(math.radians(2 * mean))
  ) / 3600
  return mean, true, nutation


def _angle_difference(first: float, second: float) -> float:
  """Signed difference in degrees, wrapped to [-180, 180). 归一化到 [-180, 180) 的角度差。"""
  return (first - second + 180.0) % 360.0 - 180.0


def _instant(case: _Case) -> datetime:
  """Read the reference instant as an aware UTC datetime. 读取参考时刻（UTC 带时区）。"""
  return datetime.fromisoformat(case["utc"].replace("Z", "+00:00"))


def _chart_for(case: _Case) -> tuple[NatalChart, ResolvedBirth]:
  """Build the chart the reference case describes. 按参考案例计算命盘。"""
  instant = _instant(case)
  location = case["location"]
  record = BirthRecord(
    instant.date(),
    instant.time(),
    FixedOffset(timedelta(0)),
    Location(location["latitude"], location["longitude"]),
    TimePrecision.SECOND,
    {"reference": case["identifier"]},
  )
  resolved = prepare_natal_input(record)
  config = ChartConfig(
    HouseSystem.PLACIDUS,
    (
      Body.SUN,
      Body.MOON,
      Body.MERCURY,
      Body.VENUS,
      Body.MARS,
      Body.JUPITER,
      Body.SATURN,
      Body.URANUS,
      Body.NEPTUNE,
      Body.PLUTO,
      LunarNode.MEAN_ASCENDING,
      LunarNode.MEAN_DESCENDING,
      LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING,
      LunarNode.MEEUS_FIVE_TERM_TRUE_DESCENDING,
    ),
    (),
  )
  return natal_chart(resolved, config), resolved


def test_the_fixture_records_its_own_provenance() -> None:
  fixture = _fixture()
  assert fixture["api"] == "https://ssd.jpl.nasa.gov/api/horizons.api"
  assert fixture["retrieved_utc"].endswith("+00:00")
  conventions = fixture["conventions"]
  assert "QUANTITIES=31" in conventions["positions"]
  assert "32.184" in conventions["tt_utc"]
  for case in _cases():
    assert case["house_system"] == "placidus"
    assert case["delta_at_source"]
    sources = case["ephemeris_sources"]
    assert set(sources) == {
      "sun",
      "moon",
      "mercury",
      "venus",
      "mars",
      "jupiter",
      "saturn",
      "uranus",
      "neptune",
      "pluto",
    }
    assert "DE4" in sources["sun"]
    queries = case["queries"]
    assert "local_apparent_sidereal_time" in queries
    for url in queries.values():
      assert url.startswith("https://ssd.jpl.nasa.gov/api/horizons.api?")


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["identifier"]))
def test_body_positions_agree_with_horizons(case: _Case) -> None:
  chart, _ = _chart_for(case)
  bodies = case["bodies"]
  for position in chart.positions[:10]:
    reference = bodies[position.identity.value]
    longitude_tolerance = (
      MOON_LONGITUDE_TOLERANCE_ARCSEC
      if position.identity is Body.MOON
      else LONGITUDE_TOLERANCE_ARCSEC
    )
    longitude_difference = abs(
      _angle_difference(position.longitude_deg, reference["longitude_deg"])
    )
    assert longitude_difference * 3600 <= longitude_tolerance
    latitude_difference = abs(position.latitude_deg - reference["latitude_deg"])
    assert latitude_difference * 3600 <= LATITUDE_TOLERANCE_ARCSEC


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["identifier"]))
def test_the_time_scale_follows_the_leap_second_table(case: _Case) -> None:
  chart, resolved = _chart_for(case)
  instant = _instant(case)
  jd_utc = _julian_day_utc(
    (
      instant.year,
      instant.month,
      instant.day,
      instant.hour,
      instant.minute,
      instant.second,
    )
  )
  expected = jd_utc + (32.184 + float(case["delta_at_seconds"])) / 86400
  assert abs(chart.times.jde_tt - expected) <= TIME_TOLERANCE_DAYS
  assert abs(chart.times.jde_tt - float(case["jde_tt"])) <= TIME_TOLERANCE_DAYS
  assert chart.times.jd_ut1 < chart.times.jde_tt
  assert resolved.utc == instant


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["identifier"]))
def test_the_axes_agree_with_the_reference_sidereal_time(case: _Case) -> None:
  chart, _ = _chart_for(case)
  location = case["location"]
  obliquity = _obliquity(chart.times.jde_tt)
  ascendant, midheaven = _axes(
    float(case["local_apparent_sidereal_time_deg"]), location["latitude"], obliquity
  )
  assert abs(_angle_difference(chart.houses.ascendant_deg, ascendant)) <= AXIS_TOLERANCE_DEGREES
  assert abs(_angle_difference(chart.houses.midheaven_deg, midheaven)) <= AXIS_TOLERANCE_DEGREES


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["identifier"]))
def test_the_lunar_nodes_agree_with_the_meeus_definition(case: _Case) -> None:
  chart, _ = _chart_for(case)
  mean, true, nutation = _meeus_nodes(chart.times.jde_tt)
  ascending = chart.positions[10]
  descending = chart.positions[11]
  true_ascending = chart.positions[12]
  true_descending = chart.positions[13]
  # The upstream refers the nodes to the true equinox of date, so the nutation
  # in longitude belongs to the reference as well. 上游交点以瞬时真春分点为基准，
  # 参考值同样要加黄经章动。
  assert (
    abs(_angle_difference(ascending.longitude_deg, mean + nutation)) * 3600 <= NODE_TOLERANCE_ARCSEC
  )
  assert (
    abs(_angle_difference(true_ascending.longitude_deg, true + nutation)) * 3600
    <= NODE_TOLERANCE_ARCSEC
  )
  assert abs(_angle_difference(descending.longitude_deg, ascending.longitude_deg + 180.0)) < 1e-9
  assert (
    abs(_angle_difference(true_descending.longitude_deg, true_ascending.longitude_deg + 180.0))
    < 1e-9
  )


def test_the_reference_fixture_is_packaged_next_to_the_tests() -> None:
  assert FIXTURE.is_file()
  assert FIXTURE.name == "natal_reference.json"
  assert files("astrology.knowledge").joinpath("catalog.json").is_file()
