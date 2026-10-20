"""The concrete adapter between resolved birth input and celestial-calendar.

It produces the chart module's own result values and raises its `ChartDomainError`,
so it depends on `chart`; `chart` imports it only inside `natal_chart`. That is
deliberate while `natal_chart` is the only consumer: a second one would be the
reason to give the adapter its own result type.

已解析出生输入与 celestial-calendar 之间的具体适配。它直接产出 chart 模块的结果值并抛出
其 `ChartDomainError`，因此依赖 `chart`；`chart` 仅在 `natal_chart` 内导入它。在
`natal_chart` 是唯一消费者时这是有意为之；出现第二个消费者才有理由给适配层单独的结果类型。
"""

from __future__ import annotations

import celestial_calendar as celestial
from celestial_calendar import BodyState, ChartTarget

from astrology.birth import Location, MissingBirthDataError, ResolvedBirth
from astrology.chart import ChartDomainError, ChartHouses, ChartTimes, EclipticPosition
from astrology.config import Body, ChartConfig, HouseSystem, LunarNode

_BODY_TARGETS: dict[Body, ChartTarget] = {
  Body.SUN: ChartTarget.SUN,
  Body.MOON: ChartTarget.MOON,
  Body.MERCURY: ChartTarget.MERCURY,
  Body.VENUS: ChartTarget.VENUS,
  Body.MARS: ChartTarget.MARS,
  Body.JUPITER: ChartTarget.JUPITER,
  Body.SATURN: ChartTarget.SATURN,
  Body.URANUS: ChartTarget.URANUS,
  Body.NEPTUNE: ChartTarget.NEPTUNE,
  Body.PLUTO: ChartTarget.PLUTO,
}

# The upstream true node is the Meeus five-term true node named in our config.
# 上游的 true node 即本仓配置具名的 Meeus 五项真交点。
_NODE_TARGETS: dict[LunarNode, ChartTarget] = {
  LunarNode.MEAN_ASCENDING: ChartTarget.MEAN_ASCENDING,
  LunarNode.MEAN_DESCENDING: ChartTarget.MEAN_DESCENDING,
  LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING: ChartTarget.TRUE_ASCENDING,
  LunarNode.MEEUS_FIVE_TERM_TRUE_DESCENDING: ChartTarget.TRUE_DESCENDING,
}

_HOUSE_SYSTEMS: dict[HouseSystem, celestial.HouseSystem] = {
  HouseSystem.WHOLE_SIGN: celestial.HouseSystem.WHOLE_SIGN,
  HouseSystem.EQUAL: celestial.HouseSystem.EQUAL,
  HouseSystem.PLACIDUS: celestial.HouseSystem.PLACIDUS,
}

# The ΔT model is fixed here, not requested by the caller, and is passed
# explicitly so the recorded identity stays true if the upstream renames its
# default. 上游的 ΔT 模型由本层固定，不由调用方请求；显式传参，
# 使上游改动默认模型时已记录的标识仍为真。
_DELTA_T_MODEL = celestial.DeltaTModel.ALGO5

_MAX_CIVIL_YEAR = 2099


def celestial_version() -> str:
  """Return the installed celestial-calendar version. 返回已安装的 celestial-calendar 版本。"""
  return celestial.__version__


def delta_t_model_id() -> str:
  """Return the ΔT model identity the adapter uses, named by the upstream member.

  返回适配层使用的 ΔT 模型标识，取自上游枚举成员。
  """
  return _DELTA_T_MODEL.value


def _target(identity: Body | LunarNode) -> ChartTarget:
  """Map a requested identity to the fixed upstream roster. 将请求标识映射到上游固定名册。"""
  if isinstance(identity, Body):
    return _BODY_TARGETS[identity]
  return _NODE_TARGETS[identity]


def _precheck(resolved: ResolvedBirth, config: ChartConfig) -> Location:
  """Reject input the upstream Python layer would otherwise reject as a bare ValueError.

  Requires a location, a latitude strictly inside ±90 (records admit the endpoints,
  geometry requires the open interval) and a civil year through 2099, all before any
  native call; returns the validated location. The JDE(TT) upper bound inside 2099 is
  left to the native domain check; both surfaces raise ChartDomainError.

  拒绝上游 Python 层会以裸 ValueError 拒绝的输入：要求地点、纬度严格在 ±90 内（记录允许
  端点，几何要求开区间）、民用年至 2099 年，均在原生调用前拒绝并返回已校验的地点。
  2099 年内的 JDE(TT) 上界留给原生域检查；两个入口抛出同一个 ChartDomainError。
  """
  location = resolved.record.location
  if location is None:
    raise MissingBirthDataError("Chart calculation requires a birth location")
  if not -90.0 < location.latitude < 90.0:
    raise ChartDomainError(
      "Birth latitude must be strictly inside ±90 degrees for house geometry",
      house_system=config.house_system,
    )
  if resolved.utc.year >= _MAX_CIVIL_YEAR + 1:
    raise ChartDomainError(
      f"Civil year {resolved.utc.year} is outside the supported range through {_MAX_CIVIL_YEAR}",
      house_system=config.house_system,
    )
  return location


def _position(identity: Body | LunarNode, body: BodyState) -> EclipticPosition:
  """Copy one upstream state under the requested identity. 按请求标识复制一个上游状态。"""
  return EclipticPosition(
    identity,
    body.longitude_deg,
    body.latitude_deg,
    body.distance_au,
    body.longitude_rate_deg_per_tt_day,
  )


def snapshot(
  resolved: ResolvedBirth, config: ChartConfig
) -> tuple[ChartTimes, tuple[EclipticPosition, ...], ChartHouses]:
  """Calculate the upstream joint snapshot for a resolved instant and requested configuration.

  The snapshot always evaluates all fourteen upstream objects and the requested house
  geometry together; selecting a subset of `config.objects` only filters its output and
  does not narrow the evaluated domain. ΔT model Algo5 is passed explicitly and recorded
  by the caller. Failures raise ChartDomainError with the requested house system and never
  a partial result or a substituted geometry.

  为已解析时刻与请求配置计算上游联合快照。快照始终联合求值全部十四个上游对象与请求的宫几何；
  选取 `config.objects` 的子集只是过滤其输出，不缩小求值域。ΔT 模型 Algo5 为显式传入，
  由调用方记录。失败抛出携带请求宫制的 ChartDomainError，绝不返回部分结果或替代几何。
  """
  location = _precheck(resolved, config)
  second_of_day = (
    resolved.utc.hour * 3600 + resolved.utc.minute * 60 + resolved.utc.second
  ) * 1_000_000 + resolved.utc.microsecond
  civil = celestial.CivilDateTime(
    resolved.utc.year,
    resolved.utc.month,
    resolved.utc.day,
    second_of_day / 86_400_000_000,
  )
  try:
    native = celestial.chart_snapshot(
      civil,
      celestial.CivilScale.UTC,
      celestial.GeoLocation(location.latitude, location.longitude),
      _HOUSE_SYSTEMS[config.house_system],
      _DELTA_T_MODEL,
    )
  except celestial.CelestialError as exc:
    raise ChartDomainError(
      f"Requested {config.house_system.value} chart is outside the supported domain: {exc}",
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
