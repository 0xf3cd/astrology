"""Render stored charts using caller-supplied bilingual vocabulary, without I/O.

用调用方提供的双语词汇显示存储盘，不执行 I/O。
"""

from __future__ import annotations

from typing import cast

from astrology.aspects import AspectMotion
from astrology.birth import Location
from astrology.chart import NatalChart
from astrology.config import Body, HouseSystem, LunarNode, MajorAspect
from astrology.knowledge import Catalog, TranslationStatus
from astrology.knowledge.catalog import _sign_concept
from astrology.knowledge.records import _LANGUAGES, Language
from astrology.zodiac import Sign, _whole_arcseconds, sign_of

_HEADINGS = {
  "en": {
    "title": "Tropical geocentric natal chart",
    "input": "Recorded clock / timezone",
    "utc": "Resolved UTC",
    "location": "Latitude / longitude (degrees, north/east positive)",
    "positions": "Positions",
    "position_columns": "Object | Sign and longitude within sign | House | Motion",
    "motion_legend": "R: decreasing longitude; D: increasing; S: zero rate (unrounded).",
    "axes": "Axes and house cusps",
    "cusp": "House cusp",
    "aspects": "Aspects",
    "aspect_columns": "First | Second | Aspect | Branch | Deviation | Orb limit | Motion",
    "none": "None",
    "configuration": "Configuration",
    "houses": "Requested / effective house system",
    "requested_objects": "Requested aspect objects",
    "effective_objects": "Effective aspect objects (requested object order)",
    "all": "All requested objects (selection omitted)",
    "combination": "Orb combination (identifier)",
    "rule": "Aspect rule / base orb / object overrides",
    "provenance": "Provenance",
    "time_source": "tzdata package / IANA release / fold",
    "times": "JD(UT1) / JDE(TT)",
    "model": "Delta-T model / evaluation",
    "versions": "astrology / celestial-calendar versions",
    "frame": "Position frame / UT1 derivation",
    "display": "Angles are truncated toward zero to whole arcseconds; stored classifications are unchanged.",
  },
  "zh-CN": {
    "title": "热带地心本命盘",
    "input": "原始钟点 / 时区",
    "utc": "已解析的 UTC",
    "location": "纬度 / 经度（度，北纬、东经为正）",
    "positions": "位置",
    "position_columns": "对象 | 星座及星座内黄经 | 宫位 | 运动",
    "motion_legend": "R：黄经减小；D：黄经增大；S：速率为零（按未舍入值判断）。",
    "axes": "四轴与宫头",
    "cusp": "宫头",
    "aspects": "相位",
    "aspect_columns": "第一对象 | 第二对象 | 相位 | 分支 | 偏差 | 容许度上限 | 运动",
    "none": "无",
    "configuration": "配置",
    "houses": "请求 / 实际宫制",
    "requested_objects": "请求参与相位的对象",
    "effective_objects": "实际参与相位的对象（按请求对象顺序）",
    "all": "全部请求对象（未单独指定）",
    "combination": "容许度合成规则（标识）",
    "rule": "相位规则 / 基础容许度 / 对象单独设置",
    "provenance": "来源",
    "time_source": "tzdata 包版本 / IANA 版本 / fold",
    "times": "JD(UT1) / JDE(TT)",
    "model": "ΔT 模型 / 求值方式",
    "versions": "astrology / celestial-calendar 版本",
    "frame": "位置坐标约定 / UT1 推导方式",
    "display": "角度向零截断到整角秒；存储的分类结果不变。",
  },
}
_AXES = {
  "en": ("Ascendant", "Midheaven", "Descendant", "Imum Coeli"),
  "zh-CN": ("上升点", "中天", "下降点", "天底"),
}
_MOTIONS = {
  "en": {motion: motion.value for motion in AspectMotion},
  "zh-CN": {
    AspectMotion.APPLYING: "入相",
    AspectMotion.SEPARATING: "离相",
    AspectMotion.EXACT: "精确",
    AspectMotion.STATIONARY: "相对速率为零",
    AspectMotion.INDETERMINATE: "无法确定",
  },
}


def _dms(arcseconds: int) -> str:
  degrees, rest = divmod(arcseconds, 3600)
  minutes, seconds = divmod(rest, 60)
  return f"{degrees}°{minutes:02d}'{seconds:02d}\""


def _angle(value: float, *, signed: bool = False) -> str:
  count = _whole_arcseconds(abs(value))
  prefix = ("-" if value < 0.0 else "+") if signed and count else ""
  return prefix + _dms(count)


def _cell(value: str) -> str:
  escaped = []
  for character in value:
    if character in "\\|":
      escaped.append("\\" + character)
    elif not character.isprintable():
      escaped.append(ascii(character)[1:-1])
    else:
      escaped.append(character)
  return "".join(escaped)


def _name(
  identity: Body | LunarNode | MajorAspect | HouseSystem | Sign,
  catalog: Catalog,
  language: Language,
) -> str:
  if isinstance(identity, Sign):
    concept = _sign_concept(catalog, identity)
  else:
    matches = [concept for concept in catalog.concepts if concept.configuration is identity]
    if len(matches) != 1:
      raise ValueError(f"Expected one catalog concept for {identity.value}")
    concept = matches[0]
  if concept.name.status(language) is not TranslationStatus.CURRENT:
    raise ValueError(f"Missing or stale {language} name for {concept.identifier}")
  name = concept.name.text(language)
  if name is None:
    raise ValueError(f"Missing {language} name for {concept.identifier}")
  return _cell(name)


def _longitude_text(value: float, catalog: Catalog, language: Language) -> str:
  count = _whole_arcseconds(value) % (30 * 3600)
  return f"{_name(sign_of(value), catalog, language)} {_dms(count)}"


def format_chart(chart: NatalChart, catalog: Catalog, *, language: Language = "en") -> str:
  """Return a text table of stored positions, houses, aspects, configuration and provenance.

  The caller supplies the loaded Catalog; rendering does no resource I/O or native
  astronomy. Names must exist with current translations for en or zh-CN, otherwise
  raise ValueError (KeyError for a missing sign ID). Angles use truncate_display's
  whole-arcsecond rule, without changing stored classifications, house or motion.
  Even a deviation displayed as zero retains its stored motion label. Invalid
  chart/catalog types raise TypeError. This table is not a lossless chart record.
  Nonprinting characters, backslashes and table delimiters in supplied names and
  provenance are escaped for display; stored values are unchanged.

  返回存储位置、宫位、相位、配置及来源的文本表格。调用方须提供已加载的 Catalog；
  显示不读取资源或调用原生天文库。en 或 zh-CN 的名称及译文必须齐备且为当前版本，
  否则抛出 ValueError（缺少星座标识时为 KeyError）。角度沿用 truncate_display 的整角秒截断规则，
  不改存储的分类、宫位或运动状态；偏差显示为零时也保留原运动标签。
  chart/catalog 类型错误时抛出 TypeError。本表不是无损命盘记录。
  传入名称及来源中的非打印字符、反斜线和表格分隔符会转义显示，不改存储值。
  """
  if type(chart) is not NatalChart or type(catalog) is not Catalog:
    raise TypeError("chart and catalog must be NatalChart and Catalog values")
  if type(language) is not str or language not in _LANGUAGES:
    raise ValueError("language must be en or zh-CN")
  labels = _HEADINGS[language]
  record = chart.resolved.record
  location = cast("Location", record.location)
  lines = [
    labels["title"],
    f"{labels['input']}: {record.birth_date} {record.birth_time} / {chart.resolved.timezone_identity}",
    f"{labels['utc']}: {chart.resolved.utc.isoformat()}",
    f"{labels['location']}: {location.latitude} / {location.longitude}",
    "",
    labels["positions"],
    labels["position_columns"],
  ]
  for position, placement in zip(chart.positions, chart.placements, strict=True):
    rate = position.longitude_rate_deg_per_tt_day
    motion = "R" if rate < 0.0 else "D" if rate > 0.0 else "S"
    lines.append(
      f"{_name(position.identity, catalog, language)} [{position.identity.value}] | "
      f"{_longitude_text(position.longitude_deg, catalog, language)} | {placement.house} | {motion}"
    )
  lines.extend([labels["motion_legend"], "", labels["axes"]])
  for label, value in zip(
    _AXES[language],
    (
      chart.houses.ascendant_deg,
      chart.houses.midheaven_deg,
      chart.houses.descendant_deg,
      chart.houses.imum_coeli_deg,
    ),
    strict=True,
  ):
    lines.append(f"{label}: {_longitude_text(value, catalog, language)}")
  for house, value in enumerate(chart.houses.cusps_deg, start=1):
    lines.append(f"{labels['cusp']} {house}: {_longitude_text(value, catalog, language)}")
  lines.extend(["", labels["aspects"], labels["aspect_columns"]])
  for hit in chart.aspects:
    lines.append(
      " | ".join(
        (
          _name(hit.first, catalog, language),
          _name(hit.second, catalog, language),
          _name(hit.aspect, catalog, language),
          _angle(hit.branch_deg, signed=True),
          _angle(hit.deviation_deg, signed=True),
          _angle(hit.orb_limit_deg),
          _MOTIONS[language][hit.motion],
        )
      )
    )
  if not chart.aspects:
    lines.append(labels["none"])
  requested = chart.requested
  participants = (
    labels["all"]
    if requested.aspect_objects is None
    else ", ".join(_name(identity, catalog, language) for identity in requested.aspect_objects)
  )
  effective = (
    ", ".join(_name(identity, catalog, language) for identity in chart.effective.aspect_objects)
    or labels["none"]
  )
  lines.extend(
    [
      "",
      labels["configuration"],
      f"{labels['houses']}: {_name(requested.house_system, catalog, language)} / "
      f"{_name(chart.effective.house_system, catalog, language)}",
      f"{labels['requested_objects']}: {participants}",
      f"{labels['effective_objects']}: {effective}",
      f"{labels['combination']}: {requested.orb_combination or labels['none']}",
    ]
  )
  for rule in requested.aspects:
    overrides = (
      ", ".join(
        f"{_name(entry.identity, catalog, language)}={_angle(entry.orb_degrees)}"
        for entry in rule.object_orbs
      )
      or labels["none"]
    )
    lines.append(
      f"{labels['rule']}: {_name(rule.aspect, catalog, language)} / "
      f"{_angle(rule.orb_degrees)} / {overrides}"
    )
  lines.extend(
    [
      "",
      labels["provenance"],
      f"{labels['time_source']}: {_cell(chart.resolved.tzdata_version or labels['none'])} / "
      f"{_cell(chart.resolved.iana_version or labels['none'])} / "
      f"{labels['none'] if chart.resolved.fold is None else chart.resolved.fold}",
      f"{labels['times']}: {chart.times.jd_ut1} / {chart.times.jde_tt}",
      f"{labels['model']}: {_cell(chart.effective.delta_t_model)} / {chart.effective.evaluation}",
      f"{labels['versions']}: {_cell(chart.provenance.astrology_version)} / "
      f"{_cell(chart.provenance.celestial_version)}",
      f"{labels['frame']}: {chart.provenance.position_frame} / {chart.provenance.ut1_derivation}",
      labels["display"],
    ]
  )
  return "\n".join(lines)
