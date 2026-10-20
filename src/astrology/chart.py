"""Composition of a modern tropical natal chart from resolved input and configuration.

把已解析的输入和请求的配置组合成现代热带本命盘。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from astrology.aspects import AspectHit, AspectObject, find_aspects
from astrology.birth import MissingBirthDataError, ResolvedBirth
from astrology.config import Body, ChartConfig, HouseSystem, LunarNode, OrbCombination
from astrology.houses import house_of
from astrology.zodiac import Sign, sign_degree, sign_of


class ChartDomainError(ValueError):
  """The request asks for a chart outside the supported computation domain.

  Pre-call rejections (latitude at a pole, civil year 2100 or later) carry no
  upstream detail. Failures reported by the astronomy library carry the
  requested house system and the upstream operation, recording status and
  message. No partial chart is ever returned and no substitution occurs.

  请求的命盘超出了支持的计算范围。调用前就拒绝的情形（纬度在极点、民用年为 2100 年或更晚）
  不带上游细节；天文库报告的失败则带有请求的宫制，以及上游的操作、记录状态和消息。
  从不返回部分命盘，也不做任何替换。
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

  所算时刻的 UT1 儒略日与 TT 儒略历书日。
  """

  jd_ut1: float
  jde_tt: float


@dataclass(frozen=True, slots=True)
class EclipticPosition:
  """Apparent geocentric state on the true ecliptic and equinox of date.

  Distances are AU and absent (`None`) for lunar nodes, whose latitude is zero
  by definition. The longitude rate is degrees per TT day; negative means
  decreasing at that instant. Positions do not depend on the birth location.

  以该时刻的真黄道和真春分点为基准的地心视位置与速率。距离以 AU 计；月交点按定义没有
  距离（为 `None`），黄纬为零。黄经速率以每 TT 日的度数计，负值表示此刻黄经在减小。
  位置与出生地点无关。
  """

  identity: Body | LunarNode
  longitude_deg: float
  latitude_deg: float
  distance_au: float | None
  longitude_rate_deg_per_tt_day: float


@dataclass(frozen=True, slots=True)
class ChartHouses:
  """Four axes and twelve cyclically ordered cusps, all in [0, 360) degrees.

  The cusps are copied into a tuple, so a list given by the caller is not aliased.

  四轴与十二个宫头，宫头按循环顺序排列，度数都在 [0, 360) 内。宫头会复制成元组，
  不会引用调用方传入的列表。
  """

  system: HouseSystem
  ascendant_deg: float
  midheaven_deg: float
  descendant_deg: float
  imum_coeli_deg: float
  cusps_deg: tuple[float, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.cusps_deg, Sequence) or isinstance(self.cusps_deg, (str, bytes)):
      raise TypeError("cusps_deg must be a sequence of twelve numbers")
    cusps = tuple(self.cusps_deg)
    if len(cusps) != 12:
      raise ValueError("cusps_deg must contain exactly twelve cusps")
    object.__setattr__(self, "cusps_deg", cusps)


@dataclass(frozen=True, slots=True)
class Placement:
  """Derived sign and house membership of one chart object; unrounded degrees retained.

  单个盘上对象推出的星座和落宫；度数保留未舍入的值。
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
  `aspect_objects` is the set of objects aspects were judged among, in the order of
  the requested objects, and is empty when no aspect rules were requested.
  `orb_combination` repeats the requested rule, or None when no rule has
  per-object orbs.

  实际采用的已确定选择。请求的宫制不会在这里变成另一种宫制。`delta_t_model` 是适配层为
  这次计算固定下来的上游 ΔT 模型取值，不是调用方的请求；`evaluation` 说明位置来自哪种
  联合求值：只选一部分对象时，只是筛选输出，不缩小求值域。`aspect_objects` 是判断相位时
  所用的对象，按请求对象的顺序排列；没有请求相位规则时为空。`orb_combination` 照录请求的
  合成规则；没有规则带按对象的容许度时为 None。
  """

  house_system: HouseSystem
  delta_t_model: str
  evaluation: Literal["fixed_fourteen_object_joint_snapshot"]
  aspect_objects: tuple[Body | LunarNode, ...]
  orb_combination: OrbCombination | None

  def __post_init__(self) -> None:
    if not isinstance(self.aspect_objects, Sequence) or isinstance(
      self.aspect_objects, (str, bytes)
    ):
      raise TypeError("aspect_objects must be a sequence")
    object.__setattr__(self, "aspect_objects", tuple(self.aspect_objects))


@dataclass(frozen=True, slots=True)
class ChartProvenance:
  """Astronomy version and coordinate conventions retained with the result.

  随结果一起保存的天文库版本和坐标约定。
  """

  celestial_version: str
  position_frame: Literal["apparent_geocentric_true_ecliptic_of_date"]
  ut1_derivation: Literal["delta_t_model_from_civil_utc"]


@dataclass(frozen=True, slots=True)
class NatalChart:
  """A complete immutable natal result; objects follow the requested order.

  Aspects are those requested in `requested.aspects`, among the objects named in
  `effective.aspect_objects`, in the order documented by `find_aspects`. The
  positions, placements and aspects are copied into tuples, so lists given by the
  caller are not aliased.

  完整且不可变的本命盘结果；对象按请求的顺序排列。相位是 `requested.aspects` 所请求的、
  在 `effective.aspect_objects` 所列对象之间成立的那些，顺序按 `find_aspects` 的文档。
  位置、落宫和相位会复制成元组，不会引用调用方传入的列表。
  """

  requested: ChartConfig
  effective: EffectiveConfiguration
  provenance: ChartProvenance
  times: ChartTimes
  positions: tuple[EclipticPosition, ...]
  houses: ChartHouses
  placements: tuple[Placement, ...]
  aspects: tuple[AspectHit, ...]

  def __post_init__(self) -> None:
    for name in ("positions", "placements", "aspects"):
      members = getattr(self, name)
      if not isinstance(members, Sequence) or isinstance(members, (str, bytes)):
        raise TypeError(f"{name} must be a sequence")
      object.__setattr__(self, name, tuple(members))


def natal_chart(resolved: ResolvedBirth, config: ChartConfig) -> NatalChart:
  """Calculate a tropical, geocentric natal chart for a resolved birth instant.

  The record must carry a location; unknown time was already rejected by
  preparation. The astronomy adapter is imported here, not at package import, so
  importing astrology or querying knowledge never initializes native astronomy.
  A requested geometry outside the joint upstream domain raises
  `ChartDomainError` and never falls back to another house system. Requested
  aspect rules are judged among the objects of `config.aspect_objects`, or among
  all requested objects when it is unset, from the positions and longitude rates
  of this calculation.

  为已解析的出生时刻计算热带地心本命盘。出生记录必须带地点；时间未知的记录在准备阶段
  就已被拒绝。天文适配层在这个函数里才导入，不在导入包时导入，所以导入 astrology 或查询
  知识都不会初始化原生天文库。请求的几何超出上游的联合求值域时，抛出
  `ChartDomainError`，绝不退回到别的宫制。请求的相位规则，在 `config.aspect_objects` 的
  对象之间判断，未设置时在所有已请求对象之间判断，所用的是这次计算的位置和黄经速率。
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
  participants = (
    tuple(
      identity
      for identity in config.objects
      if config.aspect_objects is None or identity in config.aspect_objects
    )
    if config.aspects
    else ()
  )
  aspects = find_aspects(
    [
      AspectObject(
        position.identity, position.longitude_deg, position.longitude_rate_deg_per_tt_day
      )
      for position in positions
      if position.identity in participants
    ],
    config.aspects,
    config.orb_combination,
  )
  return NatalChart(
    requested=config,
    effective=EffectiveConfiguration(
      house_system=config.house_system,
      delta_t_model=delta_t_model_id(),
      evaluation="fixed_fourteen_object_joint_snapshot",
      aspect_objects=participants,
      orb_combination=config.orb_combination,
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
    aspects=aspects,
  )
