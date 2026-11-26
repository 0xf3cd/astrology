"""Exact aspects between two moving longitudes. 两个移动黄经之间的精确相位。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from astrology._distribution import installed_version
from astrology._validation import finite_number, nonempty_text
from astrology.aspects import _branches, _deviation, _selected_aspects, _signed, aspect_angle
from astrology.birth import _normalize_utc
from astrology.config import MajorAspect
from astrology.event_records import TransitSource
from astrology.objects import AstronomicalObject, Body, LunarNode, _is_astronomical_object


class RelativeDirection(StrEnum):
  """Local direction of the unwrapped second-minus-first longitude.

  第二对象减第一对象的连续黄经差的局部方向，不按周界折回。
  """

  INCREASING = "increasing"
  DECREASING = "decreasing"
  TANGENT = "tangent"


class MovingEventDomainError(ValueError):
  """A UTC interval or ordered moving-pair event query was rejected.

  Both roles, TT endpoints and the exact upstream message are retained when
  available. Native computation failures propagate unchanged.

  UTC 区间或有序移动对象事件查询被拒绝。可用时保留两侧身份、TT 端点及上游原始文本；
  原生计算失败保留原异常。
  """

  def __init__(
    self,
    message: str,
    *,
    operation: str,
    first_object: Body | LunarNode | None = None,
    second_object: Body | LunarNode | None = None,
    start_jde_tt: float | None = None,
    end_jde_tt: float | None = None,
    upstream_message: str | None = None,
  ) -> None:
    super().__init__(message)
    self.operation = operation
    self.first_object = first_object
    self.second_object = second_object
    self.start_jde_tt = start_jde_tt
    self.end_jde_tt = end_jde_tt
    self.upstream_message = upstream_message


@dataclass(frozen=True, slots=True)
class _MovingEvent:
  jde_tt: float
  first_longitude_deg: float
  second_longitude_deg: float
  first_rate_deg_per_tt_day: float
  second_rate_deg_per_tt_day: float
  signed_difference_deg: float
  direction: RelativeDirection


def _pairs(
  values: Sequence[tuple[AstronomicalObject, AstronomicalObject]],
) -> tuple[tuple[AstronomicalObject, AstronomicalObject], ...]:
  if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
    raise TypeError("pairs must be a sequence of ordered body/node pairs")
  result = []
  for pair in values:
    if not isinstance(pair, Sequence) or isinstance(pair, (str, bytes)) or len(pair) != 2:
      raise TypeError("Each pair must contain exactly two body/node identities")
    first, second = pair
    if not _is_astronomical_object(first) or not _is_astronomical_object(second):
      raise TypeError("Pair endpoints must be Body or LunarNode values")
    if first == second:
      raise ValueError("A moving pair must have distinct identities")
    result.append((first, second))
  if not result or len(set(result)) != len(result):
    raise ValueError("pairs must be nonempty and must not repeat ordered pairs")
  return tuple(result)


@dataclass(frozen=True, slots=True)
class MovingAspectHit:
  """One major-aspect branch with both moving roles and retained event values.

  Time is JDE(TT), longitudes are degrees and rates are degrees per TT day.
  signed_difference_deg retains the provider's first-minus-second angle; separation_deg and
  deviation_deg use second-minus-first in (-180, 180]. direction describes that
  relative separation, not either object's motion. At a tangent, the reported
  relative rate need not be exactly zero.

  一个主要相位分支，保留两侧移动角色及事件原值。时刻为 JDE(TT)，黄经以度计，速率为
  度/TT 日。signed_difference_deg 保留上游第一侧减第二侧；separation_deg 与
  deviation_deg 使用第二侧减第一侧，归入 (-180, 180]。direction 是相对角距方向，
  不是任一对象自身的运动；相切时报告的相对速率不一定恰为零。
  """

  first_object: AstronomicalObject
  second_object: AstronomicalObject
  aspect: MajorAspect
  branch_deg: float
  jde_tt: float
  first_longitude_deg: float
  second_longitude_deg: float
  first_rate_deg_per_tt_day: float
  second_rate_deg_per_tt_day: float
  signed_difference_deg: float
  direction: RelativeDirection

  def __post_init__(self) -> None:
    _pairs(((self.first_object, self.second_object),))
    if type(self.aspect) is not MajorAspect or type(self.direction) is not RelativeDirection:
      raise TypeError("aspect and direction must be MajorAspect and RelativeDirection values")
    for name in (
      "branch_deg",
      "jde_tt",
      "first_longitude_deg",
      "second_longitude_deg",
      "first_rate_deg_per_tt_day",
      "second_rate_deg_per_tt_day",
      "signed_difference_deg",
    ):
      object.__setattr__(self, name, finite_number(getattr(self, name), name))
    if self.branch_deg not in _branches(aspect_angle(self.aspect)):
      raise ValueError("branch_deg does not belong to the selected aspect")
    expected = _signed(_signed(self.first_longitude_deg) - _signed(self.second_longitude_deg))
    if not -180 < self.signed_difference_deg <= 180 or self.signed_difference_deg != expected:
      raise ValueError(
        "signed_difference_deg must match the canonical first-minus-second longitudes"
      )
    finite_number(self.relative_rate_deg_per_tt_day, "relative_rate_deg_per_tt_day")

  @property
  def separation_deg(self) -> float:
    """Second-minus-first angle in (-180, 180]. 第二侧减第一侧的角度，归入 (-180, 180]。"""
    return _signed(-self.signed_difference_deg)

  @property
  def deviation_deg(self) -> float:
    """Signed separation minus the requested branch. 带符号角距减去请求分支。"""
    return _deviation(self.separation_deg, self.branch_deg)

  @property
  def relative_rate_deg_per_tt_day(self) -> float:
    """Second-minus-first longitude rate. 第二侧减第一侧的黄经速率。"""
    return self.second_rate_deg_per_tt_day - self.first_rate_deg_per_tt_day


def _ordered(
  hits: Sequence[MovingAspectHit],
  pairs: tuple[tuple[AstronomicalObject, AstronomicalObject], ...],
) -> tuple[MovingAspectHit, ...]:
  return tuple(
    sorted(
      hits,
      key=lambda hit: (
        hit.jde_tt,
        pairs.index((hit.first_object, hit.second_object)),
        aspect_angle(hit.aspect),
        hit.branch_deg,
      ),
    )
  )


@dataclass(frozen=True, slots=True)
class MovingAspectEvents:
  """Immutable ordered pairs, converted TT interval, provider records and hits.

  Sequences are copied, including nested pairs. Construction checks consistency
  and both provider windows without native calls; it does not establish a supplied
  list's astronomical origin or completeness. See entry.moving_aspect_events.

  不可变的有序对象对、转换后 TT 区间、事件模型记录及命中。复制各序列，包括嵌套对象对；
  构造时不调用原生库，只检查一致性及两侧来源窗口，不认证给定列表的天文来源或完整性。
  见 entry.moving_aspect_events。
  """

  start_utc: datetime
  end_utc: datetime
  start_jde_tt: float
  end_jde_tt: float
  pairs: tuple[tuple[AstronomicalObject, AstronomicalObject], ...]
  aspects: tuple[MajorAspect, ...]
  sources: tuple[TransitSource, ...]
  hits: tuple[MovingAspectHit, ...]
  celestial_version: str
  astrology_version: str

  def __post_init__(self) -> None:
    start, end = (
      _normalize_utc(self.start_utc, "start_utc"),
      _normalize_utc(self.end_utc, "end_utc"),
    )
    if start >= end:
      raise ValueError("UTC interval must be nonempty and increasing")
    object.__setattr__(self, "start_utc", start)
    object.__setattr__(self, "end_utc", end)
    for name in ("start_jde_tt", "end_jde_tt"):
      object.__setattr__(self, name, finite_number(getattr(self, name), name))
    if self.start_jde_tt >= self.end_jde_tt:
      raise ValueError("TT interval must be nonempty and increasing")
    object.__setattr__(self, "pairs", _pairs(self.pairs))
    object.__setattr__(self, "aspects", _selected_aspects(self.aspects))
    for name, member_type in (("sources", TransitSource), ("hits", MovingAspectHit)):
      values = getattr(self, name)
      if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a sequence")
      values = tuple(values)
      if any(type(value) is not member_type for value in values):
        raise TypeError(f"{name} must contain only {member_type.__name__} values")
      object.__setattr__(self, name, values)
    identities = tuple(dict.fromkeys(identity for pair in self.pairs for identity in pair))
    if tuple(source.moving_object for source in self.sources) != identities:
      raise ValueError("sources must match distinct pair identities in first-appearance order")
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
      nonempty_text(getattr(self, name), name)
    for hit in self.hits:
      if (hit.first_object, hit.second_object) not in self.pairs or hit.aspect not in self.aspects:
        raise ValueError("Hit pair and aspect must belong to the retained selections")
      if not self.start_jde_tt <= hit.jde_tt < self.end_jde_tt:
        raise ValueError("Hit must lie in the half-open TT interval")
    if self.hits != _ordered(self.hits, self.pairs):
      raise ValueError("Hits are not in stable moving-pair order")


def moving_hit_utc(hit: MovingAspectHit) -> datetime:
  """Read a moving hit's TT as display UTC without searching or calculating houses.

  Conversion effects, leap-boundary precision and EventDisplayError follow
  transit_hit_utc. The retained TT remains unchanged.

  将移动命中的 TT 读为显示 UTC，不搜索或计算宫位。转换副作用、闰秒边界精度及
  EventDisplayError 沿用 transit_hit_utc；保留的 TT 不变。
  """
  if type(hit) is not MovingAspectHit:
    raise TypeError("hit must be a MovingAspectHit")
  from astrology.celestial import event_utc

  return event_utc(hit.jde_tt)


def moving_aspect_events(
  *,
  pairs: Sequence[tuple[AstronomicalObject, AstronomicalObject]],
  aspects: Sequence[MajorAspect],
  start_utc: datetime,
  end_utc: datetime,
) -> MovingAspectEvents:
  """Find moving-pair major aspects in the converted half-open TT interval.

  Ordered pairs and aspects are explicit, nonempty and unique. Reversed pairs are
  distinct requests; constant mismatch is empty success. Both provider domains and their
  maximum spans apply. Domain/span or upstream UTC-conversion rejections and continuously
  satisfied relations raise MovingEventDomainError. Native computation failures
  propagate unchanged, with no partial result.
  UTC endpoints must be aware built-in datetimes at or after 1972-01-01 UTC.
  Invalid types raise TypeError; invalid selections (including self-pairs), endpoint
  order or missing UTC offsets raise ValueError. Pre-1972 endpoints raise
  HistoricalTimeError. MovingEventDomainError is a
  ValueError subclass. Search lazily initializes native astronomy.
  Hits sort by raw TT, pair request order, aspect angle and branch. Events for
  different requested pairs remain separate even at the same TT.
  See entry.moving_aspect_events for coordinate and source conventions.

  在转换后的左闭右开 TT 区间内搜索移动对象主要相位。对象对及相位须显式、非空且不重复。
  逆序是不同请求；恒定不等为空成功。两侧事件模型的域与最长
  区间均适用。求值域、区间、上游 UTC 转换被拒绝或关系持续成立时抛 MovingEventDomainError；
  原生计算失败保持原异常，不返回部分结果。
  UTC 端点须为有时区的内建 datetime，且不早于 1972-01-01 UTC。类型无效抛 TypeError；
  选择（包括自身配对）或端点顺序无效、缺少 UTC 偏移时抛 ValueError；
  早于 1972 年的端点抛 HistoricalTimeError。
  MovingEventDomainError 是 ValueError 的子类。搜索延迟初始化原生天文；
  按原始 TT、请求对象对顺序、相位角与分支排序，不同请求对象对的同时事件分别保留。
  坐标及来源约定见 entry.moving_aspect_events。
  """
  selected_pairs, selected_aspects = _pairs(pairs), _selected_aspects(aspects)
  start, end = _normalize_utc(start_utc, "start_utc"), _normalize_utc(end_utc, "end_utc")
  if start >= end:
    raise ValueError("UTC interval must be nonempty and increasing")
  from astrology.celestial import celestial_version, moving_events, moving_interval, transit_source

  start_tt, end_tt = moving_interval(start, end)
  identities = tuple(dict.fromkeys(identity for pair in selected_pairs for identity in pair))
  sources = tuple(transit_source(identity) for identity in identities)
  hits = []
  for first, second in selected_pairs:
    for aspect in selected_aspects:
      for branch in _branches(aspect_angle(aspect)):
        for event in moving_events(first, second, _signed(-branch), start_tt, end_tt):
          hits.append(
            MovingAspectHit(
              first,
              second,
              aspect,
              branch,
              event.jde_tt,
              event.first_longitude_deg,
              event.second_longitude_deg,
              event.first_rate_deg_per_tt_day,
              event.second_rate_deg_per_tt_day,
              event.signed_difference_deg,
              event.direction,
            )
          )
  return MovingAspectEvents(
    start,
    end,
    start_tt,
    end_tt,
    selected_pairs,
    selected_aspects,
    sources,
    _ordered(hits, selected_pairs),
    celestial_version(),
    installed_version(),
  )
