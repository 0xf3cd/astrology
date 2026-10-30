"""Static SVG figures from supplied results and vocabulary, without I/O.

从给定结果和词汇生成静态 SVG 图，不执行 I/O。
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping, Sequence
from xml.etree import ElementTree as ET

from astrology.aspects import AspectHit
from astrology.chart import NatalChart, _selected_longitudes
from astrology.config import AspectRule, MajorAspect, OrbCombination
from astrology.cross_aspects import CrossAspectHit, CrossChartAspects
from astrology.knowledge import Catalog
from astrology.knowledge.catalog import _configuration_name
from astrology.knowledge.records import _LANGUAGES, Language
from astrology.objects import Axis, ChartObject, LunarNode
from astrology.zodiac import Sign, _whole_arcseconds

_Hit = AspectHit | CrossAspectHit
_Coordinates = tuple[tuple[ChartObject, float], ...]
_FONT_FAMILY = "Noto Sans, Noto Sans CJK SC, sans-serif"
_MARGIN = 36
_MIN_WIDTH = 1000
_COL_WIDTH = 68
_ROW_HEADER = 58
_SIGN_UNITS = 10
_COLORS = {
  MajorAspect.CONJUNCTION: "#52677d",
  MajorAspect.SEXTILE: "#287c85",
  MajorAspect.SQUARE: "#b1614c",
  MajorAspect.TRINE: "#526fa2",
  MajorAspect.OPPOSITION: "#9c586c",
}
_LABELS = {
  "en": {
    "wheel": "Natal wheel",
    "natal": "Natal aspect matrix",
    "cross": "Cross-chart aspect matrix",
    "orientation": "ASC is on the left. Longitude increases counterclockwise.",
    "triangle": "Rows: first object. Columns: second object. Each pair appears once, above the diagonal.",
    "rectangle": "Rows: left chart (L). Columns: right chart (R). Static longitude comparison.",
    "branch": "Each cell line is one oriented aspect branch; hover or inspect its description for the stored values.",
    "objects": "Objects and stored longitudes",
    "left": "Left chart",
    "right": "Right chart",
    "configuration": "Configuration",
    "system": "House system",
    "coordinates": "Zodiac / center / position frame",
    "times": "JD(UT1) / JDE(TT)",
    "models": "Delta-T model / astrology / celestial-calendar",
    "rules": "Aspect rules: base orb; object overrides",
    "combination": "Orb combination",
    "hits": "Stored aspects",
    "none": "None",
    "no_hits": "No matching aspects",
    "no_objects": "No selected objects",
    "definition": "definition",
    "branch_value": "branch",
    "deviation": "deviation",
    "limit": "orb limit",
    "motion": "motion",
    "display": "Longitudes truncate to whole arcseconds; rule orbs and cell branches use six significant digits. Geometry and full hit details keep stored values.",
    "signs": "Zodiac sectors",
    "houses": "House cusps",
  },
  "zh-CN": {
    "wheel": "本命盘轮",
    "natal": "本命相位矩阵",
    "cross": "双盘相位矩阵",
    "orientation": "上升点位于左侧，黄经沿逆时针递增。",
    "triangle": "行表示第一对象，列表示第二对象。每对对象只在对角线上方列一次。",
    "rectangle": "行：左盘（L）；列：右盘（R）。比较两盘已存黄经，不使用速率。",
    "branch": "格内每行是一条相位分支；悬停或读取描述可查已存数值。",
    "objects": "对象与已存黄经",
    "left": "左盘",
    "right": "右盘",
    "configuration": "配置",
    "system": "宫制",
    "coordinates": "黄道 / 中心 / 位置坐标约定",
    "times": "JD(UT1) / JDE(TT)",
    "models": "ΔT 模型 / astrology / celestial-calendar",
    "rules": "相位规则：基础容许度；对象单独设置",
    "combination": "容许度合成规则",
    "hits": "已存相位",
    "none": "无",
    "no_hits": "无相位命中",
    "no_objects": "未选择对象",
    "definition": "定义",
    "branch_value": "分支",
    "deviation": "偏差",
    "limit": "容许度上限",
    "motion": "运动",
    "display": "黄经按整角秒截断；规则容许度和格内分支取六位有效数字。几何与完整相位详情保留已存数值。",
    "signs": "黄道扇区",
    "houses": "宫头",
  },
}


def _xml(value: str) -> str:
  for character in value:
    code = ord(character)
    if not (
      code in (9, 10, 13)
      or 0x20 <= code <= 0xD7FF
      or 0xE000 <= code <= 0xFFFD
      or 0x10000 <= code <= 0x10FFFF
    ):
      raise ValueError(f"XML 1.0 invalid code point: U+{code:04X}")
  return value


def _visible(value: str) -> str:
  return "".join(
    character if character.isprintable() else ascii(character)[1:-1] for character in _xml(value)
  )


def _node(
  parent: ET.Element,
  tag: str,
  attributes: Mapping[str, str] | None = None,
  text: str | None = None,
) -> ET.Element:
  child = ET.SubElement(
    parent, tag, {key: _xml(value) for key, value in (attributes or {}).items()}
  )
  if text is not None:
    child.text = _xml(text)
  return child


def _units(value: str) -> int:
  return sum(
    2 if unicodedata.east_asian_width(character) in ("W", "F") else 1 for character in value
  )


def _wrap(value: str, budget: int) -> tuple[str, ...]:
  lines: list[str] = []
  current = ""
  width = 0
  for character in _visible(value):
    advance = _units(character)
    if current and width + advance > budget:
      space = current.rfind(" ")
      if space >= len(current) // 2:
        lines.append(current[:space].rstrip())
        current = current[space + 1 :]
      else:
        lines.append(current)
        current = ""
      width = _units(current)
    current += character
    width += advance
  lines.append(current)
  return tuple(lines)


def _text(
  parent: ET.Element,
  value: str,
  x: float,
  y: float,
  width: float,
  *,
  size: int = 14,
  role: str = "label",
) -> float:
  lines = _wrap(value, max(2, int((width - 8) // size)))
  line_height = math.ceil(size * 1.65)
  block = _node(
    parent,
    "g",
    {
      "data-role": role,
      "data-box": f"{x} {y} {width} {len(lines) * line_height}",
    },
  )
  for index, line in enumerate(lines):
    _node(
      block,
      "text",
      {
        "x": str(x + 4),
        "y": str(y + size * 1.25 + index * line_height),
        "font-size": str(size),
      },
      line,
    )
  return y + len(lines) * line_height + 6


def _page(title: str, description: str, width: int, language: Language) -> ET.Element:
  root = ET.Element(
    "svg",
    {
      "xmlns": "http://www.w3.org/2000/svg",
      "width": str(width),
      "role": "img",
      "aria-label": _xml(title),
      "xml:lang": language,
      "font-family": _FONT_FAMILY,
      "fill": "#243447",
    },
  )
  _node(root, "title", text=title)
  _node(root, "desc", text=description)
  _node(root, "rect", {"width": "100%", "height": "100%", "fill": "#ffffff"})
  return root


def _finish(root: ET.Element, height: float) -> str:
  extent = math.ceil(height + _MARGIN)
  root.set("height", str(extent))
  root.set("viewBox", f"0 0 {root.get('width')} {extent}")
  return ET.tostring(root, encoding="unicode")


def _inputs(catalog: Catalog, language: Language) -> None:
  if type(catalog) is not Catalog:
    raise TypeError("catalog must be a Catalog")
  if type(language) is not str or language not in _LANGUAGES:
    raise ValueError("language must be en or zh-CN")


def _degree(value: float, *, signed: bool = False) -> str:
  return format(value, "+.6g" if signed else ".6g") + "°"


def _longitude_text(value: float) -> str:
  degrees, remainder = divmod(_whole_arcseconds(value), 3600)
  minutes, seconds = divmod(remainder, 60)
  return f"{degrees}°{minutes:02d}\u2032{seconds:02d}″"


def _chart_lines(chart: NatalChart, catalog: Catalog, language: Language) -> list[str]:
  labels = _LABELS[language]
  return [
    f"{labels['system']}: {_configuration_name(chart.effective.house_system, catalog, language)}",
    f"{labels['coordinates']}: {chart.requested.zodiac} / {chart.requested.center} / "
    f"{chart.provenance.position_frame}",
    f"{labels['times']}: {chart.times.jd_ut1} / {chart.times.jde_tt}",
    f"{labels['models']}: {chart.effective.delta_t_model} / "
    f"{chart.provenance.astrology_version} / {chart.provenance.celestial_version}",
  ]


def _rule_lines(
  rules: Sequence[AspectRule],
  combination: OrbCombination | None,
  catalog: Catalog,
  language: Language,
) -> list[str]:
  labels = _LABELS[language]
  lines = [labels["rules"]]
  for rule in rules:
    overrides = (
      ", ".join(
        f"{_configuration_name(orb.identity, catalog, language)}={_degree(orb.orb_degrees)}"
        for orb in rule.object_orbs
      )
      or labels["none"]
    )
    lines.append(
      f"{_configuration_name(rule.aspect, catalog, language)}: "
      f"{_degree(rule.orb_degrees)}; {overrides}"
    )
  if not rules:
    lines.append(labels["none"])
  lines.append(f"{labels['combination']}: {combination.value if combination else labels['none']}")
  return lines


def _lines(parent: ET.Element, values: Sequence[str], y: float, width: float) -> float:
  for value in values:
    y = _text(parent, value, _MARGIN, y, width - 2 * _MARGIN)
  return y


def _object_key(
  parent: ET.Element,
  coordinates: _Coordinates,
  prefix: str,
  title: str,
  catalog: Catalog,
  language: Language,
  y: float,
  width: float,
) -> float:
  y = _text(parent, title, _MARGIN, y + 12, width - 2 * _MARGIN, size=18)
  if not coordinates:
    return _lines(parent, [_LABELS[language]["no_objects"]], y, width)
  for index, (identity, longitude) in enumerate(coordinates, start=1):
    name = _configuration_name(identity, catalog, language)
    value = f"{prefix}{index} · {name} [{identity.value}] · {_longitude_text(longitude)}"
    if isinstance(identity, LunarNode):
      value += (
        f" · {_LABELS[language]['definition']}: "
        f"{_configuration_name(identity.definition, catalog, language)}"
      )
    group = _node(
      parent,
      "g",
      {
        "data-role": "object-key",
        "data-identity": identity.value,
        "data-prefix": prefix,
        "data-name": name,
        "data-longitude": str(longitude),
      },
    )
    _node(group, "title", text=_visible(value))
    y = _text(group, value, _MARGIN, y, width - 2 * _MARGIN)
  return y


def _endpoints(hit: _Hit) -> tuple[ChartObject, ChartObject]:
  if isinstance(hit, AspectHit):
    return hit.first, hit.second
  return hit.left_object, hit.right_object


def _hit_attributes(hit: _Hit) -> dict[str, str]:
  first, second = _endpoints(hit)
  result = {
    "data-aspect": hit.aspect.value,
    "data-first": first.value,
    "data-second": second.value,
    "data-branch": str(hit.branch_deg),
    "data-deviation": str(hit.deviation_deg),
    "data-orb-limit": str(hit.orb_limit_deg),
  }
  if type(hit) is AspectHit:
    result["data-motion"] = hit.motion.value
  return result


def _hit_text(hit: _Hit, catalog: Catalog, language: Language) -> str:
  labels = _LABELS[language]
  value = (
    f"{_configuration_name(hit.aspect, catalog, language)}; "
    f"{labels['branch_value']}={hit.branch_deg}°; "
    f"{labels['deviation']}={hit.deviation_deg}°; "
    f"{labels['limit']}={hit.orb_limit_deg}°"
  )
  if type(hit) is AspectHit:
    value += f"; {labels['motion']}={hit.motion.value}"
  return value


def _point(longitude: float, ascendant: float, radius: float) -> tuple[float, float]:
  angle = math.radians(longitude - ascendant + 180)
  return 500 + radius * math.cos(angle), 430 - radius * math.sin(angle)


def _wheel_geometry(
  root: ET.Element, chart: NatalChart, catalog: Catalog, language: Language
) -> None:
  ascendant = chart.houses.ascendant_deg
  for index, sign in enumerate(Sign):
    outer_start = _point(index * 30, ascendant, 278)
    outer_end = _point((index + 1) * 30, ascendant, 278)
    inner_start = _point(index * 30, ascendant, 240)
    inner_end = _point((index + 1) * 30, ascendant, 240)
    sector = _node(root, "g", {"data-role": "zodiac-sector", "data-sign": sign.value})
    _node(
      sector,
      "path",
      {
        "d": f"M {outer_start[0]} {outer_start[1]} A 278 278 0 0 0 "
        f"{outer_end[0]} {outer_end[1]} L {inner_end[0]} {inner_end[1]} "
        f"A 240 240 0 0 1 {inner_start[0]} {inner_start[1]} Z",
        "fill": "#eef2f5" if index % 2 == 0 else "#f8fafb",
        "stroke": "#bac6ce",
      },
    )
    name = _configuration_name(sign, catalog, language)
    x, y = _point(index * 30 + 15, ascendant, 259)
    display = name if _units(_visible(name)) <= _SIGN_UNITS else f"S{index + 1}"
    label = _node(
      sector,
      "text",
      {
        "x": str(x),
        "y": str(y + 4),
        "text-anchor": "middle",
        "font-size": "12",
        "data-role": "sign-label",
        "data-name": name,
        "data-box": f"{x - 60} {y - 16} 120 24",
      },
      _visible(display),
    )
    _node(label, "title", text=_visible(name))
  house_labels: list[tuple[float, float]] = []
  for index, longitude in enumerate(chart.houses.cusps_deg, start=1):
    start = _point(longitude, ascendant, 170)
    end = _point(longitude, ascendant, 240)
    _node(
      root,
      "line",
      {
        "x1": str(start[0]),
        "y1": str(start[1]),
        "x2": str(end[0]),
        "y2": str(end[1]),
        "stroke": "#bcc7cf",
        "data-role": "house-cusp",
        "data-house": str(index),
        "data-longitude": str(longitude),
      },
    )
    next_cusp = chart.houses.cusps_deg[index % 12]
    middle = (longitude + (next_cusp - longitude) % 360 / 2) % 360
    x, y = _point(middle, ascendant, 192)
    if all(abs(x - old_x) >= 24 or abs(y - old_y) >= 20 for old_x, old_y in house_labels):
      house_labels.append((x, y))
      _node(
        root,
        "text",
        {
          "x": str(x),
          "y": str(y + 4),
          "font-size": "12",
          "text-anchor": "middle",
          "fill": "#647382",
          "data-role": "house-number",
          "data-box": f"{x - 12} {y - 10} 24 20",
        },
        str(index),
      )
  for axis, longitude in _selected_longitudes(chart.positions, chart.houses, tuple(Axis)):
    end = _point(longitude, ascendant, 240)
    _node(
      root,
      "line",
      {
        "x1": "500",
        "y1": "430",
        "x2": str(end[0]),
        "y2": str(end[1]),
        "stroke": "#718495",
        "stroke-dasharray": "4 5",
        "data-role": "axis",
        "data-identity": axis.value,
        "data-longitude": str(longitude),
      },
    )


def _callout_positions(
  coordinates: _Coordinates, ascendant: float
) -> tuple[tuple[float, float], ...]:
  anchors = tuple(_point(longitude, ascendant, 225) for _, longitude in coordinates)
  positions = [(0.0, 0.0)] * len(anchors)
  for left in (True, False):
    order = sorted(
      (index for index, (x, _) in enumerate(anchors) if (x <= 500) is left),
      key=lambda index: (anchors[index][1], index),
    )
    last = 166.0
    levels = []
    for index in order:
      last = max(anchors[index][1], last + 26)
      levels.append(last)
    ceiling = 686.0
    for index in reversed(range(len(levels))):
      levels[index] = min(levels[index], ceiling)
      ceiling = levels[index] - 26
    for index, y in zip(order, levels, strict=True):
      positions[index] = (150.0 if left else 850.0, y)
  return tuple(positions)


def render_natal_wheel(chart: NatalChart, catalog: Catalog, *, language: Language = "en") -> str:
  """Return a natal SVG with true anchors, displaced callouts and object/cusp lists.

  Draw every stored position and all four axes; chords use chart.aspects unchanged.
  ASC is left, longitude increases counterclockwise. Natural width is 1000 CSS
  pixels; lists grow in height. Longitude text truncates to whole arcseconds.
  No I/O or astronomy is performed. Require exact NatalChart and Catalog types;
  wrong types, including subclasses, raise TypeError. Invalid language, missing/stale or
  ambiguous required names and XML-invalid text raise ValueError (a missing sign
  ID raises KeyError). A local CJK font is needed for Chinese. Inputs are unchanged.

  返回本命盘 SVG，保留真实锚点，提供避让标签及对象、宫头列表。画出全部已存位置和四轴，
  连线直接使用 chart.aspects。上升点在左，黄经沿逆时针递增；自然宽度为 1000 CSS 像素，
  列表按内容增高，黄经文字按整角秒截断。不执行 I/O 或天文计算。要求输入类型恰为 NatalChart
  和 Catalog，不接受子类，类型错误抛 TypeError；语言无效、必要名称
  缺失、陈旧、绑定不唯一或文字不符合 XML 时抛 ValueError，缺少星座 ID 时为 KeyError。
  中文需要查看器有 CJK 字体，不修改输入。
  """
  if type(chart) is not NatalChart:
    raise TypeError("chart must be a NatalChart")
  _inputs(catalog, language)
  labels = _LABELS[language]
  coordinates = _selected_longitudes(
    chart.positions, chart.houses, (*chart.requested.objects, *Axis)
  )
  root = _page(labels["wheel"], labels["orientation"], _MIN_WIDTH, language)
  root.set("data-kind", "natal-wheel")
  y = _text(root, labels["wheel"], _MARGIN, 24, 928, size=28)
  _text(root, labels["orientation"], _MARGIN, y, 928)
  _wheel_geometry(root, chart, catalog, language)
  by_identity = dict(coordinates)
  for hit in chart.aspects:
    first = _point(by_identity[hit.first], chart.houses.ascendant_deg, 166)
    second = _point(by_identity[hit.second], chart.houses.ascendant_deg, 166)
    group = _node(root, "g", {"data-role": "aspect", **_hit_attributes(hit)})
    _node(group, "title", text=_visible(_hit_text(hit, catalog, language)))
    _node(
      group,
      "line",
      {
        "x1": str(first[0]),
        "y1": str(first[1]),
        "x2": str(second[0]),
        "y2": str(second[1]),
        "stroke": _COLORS[hit.aspect],
        "stroke-opacity": "0.55",
        "stroke-width": "1.2",
      },
    )
  callouts = _callout_positions(coordinates, chart.houses.ascendant_deg)
  for index, ((identity, longitude), (label_x, label_y)) in enumerate(
    zip(coordinates, callouts, strict=True), start=1
  ):
    x, y = _point(longitude, chart.houses.ascendant_deg, 225)
    tick_end = _point(longitude, chart.houses.ascendant_deg, 237)
    name = _configuration_name(identity, catalog, language)
    group = _node(
      root,
      "g",
      {
        "data-role": "position",
        "data-identity": identity.value,
        "data-longitude": str(longitude),
        "data-name": name,
      },
    )
    _node(group, "title", text=_visible(name))
    _node(
      group,
      "line",
      {
        "x1": str(x),
        "y1": str(y),
        "x2": str(tick_end[0]),
        "y2": str(tick_end[1]),
        "stroke": "#263d51",
        "stroke-width": "2",
        "data-role": "position-tick",
      },
    )
    _node(
      group,
      "polyline",
      {
        "points": f"{x},{y} {label_x},{label_y}",
        "fill": "none",
        "stroke": "#9cabb7",
        "stroke-width": "0.8",
        "data-role": "leader",
      },
    )
    _node(
      group,
      "rect",
      {
        "x": str(label_x - 16),
        "y": str(label_y - 11),
        "width": "32",
        "height": "22",
        "rx": "5",
        "fill": "#ffffff",
        "stroke": "#a8b5c0",
        "data-role": "callout-box",
      },
    )
    _node(
      group,
      "text",
      {
        "x": str(label_x),
        "y": str(label_y + 5),
        "font-size": "13",
        "text-anchor": "middle",
        "data-role": "callout-label",
      },
      str(index),
    )
  y = _object_key(root, coordinates, "", labels["objects"], catalog, language, 734, 1000)
  y = _text(root, labels["houses"], _MARGIN, y + 10, 928, size=18)
  y = _text(
    root,
    "; ".join(
      f"{index}: {_longitude_text(longitude)}"
      for index, longitude in enumerate(chart.houses.cusps_deg, start=1)
    ),
    _MARGIN,
    y,
    928,
    role="house-key",
  )
  sign_keys = [
    f"S{index} · {_configuration_name(sign, catalog, language)}"
    for index, sign in enumerate(Sign, start=1)
    if _units(_visible(_configuration_name(sign, catalog, language))) > _SIGN_UNITS
  ]
  if sign_keys:
    y = _text(root, labels["signs"], _MARGIN, y + 10, 928, size=18)
    y = _lines(root, sign_keys, y, 1000)
  y = _text(root, labels["configuration"], _MARGIN, y + 10, 928, size=18)
  y = _lines(root, _chart_lines(chart, catalog, language), y, 1000)
  y = _lines(
    root,
    _rule_lines(chart.requested.aspects, chart.effective.orb_combination, catalog, language),
    y,
    1000,
  )
  y = _text(root, labels["hits"], _MARGIN, y + 10, 928, size=18)
  indices = {identity: index for index, (identity, _) in enumerate(coordinates, start=1)}
  for hit in chart.aspects:
    y = _text(
      root,
      f"{indices[hit.first]} / {indices[hit.second]} · {_hit_text(hit, catalog, language)}",
      _MARGIN,
      y,
      928,
    )
  if not chart.aspects:
    y = _text(root, labels["no_hits"], _MARGIN, y, 928)
  y = _text(root, labels["display"], _MARGIN, y + 12, 928)
  return _finish(root, y)


def _matrix(
  title: str,
  description: str,
  rows: _Coordinates,
  columns: _Coordinates,
  cells: Mapping[tuple[int, int], Sequence[_Hit]],
  keys: Sequence[tuple[str, str, _Coordinates]],
  metadata: Sequence[str],
  catalog: Catalog,
  language: Language,
  *,
  row_prefix: str,
  column_prefix: str,
) -> str:
  width = max(_MIN_WIDTH, 2 * _MARGIN + _ROW_HEADER + _COL_WIDTH * len(columns))
  root = _page(title, description, width, language)
  root.set("data-kind", "aspect-matrix")
  y = _text(root, title, _MARGIN, 24, width - 2 * _MARGIN, size=28)
  y = _text(root, description, _MARGIN, y, width - 2 * _MARGIN)
  y = _text(root, _LABELS[language]["branch"], _MARGIN, y, width - 2 * _MARGIN)
  count = max((len(hits) for hits in cells.values()), default=0)
  cell_height = max(42, 22 * count + 16)
  grid_y = y + 32
  grid_x = _MARGIN + _ROW_HEADER
  for column, (identity, _) in enumerate(columns):
    _node(
      root,
      "text",
      {
        "x": str(grid_x + column * _COL_WIDTH + _COL_WIDTH / 2),
        "y": str(grid_y - 12),
        "text-anchor": "middle",
        "font-size": "14",
        "data-role": "column-label",
        "data-identity": identity.value,
      },
      f"{column_prefix}{column + 1}",
    )
  for row, (identity, _) in enumerate(rows):
    _node(
      root,
      "text",
      {
        "x": str(grid_x - 12),
        "y": str(grid_y + row * cell_height + 26),
        "text-anchor": "end",
        "font-size": "14",
        "data-role": "row-label",
        "data-identity": identity.value,
      },
      f"{row_prefix}{row + 1}",
    )
    for column in range(len(columns)):
      x, top = grid_x + column * _COL_WIDTH, grid_y + row * cell_height
      enabled = (row, column) in cells
      group = _node(
        root,
        "g",
        {
          "data-role": "matrix-cell",
          "data-row": str(row),
          "data-column": str(column),
          "data-enabled": str(enabled).lower(),
          "data-box": f"{x} {top} {_COL_WIDTH} {cell_height}",
        },
      )
      _node(
        group,
        "rect",
        {
          "x": str(x),
          "y": str(top),
          "width": str(_COL_WIDTH),
          "height": str(cell_height),
          "fill": "#ffffff" if enabled else "#f1f4f6",
          "stroke": "#cbd4dc",
        },
      )
      for index, hit in enumerate(cells.get((row, column), ())):
        item = _node(group, "g", {"data-role": "matrix-hit", **_hit_attributes(hit)})
        _node(item, "title", text=_visible(_hit_text(hit, catalog, language)))
        _node(
          item,
          "text",
          {
            "x": str(x + _COL_WIDTH / 2),
            "y": str(top + 25 + index * 22),
            "font-size": "13",
            "text-anchor": "middle",
            "fill": _COLORS[hit.aspect],
          },
          _degree(hit.branch_deg, signed=True),
        )
  y = grid_y + len(rows) * cell_height + 14
  if not rows or not columns:
    y = _text(root, _LABELS[language]["no_objects"], _MARGIN, y, width - 2 * _MARGIN)
  if not any(cells.values()):
    y = _text(root, _LABELS[language]["no_hits"], _MARGIN, y, width - 2 * _MARGIN)
  for prefix, name, coordinates in keys:
    y = _object_key(root, coordinates, prefix, name, catalog, language, y, width)
  y = _text(root, _LABELS[language]["configuration"], _MARGIN, y + 12, width - 2 * _MARGIN, size=18)
  y = _lines(root, metadata, y, width)
  y = _text(root, _LABELS[language]["display"], _MARGIN, y + 12, width - 2 * _MARGIN)
  return _finish(root, y)


def render_natal_matrix(chart: NatalChart, catalog: Catalog, *, language: Language = "en") -> str:
  """Return the upper-triangle SVG matrix of all stored natal aspect hits.

  Rows are first objects and columns second objects, in effective.aspect_objects
  order, including participants with no hits. Every branch is shown; descriptions
  keep full stored deviations, limits and motion. Natural dimensions grow with
  participants, hits and object lists. No I/O or astronomy occurs. Exact input types are
  required; type/name/language/XML errors and font needs follow render_natal_wheel.

  返回全部已存本命相位的上三角 SVG 矩阵。行是第一对象，列是第二对象，按
  effective.aspect_objects 排列，保留没有命中的参与对象。逐条显示分支，描述保留完整的
  已存偏差、上限及运动。自然尺寸随对象、命中和对象列表增大。不执行 I/O 或天文计算；不接受
  输入类型的子类，类型、名称、语言、XML 错误及字体要求同 render_natal_wheel。
  """
  if type(chart) is not NatalChart:
    raise TypeError("chart must be a NatalChart")
  _inputs(catalog, language)
  labels = _LABELS[language]
  coordinates = _selected_longitudes(chart.positions, chart.houses, chart.effective.aspect_objects)
  indices = {identity: index for index, (identity, _) in enumerate(coordinates)}
  cells: dict[tuple[int, int], list[_Hit]] = {
    (row, column): []
    for row in range(len(coordinates))
    for column in range(row + 1, len(coordinates))
  }
  for hit in chart.aspects:
    cells[indices[hit.first], indices[hit.second]].append(hit)
  return _matrix(
    labels["natal"],
    labels["triangle"],
    coordinates,
    coordinates,
    cells,
    (("N", labels["objects"], coordinates),),
    [
      *_chart_lines(chart, catalog, language),
      *_rule_lines(chart.requested.aspects, chart.effective.orb_combination, catalog, language),
    ],
    catalog,
    language,
    row_prefix="N",
    column_prefix="N",
  )


def render_cross_matrix(
  comparison: CrossChartAspects, catalog: Catalog, *, language: Language = "en"
) -> str:
  """Return a static SVG matrix with left-chart rows and right-chart columns.

  Preserve recorded side orders (chart positions, then selected axes), empty
  selections and every hit/branch, not selection-argument order.
  Descriptions retain full stored deviations/limits; no motion is inferred or
  displayed. Both source house systems and the comparison's own rules are named.
  No I/O or astronomy occurs; natural dimensions grow with contents. Exact input
  types are required. Other errors and font needs follow render_natal_wheel.

  返回以左盘为行、右盘为列的静态 SVG 矩阵。按两侧已存位置、再按所选轴的顺序排列，
  不按选择参数的顺序排列。保留空选择及全部命中和分支；
  描述保留完整的已存偏差及上限，不推断或显示运动。说明两盘宫制和本次比较自己的规则。
  不执行 I/O 或天文计算，自然尺寸随内容增大；不接受输入类型的子类，其他错误及字体要求同
  render_natal_wheel。
  """
  if type(comparison) is not CrossChartAspects:
    raise TypeError("comparison must be a CrossChartAspects")
  _inputs(catalog, language)
  labels = _LABELS[language]
  left = _selected_longitudes(
    comparison.chart_left.positions, comparison.chart_left.houses, comparison.left_objects
  )
  right = _selected_longitudes(
    comparison.chart_right.positions, comparison.chart_right.houses, comparison.right_objects
  )
  left_indices = {identity: index for index, (identity, _) in enumerate(left)}
  right_indices = {identity: index for index, (identity, _) in enumerate(right)}
  cells: dict[tuple[int, int], list[_Hit]] = {
    (row, column): [] for row in range(len(left)) for column in range(len(right))
  }
  for hit in comparison.hits:
    cells[left_indices[hit.left_object], right_indices[hit.right_object]].append(hit)
  metadata = [
    labels["left"],
    *_chart_lines(comparison.chart_left, catalog, language),
    labels["right"],
    *_chart_lines(comparison.chart_right, catalog, language),
    *_rule_lines(comparison.rules, comparison.combination, catalog, language),
  ]
  return _matrix(
    labels["cross"],
    labels["rectangle"],
    left,
    right,
    cells,
    (("L", labels["left"], left), ("R", labels["right"], right)),
    metadata,
    catalog,
    language,
    row_prefix="L",
    column_prefix="R",
  )
