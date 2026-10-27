"""Lilly's sign-level rules and supplied-cusp composition. Lilly星座级规则及给定宫头的组合。"""

import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import date, time, timedelta
from enum import StrEnum
from typing import Any

import pytest

from astrology import (
  BirthRecord,
  Body,
  ChartConfig,
  ChartHouses,
  DignityStatus,
  FixedOffset,
  HouseRuler,
  HouseRulers,
  HouseSystem,
  Location,
  LunarNode,
  NatalChart,
  Placement,
  Sign,
  essential_dignities,
  format_house_rulers,
  house_of,
  load_catalog,
  natal_chart,
  prepare_natal_input,
  sign_ruler,
)
from astrology.knowledge import ConceptKind, LocalizedText
from astrology.knowledge.records import Language
from tools import installed_check
from tools.catalog_docs import check_catalog_data, dignity_rows, render_catalog
from tools.installed_check import _cross_source

# Lilly 1647, Book I, pp.57, 61-62, 65, 69, 73, 76, 80; pp.102, 104-105.
# Domicile/exaltation and chapter debilities were transcribed from page images.
# Saturn's detriments use p.105's opposite-house relation. No domain table is imported.
# 入庙、擢升及章节中的失势、落陷来自原图；土星失势按p.105相对庙关系推出，不导入领域表。
_SOURCE_SIGNS = {
  Body.SUN: ((Sign.LEO,), (Sign.ARIES,), (Sign.AQUARIUS,), (Sign.LIBRA,)),
  Body.MOON: ((Sign.CANCER,), (Sign.TAURUS,), (Sign.CAPRICORN,), (Sign.SCORPIO,)),
  Body.MERCURY: (
    (Sign.GEMINI, Sign.VIRGO),
    (Sign.VIRGO,),
    (Sign.SAGITTARIUS, Sign.PISCES),
    (Sign.PISCES,),
  ),
  Body.VENUS: (
    (Sign.TAURUS, Sign.LIBRA),
    (Sign.PISCES,),
    (Sign.ARIES, Sign.SCORPIO),
    (Sign.VIRGO,),
  ),
  Body.MARS: (
    (Sign.ARIES, Sign.SCORPIO),
    (Sign.CAPRICORN,),
    (Sign.TAURUS, Sign.LIBRA),
    (Sign.CANCER,),
  ),
  Body.JUPITER: (
    (Sign.SAGITTARIUS, Sign.PISCES),
    (Sign.CANCER,),
    (Sign.GEMINI, Sign.VIRGO),
    (Sign.CAPRICORN,),
  ),
  Body.SATURN: (
    (Sign.CAPRICORN, Sign.AQUARIUS),
    (Sign.LIBRA,),
    (Sign.CANCER, Sign.LEO),
    (Sign.ARIES,),
  ),
}
_ORDER = (
  DignityStatus.DOMICILE,
  DignityStatus.EXALTATION,
  DignityStatus.DETRIMENT,
  DignityStatus.FALL,
)
_RULERS = (
  Body.MARS,
  Body.VENUS,
  Body.MERCURY,
  Body.MOON,
  Body.SUN,
  Body.MERCURY,
  Body.VENUS,
  Body.MARS,
  Body.JUPITER,
  Body.SATURN,
  Body.SATURN,
  Body.JUPITER,
)


@pytest.mark.parametrize("body", _SOURCE_SIGNS)
@pytest.mark.parametrize("sign", list(Sign))
def test_source_grid(body: Body, sign: Sign) -> None:
  expected = tuple(
    status for status, signs in zip(_ORDER, _SOURCE_SIGNS[body], strict=True) if sign in signs
  )
  assert essential_dignities(body, sign) == expected


def test_source_grid_totals_and_sign_rulers() -> None:
  results = [essential_dignities(body, sign) for body in _SOURCE_SIGNS for sign in Sign]
  assert len(results) == 84 and results.count(()) == 48
  assert [r for r in results if len(r) > 1] == [_ORDER[:2], _ORDER[2:]]
  assert tuple(sign_ruler(sign) for sign in Sign) == _RULERS


class Foreign(StrEnum):
  ARIES = "aries"
  SUN = "sun"


@pytest.mark.parametrize(
  "bad", [None, True, 0, "aries", Foreign.ARIES, Body.SUN, DignityStatus.FALL]
)
def test_sign_input_types(bad: Any) -> None:
  with pytest.raises(TypeError):
    sign_ruler(bad)
  with pytest.raises(TypeError):
    essential_dignities(Body.SUN, bad)


@pytest.mark.parametrize("bad", [None, True, 0, "sun", Foreign.SUN, Sign.LEO, *LunarNode])
def test_body_input_types(bad: Any) -> None:
  with pytest.raises(TypeError):
    essential_dignities(bad, Sign.LEO)


@pytest.mark.parametrize("body", [Body.URANUS, Body.NEPTUNE, Body.PLUTO])
def test_unsupported_bodies_are_not_empty_assessments(body: Body) -> None:
  for sign in Sign:
    with pytest.raises(ValueError, match=body.value):
      essential_dignities(body, sign)


@pytest.fixture
def ruler_chart() -> NatalChart:
  return _cross_source(
    2000, "rulers", ((Body.MERCURY, 150), (Body.SUN, 30), (Body.MARS, 280), (Body.PLUTO, 330))
  )


def test_hand_worked_whole_sign_chart(ruler_chart: NatalChart) -> None:
  before = repr(ruler_chart)
  result = HouseRulers(ruler_chart)
  assert result.chart is ruler_chart and result.rule_id == "rule.lilly1647.essential_dignities"
  assert tuple(r.house for r in result.houses) == tuple(range(1, 13))
  assert tuple(r.cusp_sign for r in result.houses) == tuple(Sign)
  assert tuple(r.ruler for r in result.houses) == _RULERS
  mercury, sun, mars, _ = ruler_chart.placements
  assert result.houses[0].placement is mars
  assert result.houses[0].statuses == (DignityStatus.EXALTATION,)
  assert result.houses[4].placement is sun and result.houses[4].statuses == ()
  assert result.houses[5].placement is mercury and result.houses[5].statuses == _ORDER[:2]
  assert result.houses[9].ruler is Body.SATURN
  assert result.houses[9].placement is None and result.houses[9].statuses is None
  assert result == HouseRulers(ruler_chart) and result.houses == result.houses
  assert repr(ruler_chart) == before
  with pytest.raises(FrozenInstanceError):
    result.chart = ruler_chart  # type: ignore[misc]
  with pytest.raises(FrozenInstanceError):
    result.houses[0].house = 2  # type: ignore[misc]
  with pytest.raises(TypeError):
    HouseRulers(ruler_chart, houses=())  # type: ignore[call-arg]


def test_repeated_cusps_axes_and_caller_input_isolation(ruler_chart: NatalChart) -> None:
  cusps = [355.0, 5.0, 25.0, 65.0, 95.0, 125.0, 175.0, 185.0, 205.0, 245.0, 275.0, 305.0]
  houses = ChartHouses(HouseSystem.PLACIDUS, 60, 90, 240, 270, cusps)  # type: ignore[arg-type]
  placements = [
    replace(p, house=house_of(position.longitude_deg, houses.cusps_deg))
    for p, position in zip(ruler_chart.placements, ruler_chart.positions, strict=True)
  ]
  source = {"record": "original"}
  record = replace(ruler_chart.resolved.record, source=source)
  chart = replace(
    ruler_chart,
    requested=replace(ruler_chart.requested, house_system=houses.system),
    effective=replace(ruler_chart.effective, house_system=houses.system),
    resolved=replace(ruler_chart.resolved, record=record),
    houses=houses,
    placements=placements,  # type: ignore[arg-type]
  )
  result = HouseRulers(chart)
  before = repr(result)
  source.clear()
  cusps.clear()
  placements.clear()
  assert repr(result) == before
  assert len(result.houses) == 12 and result.chart is chart
  assert tuple(r.ruler for r in result.houses) == (
    Body.JUPITER,
    Body.MARS,
    Body.MARS,
    Body.MERCURY,
    Body.MOON,
    Body.SUN,
    Body.MERCURY,
    Body.VENUS,
    Body.VENUS,
    Body.JUPITER,
    Body.SATURN,
    Body.SATURN,
  )
  assert result.houses[0].cusp_sign is Sign.PISCES  # ASC is Gemini. ASC为双子。
  assert result.houses[9].cusp_sign is Sign.SAGITTARIUS  # MC is Cancer. MC为巨蟹。
  assert result.houses[1].placement is result.houses[2].placement is chart.placements[2]
  assert chart.placements[2].house == 11 and chart.placements[1].house == 3
  assert result.houses[5].statuses == () and result.houses[6].statuses == _ORDER[:2]
  assert result.houses[0].placement is None and result.houses[0].statuses is None


@pytest.mark.parametrize("system", list(HouseSystem))
def test_calculated_chart_uses_existing_geometry_and_positions(system: HouseSystem) -> None:
  chart = natal_chart(
    prepare_natal_input(
      BirthRecord(date(2000, 1, 1), time(12), FixedOffset(timedelta(0)), Location(40, 0))
    ),
    ChartConfig(system, tuple(_SOURCE_SIGNS), ()),
  )
  result = HouseRulers(chart)
  for record, cusp in zip(result.houses, chart.houses.cusps_deg, strict=True):
    assert record.cusp_sign is tuple(Sign)[int(cusp // 30)]
    assert record.ruler is _RULERS[int(cusp // 30)]
    assert record.placement is next(p for p in chart.placements if p.identity is record.ruler)
  assert result.chart is chart and result.chart.houses.system is system


@pytest.mark.parametrize("house", [None, True, "1", 1.0])
def test_house_number_types(house: Any) -> None:
  with pytest.raises(TypeError):
    HouseRuler(house, Sign.ARIES, None)


@pytest.mark.parametrize("house", [-1, 0, 13])
def test_house_number_range(house: int) -> None:
  with pytest.raises(ValueError):
    HouseRuler(house, Sign.ARIES, None)


def test_record_disagreements_and_types() -> None:
  chart_input: Any
  for bad in (None, "aries", Body.MARS, Foreign.ARIES):
    with pytest.raises(TypeError):
      HouseRuler(1, bad, None)  # type: ignore[arg-type]
  for chart_input in ([], "chart", None, (), Body.SUN):
    with pytest.raises(TypeError):
      HouseRulers(chart_input)
  with pytest.raises(TypeError):
    HouseRuler(1, Sign.ARIES, [])  # type: ignore[arg-type]
  for identity in (Body.SUN, LunarNode.MEAN_ASCENDING):
    with pytest.raises(ValueError, match="identity"):
      HouseRuler(1, Sign.ARIES, Placement(identity, Sign.ARIES, 0, 1))
  assert (
    HouseRuler(1, Sign.VIRGO, Placement(Body.MERCURY, Sign.PISCES, 29.9, 12)).statuses == _ORDER[2:]
  )


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_text_preserves_missing_empty_and_every_status(
  ruler_chart: NatalChart, language: Language
) -> None:
  catalog = load_catalog()
  result = HouseRulers(ruler_chart)
  text = format_house_rulers(result, catalog, language=language)
  labels = (
    ("Not calculated", "None of these four", "Domicile, Exaltation")
    if language == "en"
    else ("未计算", "这四项均未命中", "入庙, 擢升")
  )
  assert len(text.splitlines()) == 16
  assert all(label in text for label in (*labels, result.rule_id))
  assert catalog.concept("house.whole_sign").name.text(language) in text  # type: ignore[operator]
  for record, line in zip(result.houses, text.splitlines()[4:], strict=True):
    assert line.startswith(f"{record.house} | ")
    assert catalog.concept(f"sign.{record.cusp_sign.value}").name.text(language) in line  # type: ignore[operator]
  assert "0.0°" in text
  assert text.splitlines()[4] == (
    "1 | Aries | Mars | Capricorn 10.0° / House 10 | Exaltation"
    if language == "en"
    else "1 | 白羊座 | 火星 | 摩羯座 10.0° / 宫位 10 | 擢升"
  )


def test_formatter_errors_and_caller_vocabulary(ruler_chart: NatalChart) -> None:
  catalog, result = load_catalog(), HouseRulers(ruler_chart)
  for bad in (None, ruler_chart, ()):
    with pytest.raises(TypeError):
      format_house_rulers(bad, catalog)  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    format_house_rulers(result, None)  # type: ignore[arg-type]
  for language_input in ("fr", None, True):
    with pytest.raises(ValueError):
      format_house_rulers(result, catalog, language=language_input)  # type: ignore[arg-type]
  original = catalog.concept("dignity_status.exaltation")
  for name in (
    LocalizedText("Custom"),
    LocalizedText("Custom", "旧译", revision=2, zh_revision=1, translation_credit="test"),
  ):
    changed = replace(
      catalog,
      concepts=tuple(replace(c, name=name) if c is original else c for c in catalog.concepts),
    )
    with pytest.raises(ValueError, match="Missing or stale"):
      format_house_rulers(result, changed, language="zh-CN")
  changed = replace(
    catalog,
    concepts=tuple(
      replace(c, name=LocalizedText("A|B\nC")) if c is original else c for c in catalog.concepts
    ),
  )
  assert r"A\|B\nC" in format_house_rulers(result, changed)
  changed = replace(
    catalog,
    concepts=tuple(c for c in catalog.concepts if c is not original),
    variants=(),
    entries=(),
  )
  with pytest.raises(KeyError):
    format_house_rulers(result, changed)


def test_catalog_identity_source_and_reference_statuses() -> None:
  catalog = load_catalog()
  check_catalog_data(catalog)
  concepts = catalog.list_concepts(kind=ConceptKind.DIGNITY_STATUS)
  assert {c.identifier for c in concepts} == {f"dignity_status.{s.value}" for s in _ORDER}
  assert all(c.configuration is None for c in concepts)
  entry = catalog.entry("entry.essential_dignities")
  assert (
    entry.prerequisite_status.value,
    entry.output_eligibility.value,
    entry.chart_applicability,
  ) == ("complete", "reference_only", "not_assessed")
  assert entry.rule_ids == ("rule.lilly1647.essential_dignities",)
  source = catalog.source("source.lilly.christian-astrology-1647")
  assert source.verification.value == "verified" and source.edition.endswith("1647")
  assert "Public Domain Mark 1.0" in source.rights.en
  excerpts = [c.excerpt for c in entry.citations if c.excerpt is not None]
  assert len(excerpts) == 3 and all(e.translation_credit for e in excerpts)
  assert excerpts[-1].en == "♄ when he is in ♈ is opposite to ♎ his Exaltation"
  for language in ("en", "zh-CN"):
    rendered = render_catalog(catalog, language, "test")
    assert (
      "| Virgo | Mercury | Mercury | Jupiter | Venus |"
      if language == "en"
      else "| 处女座 | 水星 | 水星 | 木星 | 金星 |"
    ) in rendered


@pytest.mark.parametrize("mode", [[], ["-O"]])
def test_dignities_and_composition_without_native_imports(mode: list[str]) -> None:
  code = """
import sys
from astrology import *
from tools.installed_check import _cross_source
chart = _cross_source(2000, 'pure', ((Body.MERCURY, 150), (Body.SUN, 30)))
result = HouseRulers(chart)
format_house_rulers(result, load_catalog(), language='zh-CN')
if result.chart is not chart or result.houses[5].statuses != (DignityStatus.DOMICILE, DignityStatus.EXALTATION):
  raise RuntimeError('lost chart or status')
if any(n.startswith(('celestial', 'ctypes')) for n in sys.modules):
  raise RuntimeError('native import')
for call, error in (
  (lambda: sign_ruler('aries'), TypeError),
  (lambda: essential_dignities(LunarNode.MEAN_ASCENDING, Sign.ARIES), TypeError),
  (lambda: essential_dignities(Body.PLUTO, Sign.ARIES), ValueError),
  (lambda: HouseRuler(True, Sign.ARIES, None), TypeError),
  (lambda: HouseRuler(0, Sign.ARIES, None), ValueError),
  (lambda: HouseRuler(1, Sign.ARIES, Placement(Body.SUN, Sign.LEO, 0, 1)), ValueError),
  (lambda: HouseRulers(None), TypeError),
):
  try: call()
  except error: pass
  else: raise RuntimeError('missing public check')
"""
  run = subprocess.run([sys.executable, *mode, "-c", code], capture_output=True, text=True)
  assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.parametrize(
  "target", ["sign_ruler", "essential_dignities", "HouseRulers", "format_house_rulers"]
)
def test_installed_consumer_detects_defects(monkeypatch: pytest.MonkeyPatch, target: str) -> None:
  import astrology

  replacements: dict[str, Any] = {
    "sign_ruler": lambda sign: Body.PLUTO,
    "essential_dignities": lambda body, sign: (),
    "HouseRulers": lambda chart: HouseRulers(replace(chart, placements=chart.placements)),
    "format_house_rulers": lambda *args, **kwargs: "incomplete",
  }
  monkeypatch.setattr(astrology, target, replacements[target])
  with pytest.raises(ValueError, match="Installed"):
    installed_check._check_dignities()


def test_domain_tables_are_immutable() -> None:
  import astrology.dignities as domain

  with pytest.raises(TypeError):
    domain._DOMICILES[Body.MERCURY] = (Sign.LEO,)  # type: ignore[index]
  with pytest.raises(TypeError):
    domain._EXALTATIONS[Body.MERCURY] = Sign.LEO  # type: ignore[index]
  with pytest.raises(TypeError):
    domain._RULERS[Sign.ARIES] = Body.PLUTO  # type: ignore[index]


def test_generated_headers_use_supplied_status_names() -> None:
  catalog = load_catalog()
  original = catalog.concept("dignity_status.fall")
  custom = replace(
    catalog,
    concepts=tuple(
      replace(
        c, name=LocalizedText("Custom fall", "自定落陷", zh_revision=1, translation_credit="test")
      )
      if c is original
      else c
      for c in catalog.concepts
    ),
  )
  assert next(dignity_rows(custom, "en"))[-1] == "Custom fall"
  assert next(dignity_rows(custom, "zh-CN"))[-1] == "自定落陷"


@pytest.mark.parametrize("defect", ["identity", "rule_link", "entry_link"])
def test_catalog_guard_detects_missing_dignity_coverage(defect: str) -> None:
  catalog = load_catalog()
  rule = catalog.variant("rule.lilly1647.essential_dignities")
  entry = catalog.entry("entry.essential_dignities")
  if defect == "identity":
    identifier = "dignity_status.fall"
    catalog = replace(
      catalog,
      concepts=tuple(c for c in catalog.concepts if c.identifier != identifier),
      variants=tuple(
        replace(v, concept_ids=tuple(i for i in v.concept_ids if i != identifier))
        for v in catalog.variants
      ),
      entries=tuple(
        replace(e, concept_ids=tuple(i for i in e.concept_ids if i != identifier))
        for e in catalog.entries
      ),
    )
  elif defect == "rule_link":
    catalog = replace(
      catalog,
      variants=tuple(
        replace(v, concept_ids=v.concept_ids[:-1]) if v is rule else v for v in catalog.variants
      ),
    )
  else:
    catalog = replace(
      catalog, entries=tuple(replace(e, rule_ids=()) if e is entry else e for e in catalog.entries)
    )
  with pytest.raises(ValueError, match="dignity"):
    check_catalog_data(catalog)


@pytest.mark.parametrize(
  "cusp,expected",
  [
    (math.nextafter(30, 0), Sign.ARIES),
    (30, Sign.TAURUS),
    (math.nextafter(30, 60), Sign.TAURUS),
    (math.nextafter(360, 0), Sign.PISCES),
  ],
)
def test_cusp_boundary_is_not_rounded(ruler_chart: NatalChart, cusp: float, expected: Sign) -> None:
  cusps = list(ruler_chart.houses.cusps_deg)
  index = 1 if cusp < 60 else 11
  cusps[index] = cusp
  houses = replace(ruler_chart.houses, cusps_deg=tuple(cusps))
  chart = replace(
    ruler_chart,
    houses=houses,
    placements=tuple(
      replace(p, house=house_of(position.longitude_deg, houses.cusps_deg))
      for p, position in zip(ruler_chart.placements, ruler_chart.positions, strict=True)
    ),
  )
  assert HouseRulers(chart).houses[index].cusp_sign is expected
