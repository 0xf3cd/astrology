"""Agreement with independent JPL Horizons references and definition-level node references.

与 JPL Horizons 的独立参考以及按定义重算的交点参考是否一致。
"""

import hashlib
import itertools
import json
import math
from datetime import datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import TypedDict, cast

import pytest

from astrology import (
  AspectRule,
  BirthRecord,
  Body,
  ChartConfig,
  EclipticPosition,
  FixedOffset,
  HouseSystem,
  Location,
  LunarNode,
  MajorAspect,
  NatalChart,
  ObjectOrb,
  OrbCombination,
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
  center_source: str
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
# Body tolerances follow the upstream's own model error against Horizons, so a
# correct upstream passes at any instant and not only at the two fixture
# instants. The Sun and planets agree to about 0.8" in longitude over 24 instants
# in 2000-2002, and within 1.34" at the 2020 fixture instant; the truncated lunar
# model within 9.96" in longitude and 2.39" in latitude over 60 instants in
# 2000-2030. Those samples were taken ad hoc and are not kept in the repository.
# 天体容差按上游模型自身对 Horizons 的误差来定，这样正确的上游在任何时刻都能通过，
# 而不只是在两个夹具时刻。采样是临时做的，没有留在仓库里。
LONGITUDE_TOLERANCE_ARCSEC = 3.0
MOON_LONGITUDE_TOLERANCE_ARCSEC = 15.0
LATITUDE_TOLERANCE_ARCSEC = 1.0
MOON_LATITUDE_TOLERANCE_ARCSEC = 3.0
NODE_TOLERANCE_ARCSEC = 1.0
# The Ascendant, Midheaven and Placidus cusps follow UT1, which the library
# models from civil UTC while Horizons derives sidereal time from observed UT1.
# The two fixture instants differ by at most 0.91 arcseconds; 0.001 degrees is 3.6
# arcseconds, about four times that, and rejects a mean sidereal time used for the
# apparent one.
# 上升点、中天和 Placidus 宫头都随 UT1 变化：本库按模型由民用 UTC 推出 UT1，Horizons 的
# 恒星时用的是观测到的 UT1。两个夹具时刻最多差 0.91″，而 0.001° 是 3.6″，约有四倍余量，也足以拒绝把平恒星时当视恒星时用。
AXIS_TOLERANCE_DEGREES = 0.001
CUSP_TOLERANCE_DEGREES = 0.001
# JDE(TT) - JD(UTC) is an exact leap-second relation, not an approximation.
TIME_TOLERANCE_DAYS = 1e-9

# The target kernel Horizons names for each body, and the geocenter kernel.
# 各天体在 Horizons 目标行上的星历核，以及地心的星历核。
EXPECTED_EPHEMERIS_SOURCES = {
  "sun": "DE441",
  "moon": "DE441",
  "mercury": "DE441",
  "venus": "DE441",
  "mars": "mar099",
  "jupiter": "jup365_merged",
  "saturn": "sat441l",
  "uranus": "ura184_merged",
  "neptune": "nep098_merged",
  "pluto": "plu060_merged",
}

# The fixture without its retrieval time is pinned, so an edited reference value
# cannot pass unnoticed; refetching the same data leaves the digest unchanged.
# 对夹具（去掉取数时间后）的内容钉住摘要：直接改参考数值会被发现；重新取回同样的数据，摘要不变。
EXPECTED_FIXTURE_DIGEST = "7c3e1990c5785c8a077498437bd835acba793fb55311c7a6ba0574ac2a7bfb2f"


def _fixture() -> _Fixture:
  return cast(_Fixture, json.loads(FIXTURE.read_text(encoding="utf-8")))


def _cases() -> tuple[_Case, ...]:
  return tuple(_fixture()["cases"])


def _julian_day_utc(instant: tuple[int, int, int, int, int, int]) -> float:
  """Julian Day of a UTC calendar instant. UTC 日历时刻对应的儒略日。"""
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

  真黄赤交角（弧度）：Meeus 第 22 章的平黄赤交角，加上低精度的章动项。
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

  由子午圈赤经求上升点和中天的黄经；子午圈赤经取当地真恒星时。
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
  low-accuracy nutation in longitude. 平交点、五项真交点和黄经章动，单位为度。
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
  """Signed difference in degrees, wrapped to [-180, 180). 带符号的角度差，归到 [-180, 180) 内。"""
  return (first - second + 180.0) % 360.0 - 180.0


def _substantive_digest(fixture: _Fixture) -> str:
  """Hash the fixture without its retrieval time. 对去掉取数时间后的夹具取摘要。"""
  payload = {key: value for key, value in fixture.items() if key != "retrieved_utc"}
  canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
  return hashlib.sha256(canonical).hexdigest()


def _placidus_residual(
  house: int, cusp_deg: float, ramc_deg: float, latitude_deg: float, obliquity_rad: float
) -> float:
  """Degrees by which a cusp misses its Placidus time division.

  Placidus puts cusps 11 and 12 at one and two thirds of the cusp point's own
  diurnal semi-arc east of the meridian, and cusps 2 and 3 at one and two thirds
  of its nocturnal semi-arc beyond the horizon. The hour angle comes from the
  reference sidereal time, so the definition is checked without an iteration.

  宫头偏离 Placidus 时间分割的度数。Placidus 把第 11、12 宫头放在宫头点自身昼弧上、
  子午圈以东的 1/3 和 2/3 处，把第 2、3 宫头放在其夜弧上、地平线以下的 1/3 和 2/3 处。
  时角直接取参考恒星时，所以不用迭代就能核对这个定义。
  """
  longitude = math.radians(cusp_deg)
  right_ascension = math.degrees(
    math.atan2(math.sin(longitude) * math.cos(obliquity_rad), math.cos(longitude))
  )
  declination = math.asin(math.sin(obliquity_rad) * math.sin(longitude))
  diurnal = math.degrees(math.acos(-math.tan(math.radians(latitude_deg)) * math.tan(declination)))
  nocturnal = 180.0 - diurnal
  expected = {
    11: -diurnal / 3,
    12: -2 * diurnal / 3,
    2: -(diurnal + nocturnal / 3),
    3: -(diurnal + 2 * nocturnal / 3),
  }[house]
  return _angle_difference(ramc_deg - right_ascension, expected)


def _porphyry_cusps(ascendant_deg: float, midheaven_deg: float) -> dict[int, float]:
  """Cusps 11, 12, 2 and 3 of a Porphyry table, each quadrant trisected along the ecliptic.

  Porphyry 宫制的第 11、12、2、3 宫头：每个象限沿黄道三等分。
  """
  above = (ascendant_deg - midheaven_deg) % 360.0
  below = (midheaven_deg + 180.0 - ascendant_deg) % 360.0
  return {
    11: (midheaven_deg + above / 3) % 360.0,
    12: (midheaven_deg + 2 * above / 3) % 360.0,
    2: (ascendant_deg + below / 3) % 360.0,
    3: (ascendant_deg + 2 * below / 3) % 360.0,
  }


def _instant(case: _Case) -> datetime:
  """Read the reference instant as an aware UTC datetime. 把参考时刻读成带时区的 UTC 时间。"""
  return datetime.fromisoformat(case["utc"].replace("Z", "+00:00"))


def _resolved_for(case: _Case) -> ResolvedBirth:
  """Resolve the birth the reference case describes. 解析参考案例所描述的出生输入。"""
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
  return prepare_natal_input(record)


def _chart_for(case: _Case) -> tuple[NatalChart, ResolvedBirth]:
  """Build the chart the reference case describes. 按参考案例计算命盘。"""
  resolved = _resolved_for(case)
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


def _body_agrees(
  position: EclipticPosition,
  reference: _Body,
  longitude_shift_arcsec: float = 0.0,
  latitude_shift_arcsec: float = 0.0,
) -> bool:
  """Whether a position is within its tolerances of the reference, which may be displaced.

  The displacement lets a test show that a shifted reference is rejected.
  位置是否在容差之内；参考值可以人为偏移，用来证明偏移后的参考会被拒绝。
  """
  if position.identity is Body.MOON:
    longitude_tolerance = MOON_LONGITUDE_TOLERANCE_ARCSEC
    latitude_tolerance = MOON_LATITUDE_TOLERANCE_ARCSEC
  else:
    longitude_tolerance = LONGITUDE_TOLERANCE_ARCSEC
    latitude_tolerance = LATITUDE_TOLERANCE_ARCSEC
  longitude_difference = abs(
    _angle_difference(
      position.longitude_deg, reference["longitude_deg"] + longitude_shift_arcsec / 3600
    )
  )
  latitude_difference = abs(
    position.latitude_deg - (reference["latitude_deg"] + latitude_shift_arcsec / 3600)
  )
  return (
    longitude_difference * 3600 <= longitude_tolerance
    and latitude_difference * 3600 <= latitude_tolerance
  )


def _axes_agree(chart: NatalChart, case: _Case, ramc_shift_deg: float = 0.0) -> bool:
  """Whether the Ascendant and Midheaven match the reference sidereal time, which may be displaced.

  上升点和中天是否与参考恒星时一致；恒星时可以人为偏移。
  """
  ascendant, midheaven = _axes(
    float(case["local_apparent_sidereal_time_deg"]) + ramc_shift_deg,
    case["location"]["latitude"],
    _obliquity(chart.times.jde_tt),
  )
  return (
    abs(_angle_difference(chart.houses.ascendant_deg, ascendant)) <= AXIS_TOLERANCE_DEGREES
    and abs(_angle_difference(chart.houses.midheaven_deg, midheaven)) <= AXIS_TOLERANCE_DEGREES
  )


def _cusps_agree(chart: NatalChart, case: _Case, ramc_shift_deg: float = 0.0) -> bool:
  """Whether Placidus cusps 2, 3, 11 and 12 follow the definition, with a displaceable sidereal time.

  Placidus 第 2、3、11、12 宫头是否符合定义；恒星时可以人为偏移。
  """
  obliquity = _obliquity(chart.times.jde_tt)
  ramc = float(case["local_apparent_sidereal_time_deg"]) + ramc_shift_deg
  latitude = case["location"]["latitude"]
  cusps = chart.houses.cusps_deg
  return all(
    abs(_placidus_residual(house, cusps[house - 1], ramc, latitude, obliquity))
    <= CUSP_TOLERANCE_DEGREES
    for house in (11, 12, 2, 3)
  )


def _nodes_agree(chart: NatalChart, node_shift_arcsec: float = 0.0) -> bool:
  """Whether the mean and true ascending nodes match the Meeus definition, which may be displaced.

  平升交点和真升交点是否符合 Meeus 的定义；参考值可以人为偏移。
  """
  # The upstream refers the nodes to the true equinox of date, so the nutation in
  # longitude belongs to the reference as well.
  # 上游把交点算在当时的真春分点上，所以参考值也要加上黄经章动。
  mean, true, nutation = _meeus_nodes(chart.times.jde_tt)
  shift = node_shift_arcsec / 3600
  ascending = chart.positions[10]
  true_ascending = chart.positions[12]
  return (
    abs(_angle_difference(ascending.longitude_deg, mean + nutation + shift)) * 3600
    <= NODE_TOLERANCE_ARCSEC
    and abs(_angle_difference(true_ascending.longitude_deg, true + nutation + shift)) * 3600
    <= NODE_TOLERANCE_ARCSEC
  )


def test_the_fixture_records_its_own_provenance() -> None:
  fixture = _fixture()
  assert fixture["api"] == "https://ssd.jpl.nasa.gov/api/horizons.api"
  assert fixture["retrieved_utc"].endswith("+00:00")
  conventions = fixture["conventions"]
  assert "QUANTITIES=31" in conventions["positions"]
  assert "IAU76/80" in conventions["positions"]
  assert "nutation in obliquity" in conventions["axis"]
  assert "32.184" in conventions["tt_utc"]
  for case in _cases():
    assert case["house_system"] == "placidus"
    assert case["delta_at_source"]
    assert case["ephemeris_sources"] == EXPECTED_EPHEMERIS_SOURCES
    assert case["center_source"] == "DE441"
    queries = case["queries"]
    assert "local_apparent_sidereal_time" in queries
    for url in queries.values():
      assert url.startswith("https://ssd.jpl.nasa.gov/api/horizons.api?")


def test_the_fixture_values_are_the_pinned_ones() -> None:
  assert _substantive_digest(_fixture()) == EXPECTED_FIXTURE_DIGEST


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["identifier"]))
def test_body_positions_agree_with_horizons(case: _Case) -> None:
  chart, _ = _chart_for(case)
  for position in chart.positions[:10]:
    assert _body_agrees(position, case["bodies"][position.identity.value])


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
  assert _axes_agree(chart, case)


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["identifier"]))
def test_the_placidus_cusps_follow_the_time_division_of_their_semi_arcs(case: _Case) -> None:
  chart, _ = _chart_for(case)
  assert _cusps_agree(chart, case)
  cusps = chart.houses.cusps_deg
  for house in range(1, 7):
    assert abs(_angle_difference(cusps[house + 5], cusps[house - 1] + 180.0)) < 1e-9


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["identifier"]))
def test_the_placidus_check_rejects_a_different_house_system_and_a_shifted_cusp(
  case: _Case,
) -> None:
  chart, _ = _chart_for(case)
  obliquity = _obliquity(chart.times.jde_tt)
  ramc = float(case["local_apparent_sidereal_time_deg"])
  latitude = case["location"]["latitude"]
  houses = chart.houses
  porphyry = _porphyry_cusps(houses.ascendant_deg, houses.midheaven_deg)
  for house, cusp in porphyry.items():
    residual = _placidus_residual(house, cusp, ramc, latitude, obliquity)
    assert abs(residual) > 50 * CUSP_TOLERANCE_DEGREES
  for house in (11, 12, 2, 3):
    shifted = (houses.cusps_deg[house - 1] + 0.01) % 360.0
    residual = _placidus_residual(house, shifted, ramc, latitude, obliquity)
    assert abs(residual) > CUSP_TOLERANCE_DEGREES


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["identifier"]))
def test_the_lunar_nodes_agree_with_the_meeus_definition(case: _Case) -> None:
  chart, _ = _chart_for(case)
  assert _nodes_agree(chart)
  ascending, descending, true_ascending, true_descending = chart.positions[10:14]
  assert abs(_angle_difference(descending.longitude_deg, ascending.longitude_deg + 180.0)) < 1e-9
  assert (
    abs(_angle_difference(true_descending.longitude_deg, true_ascending.longitude_deg + 180.0))
    < 1e-9
  )


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["identifier"]))
def test_the_comparisons_reject_a_displaced_reference(case: _Case) -> None:
  # The displacements are written here and not read from the tolerances, so a
  # loosened tolerance or comparison fails this test.
  # 偏移量就写在这里，不从容差常量读取，所以无论放宽容差还是放宽比较，这个测试都会失败。
  chart, _ = _chart_for(case)
  by_identity = {position.identity: position for position in chart.positions}
  sun, moon = by_identity[Body.SUN], by_identity[Body.MOON]
  sun_reference, moon_reference = case["bodies"]["sun"], case["bodies"]["moon"]
  assert _body_agrees(sun, sun_reference)
  assert not _body_agrees(sun, sun_reference, longitude_shift_arcsec=4.0)
  assert not _body_agrees(sun, sun_reference, latitude_shift_arcsec=2.0)
  assert _body_agrees(moon, moon_reference, longitude_shift_arcsec=4.0)
  assert not _body_agrees(moon, moon_reference, longitude_shift_arcsec=20.0)
  assert not _body_agrees(moon, moon_reference, latitude_shift_arcsec=4.0)
  assert not _axes_agree(chart, case, ramc_shift_deg=0.003)
  assert not _cusps_agree(chart, case, ramc_shift_deg=0.003)
  assert not _nodes_agree(chart, node_shift_arcsec=2.0)


def test_the_reference_fixture_is_packaged_next_to_the_tests() -> None:
  assert FIXTURE.is_file()
  assert FIXTURE.name == "natal_reference.json"
  assert files("astrology.knowledge").joinpath("catalog.json").is_file()


# Astrodienst's published "Hellenistic" drawing style, read 2026-10-20 from
# https://www.astro.com/faq/fq_fh_owstyle_e.htm: only the conjunction, opposition,
# square, trine and sextile; an orb of 13 degrees for the Moon and 3 degrees for the
# Sun and the planets; the lunar node has no orb and no aspects are drawn for it. A
# line whose only satisfied end is the Moon is still drawn, so a pair that involves
# the Moon holds within the Moon's orb. The page publishes parameters, not the aspect
# list of any chart, so the expected hits below are derived from the Horizons
# longitudes with plain unoriented separations, apart from the library's oriented
# branches. The whole-sign (dotted) aspects of that style are not modeled here.
# Astrodienst 公布的 "Hellenistic" 绘图风格，2026-10-20 读自上面的网址：只用合相、对分、
# 四分、三分和六分；月亮的容许度 13°，太阳和行星 3°；月交点没有容许度，也不为它画相位。
# 只有月亮一端满足的线仍然会画出，所以涉及月亮的一对对象在月亮的容许度内成立。该页给出的是
# 参数，不是某张盘的相位表，所以下面的期望命中由 Horizons 的经度用无向间距的算术推出，
# 与本库的有向分支无关。该风格的整宫（虚线）相位不在这里建模。
HELLENISTIC_PLANETS = (
  Body.SUN,
  Body.MOON,
  Body.MERCURY,
  Body.VENUS,
  Body.MARS,
  Body.JUPITER,
  Body.SATURN,
)
HELLENISTIC_NODES = (LunarNode.MEAN_ASCENDING, LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING)
HELLENISTIC_ORB_DEGREES = 3.0
HELLENISTIC_MOON_ORB_DEGREES = 13.0
ASPECT_ANGLES = {
  MajorAspect.CONJUNCTION: 0.0,
  MajorAspect.SEXTILE: 60.0,
  MajorAspect.SQUARE: 90.0,
  MajorAspect.TRINE: 120.0,
  MajorAspect.OPPOSITION: 180.0,
}
# No pair may sit this close to an orb limit, so the library's few arcseconds of
# difference from Horizons cannot move a hit across it: 15 arcseconds is 0.004 degrees.
# 没有任何一对对象可以离容许度限度这么近，这样本库与 Horizons 相差的几角秒就不会让命中
# 越过限度：15″ 只有 0.004°。
LIMIT_MARGIN_DEGREES = 0.4

AspectKey = tuple[Body | LunarNode, Body | LunarNode, MajorAspect]


def _hellenistic_rules(
  moon_orb: float | None = HELLENISTIC_MOON_ORB_DEGREES,
) -> list[AspectRule]:
  entries = [] if moon_orb is None else [ObjectOrb(Body.MOON, moon_orb)]
  return [AspectRule(aspect, HELLENISTIC_ORB_DEGREES, entries) for aspect in ASPECT_ANGLES]


def _hellenistic_hits(
  case: _Case,
  *,
  rules: list[AspectRule] | None = None,
  combination: OrbCombination | None = OrbCombination.EITHER_WITHIN_OWN_ORB,
  aspect_objects: tuple[Body | LunarNode, ...] | None = HELLENISTIC_PLANETS,
) -> set[AspectKey]:
  """The library's aspects among the chosen objects, as pair-and-aspect keys.

  本库在所选对象之间求出的相位，记为「配对加相位」。
  """
  chosen = _hellenistic_rules() if rules is None else rules
  config = ChartConfig(
    HouseSystem.WHOLE_SIGN,
    (*HELLENISTIC_PLANETS, *HELLENISTIC_NODES),
    chosen,
    aspect_objects=None if aspect_objects is None else list(aspect_objects),
    orb_combination=combination if any(rule.object_orbs for rule in chosen) else None,
  )
  chart = natal_chart(_resolved_for(case), config)
  return {(hit.first, hit.second, hit.aspect) for hit in chart.aspects}


def _reference_hellenistic(case: _Case) -> tuple[set[AspectKey], float]:
  """Expected hits from the Horizons longitudes, and the smallest distance to any limit.

  由 Horizons 经度得出的期望命中，以及所有配对到限度的最小距离。
  """
  hits: set[AspectKey] = set()
  margin = 180.0
  for first, second in itertools.combinations(HELLENISTIC_PLANETS, 2):
    separation = abs(
      _angle_difference(
        case["bodies"][first.value]["longitude_deg"], case["bodies"][second.value]["longitude_deg"]
      )
    )
    limit = (
      HELLENISTIC_MOON_ORB_DEGREES if Body.MOON in (first, second) else HELLENISTIC_ORB_DEGREES
    )
    for aspect, angle in ASPECT_ANGLES.items():
      distance = abs(separation - angle)
      margin = min(margin, abs(distance - limit))
      if distance <= limit:
        hits.add((first, second, aspect))
  return hits, margin


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["identifier"])
def test_aspects_agree_with_the_published_hellenistic_orbs(case: _Case) -> None:
  expected, margin = _reference_hellenistic(case)
  assert margin > LIMIT_MARGIN_DEGREES
  assert _hellenistic_hits(case) == expected


def test_the_hellenistic_reference_has_hits_and_near_misses_to_tell_conventions_apart() -> None:
  counts = [len(_reference_hellenistic(case)[0]) for case in _cases()]
  assert counts == [3, 6]


def _hits_under(case: _Case, defect: str) -> set[AspectKey]:
  if defect == "no_moon_orb":
    return _hellenistic_hits(case, rules=_hellenistic_rules(None), combination=None)
  if defect == "both_within_own_orb":
    return _hellenistic_hits(case, combination=OrbCombination.BOTH_WITHIN_OWN_ORB)
  if defect == "mean_of_orbs":
    return _hellenistic_hits(case, combination=OrbCombination.MEAN_OF_ORBS)
  if defect == "moon_orb_for_all":
    wide = [AspectRule(aspect, HELLENISTIC_MOON_ORB_DEGREES) for aspect in ASPECT_ANGLES]
    return _hellenistic_hits(case, rules=wide, combination=None)
  return _hellenistic_hits(case, aspect_objects=None)


# One case alone cannot tell every departure apart: at the northern instant no pair
# with the Moon lies between 8 and 13 degrees, so the mean of the orbs agrees with the
# published rule there. The two instants together tell all of them apart.
# 单个案例分不出所有的偏离：北站点没有月亮的配对落在 8° 到 13° 之间，所以在那里取容许度
# 的平均与公布的规则一致。两个案例合起来才能分出每一种偏离。
@pytest.mark.parametrize(
  "defect",
  ["no_moon_orb", "both_within_own_orb", "mean_of_orbs", "moon_orb_for_all", "node_takes_part"],
)
def test_a_departure_from_the_published_convention_changes_the_hits(defect: str) -> None:
  differing = [
    case["identifier"]
    for case in _cases()
    if _hits_under(case, defect) != _reference_hellenistic(case)[0]
  ]
  assert differing


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["identifier"])
def test_the_lunar_node_is_shown_but_takes_part_in_no_aspect(case: _Case) -> None:
  chart = natal_chart(
    _resolved_for(case),
    ChartConfig(
      HouseSystem.WHOLE_SIGN,
      (*HELLENISTIC_PLANETS, *HELLENISTIC_NODES),
      _hellenistic_rules(),
      aspect_objects=list(HELLENISTIC_PLANETS),
      orb_combination=OrbCombination.EITHER_WITHIN_OWN_ORB,
    ),
  )
  assert {position.identity for position in chart.positions} >= set(HELLENISTIC_NODES)
  assert chart.effective.aspect_objects == HELLENISTIC_PLANETS
  assert not any(
    node in (hit.first, hit.second) for hit in chart.aspects for node in HELLENISTIC_NODES
  )
