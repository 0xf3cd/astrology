"""Versioned chart records, restoration without astronomy, and explicit replay.

带版本的命盘记录、不调用天文库的恢复，以及显式重算。
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version
from typing import Final, Literal, TypeVar, cast

from astrology._distribution import installed_version
from astrology._validation import finite_number
from astrology.aspects import AspectHit, AspectMotion
from astrology.birth import (
  BirthRecord,
  FixedOffset,
  IanaTimezone,
  Location,
  ResolvedBirth,
  TimePrecision,
)
from astrology.chart import (
  _EVALUATION,
  _POSITION_FRAME,
  _UT1_DERIVATION,
  ChartHouses,
  ChartProvenance,
  ChartTimes,
  EclipticPosition,
  EffectiveConfiguration,
  NatalChart,
  Placement,
  natal_chart,
)
from astrology.config import (
  AspectRule,
  Body,
  ChartConfig,
  HouseSystem,
  LunarNode,
  MajorAspect,
  ObjectOrb,
  OrbCombination,
)
from astrology.zodiac import Sign

_SCHEMA_VERSION: Final = 1
_Enum = TypeVar("_Enum", bound=StrEnum)
_Text = TypeVar("_Text", bound=str)


class ChartRecordError(ValueError):
  """The JSON chart record is malformed, inconsistent, or uses an unsupported schema.

  JSON 命盘记录格式不合法、内部不一致，或使用了不支持的结构版本。
  """


class ChartReplayError(ValueError):
  """A replay needs unavailable package metadata, a package version or a fixed model.

  重算需要的包元数据、包版本或固定模型不可用。
  """


def _microseconds(delta: timedelta) -> int:
  return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def dumps_chart(chart: NatalChart) -> str:
  """Encode schema v1 as deterministic JSON, retaining unrounded values and input provenance.

  This stores a result; it does not calculate or authenticate astronomy. Floats use
  Python's lossless JSON representation, including signed zero. Object keys are
  sorted; arrays retain their semantic order. No native astronomy is imported.
  A non-NatalChart argument raises TypeError.

  编成结构版本 v1 的确定性 JSON，保留未舍入值及输入来源。这是保存结果，不计算或认证天文值。
  浮点数用 Python 的无损 JSON 表示，保留带符号的零；对象键排序，数组保留语义顺序。
  不导入原生天文库；参数不是 NatalChart 时抛出 TypeError。
  """
  if type(chart) is not NatalChart:
    raise TypeError("chart must be a NatalChart")
  resolved = chart.resolved
  record = resolved.record
  zone = record.timezone
  zone_data = (
    {"kind": "iana", "key": zone.key}
    if isinstance(zone, IanaTimezone)
    else {"kind": "fixed_offset", "offset_microseconds": _microseconds(zone.offset)}
    if isinstance(zone, FixedOffset)
    else None
  )
  requested = chart.requested
  return json.dumps(
    {
      "schema_version": _SCHEMA_VERSION,
      "input": {
        "record": {
          "date": record.birth_date.isoformat(),
          "time": None if record.birth_time is None else record.birth_time.isoformat(),
          "calendar": record.calendar,
          "precision": None if record.precision is None else record.precision.value,
          "timezone": zone_data,
          "location": None
          if record.location is None
          else {"latitude": record.location.latitude, "longitude": record.location.longitude},
          "source": dict(record.source),
        },
        "resolved": {
          "utc": resolved.utc.isoformat(),
          "utc_offset_microseconds": _microseconds(resolved.utc_offset),
          "timezone_key": resolved.timezone_key,
          "fold": resolved.fold,
          "tzdata_version": resolved.tzdata_version,
          "iana_version": resolved.iana_version,
        },
      },
      "requested": {
        "house_system": requested.house_system.value,
        "objects": [identity.value for identity in requested.objects],
        "aspects": [
          {
            "aspect": rule.aspect.value,
            "orb_degrees": rule.orb_degrees,
            "object_orbs": [
              {"identity": entry.identity.value, "orb_degrees": entry.orb_degrees}
              for entry in rule.object_orbs
            ],
          }
          for rule in requested.aspects
        ],
        "zodiac": requested.zodiac,
        "center": requested.center,
        "aspect_objects": None
        if requested.aspect_objects is None
        else [identity.value for identity in requested.aspect_objects],
        "orb_combination": None
        if requested.orb_combination is None
        else requested.orb_combination.value,
      },
      "effective": {
        "house_system": chart.effective.house_system.value,
        "delta_t_model": chart.effective.delta_t_model,
        "evaluation": chart.effective.evaluation,
        "aspect_objects": [identity.value for identity in chart.effective.aspect_objects],
        "orb_combination": None
        if chart.effective.orb_combination is None
        else chart.effective.orb_combination.value,
      },
      "provenance": {
        "astrology_version": chart.provenance.astrology_version,
        "celestial_version": chart.provenance.celestial_version,
        "position_frame": chart.provenance.position_frame,
        "ut1_derivation": chart.provenance.ut1_derivation,
      },
      "times": {"jd_ut1": chart.times.jd_ut1, "jde_tt": chart.times.jde_tt},
      "positions": [
        {
          "identity": position.identity.value,
          "longitude_deg": position.longitude_deg,
          "latitude_deg": position.latitude_deg,
          "distance_au": position.distance_au,
          "longitude_rate_deg_per_tt_day": position.longitude_rate_deg_per_tt_day,
        }
        for position in chart.positions
      ],
      "houses": {
        "system": chart.houses.system.value,
        "ascendant_deg": chart.houses.ascendant_deg,
        "midheaven_deg": chart.houses.midheaven_deg,
        "descendant_deg": chart.houses.descendant_deg,
        "imum_coeli_deg": chart.houses.imum_coeli_deg,
        "cusps_deg": chart.houses.cusps_deg,
      },
      "placements": [
        {
          "identity": placement.identity.value,
          "sign": placement.sign.value,
          "sign_degree_deg": placement.sign_degree_deg,
          "house": placement.house,
        }
        for placement in chart.placements
      ],
      "aspects": [
        {
          "first": hit.first.value,
          "second": hit.second.value,
          "aspect": hit.aspect.value,
          "branch_deg": hit.branch_deg,
          "deviation_deg": hit.deviation_deg,
          "orb_limit_deg": hit.orb_limit_deg,
          "motion": hit.motion.value,
        }
        for hit in chart.aspects
      ],
    },
    allow_nan=False,
    sort_keys=True,
    indent=2,
  )


def _object(value: object, fields: tuple[str, ...] | None = None) -> dict[str, object]:
  if type(value) is not dict:
    raise TypeError("Expected a JSON object")
  result = cast("dict[str, object]", value)
  if fields is not None and result.keys() != set(fields):
    missing = set(fields) - result.keys()
    unknown = result.keys() - set(fields)
    raise ValueError(f"Invalid object fields: missing={sorted(missing)}, unknown={sorted(unknown)}")
  return result


def _array(value: object) -> list[object]:
  if type(value) is not list:
    raise TypeError("Expected a JSON array")
  return cast("list[object]", value)


def _text(value: object) -> str:
  if type(value) is not str:
    raise TypeError("Expected a JSON string")
  return value


def _integer(value: object) -> int:
  if type(value) is not int:
    raise TypeError("Expected a JSON integer, not bool")
  return value


def _literal(value: object, expected: _Text) -> _Text:
  if _text(value) != expected:
    raise ValueError(f"Expected {expected!r}")
  return expected


def _enum(kind: type[_Enum], value: object) -> _Enum:
  return kind(_text(value))


def _identity(value: object) -> Body | LunarNode:
  text = _text(value)
  try:
    return Body(text)
  except ValueError:
    return LunarNode(text)


def _nullable_text(value: object) -> str | None:
  return None if value is None else _text(value)


def _read_resolved(value: object) -> ResolvedBirth:
  data = _object(value, ("record", "resolved"))
  record = _object(
    data["record"], ("date", "time", "calendar", "precision", "timezone", "location", "source")
  )
  birth_date = date.fromisoformat(_text(record["date"]))
  clock = None if record["time"] is None else time.fromisoformat(_text(record["time"]))
  if birth_date.isoformat() != record["date"] or (
    clock is not None and clock.isoformat() != record["time"]
  ):
    raise ValueError("Date and time must use canonical ISO text")
  zone: IanaTimezone | FixedOffset | None = None
  if record["timezone"] is not None:
    zone_data = _object(record["timezone"])
    if zone_data.get("kind") == "iana":
      zone_data = _object(zone_data, ("kind", "key"))
      zone = IanaTimezone(_text(zone_data["key"]))
    else:
      zone_data = _object(zone_data, ("kind", "offset_microseconds"))
      _literal(zone_data["kind"], "fixed_offset")
      zone = FixedOffset(timedelta(microseconds=_integer(zone_data["offset_microseconds"])))
  location = None
  if record["location"] is not None:
    site = _object(record["location"], ("latitude", "longitude"))
    location = Location(
      finite_number(site["latitude"], "latitude"), finite_number(site["longitude"], "longitude")
    )
  original = BirthRecord(
    birth_date,
    clock,
    zone,
    location,
    None if record["precision"] is None else _enum(TimePrecision, record["precision"]),
    {key: _text(value) for key, value in _object(record["source"]).items()},
    _literal(record["calendar"], "gregorian"),
  )
  resolved = _object(
    data["resolved"],
    ("utc", "utc_offset_microseconds", "timezone_key", "fold", "tzdata_version", "iana_version"),
  )
  instant = datetime.fromisoformat(_text(resolved["utc"]))
  if instant.isoformat() != resolved["utc"]:
    raise ValueError("UTC must use canonical ISO text")
  fold = None if resolved["fold"] is None else _integer(resolved["fold"])
  if fold not in (None, 0, 1):
    raise ValueError("fold must be 0, 1 or None")
  return ResolvedBirth(
    original,
    instant,
    timedelta(microseconds=_integer(resolved["utc_offset_microseconds"])),
    _nullable_text(resolved["timezone_key"]),
    cast("Literal[0, 1] | None", fold),
    _nullable_text(resolved["tzdata_version"]),
    _nullable_text(resolved["iana_version"]),
  )


def _read_config(value: object) -> ChartConfig:
  data = _object(
    value,
    ("house_system", "objects", "aspects", "zodiac", "center", "aspect_objects", "orb_combination"),
  )
  rules = []
  for item in _array(data["aspects"]):
    rule = _object(item, ("aspect", "orb_degrees", "object_orbs"))
    orbs = []
    for item_orb in _array(rule["object_orbs"]):
      orb = _object(item_orb, ("identity", "orb_degrees"))
      orbs.append(
        ObjectOrb(_identity(orb["identity"]), finite_number(orb["orb_degrees"], "orb_degrees"))
      )
    rules.append(
      AspectRule(
        _enum(MajorAspect, rule["aspect"]), finite_number(rule["orb_degrees"], "orb_degrees"), orbs
      )
    )
  return ChartConfig(
    _enum(HouseSystem, data["house_system"]),
    tuple(_identity(item) for item in _array(data["objects"])),
    rules,
    _literal(data["zodiac"], "tropical"),
    _literal(data["center"], "geocentric"),
    None
    if data["aspect_objects"] is None
    else tuple(_identity(item) for item in _array(data["aspect_objects"])),
    None if data["orb_combination"] is None else _enum(OrbCombination, data["orb_combination"]),
  )


def _read_chart(value: object) -> NatalChart:
  data = _object(
    value,
    (
      "schema_version",
      "input",
      "requested",
      "effective",
      "provenance",
      "times",
      "positions",
      "houses",
      "placements",
      "aspects",
    ),
  )
  if _integer(data["schema_version"]) != _SCHEMA_VERSION:
    raise ValueError("Unsupported chart schema version")
  effective = _object(
    data["effective"],
    ("house_system", "delta_t_model", "evaluation", "aspect_objects", "orb_combination"),
  )
  provenance = _object(
    data["provenance"],
    ("astrology_version", "celestial_version", "position_frame", "ut1_derivation"),
  )
  times = _object(data["times"], ("jd_ut1", "jde_tt"))
  houses = _object(
    data["houses"],
    ("system", "ascendant_deg", "midheaven_deg", "descendant_deg", "imum_coeli_deg", "cusps_deg"),
  )
  positions = []
  for item in _array(data["positions"]):
    position = _object(
      item,
      ("identity", "longitude_deg", "latitude_deg", "distance_au", "longitude_rate_deg_per_tt_day"),
    )
    positions.append(
      EclipticPosition(
        _identity(position["identity"]),
        finite_number(position["longitude_deg"], "longitude_deg"),
        finite_number(position["latitude_deg"], "latitude_deg"),
        None
        if position["distance_au"] is None
        else finite_number(position["distance_au"], "distance_au"),
        finite_number(position["longitude_rate_deg_per_tt_day"], "longitude_rate_deg_per_tt_day"),
      )
    )
  placements = []
  for item in _array(data["placements"]):
    placement = _object(item, ("identity", "sign", "sign_degree_deg", "house"))
    placements.append(
      Placement(
        _identity(placement["identity"]),
        _enum(Sign, placement["sign"]),
        finite_number(placement["sign_degree_deg"], "sign_degree_deg"),
        _integer(placement["house"]),
      )
    )
  aspects = []
  for item in _array(data["aspects"]):
    hit = _object(
      item, ("first", "second", "aspect", "branch_deg", "deviation_deg", "orb_limit_deg", "motion")
    )
    aspects.append(
      AspectHit(
        _identity(hit["first"]),
        _identity(hit["second"]),
        _enum(MajorAspect, hit["aspect"]),
        finite_number(hit["branch_deg"], "branch_deg"),
        finite_number(hit["deviation_deg"], "deviation_deg"),
        finite_number(hit["orb_limit_deg"], "orb_limit_deg"),
        _enum(AspectMotion, hit["motion"]),
      )
    )
  return NatalChart(
    resolved=_read_resolved(data["input"]),
    requested=_read_config(data["requested"]),
    effective=EffectiveConfiguration(
      _enum(HouseSystem, effective["house_system"]),
      _text(effective["delta_t_model"]),
      _literal(effective["evaluation"], _EVALUATION),
      tuple(_identity(item) for item in _array(effective["aspect_objects"])),
      None
      if effective["orb_combination"] is None
      else _enum(OrbCombination, effective["orb_combination"]),
    ),
    provenance=ChartProvenance(
      _text(provenance["celestial_version"]),
      _literal(provenance["position_frame"], _POSITION_FRAME),
      _literal(provenance["ut1_derivation"], _UT1_DERIVATION),
      _text(provenance["astrology_version"]),
    ),
    times=ChartTimes(
      finite_number(times["jd_ut1"], "jd_ut1"), finite_number(times["jde_tt"], "jde_tt")
    ),
    positions=tuple(positions),
    houses=ChartHouses(
      _enum(HouseSystem, houses["system"]),
      finite_number(houses["ascendant_deg"], "ascendant_deg"),
      finite_number(houses["midheaven_deg"], "midheaven_deg"),
      finite_number(houses["descendant_deg"], "descendant_deg"),
      finite_number(houses["imum_coeli_deg"], "imum_coeli_deg"),
      tuple(finite_number(item, "cusps_deg") for item in _array(houses["cusps_deg"])),
    ),
    placements=tuple(placements),
    aspects=tuple(aspects),
  )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
  result: dict[str, object] = {}
  for key, value in pairs:
    if key in result:
      raise ValueError(f"Duplicate JSON key: {key!r}")
    result[key] = value
  return result


def loads_chart(data: str) -> NatalChart:
  """Restore schema v1 without astronomy, timezone lookup or replacing stored values.

  Reject unknown/missing/duplicate fields, unsupported identities, nonfinite values,
  noncanonical ISO timestamps and inconsistent pure derivations with ChartRecordError.
  JSON whitespace/key order need not be canonical. Free-string model/package versions
  may be unknown; replay checks their availability. This does not authenticate astronomy
  or the original timezone resolution. Non-string input raises TypeError.

  恢复结构版本 v1，不调用天文库、不查时区，也不替换存储值。未知、缺失或重复字段、
  不支持的标识、非有限数、非规范 ISO 时间文本或纯推导结果不一致时，抛出 ChartRecordError。
  JSON 的空白和键顺序不必规范化。自由字符串形式的模型及包版本可以未知，能否执行由重算检查。
  这不认证天文值或原来的时区解析；输入不是字符串时抛出 TypeError。
  """
  if type(data) is not str:
    raise TypeError("data must be a plain string")
  try:
    value: object = json.loads(data, object_pairs_hook=_unique_object)
    return _read_chart(value)
  except (TypeError, ValueError, OverflowError, RecursionError) as exc:
    raise ChartRecordError(f"Invalid chart record: {exc}") from exc


def recompute_chart(chart: NatalChart) -> NatalChart:
  """Recalculate from recorded UTC and request after checking versions and fixed models.

  No timezone database is consulted and the stored chart is not changed. Unavailable
  package metadata, versions or Delta-T model raise ChartReplayError; upstream domain failures
  remain ChartDomainError. Equal development version labels (such as 0.0.0) do not
  identify identical code. The caller compares the fresh result with suitable tolerances.
  A non-NatalChart argument raises TypeError.

  检查包版本及固定模型后，按记录中的 UTC 和请求重新计算。不查询时区库，也不改存储盘。
  包元数据、版本或 ΔT 模型不可用时抛出 ChartReplayError；上游域失败仍抛出 ChartDomainError。
  相同的开发版本号（例如 0.0.0）不代表代码完全相同；调用方按合适的容差比较新结果。
  参数不是 NatalChart 时抛出 TypeError。
  """
  if type(chart) is not NatalChart:
    raise TypeError("chart must be a NatalChart")
  try:
    if chart.provenance.astrology_version != installed_version():
      raise ChartReplayError("Recorded astrology version is unavailable")
    if chart.provenance.celestial_version != version("celestial-calendar"):
      raise ChartReplayError("Recorded celestial-calendar version is unavailable")
  except PackageNotFoundError as exc:
    raise ChartReplayError("Required installed package metadata is unavailable") from exc
  from astrology.celestial import celestial_version, delta_t_model_id

  if chart.provenance.celestial_version != celestial_version():
    raise ChartReplayError("Recorded native astronomy version is unavailable")
  if chart.effective.delta_t_model != delta_t_model_id():
    raise ChartReplayError("Recorded Delta-T model is unavailable")
  return natal_chart(chart.resolved, chart.requested)
