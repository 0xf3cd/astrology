"""Natal chart composition, entry conditions, failure classification and provenance.

命盘的组合、入口条件、失败分类和来源记录。
"""

import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, time, timedelta
from importlib.metadata import PackageNotFoundError, version

import pytest

from astrology import (
  AspectMotion,
  AspectObject,
  AspectRule,
  BirthRecord,
  Body,
  ChartConfig,
  ChartDomainError,
  FixedOffset,
  HouseSystem,
  Location,
  LunarNode,
  MajorAspect,
  MissingBirthDataError,
  NatalChart,
  ObjectOrb,
  OrbCombination,
  ResolvedBirth,
  TimePrecision,
  find_aspects,
  house_of,
  natal_chart,
  prepare_natal_input,
  resolve_birth_time,
  sign_degree,
  sign_of,
)

# A northern, non-integer-minute instant used by several cases.
_NORTH = (date(2003, 7, 17), time(5, 37, 13), 64.15, -21.94)

# A southern instant, the same as the southern reference case.
_SOUTH = (date(2020, 6, 1), time(12, 0), -33.87, 151.21)

# The fourteen objects the upstream evaluates together, in its roster order.
_ALL_OBJECTS: tuple[Body | LunarNode, ...] = (
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
)

# At the critical latitude, where the ecliptic lies on the horizon, the Ascendant has
# no direction. The sidereal time is 270 degrees at the northern witness and 90 at
# the southern one, which is 180 degrees away in longitude. The witnesses are the
# upstream consumer test's; 66.0 is a nearby latitude where the chart exists.
# 在黄道与地平圈重合的临界纬度，上升点没有确定的方向。恒星时在北站点是 270°，在南站点
# （经度相差 180°）是 90°。这两个站点取自上游消费者的测试；66.0 是附近有定义的纬度。
_UNRESOLVED_ASCENDANT = (date(2026, 1, 1), time(12, 0, 5))
_UNRESOLVED_NORTH = (66.561856230963841, -11.176256364511062)
_UNRESOLVED_SOUTH = (-66.561856230963841, 168.82374363548894)


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
  # inside it and 16:00 UTC is not.
  # 上游 JDE(TT) 的有效域在 2099-12-31 当天之内结束：14:00 UTC 仍在域内，16:00 UTC 已在域外。
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


@pytest.mark.parametrize("system", list(HouseSystem), ids=lambda system: system.value)
@pytest.mark.parametrize("site", [_UNRESOLVED_NORTH, _UNRESOLVED_SOUTH], ids=["north", "south"])
def test_an_undefined_ascendant_direction_fails_under_every_house_system(
  system: HouseSystem, site: tuple[float, float]
) -> None:
  resolved = resolved_at(*_UNRESOLVED_ASCENDANT, *site)
  with pytest.raises(ChartDomainError) as caught:
    natal_chart(resolved, config_for(system))
  assert caught.value.house_system is system
  assert caught.value.operation == "chart_snapshot"
  assert caught.value.recorded is True
  assert caught.value.upstream_message


def test_the_undefined_ascendant_is_a_point_and_not_a_latitude_band() -> None:
  nearby = resolved_at(*_UNRESOLVED_ASCENDANT, 66.0, _UNRESOLVED_NORTH[1])
  chart = natal_chart(nearby, config_for(HouseSystem.WHOLE_SIGN))
  assert chart.houses.midheaven_deg == 270.0


def test_a_latitude_just_inside_the_pole_is_left_to_the_upstream_domain() -> None:
  resolved = resolved_at(date(2003, 7, 17), time(12, 0), math.nextafter(90.0, 0.0))
  for system in (HouseSystem.WHOLE_SIGN, HouseSystem.EQUAL):
    assert natal_chart(resolved, config_for(system)).houses.system is system
  with pytest.raises(ChartDomainError) as caught:
    natal_chart(resolved, config_for(HouseSystem.PLACIDUS))
  # An upstream failure, not the pre-call rejection reserved for the poles.
  assert caught.value.operation == "chart_snapshot"
  assert caught.value.recorded is True


def test_failures_are_classified_by_structure_and_not_by_message_text() -> None:
  # A pre-call rejection carries no upstream detail; an upstream failure
  # carries the operation and recording status. Neither is decided by reading
  # the message. 调用前的拒绝不带上游细节；上游的失败带有操作和记录状态；分类不靠解析消息文本。
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
  assert chart.provenance.astrology_version == version("celestial-astrology")
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


# Each request differs from the roster order, from the alphabetical order of the
# identifiers, or from both. 每组请求要么与名册顺序不同，要么与标识的字母顺序不同，要么两者都不同。
@pytest.mark.parametrize(
  "order",
  [
    (Body.MOON, Body.SUN),
    (Body.VENUS, Body.MARS),
    (Body.MERCURY, Body.SUN, Body.MARS),
  ],
)
def test_positions_follow_the_requested_order(order: tuple[Body, ...]) -> None:
  chart = natal_chart(
    resolved_at(*_NORTH[:2], *_NORTH[2:]),
    config_for(HouseSystem.WHOLE_SIGN, order),
  )
  assert tuple(position.identity for position in chart.positions) == order
  assert tuple(placement.identity for placement in chart.placements) == order


def test_a_selected_subset_carries_the_values_of_the_full_evaluation() -> None:
  resolved = resolved_at(*_NORTH[:2], *_NORTH[2:])
  full = natal_chart(resolved, config_for(HouseSystem.WHOLE_SIGN, _ALL_OBJECTS))
  subset = natal_chart(resolved, config_for(HouseSystem.WHOLE_SIGN, (Body.MOON, Body.SUN)))
  everything = {position.identity: position for position in full.positions}
  for position in subset.positions:
    assert position == everything[position.identity]
  assert subset.houses == full.houses
  assert subset.times == full.times


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


@pytest.mark.parametrize("site", [_NORTH, _SOUTH], ids=["north", "south"])
def test_equal_houses_start_at_the_ascendant_in_thirty_degree_steps(
  site: tuple[date, time, float, float],
) -> None:
  resolved = resolved_at(*site)
  equal = natal_chart(resolved, config_for(HouseSystem.EQUAL)).houses
  cusps = equal.cusps_deg
  assert cusps[0] == equal.ascendant_deg
  for index in range(12):
    assert (cusps[(index + 1) % 12] - cusps[index]) % 360.0 == pytest.approx(30.0, abs=1e-9)
  assert cusps[9] != equal.midheaven_deg
  # The same instant under the other systems separates Equal from them.
  whole = natal_chart(resolved, config_for(HouseSystem.WHOLE_SIGN)).houses
  placidus = natal_chart(resolved, config_for(HouseSystem.PLACIDUS)).houses
  assert whole.cusps_deg[0] != whole.ascendant_deg
  assert (placidus.cusps_deg[1] - placidus.cusps_deg[0]) % 360.0 != pytest.approx(30.0)


def test_the_descendant_and_the_imum_coeli_oppose_the_ascendant_and_the_midheaven() -> None:
  houses = natal_chart(
    resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for(HouseSystem.PLACIDUS)
  ).houses
  assert (houses.descendant_deg - houses.ascendant_deg) % 360.0 == pytest.approx(180.0)
  assert (houses.imum_coeli_deg - houses.midheaven_deg) % 360.0 == pytest.approx(180.0)


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
    assert position.longitude_rate_deg_per_tt_day == upstream[target].longitude_rate_deg_per_tt_day


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


@pytest.mark.parametrize("system", list(HouseSystem))
@pytest.mark.parametrize("combination", list(OrbCombination))
def test_all_house_and_orb_policies_reach_the_result(
  recorded_chart: NatalChart, system: HouseSystem, combination: OrbCombination
) -> None:
  config = replace(recorded_chart.requested, house_system=system, orb_combination=combination)
  chart = natal_chart(recorded_chart.resolved, config)
  assert chart.resolved == recorded_chart.resolved
  assert chart.requested == config
  assert chart.houses.system is chart.effective.house_system is system
  assert chart.effective.orb_combination is combination
  assert chart.effective.aspect_objects == config.aspect_participants()


@pytest.mark.parametrize("explicit", [False, True])
def test_requested_participant_omission_stays_distinct(
  recorded_chart: NatalChart, explicit: bool
) -> None:
  config = replace(
    recorded_chart.requested,
    aspect_objects=tuple(recorded_chart.requested.objects) if explicit else None,
  )
  chart = natal_chart(recorded_chart.resolved, config)
  assert chart.requested.aspect_objects == config.aspect_objects
  assert chart.effective.aspect_objects == tuple(config.objects)


def test_calculation_preserves_offset_microseconds_and_signed_zero() -> None:
  source = {"record": "synthetic"}
  record = BirthRecord(
    date(2020, 6, 2),
    time(0, 15, 1, 654321),
    FixedOffset(timedelta(hours=5, minutes=45, microseconds=123)),
    Location(-0.0, -0.0),
    source=source,
  )
  source.clear()
  chart = natal_chart(prepare_natal_input(record), ChartConfig(HouseSystem.EQUAL, (Body.SUN,), ()))
  assert chart.resolved.utc.date() == date(2020, 6, 1)
  assert chart.resolved.utc.microsecond == 654198
  assert chart.resolved.utc_offset.microseconds == 123
  assert chart.resolved.record.precision is None
  assert chart.resolved.record.source == {"record": "synthetic"}
  site = chart.resolved.record.location
  assert site is not None
  assert math.copysign(1, site.latitude) == math.copysign(1, site.longitude) == -1


def test_calculation_requires_installed_metadata(
  recorded_chart: NatalChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  def missing(name: str) -> str:
    raise PackageNotFoundError(name)

  monkeypatch.setattr("astrology._distribution.version", missing)
  with pytest.raises(PackageNotFoundError, match="celestial-astrology"):
    natal_chart(recorded_chart.resolved, recorded_chart.requested)


def test_calculation_does_not_reresolve_timezone(
  recorded_chart: NatalChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  def forbidden(*args: object) -> None:
    raise AssertionError("Timezone data must not be read")

  monkeypatch.setattr("astrology.birth._load_iana_zone", forbidden)
  resolved = replace(recorded_chart.resolved, tzdata_version="old", iana_version="old")
  assert natal_chart(resolved, recorded_chart.requested).resolved == resolved


def test_the_result_does_not_alias_sequences_given_by_the_caller() -> None:
  chart = natal_chart(
    resolved_at(*_NORTH[:2], *_NORTH[2:]),
    config_for(HouseSystem.PLACIDUS, (Body.SUN, Body.MOON)),
  )
  cusps = list(chart.houses.cusps_deg)
  houses = replace(chart.houses, cusps_deg=cusps)  # type: ignore[arg-type]
  cusps[0] = 999.0
  assert isinstance(houses.cusps_deg, tuple)
  assert houses.cusps_deg == chart.houses.cusps_deg
  positions, placements = list(chart.positions), list(chart.placements)
  rebuilt = replace(chart, positions=positions, placements=placements)  # type: ignore[arg-type]
  positions.clear()
  placements.clear()
  assert isinstance(rebuilt.positions, tuple)
  assert isinstance(rebuilt.placements, tuple)
  assert rebuilt.positions == chart.positions
  assert rebuilt.placements == chart.placements


@pytest.mark.parametrize("cusps", ["not cusps", 30.0, (0.0,) * 11, (0.0,) * 13])
def test_a_result_needs_twelve_cusps_in_a_sequence(cusps: object) -> None:
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for())
  with pytest.raises((TypeError, ValueError), match="cusps"):
    replace(chart.houses, cusps_deg=cusps)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["positions", "placements", "aspects"])
def test_a_result_needs_its_members_in_a_sequence(name: str) -> None:
  chart = natal_chart(resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for())
  with pytest.raises(TypeError, match=name):
    replace(chart, **{name: "sun"})  # type: ignore[arg-type]


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


def wide_rules(orb: float = 10.0) -> list[AspectRule]:
  return [AspectRule(aspect, orb) for aspect in MajorAspect]


def aspect_chart(
  rules: list[AspectRule],
  objects: tuple[Body | LunarNode, ...] = _ALL_OBJECTS,
  *,
  site: tuple[date, time, float, float] = _NORTH,
  aspect_objects: list[Body | LunarNode] | None = None,
  orb_combination: OrbCombination | None = None,
) -> NatalChart:
  request = ChartConfig(
    HouseSystem.EQUAL,
    objects,
    rules,
    aspect_objects=aspect_objects,
    orb_combination=orb_combination,
  )
  return natal_chart(resolved_at(*site), request)


def test_without_aspect_rules_there_are_no_aspects_and_no_participants() -> None:
  chart = natal_chart(
    resolved_at(*_NORTH[:2], *_NORTH[2:]), config_for(HouseSystem.EQUAL, _ALL_OBJECTS)
  )
  assert chart.aspects == ()
  assert chart.effective.aspect_objects == ()
  assert chart.effective.orb_combination is None


def test_aspects_are_judged_from_the_positions_and_rates_of_the_same_calculation() -> None:
  chart = aspect_chart(wide_rules())
  rates = {
    position.identity: position.longitude_rate_deg_per_tt_day for position in chart.positions
  }
  expected = find_aspects(
    [
      AspectObject(p.identity, p.longitude_deg, p.longitude_rate_deg_per_tt_day)
      for p in chart.positions
    ],
    chart.requested.aspects,
  )
  assert chart.aspects == expected
  assert len(chart.aspects) > 10
  assert chart.effective.orb_combination is None
  assert chart.effective.aspect_objects == _ALL_OBJECTS
  for hit in chart.aspects:
    assert isinstance(hit.first, (Body, LunarNode))
    assert isinstance(hit.second, (Body, LunarNode))
    relative = rates[hit.second] - rates[hit.first]
    if hit.motion is AspectMotion.APPLYING:
      assert hit.deviation_deg * relative < 0
    elif hit.motion is AspectMotion.SEPARATING:
      assert hit.deviation_deg * relative > 0
    else:
      assert hit.motion is AspectMotion.EXACT


def test_pairs_follow_the_requested_object_order() -> None:
  forward = (Body.SUN, Body.MOON, Body.MARS, Body.SATURN)
  backward = forward[::-1]
  rules = wide_rules(15.0)
  first = {(h.first, h.second, h.aspect) for h in aspect_chart(rules, forward).aspects}
  second = aspect_chart(rules, backward).aspects
  assert first
  assert len(second) == len(first)
  order: dict[Body | LunarNode, int] = {identity: index for index, identity in enumerate(backward)}
  for hit in second:
    assert isinstance(hit.first, Body) and isinstance(hit.second, Body)
    assert order[hit.first] < order[hit.second]


def test_a_subset_of_aspect_objects_limits_the_pairs_and_is_recorded_in_chart_order() -> None:
  chart = aspect_chart(wide_rules(15.0), aspect_objects=[Body.VENUS, Body.SUN, Body.MOON])
  assert chart.effective.aspect_objects == (Body.SUN, Body.MOON, Body.VENUS)
  assert chart.aspects
  assert {h.first for h in chart.aspects} | {h.second for h in chart.aspects} <= {
    Body.SUN,
    Body.MOON,
    Body.VENUS,
  }
  assert len(chart.positions) == len(_ALL_OBJECTS)


def test_two_lunar_nodes_do_not_aspect_even_when_exactly_opposed() -> None:
  rules = [AspectRule(MajorAspect.OPPOSITION, 10.0), AspectRule(MajorAspect.CONJUNCTION, 10.0)]
  chart = aspect_chart(rules, (LunarNode.MEAN_ASCENDING, LunarNode.MEAN_DESCENDING, Body.SUN))
  assert not any(
    isinstance(h.first, LunarNode) and isinstance(h.second, LunarNode) for h in chart.aspects
  )
  assert LunarNode.MEAN_ASCENDING in {p.identity for p in chart.positions}


def test_a_node_kept_out_of_aspect_objects_still_has_its_position() -> None:
  chart = aspect_chart(
    wide_rules(30.0),
    (Body.SUN, Body.MOON, LunarNode.MEAN_ASCENDING),
    aspect_objects=[Body.SUN, Body.MOON],
  )
  assert LunarNode.MEAN_ASCENDING in {p.identity for p in chart.positions}
  assert chart.effective.aspect_objects == (Body.SUN, Body.MOON)
  assert not any(LunarNode.MEAN_ASCENDING in (h.first, h.second) for h in chart.aspects)
  with_node = aspect_chart(wide_rules(30.0), (Body.SUN, Body.MOON, LunarNode.MEAN_ASCENDING))
  assert any(LunarNode.MEAN_ASCENDING in (h.first, h.second) for h in with_node.aspects)


def test_the_requested_orb_combination_is_recorded_and_used() -> None:
  rules = [AspectRule(aspect, 3.0, [ObjectOrb(Body.MOON, 13.0)]) for aspect in MajorAspect]
  chart = aspect_chart(
    rules,
    (Body.SUN, Body.MOON, Body.MERCURY, Body.VENUS, Body.MARS, Body.JUPITER, Body.SATURN),
    site=(*_SOUTH[:2], *_SOUTH[2:]),
    orb_combination=OrbCombination.EITHER_WITHIN_OWN_ORB,
  )
  assert chart.effective.orb_combination is OrbCombination.EITHER_WITHIN_OWN_ORB
  limits = {Body.MOON in (h.first, h.second): h.orb_limit_deg for h in chart.aspects}
  assert limits == {True: 13.0, False: 3.0}


def test_the_result_does_not_alias_aspect_sequences_given_by_the_caller() -> None:
  chart = aspect_chart(wide_rules())
  aspects = list(chart.aspects)
  rebuilt = replace(chart, aspects=aspects)  # type: ignore[arg-type]
  aspects.clear()
  assert isinstance(rebuilt.aspects, tuple)
  assert rebuilt.aspects == chart.aspects
  participants = list(chart.effective.aspect_objects)
  effective = replace(chart.effective, aspect_objects=participants)  # type: ignore[arg-type]
  participants.clear()
  assert isinstance(effective.aspect_objects, tuple)
  assert effective.aspect_objects == chart.effective.aspect_objects
  with pytest.raises(TypeError, match="aspect_objects"):
    replace(chart.effective, aspect_objects="sun")  # type: ignore[arg-type]


# Aspect motion uses these rates. Check them against a one-hour central difference
# of the longitudes: agreement is about 1e-6 degrees per day for the Moon and true
# node. A wrong sign, hours instead of days, or a wrong day length gives an error
# of at least 0.01 degrees per day even for the slowest object.
# 相位的运动状态依赖这些速率，因此用相隔一小时的黄经作中心差分来核对。
# 月亮和真交点的误差约为 1e-6 度/日。如果符号错了、把每天当成每小时，或日长用错，
# 即使最慢的对象也会相差至少 0.01 度/日。
RATE_TOLERANCE_DEGREES_PER_DAY = 1e-5


def test_longitude_rates_are_the_derivative_of_the_longitudes_per_tt_day() -> None:
  middle = datetime.combine(_NORTH[0], _NORTH[1])
  half_hour = timedelta(minutes=30)
  charts = [
    natal_chart(
      resolved_at(instant.date(), instant.time(), *_NORTH[2:]),
      config_for(HouseSystem.WHOLE_SIGN, _ALL_OBJECTS),
    )
    for instant in (middle - half_hour, middle, middle + half_hour)
  ]
  one_hour = 1 / 24
  assert math.isclose(
    charts[2].times.jde_tt - charts[0].times.jde_tt, one_hour, rel_tol=0, abs_tol=1e-8
  )
  before, now, after = (chart.positions for chart in charts)
  for early, current, late in zip(before, now, after, strict=True):
    difference = (late.longitude_deg - early.longitude_deg + 180.0) % 360.0 - 180.0
    derivative = difference / one_hour
    assert abs(derivative - current.longitude_rate_deg_per_tt_day) < RATE_TOLERANCE_DEGREES_PER_DAY
    assert abs(current.longitude_rate_deg_per_tt_day) > 0.01
