"""Natal chart composition, entry conditions, failure classification and provenance.

本命盘组合、入口条件、失败分类与来源记录。
"""

import subprocess
import sys
from dataclasses import FrozenInstanceError
from datetime import date, time, timedelta
from importlib.metadata import version

import pytest

from astrology import (
  BirthRecord,
  Body,
  ChartConfig,
  ChartDomainError,
  FixedOffset,
  HouseSystem,
  Location,
  LunarNode,
  MissingBirthDataError,
  ResolvedBirth,
  TimePrecision,
  house_of,
  natal_chart,
  prepare_natal_input,
  resolve_birth_time,
  sign_degree,
  sign_of,
)

# A northern, non-integer-minute instant used by several cases.
_NORTH = (date(2003, 7, 17), time(5, 37, 13), 64.15, -21.94)


def record_at(
  day: date,
  clock: time,
  latitude: float | None,
  longitude: float = 0.0,
) -> BirthRecord:
  """Build a synthetic record with an explicit UTC offset. 建立带显式 UTC 偏移的合成记录。"""
  location = None if latitude is None else Location(latitude, longitude)
  return BirthRecord(
    day,
    clock,
    FixedOffset(timedelta(0)),
    location,
    TimePrecision.SECOND,
    {"record": "synthetic"},
  )


def resolved_at(
  day: date,
  clock: time,
  latitude: float,
  longitude: float = 0.0,
) -> ResolvedBirth:
  """Resolve a synthetic record that carries a location. 解析带地点的合成记录。"""
  return prepare_natal_input(record_at(day, clock, latitude, longitude))


def config_for(
  system: HouseSystem = HouseSystem.WHOLE_SIGN,
  objects: tuple[Body | LunarNode, ...] = (Body.SUN,),
) -> ChartConfig:
  """Build a request without aspect rules. 建立不含相位规则的请求。"""
  return ChartConfig(system, objects, ())


def test_a_missing_location_is_rejected() -> None:
  resolved = resolve_birth_time(record_at(*_NORTH[:2], None))
  assert resolved.record.location is None
  with pytest.raises(MissingBirthDataError):
    natal_chart(resolved, config_for())


@pytest.mark.parametrize("latitude", [90.0, -90.0])
def test_a_polar_latitude_is_outside_the_geometry_domain(latitude: float) -> None:
  resolved = resolved_at(date(2003, 7, 17), time(12, 0), latitude)
  with pytest.raises(ChartDomainError) as caught:
    natal_chart(resolved, config_for())
  assert caught.value.house_system is HouseSystem.WHOLE_SIGN
  # Rejected before any native call, so no upstream detail is claimed.
  assert caught.value.operation is None
  assert caught.value.recorded is None
  assert caught.value.upstream_message is None


def test_a_civil_year_beyond_the_supported_range_is_rejected() -> None:
  resolved = resolved_at(date(2100, 1, 1), time(12, 0), 0.0)
  with pytest.raises(ChartDomainError) as caught:
    natal_chart(resolved, config_for())
  assert caught.value.house_system is HouseSystem.WHOLE_SIGN
  assert caught.value.operation is None
  assert caught.value.upstream_message is None


def test_the_upper_jde_bound_is_reported_as_a_domain_error() -> None:
  # The upstream JDE(TT) domain ends inside 2099-12-31; 14:00 UTC is still
  # inside it and 16:00 UTC is not. 上游 JDE(TT) 有效域在 2099-12-31 内结束。
  inside = natal_chart(resolved_at(date(2099, 12, 31), time(14, 0), 0.0), config_for())
  assert inside.positions[0].longitude_deg >= 0.0
  with pytest.raises(ChartDomainError) as caught:
    natal_chart(resolved_at(date(2099, 12, 31), time(16, 0), 0.0), config_for())
  assert caught.value.house_system is HouseSystem.WHOLE_SIGN
  assert caught.value.operation == "chart_snapshot"
  assert caught.value.recorded is True
  assert caught.value.upstream_message


def test_a_high_latitude_placidus_failure_is_reported_without_substitution() -> None:
  resolved = resolved_at(date(1990, 6, 21), time(0, 0), 69.65)
  with pytest.raises(ChartDomainError) as caught:
    natal_chart(resolved, config_for(HouseSystem.PLACIDUS))
  assert caught.value.house_system is HouseSystem.PLACIDUS
  assert caught.value.operation == "chart_snapshot"
  assert caught.value.recorded is True
  assert caught.value.upstream_message
  # The same instant succeeds with the other systems, so the failure above was
  # the requested geometry and not the instant.
  for system in (HouseSystem.EQUAL, HouseSystem.WHOLE_SIGN):
    chart = natal_chart(resolved, config_for(system))
    assert chart.effective.house_system is system
    assert chart.houses.system is system
    assert chart.requested.house_system is system


def test_failures_are_classified_by_structure_and_not_by_message_text() -> None:
  # A pre-call rejection carries no upstream detail; an upstream failure
  # carries the operation and recording status. Neither is decided by reading
  # the message. 调用前拒绝不带上游细节；上游失败携带操作与记录状态，分类不靠解析消息文本。
  with pytest.raises(ChartDomainError) as rejected:
    natal_chart(resolved_at(date(2100, 1, 1), time(12, 0), 0.0), config_for())
  assert rejected.value.operation is None
  with pytest.raises(ChartDomainError) as reported:
    natal_chart(resolved_at(date(1990, 6, 21), time(0, 0), 69.65), config_for(HouseSystem.PLACIDUS))
  assert reported.value.operation == "chart_snapshot"
  assert reported.value.recorded is True


def test_the_delta_t_model_and_the_astronomy_version_are_recorded() -> None:
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for())
  assert chart.effective.delta_t_model == "algo5"
  assert chart.provenance.celestial_version == version("celestial-calendar")
  assert chart.provenance.ut1_derivation == "delta_t_model_from_civil_utc"


def test_the_coordinate_convention_is_recorded() -> None:
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for())
  assert chart.provenance.position_frame == "apparent_geocentric_true_ecliptic_of_date"


def test_requested_and_effective_configuration_are_kept_apart() -> None:
  request = config_for(HouseSystem.EQUAL)
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), request)
  assert chart.requested is request
  assert chart.effective.house_system is request.house_system
  assert chart.effective.evaluation == "fixed_fourteen_object_joint_snapshot"


def test_positions_do_not_depend_on_the_location() -> None:
  northern = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for())
  southern = natal_chart(resolved_at(*_NORTH[:2], -33.87, 151.21), config_for())
  assert northern.positions == southern.positions
  assert northern.times == southern.times
  assert northern.houses != southern.houses


def test_selecting_one_object_does_not_widen_the_evaluation_domain() -> None:
  outside = resolved_at(date(2099, 12, 31), time(16, 0), 0.0)
  with pytest.raises(ChartDomainError):
    natal_chart(outside, config_for(HouseSystem.WHOLE_SIGN, (Body.SUN,)))
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for())
  assert len(chart.positions) == 1
  assert chart.effective.evaluation == "fixed_fourteen_object_joint_snapshot"


def test_whole_sign_keeps_the_ascendant_in_the_first_house() -> None:
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for(HouseSystem.WHOLE_SIGN))
  cusps = chart.houses.cusps_deg
  assert chart.houses.ascendant_deg != cusps[0]
  assert house_of(chart.houses.ascendant_deg, cusps) == 1
  # The Midheaven is in the eighth house of this chart, not the tenth.
  assert chart.houses.midheaven_deg != cusps[9]
  assert house_of(chart.houses.midheaven_deg, cusps) == 8


def test_placidus_keeps_the_ascendant_and_midheaven_on_their_cusps() -> None:
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for(HouseSystem.PLACIDUS))
  assert chart.houses.cusps_deg[0] == chart.houses.ascendant_deg
  assert chart.houses.cusps_deg[9] == chart.houses.midheaven_deg


def test_each_identity_binds_to_its_upstream_target() -> None:
  import celestial_calendar as celestial

  expected: dict[Body | LunarNode, celestial.ChartTarget] = {
    Body.SUN: celestial.ChartTarget.SUN,
    Body.MOON: celestial.ChartTarget.MOON,
    Body.MERCURY: celestial.ChartTarget.MERCURY,
    Body.VENUS: celestial.ChartTarget.VENUS,
    Body.MARS: celestial.ChartTarget.MARS,
    Body.JUPITER: celestial.ChartTarget.JUPITER,
    Body.SATURN: celestial.ChartTarget.SATURN,
    Body.URANUS: celestial.ChartTarget.URANUS,
    Body.NEPTUNE: celestial.ChartTarget.NEPTUNE,
    Body.PLUTO: celestial.ChartTarget.PLUTO,
    LunarNode.MEAN_ASCENDING: celestial.ChartTarget.MEAN_ASCENDING,
    LunarNode.MEAN_DESCENDING: celestial.ChartTarget.MEAN_DESCENDING,
    LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING: celestial.ChartTarget.TRUE_ASCENDING,
    LunarNode.MEEUS_FIVE_TERM_TRUE_DESCENDING: celestial.ChartTarget.TRUE_DESCENDING,
  }
  day, clock, latitude, longitude = _NORTH
  chart = natal_chart(
    resolved_at(day, clock, latitude, longitude),
    config_for(HouseSystem.EQUAL, tuple(expected)),
  )
  civil = celestial.CivilDateTime(
    day.year, day.month, day.day, (clock.hour * 3600 + clock.minute * 60 + clock.second) / 86400
  )
  snapshot = celestial.chart_snapshot(
    civil,
    celestial.CivilScale.UTC,
    celestial.GeoLocation(latitude, longitude),
    celestial.HouseSystem.EQUAL,
    celestial.DeltaTModel.ALGO5,
  )
  upstream = {body.target: body for body in snapshot.bodies}
  assert len(chart.positions) == len(expected)
  for position in chart.positions:
    target = expected[position.identity]
    assert position.longitude_deg == upstream[target].longitude_deg
    assert position.latitude_deg == upstream[target].latitude_deg
    assert position.distance_au == upstream[target].distance_au


def test_lunar_nodes_carry_no_distance_and_no_latitude() -> None:
  chart = natal_chart(
    resolved_at(*_NORTH[:2], *_NORTH[2:]),
    config_for(
      HouseSystem.EQUAL,
      (
        LunarNode.MEAN_ASCENDING,
        LunarNode.MEAN_DESCENDING,
        LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING,
        LunarNode.MEEUS_FIVE_TERM_TRUE_DESCENDING,
      ),
    ),
  )
  for position in chart.positions:
    assert position.distance_au is None
    assert position.latitude_deg == 0.0
  ascending, descending, true_ascending, true_descending = chart.positions
  assert (descending.longitude_deg - ascending.longitude_deg) % 360 == pytest.approx(180.0)
  assert (true_descending.longitude_deg - true_ascending.longitude_deg) % 360 == pytest.approx(
    180.0
  )
  assert ascending.longitude_deg != true_ascending.longitude_deg


def test_placements_keep_unrounded_degrees() -> None:
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for())
  for position, placement in zip(chart.positions, chart.placements, strict=True):
    assert placement.identity is position.identity
    assert placement.sign is sign_of(position.longitude_deg)
    assert placement.sign_degree_deg == sign_degree(position.longitude_deg)
    assert placement.house == house_of(position.longitude_deg, chart.houses.cusps_deg)


def test_the_result_is_immutable() -> None:
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for())
  with pytest.raises(FrozenInstanceError):
    chart.provenance = chart.provenance  # type: ignore[misc]
  with pytest.raises(FrozenInstanceError):
    chart.positions[0].longitude_deg = 0.0  # type: ignore[misc]


@pytest.mark.parametrize(
  "arguments",
  [("record", "config"), (None, None)],
)
def test_wrong_argument_types_are_rejected(arguments: tuple[object, object]) -> None:
  with pytest.raises(TypeError):
    natal_chart(*arguments)  # type: ignore[arg-type]


def test_importing_the_package_does_not_initialize_astronomy() -> None:
  code = """
import sys
import astrology
loaded = [
    name
    for name in sys.modules
    if name in ('celestial_calendar', 'astrology.celestial')
    or name.startswith('celestial_calendar.')
    or name.startswith('ctypes')
]
if loaded:
    raise RuntimeError(f'package import initialized native machinery: {loaded}')
from datetime import date, time, timedelta
from astrology import (
    Body, BirthRecord, ChartConfig, FixedOffset, HouseSystem, Location, TimePrecision,
    natal_chart, prepare_natal_input,
)
record = BirthRecord(
    date(2003, 7, 17), time(12, 0), FixedOffset(timedelta(0)),
    Location(40.0, 0.0), TimePrecision.SECOND, {'record': 'synthetic'},
)
resolved = prepare_natal_input(record)
natal_chart(resolved, ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ()))
if 'astrology.celestial' not in sys.modules:
    raise RuntimeError('chart calculation did not load the astronomy adapter')
"""
  subprocess.run([sys.executable, "-c", code], check=True)


def test_entry_checks_run_in_optimized_mode() -> None:
  code = """
from datetime import date, time, timedelta
from astrology import (
    Body, BirthRecord, ChartConfig, FixedOffset, HouseSystem, Location, TimePrecision,
    natal_chart, prepare_natal_input, resolve_birth_time,
)
config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ())
record = BirthRecord(
    date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)),
    Location(90.0, 0.0), TimePrecision.SECOND, {'record': 'synthetic'},
)
try:
    natal_chart(prepare_natal_input(record), config)
except ValueError:
    pass
else:
    raise RuntimeError('optimized mode skipped the latitude domain check')
without_location = BirthRecord(
    date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)), None,
    TimePrecision.SECOND, {'record': 'synthetic'},
)
try:
    natal_chart(resolve_birth_time(without_location), config)
except ValueError:
    pass
else:
    raise RuntimeError('optimized mode skipped the missing location check')
"""
  for mode in ((), ("-O",)):
    result = subprocess.run([sys.executable, *mode, "-c", code], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
