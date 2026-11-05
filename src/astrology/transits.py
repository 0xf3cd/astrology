"""Exact moving-to-fixed-natal aspects over a modern UTC interval.

在现代 UTC 区间内搜索移动对象与固定本命黄经的精确相位。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from enum import StrEnum
from typing import Final, Literal, get_args

from astrology._comparison import _selection_for_chart
from astrology._distribution import installed_version
from astrology._validation import finite_number
from astrology.aspects import _branches, aspect_angle
from astrology.birth import _require_modern_utc
from astrology.chart import _POSITION_FRAME, NatalChart, _PositionFrame, _selected_longitudes
from astrology.config import MajorAspect
from astrology.objects import (
  AstronomicalObject,
  Body,
  ChartObject,
  LunarNode,
  _is_astronomical_object,
  _is_chart_object,
)

_TimePolicy = Literal["modern_utc_frozen_leap_offsets"]
_EpochPolicy = Literal["fixed_natal_degree_against_moving_of_date_longitude"]
_TIME_POLICY: Final[_TimePolicy] = get_args(_TimePolicy)[0]
_EPOCH_POLICY: Final[_EpochPolicy] = get_args(_EpochPolicy)[0]


class TransitDirection(StrEnum):
  """Crossing or contact direction supplied by the event search.

  事件搜索给出的穿越或相切方向。
  """

  INCREASING = "increasing"
  DECREASING = "decreasing"
  TANGENT = "tangent"


@dataclass(frozen=True, slots=True)
class _TransitEvent:
  """Adapter-copied event values without query identity. 由适配层复制、不含查询身份的事件值。"""

  jde_tt: float
  longitude_deg: float
  longitude_rate_deg_per_tt_day: float
  direction: TransitDirection


class TransitDomainError(ValueError):
  """A UTC conversion, TT span or selected event-provider domain was rejected.

  Retains the operation, optional moving object and TT endpoints, exact upstream
  message and chained cause. Native computation failures propagate unchanged.

  UTC 转换、TT 区间或所选事件来源的求值域被拒绝。保留操作、可用时的移动对象与 TT 端点、
  上游原始错误文本及异常因果链。原生计算失败直接向外抛出，不改成域拒绝。
  """

  def __init__(
    self,
    message: str,
    *,
    operation: str,
    moving_object: Body | LunarNode | None = None,
    start_jde_tt: float | None = None,
    end_jde_tt: float | None = None,
    upstream_message: str | None = None,
  ) -> None:
    super().__init__(message)
    self.operation = operation
    self.moving_object = moving_object
    self.start_jde_tt = start_jde_tt
    self.end_jde_tt = end_jde_tt
    self.upstream_message = upstream_message


def _utc(value: datetime, name: str) -> datetime:
  if type(value) is not datetime:
    raise TypeError(f"{name} must be a built-in datetime")
  offset = value.utcoffset()
  if value.tzinfo is None or offset is None:
    raise ValueError(f"{name} must have a defined UTC offset")
  try:
    normalized = value.replace(tzinfo=timezone(offset), fold=0).astimezone(UTC)
  except OverflowError as exc:
    raise ValueError(f"{name} is outside the datetime range after UTC normalization") from exc
  _require_modern_utc(normalized)
  return normalized


def _moving(values: Sequence[AstronomicalObject]) -> tuple[AstronomicalObject, ...]:
  if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
    raise TypeError("moving_objects must be a sequence of Body or LunarNode values")
  result = tuple(values)
  if any(not _is_astronomical_object(value) for value in result):
    raise TypeError("moving_objects must contain only Body or LunarNode values")
  if not result or len(set(result)) != len(result):
    raise ValueError("moving_objects must be nonempty and must not repeat identities")
  return result


def _aspects(values: Sequence[MajorAspect]) -> tuple[MajorAspect, ...]:
  if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
    raise TypeError("aspects must be a sequence of MajorAspect values")
  result = tuple(values)
  if any(type(value) is not MajorAspect for value in result):
    raise TypeError("aspects must contain only MajorAspect values")
  if not result or len(set(result)) != len(result):
    raise ValueError("aspects must be nonempty and must not repeat identities")
  return tuple(sorted(result, key=aspect_angle))


def _text(value: str, name: str) -> None:
  if type(value) is not str or not value.strip():
    raise ValueError(f"{name} must be a nonempty plain string")


@dataclass(frozen=True, slots=True)
class TransitSource:
  """One moving object's effective model and bounded event window.

  Bounds and maximum span are in JDE(TT) and TT days. Descriptions are copied from
  the upstream; these implementation windows are not astronomical accuracy bounds.

  一个移动对象实际使用的模型及有界事件求值窗口。端点为 JDE(TT)，最长区间以 TT 日计。
  说明文字复制自上游；实现求值窗口不是天文精度界。
  """

  moving_object: AstronomicalObject
  model_kind: str
  model_identity: int
  model_description: str
  domain_start_jde_tt: float
  domain_end_jde_tt: float
  maximum_span_tt_days: float
  capability_description: str

  def __post_init__(self) -> None:
    if not _is_astronomical_object(self.moving_object):
      raise TypeError("moving_object must be a Body or LunarNode")
    if type(self.model_kind) is not str or self.model_kind != "position_source":
      raise ValueError("model_kind must be position_source")
    if type(self.model_identity) is not int or self.model_identity <= 0:
      raise ValueError("model_identity must be a positive integer")
    _text(self.model_description, "model_description")
    _text(self.capability_description, "capability_description")
    for name in ("domain_start_jde_tt", "domain_end_jde_tt", "maximum_span_tt_days"):
      object.__setattr__(self, name, finite_number(getattr(self, name), name))
    if self.domain_start_jde_tt >= self.domain_end_jde_tt or self.maximum_span_tt_days <= 0:
      raise ValueError("Event domain and maximum span must be nonempty and positive")


@dataclass(frozen=True, slots=True)
class TransitHit:
  """One queried aspect branch and its unchanged native event values.

  Time is JDE(TT); angles are degrees and rate is degrees per TT day.
  query_longitude_deg is the natal degree plus branch_deg, reduced to [0, 360).
  longitude_deg is raw and may
  differ from that level across a wrap. Tangent does not imply a bitwise-zero rate.

  一条查询相位分支及未经改写的原生事件值。时刻为 JDE(TT)，角度为度，速率为度/TT 日。
  query_longitude_deg 是本命度数加 branch_deg 后归入 [0, 360) 的黄经；
  longitude_deg 保留原值，环绕处可能位于另一侧。
  tangent 不意味着速率的位模式恰为零。
  """

  moving_object: AstronomicalObject
  natal_object: ChartObject
  aspect: MajorAspect
  branch_deg: float
  query_longitude_deg: float
  jde_tt: float
  longitude_deg: float
  longitude_rate_deg_per_tt_day: float
  direction: TransitDirection

  def __post_init__(self) -> None:
    if not _is_astronomical_object(self.moving_object) or not _is_chart_object(self.natal_object):
      raise TypeError("Transit endpoints require a moving body/node and a natal body/node/axis")
    if type(self.aspect) is not MajorAspect or type(self.direction) is not TransitDirection:
      raise TypeError("aspect and direction must be MajorAspect and TransitDirection values")
    for name in (
      "branch_deg",
      "query_longitude_deg",
      "jde_tt",
      "longitude_deg",
      "longitude_rate_deg_per_tt_day",
    ):
      object.__setattr__(self, name, finite_number(getattr(self, name), name))
    if self.branch_deg not in _branches(aspect_angle(self.aspect)):
      raise ValueError("branch_deg does not belong to the selected aspect")
    if not 0 <= self.query_longitude_deg < 360:
      raise ValueError("query_longitude_deg must be within [0, 360)")


@dataclass(frozen=True, slots=True)
class TransitHits:
  """Immutable natal source, search configuration, model provenance and ordered hits.

  Sequences are isolated as tuples. Construction checks supplied consistency,
  not the astronomical origin or completeness of a caller-supplied hit list.
  It performs no native calls. Coordinate and source details are in
  rule.project.exact_transit_hits and entry.transit_hits.

  不可变的本命来源、搜索配置、模型溯源及已排序命中。序列复制为元组；构造时检查给定数据的
  一致性，不认证天文来源或调用方所给命中列表的完整性，也不调用原生天文库。
  坐标及来源详情分别见 rule.project.exact_transit_hits 和 entry.transit_hits。
  """

  chart: NatalChart
  start_utc: datetime
  end_utc: datetime
  start_jde_tt: float
  end_jde_tt: float
  moving_objects: tuple[AstronomicalObject, ...]
  natal_objects: tuple[ChartObject, ...]
  aspects: tuple[MajorAspect, ...]
  sources: tuple[TransitSource, ...]
  hits: tuple[TransitHit, ...]
  celestial_version: str
  astrology_version: str
  position_frame: _PositionFrame = _POSITION_FRAME
  time_policy: _TimePolicy = _TIME_POLICY
  epoch_policy: _EpochPolicy = _EPOCH_POLICY

  def __post_init__(self) -> None:
    if type(self.chart) is not NatalChart:
      raise TypeError("chart must be a NatalChart")
    start, end = _utc(self.start_utc, "start_utc"), _utc(self.end_utc, "end_utc")
    if start >= end:
      raise ValueError("UTC interval must be nonempty and increasing")
    for name, instant in (("start_utc", start), ("end_utc", end)):
      object.__setattr__(self, name, instant)
    for name in ("start_jde_tt", "end_jde_tt"):
      object.__setattr__(self, name, finite_number(getattr(self, name), name))
    if self.start_jde_tt >= self.end_jde_tt:
      raise ValueError("TT interval must be nonempty and increasing")
    moving = _moving(self.moving_objects)
    natal = _selection_for_chart(self.chart, self.natal_objects, "natal_objects")
    if not natal:
      raise ValueError("natal_objects must not be empty")
    aspects = _aspects(self.aspects)
    for name, value in (("moving_objects", moving), ("natal_objects", natal), ("aspects", aspects)):
      object.__setattr__(self, name, value)
    for name, member_type in (("sources", TransitSource), ("hits", TransitHit)):
      values = getattr(self, name)
      if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a sequence")
      values = tuple(values)
      if any(type(value) is not member_type for value in values):
        raise TypeError(f"{name} must contain only {member_type.__name__} values")
      object.__setattr__(self, name, values)
    if tuple(source.moving_object for source in self.sources) != moving:
      raise ValueError("sources must match moving_objects in order")
    for source in self.sources:
      if (
        not source.domain_start_jde_tt
        <= self.start_jde_tt
        < self.end_jde_tt
        <= source.domain_end_jde_tt
      ):
        raise ValueError("TT interval leaves a retained event-source domain")
      if self.end_jde_tt - self.start_jde_tt > source.maximum_span_tt_days:
        raise ValueError("TT interval exceeds a retained event-source span")
    for name in ("celestial_version", "astrology_version"):
      _text(getattr(self, name), name)
    for name, expected in (
      ("position_frame", _POSITION_FRAME),
      ("time_policy", _TIME_POLICY),
      ("epoch_policy", _EPOCH_POLICY),
    ):
      if type(getattr(self, name)) is not str or getattr(self, name) != expected:
        raise ValueError(f"Unknown {name}")
    longitudes = dict(_selected_longitudes(self.chart.positions, self.chart.houses, natal))
    for hit in self.hits:
      if (
        hit.moving_object not in moving
        or hit.natal_object not in natal
        or hit.aspect not in aspects
      ):
        raise ValueError("Hit endpoints and aspect must belong to the retained selections")
      if not self.start_jde_tt <= hit.jde_tt < self.end_jde_tt:
        raise ValueError("Hit must lie in the half-open TT interval")
      if hit.query_longitude_deg != (longitudes[hit.natal_object] + hit.branch_deg) % 360:
        raise ValueError("Hit query level differs from the retained natal branch")
    if self.hits != _ordered(self.hits, moving, natal):
      raise ValueError("Hits are not in stable transit order")


def _ordered(
  hits: Sequence[TransitHit], moving: tuple[AstronomicalObject, ...], natal: tuple[ChartObject, ...]
) -> tuple[TransitHit, ...]:
  return tuple(
    sorted(
      hits,
      key=lambda hit: (
        hit.jde_tt,
        moving.index(hit.moving_object),
        natal.index(hit.natal_object),
        aspect_angle(hit.aspect),
        hit.branch_deg,
      ),
    )
  )


def transit_hits(
  chart: NatalChart,
  *,
  start_utc: datetime,
  end_utc: datetime,
  moving_objects: Sequence[AstronomicalObject],
  natal_objects: Sequence[ChartObject],
  aspects: Sequence[MajorAspect],
) -> TransitHits:
  """Find every exact selected moving-to-natal branch in [start_utc, end_utc).

  Endpoints must be aware built-in datetimes at or after 1972-01-01 UTC. Selections
  and aspects are explicit, nonempty and unique; moving bodies/nodes need not be
  present on the natal chart. Natal axes require explicit selection. No orbs are used.
  UTC is converted upstream; the half-open search is capped at 3660 TT days and
  each selected provider's event domain. A failed query aborts the whole result.
  Domain/span rejections raise TransitDomainError; native computation failures
  propagate unchanged. Native astronomy is loaded only by this calculation call.
  Hits are ordered by TT time, moving order, natal source order, aspect angle,
  then negative before positive branch. Raw event values, including tangent rates,
  are preserved, with times reported as multiples of 2^-30 day. Coordinate/source
  details: rule.project.exact_transit_hits and entry.transit_hits. Missing installed
  distribution metadata raises importlib.metadata.PackageNotFoundError.

  搜索 [start_utc, end_utc) 内所选移动对象与本命黄经的全部精确分支。
  端点须为有时区的内建 datetime，归一为 UTC 后不早于 1972-01-01。对象及相位须显式、非空且
  不重复；移动天体或交点不必出现在本命盘中，本命四轴须显式选择。不使用容许度。
  上游将 UTC 转为 TT；半开搜索区间最长 3660 TT 日，并受每个所选事件来源的域限制。
  任一查询失败即整次失败。域或区间拒绝抛 TransitDomainError；原生计算失败保持原异常。
  只有此计算调用才加载原生天文。按 TT 时刻、移动对象顺序、本命源盘顺序、相位角升序及
  负分支在前排序。保留原值，包括相切速率；报告时刻为 2^-30 日的整数倍。
  坐标及来源详情分别见 rule.project.exact_transit_hits 和 entry.transit_hits；
  已安装分发包元数据缺失时抛出 importlib.metadata.PackageNotFoundError。
  """
  if type(chart) is not NatalChart:
    raise TypeError("chart must be a NatalChart")
  start, end = _utc(start_utc, "start_utc"), _utc(end_utc, "end_utc")
  if start >= end:
    raise ValueError("UTC interval must be nonempty and increasing")
  moving = _moving(moving_objects)
  natal = _selection_for_chart(chart, natal_objects, "natal_objects")
  if not natal:
    raise ValueError("natal_objects must not be empty")
  selected_aspects = _aspects(aspects)

  from astrology.celestial import (
    celestial_version,
    transit_events,
    transit_interval,
    transit_source,
  )

  start_tt, end_tt = transit_interval(start, end)
  sources = tuple(transit_source(identity) for identity in moving)
  natal_longitudes = _selected_longitudes(chart.positions, chart.houses, natal)
  hits = []
  for identity in moving:
    for natal_object, longitude in natal_longitudes:
      for aspect in selected_aspects:
        for branch in _branches(aspect_angle(aspect)):
          level = (longitude + branch) % 360
          for event in transit_events(identity, level, start_tt, end_tt):
            hits.append(
              TransitHit(
                identity,
                natal_object,
                aspect,
                branch,
                level,
                event.jde_tt,
                event.longitude_deg,
                event.longitude_rate_deg_per_tt_day,
                event.direction,
              )
            )
  return TransitHits(
    chart=chart,
    start_utc=start,
    end_utc=end,
    start_jde_tt=start_tt,
    end_jde_tt=end_tt,
    moving_objects=moving,
    natal_objects=natal,
    aspects=selected_aspects,
    sources=sources,
    hits=_ordered(hits, moving, natal),
    celestial_version=celestial_version(),
    astrology_version=installed_version(),
  )
