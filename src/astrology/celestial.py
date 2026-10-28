"""The concrete adapter between resolved birth input and celestial-calendar.

It produces the chart module's own result values and raises its `ChartDomainError`,
so it depends on `chart`; `chart` imports it only inside `natal_chart`. That is
deliberate while `natal_chart` is the only consumer: a second one would be the
reason to give the adapter its own result type.

已解析的出生输入与 celestial-calendar 之间的具体适配层。它直接产出 `chart` 模块的结果值，
并抛出该模块的 `ChartDomainError`，所以依赖 `chart`；`chart` 只在 `natal_chart` 内部才导入
它。目前 `natal_chart` 是唯一的使用方，这样做是有意的；出现第二个使用方时，才有理由给
适配层单独定义结果类型。
"""

from __future__ import annotations

import celestial_calendar as celestial
from celestial_calendar import BodyState, ChartTarget

from astrology.birth import Location, MissingBirthDataError, ResolvedBirth
from astrology.chart import ChartDomainError, ChartHouses, ChartTimes, EclipticPosition
from astrology.config import ChartConfig, HouseSystem
from astrology.objects import AstronomicalObject, Body, LunarNode, _is_astronomical_object

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

# The upstream names it only "true node"; this project identifies it with the
# Meeus five-term true node named in our config.
# 上游只称它 true node；本项目把它认定为配置里具名的 Meeus 五项真交点。
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
# default.
# ΔT 模型由本层固定，不让调用方选择，并显式传给上游：即使上游改了默认模型，
# 记录下来的模型标识仍然是真的。
_DELTA_T_MODEL = celestial.DeltaTModel.ALGO5

_MAX_CIVIL_YEAR = 2099


def celestial_version() -> str:
  """Return the installed celestial-calendar version. 返回已安装的 celestial-calendar 版本。"""
  return celestial.__version__


def delta_t_model_id() -> str:
  """Return the ΔT model identity the adapter uses, named by the upstream member.

  返回适配层所用 ΔT 模型的标识，取值就是上游枚举成员的值。
  """
  return _DELTA_T_MODEL.value


def _target(identity: AstronomicalObject) -> ChartTarget:
  """Map a requested identity to the fixed upstream roster. 把请求的标识映射到上游固定的名册。"""
  if not _is_astronomical_object(identity):
    raise TypeError("Native targets require a Body or LunarNode")
  if isinstance(identity, Body):
    return _BODY_TARGETS[identity]
  return _NODE_TARGETS[identity]


def _precheck(resolved: ResolvedBirth, config: ChartConfig) -> Location:
  """Reject input the upstream Python layer would otherwise reject as a bare ValueError.

  Requires a location, a latitude strictly inside ±90 (records admit the endpoints,
  geometry requires the open interval) and a civil year through 2099, all before any
  native call; returns the validated location. The JDE(TT) upper bound inside 2099 is
  left to the native domain check; both surfaces raise ChartDomainError.

  在调用原生库之前，先拒绝上游 Python 层会用裸 ValueError 拒绝的输入：缺少地点；纬度不在
  ±90 的开区间内（出生记录允许取到端点，宫位几何不允许）；民用年超过 2099。通过时返回
  校验过的地点。2099 年内 JDE(TT) 的上界留给原生库自己的域检查；两处拒绝抛出的都是
  ChartDomainError。
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


def _position(identity: AstronomicalObject, body: BodyState) -> EclipticPosition:
  """Copy one upstream state under the requested identity. 复制上游的一个状态，标识换成请求里给的那个。"""
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

  为已解析的时刻和请求的配置计算上游的联合快照。快照总是把上游十四个对象和请求的宫几何
  一起求值；`config.objects` 只选一部分时，只是从结果里筛出这些，求值域不会缩小。ΔT 模型
  固定为 Algo5 并显式传入，由调用方记录。失败时抛出带有请求宫制的 ChartDomainError，
  绝不返回部分结果，也绝不换用别的宫几何。
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
