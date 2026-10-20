"""Unrounded classifications survive bilingual display. 双语显示保留未舍入分类。"""

import math
from dataclasses import replace

import pytest

from astrology import (
  AspectObject,
  AspectRule,
  Body,
  ChartConfig,
  ChartHouses,
  EclipticPosition,
  HouseSystem,
  MajorAspect,
  NatalChart,
  Placement,
  find_aspects,
  format_chart,
  house_of,
  load_catalog,
  sign_degree,
  sign_of,
)
from astrology.knowledge import Catalog

_CUSPS = tuple(float(index * 30) for index in range(12))


def display_case(
  chart: NatalChart,
  longitude: float,
  *,
  second: float = 0.0,
  orb: float = 720.0,
  cusps: tuple[float, ...] = _CUSPS,
) -> NatalChart:
  config = ChartConfig(
    HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MARS), (AspectRule(MajorAspect.CONJUNCTION, orb),)
  )
  positions = (
    EclipticPosition(Body.SUN, longitude, 0, 1, -4e-6),
    EclipticPosition(Body.MARS, second, 0, 1, 1),
  )
  houses = ChartHouses(HouseSystem.WHOLE_SIGN, 0, 90, 180, 270, cusps)
  placements = tuple(
    Placement(
      p.identity,
      sign_of(p.longitude_deg),
      sign_degree(p.longitude_deg),
      house_of(p.longitude_deg, cusps),
    )
    for p in positions
  )
  aspects = find_aspects(
    [AspectObject(p.identity, p.longitude_deg, p.longitude_rate_deg_per_tt_day) for p in positions],
    config.aspects,
  )
  return replace(
    chart,
    requested=config,
    effective=replace(
      chart.effective,
      house_system=config.house_system,
      aspect_objects=config.aspect_participants(),
      orb_combination=None,
    ),
    houses=houses,
    positions=positions,
    placements=placements,
    aspects=aspects,
  )


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_complete_table_and_no_mutation(recorded_chart: NatalChart, language: str) -> None:
  before = repr(recorded_chart)
  output = format_chart(recorded_chart, load_catalog(), language=language)  # type: ignore[arg-type]
  assert ("Sun" if language == "en" else "太阳") in output
  assert ("Mean ascending lunar node" if language == "en" else "平均升交点") in output
  assert "mean_of_orbs" in output
  assert "algo5" in output
  assert "0.8.0" in output
  assert "2021-11-07T06:30:00+00:00" in output
  assert ("House cusp" if language == "en" else "宫头") in output
  assert "°" in output
  assert repr(recorded_chart) == before


@pytest.mark.parametrize(
  "longitude,expected",
  [
    (29.9999999, "Aries 29°59'59\""),
    (359.9999999, "Pisces 29°59'59\""),
    (30.0, "Taurus 0°00'00\""),
    (-0.0, "Aries 0°00'00\""),
    (math.nextafter(115 / 3600, math.inf), "Aries 0°01'55\""),
  ],
)
def test_angle_truncation(recorded_chart: NatalChart, longitude: float, expected: str) -> None:
  chart = display_case(recorded_chart, longitude)
  output = format_chart(chart, load_catalog())
  row = next(line for line in output.splitlines() if line.startswith("Sun [sun]"))
  assert expected in row
  assert " | R" in row
  assert "30°00'00\"" not in row
  assert "-0°00'00\"" not in output
  assert "720°00'00\"" in output


def test_truncated_deviation_is_not_exact(recorded_chart: NatalChart) -> None:
  chart = display_case(recorded_chart, 1e-9)
  assert chart.aspects[0].motion.value == "applying"
  output = format_chart(chart, load_catalog())
  row = next(line for line in output.splitlines() if " | Conjunction | " in line)
  assert " | 0°00'00\" | 720°00'00\" | applying" in row
  assert "-0" not in row


def test_truncated_position_tied_with_cusp_keeps_house(recorded_chart: NatalChart) -> None:
  cusps = (0.0, 10.00005, *(float(i * 30) for i in range(2, 12)))
  chart = display_case(recorded_chart, 10.00004, cusps=cusps)
  output = format_chart(chart, load_catalog())
  assert "Sun [sun] | Aries 10°00'00\" | 1 | R" in output
  assert "House cusp 2: Aries 10°00'00\"" in output


def test_all_current_catalog_labels(recorded_chart: NatalChart) -> None:
  catalog = load_catalog()
  for sign in (
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
  ):
    assert catalog.concept("sign." + sign).name.zh is not None
  for language in ("en", "zh-CN"):
    output = format_chart(recorded_chart, catalog, language=language)
    for position in recorded_chart.positions:
      concept = next(c for c in catalog.concepts if c.configuration is position.identity)
      assert concept.name.text(language) in output  # type: ignore[operator]


@pytest.mark.parametrize("defect", ["missing", "stale", "ambiguous"])
def test_unusable_catalog_fails(recorded_chart: NatalChart, defect: str) -> None:
  catalog = load_catalog()
  sun = catalog.concept("body.sun")
  if defect == "missing":
    incomplete = Catalog("test", (), (), (), ())
  elif defect == "stale":
    changed = replace(sun, name=replace(sun.name, revision=2))
    incomplete = replace(
      catalog, concepts=tuple(changed if c is sun else c for c in catalog.concepts)
    )
  else:
    duplicate = replace(
      sun,
      identifier="body.other_sun",
      en_aliases=(),
      zh_aliases=(),
      name=replace(sun.name, en="Other Sun", zh="另一太阳"),
    )
    incomplete = replace(catalog, concepts=(*catalog.concepts, duplicate))
  with pytest.raises(ValueError):
    format_chart(recorded_chart, incomplete, language="zh-CN")


@pytest.mark.parametrize("language", ["zh", "fr", "", 1, None])
def test_invalid_language(recorded_chart: NatalChart, language: object) -> None:
  with pytest.raises(ValueError):
    format_chart(recorded_chart, load_catalog(), language=language)  # type: ignore[arg-type]


def test_invalid_types(recorded_chart: NatalChart) -> None:
  with pytest.raises(TypeError):
    format_chart(None, load_catalog())  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    format_chart(recorded_chart, None)  # type: ignore[arg-type]
