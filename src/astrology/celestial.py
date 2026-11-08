"""Concrete celestial-calendar calls for natal snapshots and transit event searches.

Copy native records into chart/transit domain values. Calculation entries import
this adapter lazily; importing the public value types does not load it.

为本命快照与行运事件搜索提供 celestial-calendar 的具体调用。
将原生记录复制为命盘或行运领域值；计算入口延迟导入本层，导入公开值类型不会加载它。
"""

from __future__ import annotations

from datetime import datetime

import celestial_calendar as celestial
from celestial_calendar import BodyState, Target

from astrology.birth import Location, MissingBirthDataError, ResolvedBirth
from astrology.chart import ChartDomainError, ChartHouses, ChartTimes, EclipticPosition
from astrology.config import ChartConfig, HouseSystem
from astrology.objects import AstronomicalObject, Body, LunarNode, _is_astronomical_object
from astrology.transits import TransitDirection, TransitDomainError, TransitSource, _TransitEvent

_BODY_TARGETS: dict[Body, Target] = {
  Body.SUN: Target.SUN,
  Body.MOON: Target.MOON,
  Body.MERCURY: Target.MERCURY,
  Body.VENUS: Target.VENUS,
  Body.MARS: Target.MARS,
  Body.JUPITER: Target.JUPITER,
  Body.SATURN: Target.SATURN,
  Body.URANUS: Target.URANUS,
  Body.NEPTUNE: Target.NEPTUNE,
  Body.PLUTO: Target.PLUTO,
}

# The upstream names it only "true node"; this project identifies it with the
# Meeus five-term true node named in our config.
# 上游只称它 true node；本项目把它认定为配置里具名的 Meeus 五项真交点。
_NODE_TARGETS: dict[LunarNode, Target] = {
  LunarNode.MEAN_ASCENDING: Target.MEAN_ASCENDING,
  LunarNode.MEAN_DESCENDING: Target.MEAN_DESCENDING,
  LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING: Target.TRUE_ASCENDING,
  LunarNode.MEEUS_FIVE_TERM_TRUE_DESCENDING: Target.TRUE_DESCENDING,
}

_HOUSE_SYSTEMS: dict[HouseSystem, celestial.HouseSystem] = {
  HouseSystem.WHOLE_SIGN: celestial.HouseSystem.WHOLE_SIGN,
  HouseSystem.EQUAL: celestial.HouseSystem.EQUAL,
  HouseSystem.PLACIDUS: celestial.HouseSystem.PLACIDUS,
}

_EVENT_DIRECTIONS: dict[celestial.EventDirection, TransitDirection] = {
  celestial.EventDirection.INCREASING: TransitDirection.INCREASING,
  celestial.EventDirection.DECREASING: TransitDirection.DECREASING,
  celestial.EventDirection.TANGENT: TransitDirection.TANGENT,
}

# The ΔT model is fixed here, not requested by the caller, and is passed
# explicitly so the recorded identity stays true if the upstream renames its
# default.
# ΔT 模型由本层固定，不让调用方选择，并显式传给上游：即使上游改了默认模型，
# 记录下来的模型标识仍然是真的。
_DELTA_T_MODEL = celestial.DeltaTModel.ALGO5


def celestial_version() -> str:
  """Return the installed celestial-calendar version. 返回已安装的 celestial-calendar 版本。"""
  return celestial.__version__


def delta_t_model_id() -> str:
  """Return the ΔT model identity the adapter uses, named by the upstream member.

  返回适配层所用 ΔT 模型的标识，取值就是上游枚举成员的值。
  """
  return _DELTA_T_MODEL.value


def _target(identity: AstronomicalObject) -> Target:
  """Map a requested identity to the fixed upstream roster. 把请求的标识映射到上游固定的名册。"""
  if not _is_astronomical_object(identity):
    raise TypeError("Native targets require a Body or LunarNode")
  if isinstance(identity, Body):
    return _BODY_TARGETS[identity]
  return _NODE_TARGETS[identity]


def _precheck(resolved: ResolvedBirth, config: ChartConfig) -> Location:
  """Validate location and the upstream civil-year ceiling before chart calculation.

  Reject missing locations and latitudes outside the open interval ±90 before any
  native call. Then query house_capability for the selected ΔT model and enforce its
  exclusive upper year. Native TT and geometry checks still apply. Capability failures
  retain their diagnostics in ChartDomainError; return the validated location.

  排盘前校验地点与上游民用年上界。缺少地点或纬度不在 ±90 开区间内时，不调用原生库。
  随后用所选 ΔT 模型查询 house_capability，按其不包含的结束年校验；原生 TT 与几何检查仍适用。
  能力查询失败时，ChartDomainError 保留上游诊断。通过时返回已校验的地点。
  """
  location = resolved.record.location
  if location is None:
    raise MissingBirthDataError("Chart calculation requires a birth location")
  if not -90.0 < location.latitude < 90.0:
    raise ChartDomainError(
      "Birth latitude must be strictly inside ±90 degrees for house geometry",
      house_system=config.house_system,
    )
  try:
    capability = celestial.house_capability(delta_t_model=_DELTA_T_MODEL)
  except celestial.CelestialError as exc:
    raise ChartDomainError(
      f"Requested {config.house_system.value} house capability query failed: {exc}",
      house_system=config.house_system,
      operation=exc.operation,
      recorded=exc.recorded,
      upstream_message=str(exc),
    ) from exc
  if resolved.utc.year >= capability.civil_end_year_exclusive:
    raise ChartDomainError(
      f"Civil year {resolved.utc.year} reaches or exceeds the upstream house capability "
      f"end year {capability.civil_end_year_exclusive} (exclusive)",
      house_system=config.house_system,
    )
  return location


def _position(identity: AstronomicalObject, body: BodyState) -> EclipticPosition:
  """Copy one upstream state under the requested identity. 复制上游的一个状态，标识换成请求里给的那个。"""
  return EclipticPosition(
    identity,
    body.longitude_deg,
    body.latitude_deg,
    body.distance_au,
    body.longitude_rate_deg_per_tt_day,
  )


def _civil(instant: datetime) -> celestial.CivilDateTime:
  """Copy a validated UTC instant to upstream civil fields. 将已校验的 UTC 时刻复制为上游民用字段。"""
  second_of_day = (
    instant.hour * 3600 + instant.minute * 60 + instant.second
  ) * 1_000_000 + instant.microsecond
  return celestial.CivilDateTime(
    instant.year, instant.month, instant.day, second_of_day / 86_400_000_000
  )


def snapshot(
  resolved: ResolvedBirth, config: ChartConfig
) -> tuple[ChartTimes, tuple[EclipticPosition, ...], ChartHouses]:
  """Calculate the upstream joint snapshot for a resolved instant and requested configuration.

  The snapshot always evaluates all fourteen upstream objects and the requested house
  geometry together; selecting a subset of `config.objects` only filters its output and
  does not narrow the evaluated domain. ΔT model Algo5 is passed explicitly and recorded
  by the caller. Failures raise ChartDomainError with the requested house system.

  为已解析的时刻和请求的配置计算上游的联合快照。快照总是把上游十四个对象和请求的宫几何
  一起求值；`config.objects` 只选一部分时，只是从结果里筛出这些，求值域不会缩小。ΔT 模型
  固定为 Algo5 并显式传入，由调用方记录。失败时抛出带有请求宫制的 ChartDomainError。
  """
  location = _precheck(resolved, config)
  civil = _civil(resolved.utc)
  native_location = celestial.GeoLocation(location.latitude, location.longitude)
  native_system = _HOUSE_SYSTEMS[config.house_system]
  try:
    native = celestial.chart_snapshot(
      civil,
      celestial.CivilScale.UTC,
      native_location,
      native_system,
      _DELTA_T_MODEL,
    )
  except ValueError as exc:
    raise ChartDomainError(
      f"Requested {config.house_system.value} chart is outside the supported domain: {exc}",
      house_system=config.house_system,
      upstream_message=str(exc),
    ) from exc
  except celestial.CelestialError as exc:
    raise ChartDomainError(
      f"Requested {config.house_system.value} chart calculation failed: {exc}",
      house_system=config.house_system,
      operation=exc.operation,
      recorded=exc.recorded,
      upstream_message=str(exc),
    ) from exc

  by_target = {body.target: body for body in native.bodies}
  positions = tuple(
    _position(identity, by_target[_target(identity)]) for identity in config.objects
  )
  houses = ChartHouses(
    config.house_system,
    native.houses.ascendant_deg,
    native.houses.midheaven_deg,
    native.houses.descendant_deg,
    native.houses.imum_coeli_deg,
    native.houses.cusps_deg,
  )
  times = ChartTimes(native.times.jd_ut1, native.times.jde_tt)
  return times, positions, houses


def transit_interval(start: datetime, end: datetime) -> tuple[float, float]:
  """Convert validated UTC endpoints to TT. 把已校验的 UTC 端点转为 TT。"""
  try:
    return celestial.utc_to_jde(_civil(start)), celestial.utc_to_jde(_civil(end))
  except ValueError as exc:
    raise TransitDomainError(str(exc), operation="utc_to_jde", upstream_message=str(exc)) from exc


def transit_source(identity: AstronomicalObject) -> TransitSource:
  """Copy one selected target's effective event model and window. 复制所选目标的实际事件模型与窗口。"""
  target = _target(identity)
  capabilities = celestial.capabilities(celestial.CapabilityOperation.EVENTS, target)
  if len(capabilities) != 1:
    raise RuntimeError("Expected one effective event capability for the selected target")
  capability = capabilities[0]
  return TransitSource(
    identity,
    capability.source.kind.value,
    capability.source.identity,
    celestial.model_identity_text(capability.source),
    capability.domain_start_jde_tt,
    capability.domain_end_jde_tt,
    capability.maximum_span_tt_days,
    celestial.capability_text(celestial.CapabilityOperation.EVENTS, target),
  )


def transit_events(
  identity: AstronomicalObject, longitude_deg: float, start_jde_tt: float, end_jde_tt: float
) -> tuple[_TransitEvent, ...]:
  """Search one level; preserve computation failures and wrap domain rejections.

  搜索一个黄经；保留计算失败的原异常，为域拒绝附上行运查询信息。
  """
  target = _target(identity)
  try:
    events = celestial.longitude_events(target, longitude_deg, start_jde_tt, end_jde_tt)
  except ValueError as exc:
    raise TransitDomainError(
      str(exc),
      operation="longitude_events",
      moving_object=identity,
      start_jde_tt=start_jde_tt,
      end_jde_tt=end_jde_tt,
      upstream_message=str(exc),
    ) from exc
  return tuple(
    _TransitEvent(
      event.jde_tt,
      event.longitude_deg,
      event.longitude_rate_deg_per_tt_day,
      _EVENT_DIRECTIONS[event.direction],
    )
    for event in events
  )
