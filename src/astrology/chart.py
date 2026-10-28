"""Composition of a modern tropical natal chart from resolved input and configuration.

把已解析的输入和请求的配置组合成现代热带本命盘。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, Literal, get_args

from astrology._distribution import installed_version
from astrology._validation import finite_number
from astrology.aspects import AspectHit, AspectObject, find_aspects
from astrology.birth import MissingBirthDataError, ResolvedBirth
from astrology.config import ChartConfig, HouseSystem, OrbCombination
from astrology.houses import _cusps, house_of
from astrology.objects import (
  AstronomicalObject,
  Axis,
  ChartObject,
  LunarNode,
  _is_astronomical_object,
  _is_chart_object,
)
from astrology.zodiac import Sign, _longitude, sign_degree, sign_of

_Evaluation = Literal["fixed_fourteen_object_joint_snapshot"]
_PositionFrame = Literal["apparent_geocentric_true_ecliptic_of_date"]
_UT1Derivation = Literal["delta_t_model_from_civil_utc"]

_EVALUATION: Final[_Evaluation] = get_args(_Evaluation)[0]
_POSITION_FRAME: Final[_PositionFrame] = get_args(_PositionFrame)[0]
_UT1_DERIVATION: Final[_UT1Derivation] = get_args(_UT1Derivation)[0]

_AXIS_FIELDS: dict[Axis, str] = {
  Axis.ASCENDANT: "ascendant_deg",
  Axis.MIDHEAVEN: "midheaven_deg",
  Axis.DESCENDANT: "descendant_deg",
  Axis.IMUM_COELI: "imum_coeli_deg",
}


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

  def __post_init__(self) -> None:
    for name in ("jd_ut1", "jde_tt"):
      object.__setattr__(self, name, finite_number(getattr(self, name), name))


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

  identity: AstronomicalObject
  longitude_deg: float
  latitude_deg: float
  distance_au: float | None
  longitude_rate_deg_per_tt_day: float

  def __post_init__(self) -> None:
    if not _is_astronomical_object(self.identity):
      raise TypeError("identity must be a Body or LunarNode")
    object.__setattr__(self, "longitude_deg", _longitude(self.longitude_deg))
    latitude = finite_number(self.latitude_deg, "latitude_deg")
    if not -90.0 <= latitude <= 90.0:
      raise ValueError("latitude_deg must be in [-90, 90]")
    object.__setattr__(self, "latitude_deg", latitude)
    object.__setattr__(
      self,
      "longitude_rate_deg_per_tt_day",
      finite_number(self.longitude_rate_deg_per_tt_day, "longitude_rate_deg_per_tt_day"),
    )
    if isinstance(self.identity, LunarNode):
      if self.distance_au is not None or latitude != 0.0:
        raise ValueError("Lunar nodes require zero latitude and absent distance")
    else:
      distance = finite_number(self.distance_au, "distance_au")
      if distance <= 0.0:
        raise ValueError("Physical objects require positive distance_au")
      object.__setattr__(self, "distance_au", distance)


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
    if type(self.system) is not HouseSystem:
      raise TypeError("system must be a HouseSystem")
    for name in ("ascendant_deg", "midheaven_deg", "descendant_deg", "imum_coeli_deg"):
      object.__setattr__(self, name, _longitude(getattr(self, name)))
    object.__setattr__(self, "cusps_deg", _cusps(self.cusps_deg))


@dataclass(frozen=True, slots=True)
class Placement:
  """Derived sign and house membership of one chart object; unrounded degrees retained.

  单个盘上对象推出的星座和落宫；度数保留未舍入的值。
  """

  identity: AstronomicalObject
  sign: Sign
  sign_degree_deg: float
  house: int

  def __post_init__(self) -> None:
    if not _is_astronomical_object(self.identity) or type(self.sign) is not Sign:
      raise TypeError("identity and sign must use their owning enum types")
    degree = finite_number(self.sign_degree_deg, "sign_degree_deg")
    if not 0.0 <= degree < 30.0:
      raise ValueError("sign_degree_deg must be in [0, 30)")
    object.__setattr__(self, "sign_degree_deg", degree)
    if type(self.house) is not int:
      raise TypeError("house must be an integer, not bool")
    if not 1 <= self.house <= 12:
      raise ValueError("house must be in [1, 12]")


@dataclass(frozen=True, slots=True)
class EffectiveConfiguration:
  """The resolved choices actually used; a requested system never appears here as another one.

  `delta_t_model` is the upstream ΔT model member value the adapter fixed for
  this calculation, not a caller request. `evaluation` names the joint
  evaluation that produced the positions: selecting a subset of the requested
  objects filters that output and does not narrow the evaluated domain.
  `aspect_objects` holds the objects aspects were judged among, in the order of
  the requested bodies/nodes, then selected axes in ASC/MC/DSC/IC order. It is empty
  when no aspect rules were requested.
  `orb_combination` repeats the requested rule, or None when no rule has
  per-object orbs.

  实际采用的已确定选择。请求的宫制不会在这里变成另一种宫制。`delta_t_model` 是适配层为
  这次计算固定下来的上游 ΔT 模型取值，不是调用方的请求；`evaluation` 说明位置来自哪种
  联合求值：只选一部分对象时，只是筛选输出，不缩小求值域。`aspect_objects` 是判断相位时
  所用的对象，天体和交点按请求顺序排列，所选四轴按上升、中天、下降、天底顺序追加；
  没有请求相位规则时为空。`orb_combination` 保存请求中的
  合成规则；没有规则带按对象的容许度时为 None。
  """

  house_system: HouseSystem
  delta_t_model: str
  evaluation: _Evaluation
  aspect_objects: tuple[ChartObject, ...]
  orb_combination: OrbCombination | None

  def __post_init__(self) -> None:
    if type(self.house_system) is not HouseSystem:
      raise TypeError("house_system must be a HouseSystem")
    if type(self.delta_t_model) is not str or not self.delta_t_model.strip():
      raise ValueError("delta_t_model must be a plain string containing a non-whitespace character")
    if type(self.evaluation) is not str or self.evaluation != _EVALUATION:
      raise ValueError("Unknown chart evaluation")
    if not isinstance(self.aspect_objects, Sequence) or isinstance(
      self.aspect_objects, (str, bytes)
    ):
      raise TypeError("aspect_objects must be a sequence")
    participants = tuple(self.aspect_objects)
    if any(not _is_chart_object(identity) for identity in participants):
      raise TypeError("aspect_objects must contain Body, LunarNode or Axis values")
    if len(set(participants)) != len(participants):
      raise ValueError("aspect_objects must not contain duplicate identities")
    object.__setattr__(self, "aspect_objects", participants)
    if self.orb_combination is not None and type(self.orb_combination) is not OrbCombination:
      raise TypeError("orb_combination must be an OrbCombination or None")


@dataclass(frozen=True, slots=True)
class ChartProvenance:
  """Package versions and coordinate conventions retained with the result.

  随结果一起保存的包版本和坐标约定。
  """

  celestial_version: str
  position_frame: _PositionFrame
  ut1_derivation: _UT1Derivation
  astrology_version: str

  def __post_init__(self) -> None:
    for name in ("celestial_version", "astrology_version"):
      value = getattr(self, name)
      if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a plain string containing a non-whitespace character")
    if type(self.position_frame) is not str or self.position_frame != _POSITION_FRAME:
      raise ValueError("Unknown position frame")
    if type(self.ut1_derivation) is not str or self.ut1_derivation != _UT1_DERIVATION:
      raise ValueError("Unknown UT1 derivation")


@dataclass(frozen=True, slots=True)
class NatalChart:
  """A complete immutable natal result; objects follow the requested order.

  Aspects are those requested in `requested.aspects`, among the objects named in
  `effective.aspect_objects`, in the order documented by `find_aspects`. The
  positions, placements and aspects are copied into tuples, so lists given by the
  caller are not aliased.

  Construction checks field types, ranges and pure derived-value consistency. It
  does not verify that the astronomical values were calculated from the claimed input.
  Equality includes the resolved input; hashing excludes it because its source
  mapping is unhashable.

  完整且不可变的本命盘结果；对象按请求的顺序排列。按 `requested.aspects` 中的规则，
  在 `effective.aspect_objects` 所列对象之间计算相位，结果顺序见 `find_aspects`。
  位置、落宫和相位会复制成元组，不会引用调用方传入的列表。
  构造时检查字段类型、范围及纯规则推导结果的一致性，不核实天文值是否确实由所称输入算得。
  相等判断包括已解析输入；哈希不包括它，因为其中的来源映射不可哈希。
  """

  resolved: ResolvedBirth = field(hash=False)
  requested: ChartConfig
  effective: EffectiveConfiguration
  provenance: ChartProvenance
  times: ChartTimes
  positions: tuple[EclipticPosition, ...]
  houses: ChartHouses
  placements: tuple[Placement, ...]
  aspects: tuple[AspectHit, ...]

  def __post_init__(self) -> None:
    for name, expected in (
      ("resolved", ResolvedBirth),
      ("requested", ChartConfig),
      ("effective", EffectiveConfiguration),
      ("provenance", ChartProvenance),
      ("times", ChartTimes),
      ("houses", ChartHouses),
    ):
      if type(getattr(self, name)) is not expected:
        raise TypeError(f"{name} must be a {expected.__name__}")
    if self.resolved.record.location is None:
      raise MissingBirthDataError("A complete chart requires a birth location")
    for name, member_type in (
      ("positions", EclipticPosition),
      ("placements", Placement),
      ("aspects", AspectHit),
    ):
      members = getattr(self, name)
      if not isinstance(members, Sequence) or isinstance(members, (str, bytes)):
        raise TypeError(f"{name} must be a sequence")
      snapshot = tuple(members)
      if any(type(member) is not member_type for member in snapshot):
        raise TypeError(f"{name} must contain only {member_type.__name__} values")
      object.__setattr__(self, name, snapshot)
    if not self.requested.house_system is self.effective.house_system is self.houses.system:
      raise ValueError("Requested, effective and stored house systems must agree")
    if tuple(position.identity for position in self.positions) != self.requested.objects:
      raise ValueError("Position identities and order must match requested objects")
    if self.effective.aspect_objects != self.requested.aspect_participants():
      raise ValueError("Effective aspect participants differ from the request")
    if self.effective.orb_combination is not self.requested.orb_combination:
      raise ValueError("Effective orb combination differs from the request")
    if self.placements != _placements(self.positions, self.houses):
      raise ValueError("Stored placements differ from pure derivation")
    if self.aspects != _aspects(self.positions, self.houses, self.requested):
      raise ValueError("Stored aspects differ from pure derivation")


def _placements(
  positions: Sequence[EclipticPosition], houses: ChartHouses
) -> tuple[Placement, ...]:
  return tuple(
    Placement(
      position.identity,
      sign_of(position.longitude_deg),
      sign_degree(position.longitude_deg),
      house_of(position.longitude_deg, houses.cusps_deg),
    )
    for position in positions
  )


def _require_comparable_sources(chart_left: NatalChart, chart_right: NatalChart) -> None:
  """Check the coordinate conventions of two supplied charts.

  校验两张给定命盘的位置坐标约定。
  """
  if type(chart_left) is not NatalChart or type(chart_right) is not NatalChart:
    raise TypeError("chart_left and chart_right must be NatalChart values")
  if (
    chart_left.requested.zodiac != chart_right.requested.zodiac
    or chart_left.requested.center != chart_right.requested.center
    or chart_left.provenance.position_frame != chart_right.provenance.position_frame
  ):
    raise ValueError("Cross charts must use matching zodiac, center and position frame")


def _selection_for_chart(
  chart: NatalChart, objects: Sequence[ChartObject], name: str
) -> tuple[ChartObject, ...]:
  """Validate a comparison selection and order it by stored positions, then axes.

  校验比较所用的对象选择，按已存位置及四轴的顺序排列。
  """
  if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
    raise TypeError(f"{name} must be a sequence of Body, LunarNode or Axis values")
  selected = tuple(objects)
  if any(not _is_chart_object(value) for value in selected):
    raise TypeError(f"{name} must contain Body, LunarNode or Axis values")
  if len(set(selected)) != len(selected):
    raise ValueError(f"{name} must not contain duplicate identities")
  available: tuple[ChartObject, ...] = (*[position.identity for position in chart.positions], *Axis)
  if not set(selected) <= set(available):
    raise ValueError(f"{name} must name only objects available in its source chart")
  return tuple(identity for identity in available if identity in selected)


def _selected_longitudes(
  positions: Sequence[EclipticPosition], houses: ChartHouses, participants: Sequence[ChartObject]
) -> tuple[tuple[ChartObject, float], ...]:
  """Read selected stored longitudes; axes follow bodies/nodes in their enum order.

  读取选中的已存黄经；四轴按枚举顺序排在天体和交点之后。
  """
  return (
    *[
      (position.identity, position.longitude_deg)
      for position in positions
      if position.identity in participants
    ],
    *[(axis, getattr(houses, _AXIS_FIELDS[axis])) for axis in Axis if axis in participants],
  )


def _aspect_positions(
  positions: Sequence[EclipticPosition], houses: ChartHouses, participants: Sequence[ChartObject]
) -> tuple[AspectObject, ...]:
  rates = {position.identity: position.longitude_rate_deg_per_tt_day for position in positions}
  return tuple(
    AspectObject(identity, longitude, None if isinstance(identity, Axis) else rates[identity])
    for identity, longitude in _selected_longitudes(positions, houses, participants)
  )


def _aspects(
  positions: Sequence[EclipticPosition], houses: ChartHouses, config: ChartConfig
) -> tuple[AspectHit, ...]:
  return find_aspects(
    _aspect_positions(positions, houses, config.aspect_participants()),
    config.aspects,
    config.orb_combination,
  )


def natal_chart(resolved: ResolvedBirth, config: ChartConfig) -> NatalChart:
  """Calculate a tropical, geocentric natal chart for a resolved birth instant.

  The record must carry a location; unknown time was already rejected by
  preparation. The astronomy adapter is imported here, not at package import, so
  importing astrology or querying knowledge never initializes native astronomy.
  A requested geometry outside the joint upstream domain raises
  `ChartDomainError` and never falls back to another house system. Requested
  aspect rules are judged among the objects of `config.aspect_objects`, or among
  all requested bodies/nodes when it is unset. Explicitly selected axes use the
  stored axis fields, not cusps, and have no supplied rate. Their non-exact hits
  are INDETERMINATE; zero deviation still gives EXACT. No axis is added to raw
  positions or placements. The distribution must be installed: missing package metadata
  raises `importlib.metadata.PackageNotFoundError` rather than inventing a version.

  为已解析的出生时刻计算热带地心本命盘。出生记录必须带地点；时间未知的记录在准备阶段
  就已被拒绝。天文适配层在这个函数里才导入，不在导入包时导入，所以导入 astrology 或查询
  知识都不会初始化原生天文库。请求的几何超出上游的联合求值域时，抛出
  `ChartDomainError`，不会改用别的宫制。根据这次计算的位置和黄经速率，
  在 `config.aspect_objects` 指定的对象之间计算相位；未设置时，所有请求的天体和交点都参与。
  显式所选四轴直接使用已存轴字段，不使用宫头，也不提供速率；其非精确命中为 INDETERMINATE，
  偏差恰为零时仍为 EXACT。不把四轴加入原始位置或落点。
  分发包必须已安装；元数据缺失时抛出 `importlib.metadata.PackageNotFoundError`，不编造版本号。
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
  placements = _placements(positions, houses)
  aspects = _aspects(positions, houses, config)
  return NatalChart(
    resolved=resolved,
    requested=config,
    effective=EffectiveConfiguration(
      house_system=config.house_system,
      delta_t_model=delta_t_model_id(),
      evaluation=_EVALUATION,
      aspect_objects=config.aspect_participants(),
      orb_combination=config.orb_combination,
    ),
    provenance=ChartProvenance(
      celestial_version=celestial_version(),
      position_frame=_POSITION_FRAME,
      ut1_derivation=_UT1_DERIVATION,
      astrology_version=installed_version(),
    ),
    times=times,
    positions=positions,
    houses=houses,
    placements=placements,
    aspects=aspects,
  )
