"""SVG geometry, record preservation and rendering boundaries. SVG 几何、记录保全与显示边界。"""

import json
import math
import os
import subprocess
import sys
import unicodedata
from collections.abc import Callable
from dataclasses import fields, replace
from itertools import pairwise
from typing import Any
from xml.etree import ElementTree as ET

import pytest

from astrology import (
  AspectRule,
  Axis,
  Body,
  Catalog,
  ChartConfig,
  HouseSystem,
  LunarNode,
  MajorAspect,
  NatalChart,
  ObjectOrb,
  OrbCombination,
  Sign,
  cross_chart_aspects,
  load_catalog,
  render_cross_matrix,
  render_natal_matrix,
  render_natal_wheel,
)
from astrology.chart import _aspects
from astrology.knowledge.records import Language
from tools.installed_check import (
  _cross_source,
  acceptance_cross_aspects,
  acceptance_svg_chart,
)

_SVG = "{http://www.w3.org/2000/svg}"
_RENDERERS: tuple[tuple[Callable[..., str], Callable[[], Any]], ...] = (
  (render_natal_wheel, acceptance_svg_chart),
  (render_natal_matrix, acceptance_svg_chart),
  (render_cross_matrix, acceptance_cross_aspects),
)


def _roles(root: ET.Element, role: str) -> list[ET.Element]:
  return root.findall(f".//*[@data-role='{role}']")


def _configured(source: NatalChart, *, orb: float = 180, objects: Any = None) -> NatalChart:
  config = ChartConfig(
    source.requested.house_system,
    source.requested.objects,
    tuple(AspectRule(aspect, orb) for aspect in MajorAspect),
    aspect_objects=objects,
  )
  return replace(
    source,
    requested=config,
    effective=replace(
      source.effective,
      aspect_objects=config.aspect_participants(),
      orb_combination=config.orb_combination,
    ),
    aspects=_aspects(source.positions, source.houses, config),
  )


def _catalog_name(catalog: Catalog, identity: str, name: str) -> Catalog:
  return replace(
    catalog,
    concepts=tuple(
      replace(c, name=replace(c.name, en=name, zh=name), en_aliases=(), zh_aliases=())
      if c.identifier == identity
      else c
      for c in catalog.concepts
    ),
  )


def _drawn_text(root: ET.Element) -> str:
  return "".join("".join(node.text or "" for node in root.iter(_SVG + "text")).split())


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("renderer,_factory", _RENDERERS)
def test_svg_metadata_keeps_configuration_and_rule_ownership(
  renderer: Callable[..., str], _factory: Callable[[], Any], language: Language
) -> None:
  left = acceptance_svg_chart()
  right = _cross_source(2001, "svg-right", ((Body.SUN, 40),), house_system=HouseSystem.EQUAL)
  comparison = cross_chart_aspects(
    left,
    right,
    (AspectRule(MajorAspect.SEXTILE, 7, (ObjectOrb(Body.SUN, 9),)),),
    combination=OrbCombination.MEAN_OF_ORBS,
  )
  catalog = load_catalog()
  root = ET.fromstring(
    renderer(comparison if renderer is render_cross_matrix else left, catalog, language=language)
  )
  drawn = _drawn_text(root)
  system, coordinates, times, models, combination = {
    "en": (
      "House system",
      "Zodiac / center / position frame",
      "JD(UT1) / JDE(TT)",
      "Delta-T model / astrology / celestial-calendar",
      "Orb combination",
    ),
    "zh-CN": (
      "宫制",
      "黄道 / 中心 / 位置坐标约定",
      "JD(UT1) / JDE(TT)",
      "ΔT 模型 / astrology / celestial-calendar",
      "容许度合成规则",
    ),
  }[language]
  sources = (left, right) if renderer is render_cross_matrix else (left,)
  for chart in sources:
    name = catalog.concept(f"house.{chart.effective.house_system.value}").name.text(language)
    expected = (
      f"{system}: {name}",
      f"{coordinates}: {chart.requested.zodiac} / {chart.requested.center} / {chart.provenance.position_frame}",
      f"{times}: {chart.times.jd_ut1} / {chart.times.jde_tt}",
      f"{models}: {chart.effective.delta_t_model} / {chart.provenance.astrology_version} / {chart.provenance.celestial_version}",
    )
    for fragment in expected:
      assert "".join(fragment.split()) in drawn
  aspect = MajorAspect.SEXTILE if renderer is render_cross_matrix else MajorAspect.CONJUNCTION
  name = catalog.concept(f"aspect.{aspect.value}").name.text(language)
  sun = catalog.concept("body.sun").name.text(language)
  base, override = (7, 9) if renderer is render_cross_matrix else (1, 3)
  assert "".join(f"{name}: {base}°; {sun}={override}°".split()) in drawn
  assert "".join(f"{combination}: mean_of_orbs".split()) in drawn
  if renderer is render_cross_matrix:
    assert "Conjunction:1°" not in drawn and "合相:1°" not in drawn


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_wheel_drawn_geometry_and_callout_ownership(language: Language) -> None:
  source = _cross_source(
    2000,
    "drawn-geometry",
    ((Body.SUN, 0), (Body.MOON, 90), (Body.MERCURY, 180), (Body.VENUS, 270)),
    axes=(0, 90, 180, 270),
    cusps_deg=(0, 20, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330),
  )
  chart = _configured(source, orb=0)
  root = ET.fromstring(render_natal_wheel(chart, load_catalog(), language=language))
  identities = [n.attrib["data-identity"] for n in _roles(root, "object-key")]
  for index, group in enumerate(_roles(root, "position"), start=1):
    assert group.attrib["data-identity"] == identities[index - 1]
    tick, leader = _roles(group, "position-tick")[0], _roles(group, "leader")[0]
    start, end = (tuple(map(float, pair.split(","))) for pair in leader.attrib["points"].split())
    assert start == (float(tick.attrib["x1"]), float(tick.attrib["y1"]))
    box, label = _roles(group, "callout-box")[0], _roles(group, "callout-label")[0]
    assert label.text == str(index)
    assert end == (float(box.attrib["x"]) + 16, float(box.attrib["y"]) + 11)
    assert float(label.attrib["x"]) == end[0]
  endpoints = {"sun": (334, 430), "moon": (500, 596), "mercury": (666, 430), "venus": (500, 264)}
  assert _roles(root, "aspect")
  for group in _roles(root, "aspect"):
    line = group.find(_SVG + "line")
    assert line is not None
    assert tuple(float(line.attrib[key]) for key in ("x1", "y1", "x2", "y2")) == pytest.approx(
      (*endpoints[group.attrib["data-first"]], *endpoints[group.attrib["data-second"]]), abs=1e-10
    )
  outer: dict[float, tuple[int, int]] = {
    0: (260, 430),
    90: (500, 670),
    180: (740, 430),
    270: (500, 190),
  }
  inner: dict[float, tuple[int, int]] = {
    0: (330, 430),
    90: (500, 600),
    180: (670, 430),
    270: (500, 260),
  }
  for axis in _roles(root, "axis"):
    assert (float(axis.attrib["x1"]), float(axis.attrib["y1"])) == (500, 430)
    assert (float(axis.attrib["x2"]), float(axis.attrib["y2"])) == pytest.approx(
      outer[float(axis.attrib["data-longitude"])], abs=1e-10
    )
  for cusp in _roles(root, "house-cusp"):
    longitude = float(cusp.attrib["data-longitude"])
    if longitude in outer:
      assert tuple(float(cusp.attrib[key]) for key in ("x1", "y1", "x2", "y2")) == pytest.approx(
        (*inner[longitude], *outer[longitude]), abs=1e-10
      )
  path = _roles(root, "zodiac-sector")[0].find(_SVG + "path")
  assert path is not None
  tokens = path.attrib["d"].split()
  commands = (0, 3, 11, 14, 22)
  assert [tokens[i] for i in commands] == ["M", "A", "L", "A", "Z"]
  assert [float(token) for i, token in enumerate(tokens) if i not in commands] == pytest.approx(
    [
      222,
      430,
      278,
      278,
      0,
      0,
      0,
      500 - 139 * math.sqrt(3),
      569,
      500 - 120 * math.sqrt(3),
      550,
      240,
      240,
      0,
      0,
      1,
      260,
      430,
    ],
    abs=1e-10,
  )


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_long_sign_names_have_correct_codes_and_complete_names(language: Language) -> None:
  catalog = load_catalog()
  names = [f"LongSign{index}" + "W" * 80 for index in range(1, 13)]
  for sign, name in zip(Sign, names, strict=True):
    catalog = _catalog_name(catalog, f"sign.{sign.value}", name)
  root = ET.fromstring(render_natal_wheel(acceptance_svg_chart(), catalog, language=language))
  assert [node.text for node in _roles(root, "sign-label")] == [
    f"S{index}" for index in range(1, 13)
  ]
  drawn = _drawn_text(root)
  for index, name in enumerate(names, start=1):
    assert f"S{index}·{name}" in drawn


@pytest.mark.parametrize(
  "name,expected", [("A" * 10, "A" * 10), ("A" * 11, "S1"), ("宽" * 5, "宽" * 5), ("宽" * 6, "S1")]
)
def test_sign_short_label_threshold(name: str, expected: str) -> None:
  catalog = _catalog_name(load_catalog(), "sign.aries", name)
  root = ET.fromstring(render_natal_wheel(acceptance_svg_chart(), catalog))
  assert _roles(root, "sign-label")[0].text == expected


@pytest.mark.parametrize("renderer,factory", _RENDERERS)
@pytest.mark.parametrize("catalog_subclass", [False, True])
def test_svg_rejects_exact_input_subclasses(
  renderer: Callable[..., str], factory: Callable[[], Any], catalog_subclass: bool
) -> None:
  value, catalog = factory(), load_catalog()
  original = catalog if catalog_subclass else value
  subclass = type("DerivedInput", (type(original),), {})
  derived = subclass(**{field.name: getattr(original, field.name) for field in fields(original)})
  with pytest.raises(TypeError):
    renderer(value, derived) if catalog_subclass else renderer(derived, catalog)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_bottom_cluster_uses_backward_callout_clamp(language: Language) -> None:
  chart = _cross_source(
    2000,
    "bottom-cluster",
    tuple((identity, 90) for identity in (*Body, *LunarNode)),
    axes=(0, 90, 90, 90),
  )
  root = ET.fromstring(render_natal_wheel(chart, load_catalog(), language=language))
  centers = sorted(float(node.attrib["y"]) + 11 for node in _roles(root, "callout-box"))
  assert len(centers) == 18 and centers[-1] == 686
  assert centers[0] >= 192
  assert all(right - left >= 26 for left, right in pairwise(centers))


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("columns,expected", [(12, 1000), (13, 1014), (18, 1354)])
def test_matrix_width_growth_uses_column_count(
  language: Language, columns: int, expected: int
) -> None:
  chart = acceptance_svg_chart()
  identities = (*chart.requested.objects, *Axis)
  chart = _configured(chart, orb=0, objects=identities[:columns])
  comparison = cross_chart_aspects(
    chart, chart, (), left_objects=(Body.SUN,), right_objects=identities[:columns]
  )
  catalog = load_catalog()
  for svg in (
    render_natal_matrix(chart, catalog, language=language),
    render_cross_matrix(comparison, catalog, language=language),
  ):
    root = ET.fromstring(svg)
    assert len(_roles(root, "column-label")) == columns
    assert int(root.attrib["width"]) == expected


@pytest.mark.parametrize(
  "language,empty,no_hits",
  [("en", "No selected objects", "No matching aspects"), ("zh-CN", "未选择对象", "无相位命中")],
)
def test_svg_empty_status_labels(language: Language, empty: str, no_hits: str) -> None:
  chart = _cross_source(2000, "status", ((Body.SUN, 13),))
  catalog = load_catalog()
  for svg in (
    render_natal_matrix(chart, catalog, language=language),
    render_cross_matrix(
      cross_chart_aspects(chart, chart, (), left_objects=(), right_objects=()),
      catalog,
      language=language,
    ),
  ):
    drawn = _drawn_text(ET.fromstring(svg))
    assert "".join(empty.split()) in drawn and "".join(no_hits.split()) in drawn
  assert "".join(no_hits.split()) in _drawn_text(
    ET.fromstring(render_natal_wheel(chart, catalog, language=language))
  )


@pytest.mark.parametrize("renderer,_factory", _RENDERERS)
@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize(
  "longitude,expected",
  [
    (0.0, "0°00\u203200″"),
    (1e-8, "0°00\u203200″"),
    (0.5, "0°30\u203200″"),
    (1.25, "1°15\u203200″"),
    (math.nextafter(30, 0), "29°59\u203259″"),
    (30.0, "30°00\u203200″"),
    (359.99994, "359°59\u203259″"),
    (math.nextafter(360, 0), "359°59\u203259″"),
  ],
)
def test_svg_longitude_text_never_crosses_a_boundary(
  renderer: Callable[..., str],
  _factory: Callable[[], Any],
  language: Language,
  longitude: float,
  expected: str,
) -> None:
  source = _cross_source(
    2000,
    "boundary",
    ((Body.SUN, longitude),),
    cusps_deg=tuple((longitude + index * 30) % 360 for index in range(12)),
  )
  chart = _configured(source, orb=0, objects=(Body.SUN,))
  value = cross_chart_aspects(chart, chart, ()) if renderer is render_cross_matrix else chart
  root = ET.fromstring(renderer(value, load_catalog(), language=language))
  key = next(node for node in _roles(root, "object-key") if node.get("data-identity") == "sun")
  assert key.attrib["data-longitude"] == str(longitude)
  assert expected in _drawn_text(key)
  if renderer is render_natal_wheel:
    assert f"1:{expected}" in _drawn_text(_roles(root, "house-key")[0])


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_wheel_uses_independent_cardinals_unrounded_anchors_and_actual_cusps(
  language: Language,
) -> None:
  source = _cross_source(
    2000,
    "geometry",
    (
      (Body.SUN, 10),
      (Body.MOON, 100),
      (Body.MERCURY, 190),
      (Body.VENUS, 280),
      (Body.MARS, 359.99994),
      (Body.JUPITER, 0.00003),
    ),
    axes=(10, 111, 204, 291),
    cusps_deg=(20, 42, 70, 110, 140, 170, 200, 222, 250, 290, 320, 350),
  )
  root = ET.fromstring(render_natal_wheel(source, load_catalog(), language=language))
  positions = {n.get("data-identity"): n for n in _roles(root, "position")}
  for identity, expected in (
    ("sun", (275, 430)),
    ("moon", (500, 655)),
    ("mercury", (725, 430)),
    ("venus", (500, 205)),
  ):
    tick = _roles(positions[identity], "position-tick")[0]
    assert (float(tick.attrib["x1"]), float(tick.attrib["y1"])) == pytest.approx(
      expected, abs=1e-10
    )
  for identity, longitude in (("mars", 359.99994), ("jupiter", 0.00003)):
    tick = _roles(positions[identity], "position-tick")[0]
    x, y = float(tick.attrib["x1"]), float(tick.attrib["y1"])
    recovered = (math.degrees(math.atan2(430 - y, x - 500)) - 180 + 10) % 360
    assert recovered == pytest.approx(longitude, abs=1e-11)
  cusps = _roles(root, "house-cusp")
  assert tuple(float(n.attrib["data-longitude"]) for n in cusps) == source.houses.cusps_deg
  assert len(_roles(root, "zodiac-sector")) == 12
  axes = _roles(root, "axis")
  assert [float(n.attrib["data-longitude"]) for n in axes] == [10, 111, 204, 291]
  assert axes[1].get("y2") != "190"
  assert [n.get("data-identity") for n in _roles(root, "position")] == [
    *(p.identity.value for p in source.positions),
    *(a.value for a in Axis),
  ]


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_wheel_and_natal_matrix_keep_every_hit_branch_motion_and_selected_order(
  language: Language,
) -> None:
  source = _cross_source(2000, "hits", ((Body.MOON, 359.95), (Body.SUN, 0.05), (Body.VENUS, 80)))
  chart = _configured(source, objects=(Axis.MIDHEAVEN, Body.SUN, Body.MOON, Axis.ASCENDANT))
  expected_order = ["moon", "sun", "ascendant", "midheaven"]
  catalog = load_catalog()
  wheel = ET.fromstring(render_natal_wheel(chart, catalog, language=language))
  matrix = ET.fromstring(render_natal_matrix(chart, catalog, language=language))
  assert [n.get("data-identity") for n in _roles(matrix, "row-label")] == expected_order
  assert [n.get("data-identity") for n in _roles(matrix, "column-label")] == expected_order
  assert len(_roles(wheel, "position")) == 7
  for root, role in ((wheel, "aspect"), (matrix, "matrix-hit")):
    observed = [
      tuple(
        n.attrib[key]
        for key in (
          "data-first",
          "data-second",
          "data-aspect",
          "data-branch",
          "data-deviation",
          "data-orb-limit",
          "data-motion",
        )
      )
      for n in _roles(root, role)
    ]
    assert observed == [
      (
        h.first.value,
        h.second.value,
        h.aspect.value,
        str(h.branch_deg),
        str(h.deviation_deg),
        str(h.orb_limit_deg),
        h.motion.value,
      )
      for h in chart.aspects
    ]
  for cell in _roles(matrix, "matrix-cell"):
    row, column = int(cell.attrib["data-row"]), int(cell.attrib["data-column"])
    assert (cell.get("data-enabled") == "true") is (row < column)
    for hit in _roles(cell, "matrix-hit"):
      assert (hit.get("data-first"), hit.get("data-second")) == (
        expected_order[row],
        expected_order[column],
      )
  assert {h.branch_deg for h in chart.aspects} >= {-120, 120, -90, 90}


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("reverse", [False, True])
def test_cross_matrix_preserves_owners_orders_and_all_broad_orb_branches(
  language: Language, reverse: bool
) -> None:
  left = _cross_source(
    2000, "left", ((Body.MOON, 359.95), (Body.SUN, 0.05), (LunarNode.MEAN_ASCENDING, 90))
  )
  right = _cross_source(
    2001, "right", ((Body.SUN, 0.05), (LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING, 90))
  )
  if reverse:
    left, right = right, left
  result = cross_chart_aspects(
    left,
    right,
    tuple(AspectRule(a, 180) for a in MajorAspect),
    left_objects=(*reversed(left.requested.objects), Axis.MIDHEAVEN),
  )
  root = ET.fromstring(render_cross_matrix(result, load_catalog(), language=language))
  assert [n.get("data-identity") for n in _roles(root, "row-label")] == [
    i.value for i in result.left_objects
  ]
  assert [n.get("data-identity") for n in _roles(root, "column-label")] == [
    i.value for i in result.right_objects
  ]
  hits = _roles(root, "matrix-hit")
  assert len(hits) == len(result.hits)
  assert [
    (n.get("data-first"), n.get("data-second"), float(n.attrib["data-branch"])) for n in hits
  ] == [(h.left_object.value, h.right_object.value, h.branch_deg) for h in result.hits]
  assert not any("data-motion" in n.attrib for n in root.iter())
  assert (
    len([h for h in result.hits if h.left_object is Body.SUN and h.right_object is Body.SUN]) > 1
  )
  assert any(
    isinstance(h.left_object, LunarNode) and isinstance(h.right_object, LunarNode)
    for h in result.hits
  )
  assert {n.get("data-prefix") for n in _roles(root, "object-key")} == {"L", "R"}


def test_empty_selections_rules_and_nonempty_no_hit_participants() -> None:
  source = _cross_source(2000, "empty", ((Body.SUN, 13), (Body.MOON, 26)))
  chart = _configured(source, orb=0)
  assert not chart.aspects
  root = ET.fromstring(render_natal_matrix(chart, load_catalog()))
  assert len(_roles(root, "row-label")) == 2
  assert not _roles(root, "matrix-hit")
  assert "Conjunction" in "".join(root.itertext())
  assert not _roles(ET.fromstring(render_natal_matrix(source, load_catalog())), "row-label")
  for left, right in (((), (Body.SUN,)), ((Body.SUN,), ()), ((), ())):
    result = cross_chart_aspects(source, source, (), left_objects=left, right_objects=right)
    root = ET.fromstring(render_cross_matrix(result, load_catalog()))
    assert len(_roles(root, "row-label")) == len(left)
    assert len(_roles(root, "column-label")) == len(right)


@pytest.mark.parametrize("renderer,factory", _RENDERERS)
@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_svg_is_accessible_deterministic_and_does_not_mutate_inputs(
  renderer: Callable[..., str], factory: Callable[[], Any], language: Language
) -> None:
  value, catalog = factory(), load_catalog()
  before = repr((value, catalog))
  text = renderer(value, catalog, language=language)
  assert renderer(value, catalog, language=language) == text
  assert repr((value, catalog)) == before
  root = ET.fromstring(text)
  assert root.tag == _SVG + "svg"
  assert root.get("role") == "img"
  assert root.get("{http://www.w3.org/XML/1998/namespace}lang") == language
  assert root.find(_SVG + "title") is not None and root.find(_SVG + "desc") is not None
  assert root.attrib["font-family"].endswith(", sans-serif")
  assert all(
    n.tag not in {_SVG + tag for tag in ("script", "image", "foreignObject", "style")}
    for n in root.iter()
  )
  assert not any("href" in key or key.startswith("on") for n in root.iter() for key in n.attrib)
  assert "source" not in text and '"side"' not in text


@pytest.mark.parametrize("renderer,factory", _RENDERERS)
@pytest.mark.parametrize("bad", [None, True, "fr", ["en"]])
def test_renderers_reject_wrong_inputs_and_languages(
  renderer: Callable[..., str], factory: Callable[[], Any], bad: Any
) -> None:
  with pytest.raises(TypeError):
    renderer(None, load_catalog())
  with pytest.raises(TypeError):
    renderer(factory(), None)
  with pytest.raises(ValueError, match="language"):
    renderer(factory(), load_catalog(), language=bad)


@pytest.mark.parametrize("renderer,factory", _RENDERERS)
@pytest.mark.parametrize("character", ["\x00", "\x01", "\x1f", "\ud800", "\ufffe", "\uffff"])
def test_xml_invalid_catalog_text_is_rejected_before_visible_escaping(
  renderer: Callable[..., str], factory: Callable[[], Any], character: str
) -> None:
  catalog = _catalog_name(load_catalog(), "body.sun", "Bad" + character)
  with pytest.raises(ValueError, match=r"XML 1\.0 invalid"):
    renderer(factory(), catalog)


@pytest.mark.parametrize("renderer,factory", _RENDERERS)
def test_xml_special_text_round_trips_without_injection_or_table_escaping(
  renderer: Callable[..., str], factory: Callable[[], Any]
) -> None:
  payload = """Sun <script a="'&"> | back\\slash\n\t\r\u0085\u2028"""
  root = ET.fromstring(renderer(factory(), _catalog_name(load_catalog(), "body.sun", payload)))
  names = [n.attrib["data-name"] for n in root.iter() if "data-name" in n.attrib]
  assert payload in names
  assert not root.findall(".//" + _SVG + "script")
  assert r"\n\t\r\x85\u2028" in "".join(root.itertext())
  assert r"\|" not in "".join(root.itertext())


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_every_node_identity_and_definition_is_visible_in_the_key(language: Language) -> None:
  catalog = load_catalog()
  root = ET.fromstring(render_natal_wheel(acceptance_svg_chart(), catalog, language=language))
  for node in LunarNode:
    key = next(n for n in _roles(root, "object-key") if n.get("data-identity") == node.value)
    for identity in (node, node.definition):
      concept = next(c for c in catalog.concepts if c.configuration is identity)
      name = concept.name.text(language)
      assert name is not None and name in "".join(key.itertext())
  assert not any(
    isinstance(h.first, LunarNode) and isinstance(h.second, LunarNode)
    for h in acceptance_svg_chart().aspects
  )


@pytest.mark.parametrize(
  "identity",
  [
    "node_definition.mean",
    "node_definition.meeus_five_term_true",
    "body.sun",
    "aspect.sextile",
    "house.placidus",
  ],
)
@pytest.mark.parametrize("defect", ["stale", "missing", "ambiguous"])
def test_required_vocabulary_fails_even_when_no_hit_uses_it(identity: str, defect: str) -> None:
  catalog = load_catalog()
  concept = catalog.concept(identity)
  if defect == "stale":
    changed = replace(concept, name=replace(concept.name, revision=concept.name.revision + 1))
  elif defect == "missing":
    changed = replace(
      concept, name=replace(concept.name, zh=None, zh_revision=None, translation_credit=None)
    )
  else:
    changed = replace(
      concept,
      identifier="custom.ambiguous",
      name=replace(concept.name, en="Distinct", zh="另名"),
      en_aliases=(),
      zh_aliases=(),
    )
  concepts = tuple(
    changed if c is concept and defect != "ambiguous" else c for c in catalog.concepts
  )
  if defect == "ambiguous":
    concepts += (changed,)
  supplied = replace(catalog, concepts=concepts)
  with pytest.raises(ValueError):
    render_natal_wheel(acceptance_svg_chart(), supplied, language="zh-CN")


def test_missing_sign_and_unselected_names_have_distinct_contracts() -> None:
  catalog = load_catalog()
  sparse = _cross_source(2000, "sparse", ((Body.SUN, 0),))
  changed = _catalog_name(catalog, "body.pluto", "Bad\x01")
  assert render_natal_wheel(sparse, changed)
  minimal = replace(
    catalog,
    concepts=tuple(
      replace(c, related=()) for c in catalog.concepts if c.identifier != "sign.aries"
    ),
    variants=(),
    entries=(),
  )
  with pytest.raises(KeyError, match=r"sign\.aries"):
    render_natal_wheel(sparse, minimal)


@pytest.mark.parametrize("renderer,factory", _RENDERERS)
def test_string_subclass_language_and_invalid_chart_labels_fail(
  renderer: Callable[..., str], factory: Callable[[], Any]
) -> None:
  class Label(str):
    pass

  value = factory()
  with pytest.raises(ValueError, match="language"):
    renderer(value, load_catalog(), language=Label("en"))
  chart = value.chart_left if renderer is render_cross_matrix else value
  chart = replace(chart, provenance=replace(chart.provenance, astrology_version="bad\x01"))
  value = replace(value, chart_left=chart) if renderer is render_cross_matrix else chart
  with pytest.raises(ValueError, match=r"XML 1\.0 invalid"):
    renderer(value, load_catalog())


def test_long_unbroken_names_wrap_instead_of_overflowing() -> None:
  catalog = _catalog_name(load_catalog(), "body.sun", "W" * 250)
  root = ET.fromstring(render_natal_wheel(acceptance_svg_chart(), catalog))
  key = next(n for n in _roles(root, "object-key") if n.get("data-identity") == "sun")
  assert len(key.findall(".//" + _SVG + "text")) > 3
  assert "W" * 250 in "".join(key.itertext())


def test_crowded_house_numbers_use_the_complete_cusp_key() -> None:
  cusps = tuple(20 + index * 0.00001 for index in range(12))
  chart = _cross_source(2000, "cusps", ((Body.SUN, 0),), cusps_deg=cusps)
  root = ET.fromstring(render_natal_wheel(chart, load_catalog()))
  numbers = _roles(root, "house-number")
  assert 0 < len(numbers) < 12
  for i, a in enumerate(numbers):
    for b in numbers[i + 1 :]:
      assert (
        abs(float(a.attrib["x"]) - float(b.attrib["x"])) >= 24
        or abs(float(a.attrib["y"]) - float(b.attrib["y"])) >= 20
      )
  assert len(_roles(root, "house-cusp")) == 12
  key = "".join(_roles(root, "house-key")[0].itertext())
  assert all(f"{index}:" in key for index in range(1, 13))


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_recurring_layout_bounds_separation_and_expansion(language: Language) -> None:
  source = _cross_source(
    2000,
    "dense",
    tuple((identity, 359.95 + index * 0.00001) for index, identity in enumerate(Body)),
  )
  chart = _configured(source)
  catalog = load_catalog()
  catalog = replace(
    catalog,
    concepts=tuple(
      replace(
        c,
        name=replace(c.name, en="Long 重复名 " * 50, zh="Long 重复名 " * 50),
        en_aliases=(),
        zh_aliases=(),
      )
      for c in catalog.concepts
    ),
  )
  outputs = [
    render_natal_wheel(chart, catalog, language=language),
    render_natal_matrix(chart, catalog, language=language),
    render_cross_matrix(
      cross_chart_aspects(chart, chart, tuple(AspectRule(a, 180) for a in MajorAspect)),
      catalog,
      language=language,
    ),
  ]
  for output in outputs:
    root = ET.fromstring(output)
    width, height = float(root.attrib["width"]), float(root.attrib["height"])
    assert list(map(float, root.attrib["viewBox"].split())) == [0, 0, width, height]
    blocks = root.findall(".//*[@data-box]")
    for block in blocks:
      x, y, w, h = map(float, block.attrib["data-box"].split())
      assert 0 <= x < x + w <= width
      assert 0 <= y < y + h <= height
      if block.get("data-role") == "label":
        for text in block.findall(_SVG + "text"):
          units = sum(
            2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text.text or ""
          )
          assert units * int(text.attrib["font-size"]) <= w
    callouts = _roles(root, "callout-box")
    for callout in callouts:
      x, y = float(callout.attrib["x"]), float(callout.attrib["y"])
      assert 0 <= x < x + float(callout.attrib["width"]) <= width
      assert 0 <= y < y + float(callout.attrib["height"]) <= height
    for i, a in enumerate(callouts):
      for b in callouts[i + 1 :]:
        assert (
          abs(float(a.attrib["x"]) - float(b.attrib["x"])) >= 32
          or abs(float(a.attrib["y"]) - float(b.attrib["y"])) >= 26
        )
    labels = [n for n in blocks if n.get("data-role") == "label"]
    for a, b in pairwise(labels):
      _, y, _, h = map(float, a.attrib["data-box"].split())
      assert y + h <= float(b.attrib["data-box"].split()[1])
    assert height > 1500


@pytest.mark.parametrize("mode", [(), ("-O",)])
@pytest.mark.parametrize("encoding", ["utf-8", "cp1252"])
def test_fresh_process_determinism_and_effect_boundaries(
  mode: tuple[str, ...], encoding: str
) -> None:
  script = """
import builtins, io, importlib.metadata as metadata, socket, json
import astrology, astrology.chart as chart, astrology.birth as birth
import astrology.knowledge.catalog as catalog_module
from tools.installed_check import acceptance_svg_chart, acceptance_cross_aspects
source, cross, catalog = acceptance_svg_chart(), acceptance_cross_aspects(), astrology.load_catalog()
original_import = builtins.__import__
def forbidden(*args, **kwargs):
  raise RuntimeError('Renderer crossed effect boundary')
def guarded(name, *args, **kwargs):
  if name == 'astrology.celestial' or name.startswith(('celestial_calendar','tzdata','zoneinfo')):
    forbidden()
  return original_import(name, *args, **kwargs)
builtins.__import__ = guarded
builtins.open = io.open = socket.socket = forbidden
metadata.version = metadata.distribution = forbidden
astrology.load_catalog = catalog_module.load_catalog = catalog_module.files = forbidden
astrology.natal_chart = chart.natal_chart = chart._aspects = forbidden
birth.resolve_birth_time = birth.prepare_natal_input = forbidden
for language in ('en','zh-CN'):
  for renderer, value in ((astrology.render_natal_wheel,source),(astrology.render_natal_matrix,source),(astrology.render_cross_matrix,cross)):
    print(json.dumps(renderer(value,catalog,language=language), ensure_ascii=True))
"""
  outputs = [
    subprocess.run(
      [sys.executable, *mode, "-c", script],
      check=True,
      capture_output=True,
      env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": encoding},
      text=True,
    ).stdout
    for seed in ("1", "73")
  ]
  assert outputs[0] == outputs[1]
  assert len(outputs[0].splitlines()) == 6
  assert all(
    ET.fromstring(json.loads(line)).tag == _SVG + "svg" for line in outputs[0].splitlines()
  )
