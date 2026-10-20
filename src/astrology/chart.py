"""Composition of a modern tropical natal chart from resolved input and configuration.

由已解析输入与请求配置组合现代热带本命盘。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from astrology.birth import MissingBirthDataError, ResolvedBirth
from astrology.config import Body, ChartConfig, HouseSystem, LunarNode
from astrology.houses import house_of
from astrology.zodiac import Sign, sign_degree, sign_of


class ChartDomainError(ValueError):
  """The request asks for a chart outside the supported computation domain.

  Pre-call rejections (latitude at a pole, civil year 2100 or later) carry no
  upstream detail. Failures reported by the astronomy library carry the
  requested house system and the upstream operation, recording status and
  message. No partial chart is ever returned and no substitution occurs.

  请求的命盘超出支持的计算域。调用前拒绝（极点纬度、2100 年及以后的民用年）不携带上游细节；
  天文库报告的失败携带请求的宫制及上游操作、记录状态与消息。绝不返回部分命盘，也不发生替代。
  """

  def __init__(
    self,
    message: str,
    *,
    house_system: HouseSystem,
    operation: str | None = None,
    recorded: bool | None = None,
    upstream_message: str | None = None,
  ) -> None:
    super().__init__(message)
    self.house_system = house_system
    self.operation = operation
    self.recorded = recorded
    self.upstream_message = upstream_message


@dataclass(frozen=True, slots=True)
class ChartTimes:
  """UT1-based Julian Day and TT-based Julian Ephemeris Day of the calculated instant.

  计算时刻的 UT1 儒略日与 TT 儒略历书日。
  """

  jd_ut1: float
  jde_tt: float


@dataclass(frozen=True, slots=True)
class EclipticPosition:
  """Apparent geocentric state on the true ecliptic and equinox of date.

  Distances are AU and absent (`None`) for lunar nodes, whose latitude is zero
  by definition. The longitude rate is degrees per TT day; negative means
  decreasing at that instant. Positions do not depend on the birth location.

  瞬时真黄道与真春分点上的地心视状态。距离单位 AU，月交点按定义无距离（`None`）、黄纬为零。
  黄经速率为每 TT 日度数，负值表示该瞬间递减。位置不依赖出生地点。
  """

  identity: Body | LunarNode
  longitude_deg: float
  latitude_deg: float
  distance_au: float | None
  longitude_rate_deg_per_tt_day: float


@dataclass(frozen=True, slots=True)
class ChartHouses:
  """Four axes and twelve cyclically ordered cusps, all in [0, 360) degrees.

  四轴与十二个按循环顺序排列的宫头，均为 [0, 360) 度。
  """

  system: HouseSystem
  ascendant_deg: float
  midheaven_deg: float
  descendant_deg: float
  imum_coeli_deg: float
  cusps_deg: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Placement:
  """Derived sign and house membership of one chart object; unrounded degrees retained.

  单个盘对象派生出的星座与宫位成员关系；保留未舍入度数。
  """

  identity: Body | LunarNode
  sign: Sign
  sign_degree_deg: float
  house: int


@dataclass(frozen=True, slots=True)
class EffectiveConfiguration:
  """The resolved choices actually used; a requested system never appears here as another one.

  `delta_t_model` is the upstream ΔT model member value the adapter fixed for
  this calculation, not a caller request. `evaluation` names the joint
  evaluation that produced the positions: selecting a subset of the requested
  objects filters that output and does not narrow the evaluated domain.

  实际使用的已解析选择；请求的宫制不会以另一种宫制出现在这里。`delta_t_model` 是适配层为本次计算
  固定的上游 ΔT 模型成员值，不是调用方请求；`evaluation` 标明产出位置的联合求值方式：
  选取请求对象的子集只是过滤输出，不缩小求值域。
  """

  house_system: HouseSystem
  delta_t_model: str
  evaluation: Literal["fixed_fourteen_object_joint_snapshot"]


@dataclass(frozen=True, slots=True)
class ChartProvenance:
  """Astronomy version and coordinate conventions retained with the result.

  随结果保存的天文库版本与坐标约定。
  """

  celestial_version: str
  position_frame: Literal["apparent_geocentric_true_ecliptic_of_date"]
  ut1_derivation: Literal["delta_t_model_from_civil_utc"]


@dataclass(frozen=True, slots=True)
class NatalChart:
  """A complete immutable natal result; objects follow the requested order.

  完整的不可变命盘结果；对象遵循请求顺序。
  """

  requested: ChartConfig
  effective: EffectiveConfiguration
  provenance: ChartProvenance
  times: ChartTimes
  positions: tuple[EclipticPosition, ...]
  houses: ChartHouses
  placements: tuple[Placement, ...]


def natal_chart(resolved: ResolvedBirth, config: ChartConfig) -> NatalChart:
  """Calculate a tropical, geocentric natal chart for a resolved birth instant.

  The record must carry a location; unknown time was already rejected by
  preparation. The astronomy adapter is imported here, not at package import, so
  importing astrology or querying knowledge never initializes native astronomy.
  A requested geometry outside the joint upstream domain raises
  `ChartDomainError` and never falls back to another house system.

  为已解析的出生时刻计算热带地心本命盘。记录必须带地点；未知时辰已在准备阶段拒绝。
  天文适配器在此处导入而非包导入时导入，因此导入 astrology 或查询知识永不起初始化原生天文库。
  联合上游域之外的请求几何抛出 `ChartDomainError`，绝不回退到其他宫制。
  """
  if type(resolved) is not ResolvedBirth:
    raise TypeError("resolved must be a ResolvedBirth")
  if type(config) is not ChartConfig:
    raise TypeError("config must be a ChartConfig")
  if resolved.record.location is None:
    raise MissingBirthDataError("Chart calculation requires a birth location")

  from astrology.celestial import (  # Deferred: native astronomy out of imports.
    celestial_version,
    delta_t_model_id,
    snapshot,
  )

  times, positions, houses = snapshot(resolved, config)
  placements = tuple(
    Placement(
      position.identity,
      sign_of(position.longitude_deg),
      sign_degree(position.longitude_deg),
      house_of(position.longitude_deg, houses.cusps_deg),
    )
    for position in positions
  )
  return NatalChart(
    requested=config,
    effective=EffectiveConfiguration(
      house_system=config.house_system,
      delta_t_model=delta_t_model_id(),
      evaluation="fixed_fourteen_object_joint_snapshot",
    ),
    provenance=ChartProvenance(
      celestial_version=celestial_version(),
      position_frame="apparent_geocentric_true_ecliptic_of_date",
      ut1_derivation="delta_t_model_from_civil_utc",
    ),
    times=times,
    positions=positions,
    houses=houses,
    placements=placements,
  )
