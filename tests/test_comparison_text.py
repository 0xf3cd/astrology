"""Bilingual comparison output, preserved static geometry and explicit effect boundaries.

双语比较输出、静态几何保全及显式副作用边界。
"""

import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from astrology import (
  AspectRule,
  Axis,
  Body,
  Catalog,
  MajorAspect,
  ObjectOrb,
  OrbCombination,
  cross_chart_aspects,
  cross_chart_house_overlays,
  format_cross_aspects,
  format_house_overlays,
  load_catalog,
)
from astrology.knowledge.records import Language
from tools.installed_check import (
  _cross_source,
  acceptance_cross_aspects,
  acceptance_house_overlays,
)


@pytest.mark.parametrize(
  "language,left,right,sun,venus",
  [
    ("en", "Left", "Right", "Sun", "Venus"),
    ("zh-CN", "左盘", "右盘", "太阳", "金星"),
  ],
)
def test_overlay_text_shows_both_ownership_directions_and_source_systems(
  language: Language, left: str, right: str, sun: str, venus: str
) -> None:
  result = acceptance_house_overlays()
  before = repr(result)
  output = format_house_overlays(result, load_catalog(), language=language)
  assert f"{left} | {sun} [sun] | {right} | 1" in output.splitlines()
  assert f"{left} | {venus} [venus] | {right} | 7" in output.splitlines()
  assert f"{right} | {sun} [sun] | {left} | 12" in output.splitlines()
  assert f"{right} | {venus} [venus] | {left} | 1" in output.splitlines()
  assert ("Whole Sign" if language == "en" else "整宫制") in output
  assert ("Equal" if language == "en" else "等宫制") in output
  assert "synthetic-left / synthetic-left" in output
  assert "synthetic-right / synthetic-right" in output
  assert "JD(UT1) / JDE(TT)" in output
  assert repr(result) == before


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_static_text_keeps_all_overlapping_aspects_and_both_oriented_branches(
  language: Language,
) -> None:
  chart = _cross_source(2000, "same", ((Body.SUN, 0),))
  result = cross_chart_aspects(chart, chart, tuple(AspectRule(a, 180) for a in MajorAspect))
  before = repr(result)
  output = format_cross_aspects(result, load_catalog(), language=language)
  rows = [line for line in output.splitlines() if "[sun] |" in line]
  assert len(rows) == len(result.hits) == 8
  assert [row.split(" | ")[3] for row in rows] == [
    "0°00'00\"",
    "-60°00'00\"",
    "+60°00'00\"",
    "-90°00'00\"",
    "+90°00'00\"",
    "-120°00'00\"",
    "+120°00'00\"",
    "+180°00'00\"",
  ]
  assert all(row.endswith("180°00'00\"") for row in rows)
  assert not any(
    label in output.lower()
    for label in (
      "applying",
      "separating",
      "stationary",
      "indeterminate",
      "入相",
      "离相",
      "无法确定",
    )
  )
  assert repr(result) == before


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_static_text_distinguishes_rule_base_overrides_combination_and_effective_limit(
  language: Language,
) -> None:
  left = _cross_source(2000, "left", ((Body.SUN, 0),))
  right = _cross_source(2001, "right", ((Body.MOON, 58),))
  rule = AspectRule(MajorAspect.SEXTILE, 4, (ObjectOrb(Body.SUN, 8), ObjectOrb(Body.MOON, 2)))
  result = cross_chart_aspects(left, right, (rule,), combination=OrbCombination.MEAN_OF_ORBS)
  output = format_cross_aspects(result, load_catalog(), language=language)
  row = next(line for line in output.splitlines() if "[sun] |" in line)
  assert row.endswith(" | -2°00'00\" | 5°00'00\"")
  assert " / 4°00'00\" / " in output
  assert "=8°00'00\"" in output and "=2°00'00\"" in output
  assert "mean_of_orbs" in output


@pytest.mark.parametrize("kind", ["overlays", "aspects"])
@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize(
  "left_empty,right_empty", [(False, False), (True, False), (False, True), (True, True)]
)
def test_effective_selection_lines_keep_each_side_and_empty_meaning(
  kind: str, language: Language, left_empty: bool, right_empty: bool
) -> None:
  left = _cross_source(2000, "left", ((Body.SUN, 0), (Body.VENUS, 215)))
  right = _cross_source(2001, "right", ((Body.MOON, 10), (Body.VENUS, 60)))
  selected_left = () if left_empty else (Body.VENUS, Body.SUN)
  selected_right = () if right_empty else (Body.MOON,)
  if kind == "overlays":
    output = format_house_overlays(
      cross_chart_house_overlays(
        left, right, left_objects=selected_left, right_objects=selected_right
      ),
      load_catalog(),
      language=language,
    )
  else:
    output = format_cross_aspects(
      cross_chart_aspects(
        left, right, (), left_objects=selected_left, right_objects=selected_right
      ),
      load_catalog(),
      language=language,
    )
  if language == "en":
    expected_left = "Left selected objects: " + (
      "No objects" if left_empty else "Sun [sun], Venus [venus]"
    )
    expected_right = "Right selected objects: " + ("No objects" if right_empty else "Moon [moon]")
  else:
    expected_left = "左盘所选对象: " + ("无" if left_empty else "太阳 [sun], 金星 [venus]")
    expected_right = "右盘所选对象: " + ("无" if right_empty else "月亮 [moon]")
  lines = output.splitlines()
  assert lines.count(expected_left) == lines.count(expected_right) == 1


def test_zero_display_deviation_does_not_remove_a_static_row() -> None:
  left = _cross_source(2000, "left", ((Body.SUN, 0),))
  right = _cross_source(2001, "right", ((Body.SUN, 0.0001),))
  result = cross_chart_aspects(left, right, (AspectRule(MajorAspect.CONJUNCTION, 1),))
  output = format_cross_aspects(result, load_catalog())
  assert len(result.hits) == 1 and result.hits[0].deviation_deg != 0
  assert "0°00'00\" | 0°00'00\" | 1°00'00\"" in output


@pytest.mark.parametrize("language,none", [("en", "None"), ("zh-CN", "无")])
def test_empty_comparisons_show_selections_and_explicit_rules(
  language: Language, none: str
) -> None:
  source = acceptance_house_overlays()
  catalog = load_catalog()
  overlays = cross_chart_house_overlays(
    source.chart_left, source.chart_right, left_objects=(), right_objects=()
  )
  overlay_text = format_house_overlays(overlays, catalog, language=language)
  assert overlay_text.splitlines()[-1] == none
  rule = AspectRule(MajorAspect.SQUARE, 3)
  aspects = cross_chart_aspects(
    source.chart_left, source.chart_right, (rule,), left_objects=(), right_objects=()
  )
  aspect_text = format_cross_aspects(aspects, catalog, language=language)
  assert none in aspect_text.splitlines()
  assert " / 3°00'00\" / " in aspect_text
  no_rules = cross_chart_aspects(source.chart_left, source.chart_right, ())
  assert (
    "Aspect rule / base orb / object overrides: None"
    if language == "en"
    else "相位规则 / 基础容许度 / 对象单独设置: 无"
  ) in format_cross_aspects(no_rules, catalog, language=language)


@pytest.mark.parametrize(
  "formatter,factory",
  [
    (format_house_overlays, acceptance_house_overlays),
    (format_cross_aspects, acceptance_cross_aspects),
  ],
)
@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_missing_catalog_bindings_are_not_replaced_with_builtin_names(
  formatter: Callable[..., str], factory: Callable[[], Any], language: Language
) -> None:
  with pytest.raises(ValueError, match="Expected one catalog concept"):
    formatter(factory(), Catalog("empty", (), (), (), ()), language=language)


@pytest.mark.parametrize(
  "formatter,factory",
  [
    (format_house_overlays, acceptance_house_overlays),
    (format_cross_aspects, acceptance_cross_aspects),
  ],
)
@pytest.mark.parametrize("defect", ["missing-zh", "stale-zh", "ambiguous"])
def test_required_object_translation_failures_do_not_fall_back(
  formatter: Callable[..., str], factory: Callable[[], Any], defect: str
) -> None:
  catalog = load_catalog()
  sun = catalog.concept("body.sun")
  if defect == "ambiguous":
    changed = replace(sun, identifier="body.other_sun", en_aliases=(), zh_aliases=())
    concepts = (*catalog.concepts, changed)
  else:
    name = (
      replace(sun.name, zh=None, zh_revision=None, translation_credit=None)
      if defect == "missing-zh"
      else replace(sun.name, revision=sun.name.revision + 1)
    )
    changed = replace(sun, name=name)
    concepts = tuple(changed if c is sun else c for c in catalog.concepts)
  supplied = replace(catalog, concepts=concepts)
  with pytest.raises(ValueError, match=r"catalog concept|Missing or stale"):
    formatter(factory(), supplied, language="zh-CN")


@pytest.mark.parametrize("formatter", [format_house_overlays, format_cross_aspects])
@pytest.mark.parametrize("concept_id", ["axis.ascendant", "house.equal"])
def test_axes_and_house_systems_require_current_translations(
  formatter: Callable[..., str], concept_id: str
) -> None:
  overlays = acceptance_house_overlays()
  result: Any = (
    overlays
    if formatter is format_house_overlays
    else cross_chart_aspects(
      overlays.chart_left,
      overlays.chart_right,
      (),
      left_objects=(Axis.ASCENDANT,),
      right_objects=(),
    )
  )
  catalog = load_catalog()
  concept = catalog.concept(concept_id)
  changed = replace(concept, name=replace(concept.name, revision=concept.name.revision + 1))
  supplied = replace(
    catalog, concepts=tuple(changed if c is concept else c for c in catalog.concepts)
  )
  with pytest.raises(ValueError, match="Missing or stale"):
    formatter(result, supplied, language="zh-CN")


def test_rule_translation_is_required_even_when_no_aspect_matches() -> None:
  overlays = acceptance_house_overlays()
  result = cross_chart_aspects(
    overlays.chart_left,
    overlays.chart_right,
    (AspectRule(MajorAspect.SEXTILE, 0),),
    left_objects=(Axis.ASCENDANT,),
    right_objects=(),
  )
  catalog = load_catalog()
  concept = catalog.concept("aspect.sextile")
  changed = replace(concept, name=replace(concept.name, revision=concept.name.revision + 1))
  supplied = replace(
    catalog, concepts=tuple(changed if c is concept else c for c in catalog.concepts)
  )
  with pytest.raises(ValueError, match="Missing or stale"):
    format_cross_aspects(result, supplied, language="zh-CN")


@pytest.mark.parametrize(
  "formatter,factory",
  [
    (format_house_overlays, acceptance_house_overlays),
    (format_cross_aspects, acceptance_cross_aspects),
  ],
)
def test_supplied_names_are_used_and_unselected_names_are_not_required(
  formatter: Callable[..., str], factory: Callable[[], Any]
) -> None:
  catalog = load_catalog()
  sun = catalog.concept("body.sun")
  pluto = catalog.concept("body.pluto")
  supplied = replace(
    catalog,
    concepts=tuple(
      replace(c, name=replace(c.name, en="Caller Sun"))
      if c is sun
      else replace(c, name=replace(c.name, revision=c.name.revision + 1))
      if c is pluto
      else c
      for c in catalog.concepts
    ),
  )
  assert "Caller Sun [sun]" in formatter(factory(), supplied)
  assert formatter(factory(), supplied, language="zh-CN")


@pytest.mark.parametrize(
  "formatter,factory",
  [
    (format_house_overlays, acceptance_house_overlays),
    (format_cross_aspects, acceptance_cross_aspects),
  ],
)
@pytest.mark.parametrize("bad", [None, "fr", True, ["en"]])
def test_invalid_formatter_language(
  formatter: Callable[..., str], factory: Callable[[], Any], bad: object
) -> None:
  with pytest.raises(ValueError, match="language"):
    formatter(factory(), load_catalog(), language=bad)


@pytest.mark.parametrize(
  "formatter,factory",
  [
    (format_house_overlays, acceptance_house_overlays),
    (format_cross_aspects, acceptance_cross_aspects),
  ],
)
def test_wrong_formatter_inputs_and_string_subclass_language(
  formatter: Callable[..., str], factory: Callable[[], Any]
) -> None:
  class Label(str):
    pass

  with pytest.raises(TypeError):
    formatter(None, load_catalog())
  with pytest.raises(TypeError):
    formatter(factory(), None)
  with pytest.raises(ValueError, match="language"):
    formatter(factory(), load_catalog(), language=Label("en"))


@pytest.mark.parametrize(
  "formatter,factory",
  [
    (format_house_overlays, acceptance_house_overlays),
    (format_cross_aspects, acceptance_cross_aspects),
  ],
)
@pytest.mark.parametrize("field", ["delta_t_model", "astrology_version", "celestial_version"])
def test_source_labels_cannot_forge_comparison_rows(
  formatter: Callable[..., str], factory: Callable[[], Any], field: str
) -> None:
  result = factory()
  payload = "foreign\\value|column\nFAKE ROW\r\u0085\u2028\u2029\x1b[2J"
  chart = result.chart_right
  if field == "delta_t_model":
    chart = replace(chart, effective=replace(chart.effective, delta_t_model=payload))
  else:
    chart = replace(chart, provenance=replace(chart.provenance, **{field: payload}))
  changed = replace(result, chart_right=chart)
  catalog = load_catalog()
  baseline = formatter(result, catalog)
  output = formatter(changed, catalog)
  assert len(output.splitlines()) == len(baseline.splitlines())
  assert r"foreign\\value\|column\nFAKE ROW\r\x85\u2028\u2029\x1b[2J" in output
  assert "FAKE ROW" not in output.splitlines()


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_supplied_comparisons_and_text_block_effects_after_inputs_are_ready(
  mode: tuple[str, ...],
) -> None:
  source = """
import builtins
import io
import importlib.metadata as metadata
import astrology
import astrology.birth as birth
import astrology.chart as chart
import astrology._distribution as distribution
import astrology.knowledge.catalog as catalog_module
from tools.installed_check import acceptance_house_overlays, acceptance_cross_aspects
overlays = acceptance_house_overlays()
aspects = acceptance_cross_aspects()
catalog = astrology.load_catalog()
original_import = builtins.__import__
def forbidden(*args, **kwargs):
  raise RuntimeError('Supplied comparison crossed an effectful boundary')
def guarded(name, *args, **kwargs):
  if name == 'astrology.celestial' or name.startswith(('celestial_calendar', 'tzdata', 'zoneinfo')):
    forbidden()
  return original_import(name, *args, **kwargs)
builtins.__import__ = guarded
builtins.open = io.open = forbidden
metadata.version = metadata.distribution = distribution.distribution = forbidden
astrology.load_catalog = catalog_module.load_catalog = catalog_module.files = forbidden
astrology.natal_chart = chart.natal_chart = forbidden
astrology.prepare_natal_input = birth.prepare_natal_input = birth.resolve_birth_time = forbidden
again = astrology.cross_chart_house_overlays(overlays.chart_left, overlays.chart_right,
  left_objects=overlays.left_objects, right_objects=overlays.right_objects)
if again != overlays:
  raise RuntimeError('Supplied geometry changed')
for language in ('en', 'zh-CN'):
  if not astrology.format_house_overlays(again, catalog, language=language):
    raise RuntimeError('Empty overlay output')
  if not astrology.format_cross_aspects(aspects, catalog, language=language):
    raise RuntimeError('Empty aspect output')
try:
  astrology.HouseOverlay('left', 'right', astrology.Body.SUN, True)
except TypeError:
  pass
else:
  raise RuntimeError('Optimized mode lost house validation')
"""
  completed = subprocess.run([sys.executable, *mode, "-c", source], capture_output=True, text=True)
  assert completed.returncode == 0, completed.stdout + completed.stderr
