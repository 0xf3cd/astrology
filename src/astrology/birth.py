"""Original birth records and explicit modern time resolution.

原始出生记录与显式的现代时刻解析。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from enum import StrEnum
from errno import EINVAL, EISDIR, ENAMETOOLONG, ENOENT, ENOTDIR
from types import MappingProxyType
from typing import Literal

_DAY = timedelta(days=1)
_MODERN_UTC_START = datetime(1972, 1, 1, tzinfo=UTC)
_EARLIEST_MODERN_WALL = _MODERN_UTC_START.replace(tzinfo=None) - _DAY
_IANA_KEY = re.compile(r"[A-Za-z0-9_+\-]+(?:/[A-Za-z0-9_+\-]+)*")


class MissingBirthDataError(ValueError):
  """Required birth information is absent. 缺少必需的出生资料。"""


class AmbiguousBirthTimeError(ValueError):
  """A repeated wall time needs an explicit fold. 重复的本地钟点需要显式选择 fold。"""


class NonexistentBirthTimeError(ValueError):
  """The wall time falls in a clock-change gap. 本地钟点落在时钟调整的空缺中。"""


class HistoricalTimeError(ValueError):
  """The instant needs the future historical-time contract. 该时刻需要未来的历史时标合同。"""


class TimePrecision(StrEnum):
  """Stated clock precision, without inventing uncertainty bounds.

  记录所声明的钟点精度，不推定不确定区间。
  """

  HOUR = "hour"
  MINUTE = "minute"
  SECOND = "second"
  MICROSECOND = "microsecond"


@dataclass(frozen=True, slots=True)
class Location:
  """Finite degrees: latitude [-90, 90], longitude [-180, 180], north/east positive.

  有限角度：纬度 [-90, 90]、经度 [-180, 180]，北纬和东经为正。
  """

  latitude: float
  longitude: float

  def __post_init__(self) -> None:
    for name, value, limit in (
      ("latitude", self.latitude, 90),
      ("longitude", self.longitude, 180),
    ):
      if type(value) not in (int, float):
        raise TypeError(f"{name} must be a number, not bool or a converted string")
      if not -limit <= value <= limit:
        raise ValueError(f"{name} must be finite and within [-{limit}, {limit}] degrees")
      object.__setattr__(self, name, float(value))


@dataclass(frozen=True, slots=True)
class IanaTimezone:
  """A plain-string IANA key; existence is checked only during explicit resolution.

  普通字符串形式的 IANA 标识；仅在显式解析时检查其是否存在。
  """

  key: str

  def __post_init__(self) -> None:
    if type(self.key) is not str:
      raise TypeError("IANA key must be a plain string")
    if _IANA_KEY.fullmatch(self.key) is None:
      raise ValueError("IANA key must be a normalized relative timezone name")


@dataclass(frozen=True, slots=True)
class FixedOffset:
  """An explicit UTC offset strictly between -24 and +24 hours, without a database.

  显式 UTC 偏移量，严格介于 -24 和 +24 小时之间，不使用时区数据库。
  """

  offset: timedelta

  def __post_init__(self) -> None:
    if type(self.offset) is not timedelta:
      raise TypeError("offset must be a timedelta")
    if not -_DAY < self.offset < _DAY:
      raise ValueError("UTC offset must be strictly between -24 and +24 hours")


@dataclass(frozen=True, slots=True)
class BirthRecord:
  """A Gregorian civil record, retaining missing fields and copied source metadata.

  The clock must be naive with fold=0. Precision constrains smaller clock fields;
  None means unstated, not an assumed accuracy. Historical dates remain storable.
  Source keys and values must be plain strings, not mutable subclasses.

  公历民用记录，保留缺失字段并复制来源元数据。钟点须无时区且 fold=0；精度约束更小的钟点字段，
  None 表示未声明，不代表推定精度。历史日期仍可保存。
  来源键值须为普通字符串，不接纳可变子类。
  """

  birth_date: date
  birth_time: time | None = None
  timezone: IanaTimezone | FixedOffset | None = None
  location: Location | None = None
  precision: TimePrecision | None = None
  source: Mapping[str, str] = field(default_factory=dict)
  calendar: Literal["gregorian"] = "gregorian"

  def __post_init__(self) -> None:
    if type(self.birth_date) is not date:
      raise TypeError("birth_date must be a date, not a datetime or string")
    if type(self.calendar) is not str:
      raise TypeError("calendar must be a plain string")
    if self.calendar != "gregorian":
      raise ValueError("Only the gregorian record calendar is supported")
    if self.location is not None and type(self.location) is not Location:
      raise TypeError("location must be a Location or None")
    if self.timezone is not None and type(self.timezone) not in (IanaTimezone, FixedOffset):
      raise TypeError("timezone must be an IanaTimezone, FixedOffset, or None")
    if self.precision is not None and not isinstance(self.precision, TimePrecision):
      raise TypeError("precision must be a TimePrecision or None")

    clock = self.birth_time
    if clock is None:
      if self.precision is not None:
        raise ValueError("Clock precision requires a known birth_time")
    else:
      if type(clock) is not time:
        raise TypeError("birth_time must be a time or None")
      if clock.tzinfo is not None or clock.fold != 0:
        raise ValueError("birth_time must be naive with fold=0; resolve the timezone separately")
      if self.precision is not None:
        smaller_fields = {
          TimePrecision.HOUR: (clock.minute, clock.second, clock.microsecond),
          TimePrecision.MINUTE: (clock.second, clock.microsecond),
          TimePrecision.SECOND: (clock.microsecond,),
          TimePrecision.MICROSECOND: (),
        }[self.precision]
        if any(smaller_fields):
          raise ValueError("birth_time contains fields smaller than its stated precision")

    if not isinstance(self.source, Mapping):
      raise TypeError("source must be a string-to-string mapping")
    source = dict(self.source)
    if any(type(key) is not str or type(value) is not str for key, value in source.items()):
      raise TypeError("source keys and values must be plain strings")
    if any(not key for key in source):
      raise ValueError("source keys must not be empty")
    object.__setattr__(self, "source", MappingProxyType(source))


@dataclass(frozen=True, slots=True)
class ResolvedBirth:
  """A preserved record and separate UTC, offset, choice, and data provenance.

  UTC is canonical and at or after 1972-01-01T00:00:00Z. IANA results carry both
  data versions; fixed offsets carry neither. Construction checks consistency,
  not the truth of supplied version identifiers; resolve_birth_time reads them.

  保留原始记录，另存 UTC、偏移、消歧选择和数据来源。UTC 使用规范表示且不早于
  1972-01-01T00:00:00Z。IANA 结果记录两种数据版本，固定偏移不记录版本。构造时检查一致性，
  不核实所提供版本标识的真实性；resolve_birth_time 负责读取实际版本。
  """

  record: BirthRecord
  utc: datetime
  utc_offset: timedelta
  timezone_key: str | None
  fold: Literal[0, 1] | None
  tzdata_version: str | None
  iana_version: str | None

  def __post_init__(self) -> None:
    if type(self.record) is not BirthRecord:
      raise TypeError("record must be a BirthRecord")
    if self.record.birth_time is None or self.record.timezone is None:
      raise MissingBirthDataError("A resolved record requires birth_time and timezone")
    if type(self.utc) is not datetime:
      raise TypeError("utc must be a datetime")
    if self.utc.tzinfo is not UTC or self.utc.fold != 0:
      raise ValueError("utc must use datetime.UTC with fold=0")
    _require_modern_utc(self.utc)
    FixedOffset(self.utc_offset)
    _validate_fold(self.fold)

    original = datetime.combine(self.record.birth_date, self.record.birth_time)
    try:
      reconstructed = (self.utc + self.utc_offset).replace(tzinfo=None)
    except OverflowError as exc:
      raise ValueError("Resolved wall time is outside datetime's representable range") from exc
    if reconstructed != original:
      raise ValueError("Resolved UTC and offset do not preserve the recorded wall time")

    zone = self.record.timezone
    if isinstance(zone, FixedOffset):
      if self.utc_offset != zone.offset:
        raise ValueError("Resolved offset differs from the explicit input offset")
      if any(
        value is not None
        for value in (self.timezone_key, self.fold, self.tzdata_version, self.iana_version)
      ):
        raise ValueError("Fixed-offset results cannot claim IANA data or a fold choice")
    else:
      if type(self.timezone_key) is not str or self.timezone_key != zone.key:
        raise ValueError("Resolved timezone key differs from the recorded IANA key")
      if not all(
        type(value) is str and value for value in (self.tzdata_version, self.iana_version)
      ):
        raise ValueError("IANA results require package and IANA data versions")

  @property
  def timezone_source(self) -> Literal["fixed_offset", "tzdata"]:
    """Identify the resolution data source. 标识时刻解析的数据来源。"""
    return "fixed_offset" if self.timezone_key is None else "tzdata"

  @property
  def timezone_identity(self) -> str:
    """Return the IANA key or explicit UTC-offset name. 返回 IANA 标识或显式 UTC 偏移名称。"""
    return (
      self.timezone_key if self.timezone_key is not None else timezone(self.utc_offset).tzname(None)
    )


def _validate_fold(fold: int | None) -> None:
  if fold is not None:
    if type(fold) is not int:
      raise TypeError("fold must be the integer 0 or 1, not bool")
    if fold not in (0, 1):
      raise ValueError("fold must be 0, 1, or None")


def _require_modern_utc(instant: datetime) -> None:
  if instant < _MODERN_UTC_START:
    raise HistoricalTimeError("UTC before 1972-01-01 requires an explicit historical-time contract")


def _load_iana_zone(key: str) -> tuple[tzinfo, str, str]:
  from importlib import import_module
  from importlib.resources import files
  from zoneinfo import ZoneInfo

  data = import_module("tzdata")
  package_version = getattr(data, "__version__", None)
  iana_version = getattr(data, "IANA_VERSION", None)
  if not isinstance(package_version, str) or not isinstance(iana_version, str):
    raise RuntimeError("Installed tzdata does not expose its package and IANA versions")
  resource = files("tzdata.zoneinfo").joinpath(*key.split("/"))
  try:
    with resource.open("rb") as stream:
      zone = ZoneInfo.from_file(stream, key=key)
  except (OSError, ValueError) as exc:
    if isinstance(exc, OSError) and exc.errno not in (
      ENOENT,
      ENOTDIR,
      EISDIR,
      ENAMETOOLONG,
      EINVAL,
    ):
      raise
    raise ValueError(f"Unknown IANA timezone: {key!r}") from exc
  return zone, package_version, iana_version


def resolve_birth_time(record: BirthRecord, *, fold: Literal[0, 1] | None = None) -> ResolvedBirth:
  """Resolve a known clock/timezone without requiring a location or changing the record.

  IANA folds require 0 (earlier) or 1 (later); gaps and irrelevant choices fail.
  Read pinned tzdata only here. UTC before 1972 or outside datetime's range fails.

  解析已知钟点和时区，不要求地点，也不改变记录。IANA 重叠时刻须选 0（较早）或 1（较晚）；
  空缺时刻和无关选择均报错。仅在此处读取钉版 tzdata；早于 1972 或超出 datetime 范围的 UTC 报错。
  """
  if type(record) is not BirthRecord:
    raise TypeError("record must be a BirthRecord")
  _validate_fold(fold)
  if record.birth_time is None or record.timezone is None:
    raise MissingBirthDataError("Time resolution requires birth_time and timezone")
  wall = datetime.combine(record.birth_date, record.birth_time)
  if wall < _EARLIEST_MODERN_WALL:
    raise HistoricalTimeError("The recorded clock cannot represent a modern UTC instant")

  if isinstance(record.timezone, FixedOffset):
    if fold is not None:
      raise ValueError("fold is not applicable to a fixed UTC offset")
    offset = record.timezone.offset
    try:
      utc = wall.replace(tzinfo=timezone(offset)).astimezone(UTC)
    except OverflowError as exc:
      raise ValueError("Resolved UTC is outside datetime's representable range") from exc
    return ResolvedBirth(record, utc, offset, None, None, None, None)

  zone, package_version, iana_version = _load_iana_zone(record.timezone.key)
  try:
    potential = [wall.replace(tzinfo=zone, fold=choice).astimezone(UTC) for choice in (0, 1)]
  except OverflowError as exc:
    raise ValueError("Resolved UTC is outside datetime's representable range") from exc
  if all(utc < _MODERN_UTC_START for utc in potential):
    raise HistoricalTimeError("The recorded clock cannot represent a modern UTC instant")

  candidates = {
    utc: wall - utc.replace(tzinfo=None)
    for utc in potential
    if utc.astimezone(zone).replace(tzinfo=None, fold=0) == wall
  }
  if not candidates:
    raise NonexistentBirthTimeError("The recorded local time does not exist in this timezone")
  if len(candidates) == 1:
    if fold is not None:
      raise ValueError("fold is not applicable to a unique local time")
    utc = next(iter(candidates))
  else:
    if fold is None:
      raise AmbiguousBirthTimeError("The recorded local time is ambiguous; choose fold=0 or fold=1")
    utc = sorted(candidates)[fold]
  return ResolvedBirth(
    record, utc, candidates[utc], record.timezone.key, fold, package_version, iana_version
  )


def prepare_natal_input(record: BirthRecord, *, fold: Literal[0, 1] | None = None) -> ResolvedBirth:
  """Require known clock, timezone and location, then resolve; this does not calculate a chart.

  要求已知钟点、时区和地点后解析；此函数不计算命盘。
  """
  if type(record) is not BirthRecord:
    raise TypeError("record must be a BirthRecord")
  if record.birth_time is None or record.timezone is None or record.location is None:
    raise MissingBirthDataError("Complete natal input requires birth_time, timezone, and location")
  return resolve_birth_time(record, fold=fold)
