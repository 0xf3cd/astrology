"""Unrounded classifications survive bilingual display and chart-record round trips.

双语显示与命盘记录往返都保留未舍入分类。
"""

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import get_args

import pytest

from astrology import (
  AspectMotion,
  AspectObject,
  AspectRule,
  Body,
  ChartConfig,
  ChartHouses,
  ChartRecordError,
  EclipticPosition,
  FixedOffset,
  HouseSystem,
  MajorAspect,
  NatalChart,
  ObjectOrb,
  OrbCombination,
  Placement,
  Sign,
  dumps_chart,
  find_aspects,
  format_chart,
  house_of,
  load_catalog,
  loads_chart,
  sign_degree,
  sign_of,
)
from astrology.knowledge import Catalog
from astrology.knowledge.records import Language

_CUSPS = tuple(float(index * 30) for index in range(12))


def test_presentation_tables_cover_supported_languages_and_motion() -> None:
  from astrology import text

  assert set(text._HEADINGS) == set(text._MOTIONS) == set(text._AXES) == set(get_args(Language))
  assert get_args(Language) == ("en", "zh-CN")
  for motions in text._MOTIONS.values():
    assert set(motions) == set(AspectMotion)


@pytest.mark.parametrize(
  "language,expected",
  [
    ("en", "tzdata package / IANA release / fold: None / None / None"),
    ("zh-CN", "tzdata 包版本 / IANA 版本 / fold: 无 / 无 / 无"),
  ],
)
def test_missing_timezone_provenance_uses_language_label(
  recorded_chart: NatalChart, language: Language, expected: str
) -> None:
  resolved = recorded_chart.resolved
  fixed = replace(
    resolved,
    record=replace(resolved.record, timezone=FixedOffset(resolved.utc_offset)),
    timezone_key=None,
    fold=None,
    tzdata_version=None,
    iana_version=None,
  )
  output = format_chart(replace(recorded_chart, resolved=fixed), load_catalog(), language=language)
  assert expected in output.splitlines()
  assert output.splitlines()[1].endswith(" / UTC-05:00")


def display_case(
  chart: NatalChart,
  longitude: float,
  *,
  second: float = 0.0,
  orb: float = 720.0,
  first_rate: float = -4e-6,
  second_rate: float = 1.0,
  object_orbs: tuple[ObjectOrb, ...] = (),
  combination: OrbCombination | None = None,
  aspect: MajorAspect = MajorAspect.CONJUNCTION,
  cusps: tuple[float, ...] = _CUSPS,
) -> NatalChart:
  config = ChartConfig(
    HouseSystem.WHOLE_SIGN,
    (Body.SUN, Body.MARS),
    (AspectRule(aspect, orb, object_orbs),),
    orb_combination=combination,
  )
  positions = (
    EclipticPosition(Body.SUN, longitude, 0, 1, first_rate),
    EclipticPosition(Body.MARS, second, 0, 1, second_rate),
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
    combination,
  )
  return replace(
    chart,
    requested=config,
    effective=replace(
      chart.effective,
      house_system=config.house_system,
      aspect_objects=config.aspect_participants(),
      orb_combination=combination,
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
  assert recorded_chart.provenance.celestial_version in output
  assert "2021-11-07T06:30:00+00:00" in output
  assert ("House cusp" if language == "en" else "宫头") in output
  assert "°" in output
  assert repr(recorded_chart) == before


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_complete_constructed_geometry_table(language: Language) -> None:
  reference = Path(__file__).parent / "reference"
  base = loads_chart((reference / "chart_record_v1.json").read_text(encoding="utf-8"))
  chart = display_case(
    base,
    0,
    second=7,
    orb=6,
    object_orbs=(ObjectOrb(Body.SUN, 10),),
    combination=OrbCombination.MEAN_OF_ORBS,
  )
  expected = (reference / f"constructed_chart.{language}.txt").read_text(encoding="utf-8")
  assert format_chart(chart, load_catalog(), language=language) == expected.removesuffix("\n")


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_distinct_position_houses_and_zero_rate(
  recorded_chart: NatalChart, language: Language
) -> None:
  chart = display_case(recorded_chart, 0, second=35, second_rate=0, orb=6)
  rows = format_chart(chart, load_catalog(), language=language).splitlines()
  if language == "en":
    assert "Sun [sun] | Aries 0°00'00\" | 1 | R" in rows
    assert "Mars [mars] | Taurus 5°00'00\" | 2 | S" in rows
  else:
    assert "太阳 [sun] | 白羊座 0°00'00\" | 1 | R" in rows
    assert "火星 [mars] | 金牛座 5°00'00\" | 2 | S" in rows


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize(
  "first,second,aspect,branch,english,chinese",
  [
    (1.0, 0.0, MajorAspect.CONJUNCTION, "0°00'00\"", "Conjunction", "合相"),
    (0.0, 179.0, MajorAspect.OPPOSITION, "+180°00'00\"", "Opposition", "对分相"),
  ],
)
def test_signed_aspect_branch_and_negative_deviation(
  recorded_chart: NatalChart,
  language: Language,
  first: float,
  second: float,
  aspect: MajorAspect,
  branch: str,
  english: str,
  chinese: str,
) -> None:
  chart = display_case(recorded_chart, first, second=second, orb=6, aspect=aspect)
  rows = format_chart(chart, load_catalog(), language=language).splitlines()
  if language == "en":
    assert f"Sun | Mars | {english} | {branch} | -1°00'00\" | 6°00'00\" | applying" in rows
  else:
    assert f"太阳 | 火星 | {chinese} | {branch} | -1°00'00\" | 6°00'00\" | 入相" in rows


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize(
  "first,second,first_rate,second_rate,motion,english,chinese",
  [
    (1.0, 0.0, 0.0, 1.0, AspectMotion.APPLYING, "applying", "入相"),
    (0.0, 1.0, 0.0, 1.0, AspectMotion.SEPARATING, "separating", "离相"),
    (0.0, 0.0, 0.0, 1.0, AspectMotion.EXACT, "exact", "精确"),
    (0.0, 1.0, 1.0, 1.0, AspectMotion.STATIONARY, "stationary", "相对速率为零"),
    (0.0, 180.0, 0.0, 1.0, AspectMotion.INDETERMINATE, "indeterminate", "无法确定"),
  ],
)
def test_all_aspect_motion_labels(
  recorded_chart: NatalChart,
  language: Language,
  first: float,
  second: float,
  first_rate: float,
  second_rate: float,
  motion: AspectMotion,
  english: str,
  chinese: str,
) -> None:
  chart = display_case(
    recorded_chart, first, second=second, orb=180, first_rate=first_rate, second_rate=second_rate
  )
  assert chart.aspects[0].motion is motion
  label = english if language == "en" else chinese
  output = format_chart(chart, load_catalog(), language=language)
  assert any(line.endswith(" | " + label) for line in output.splitlines())


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_no_aspects_and_no_overrides_are_rendered(
  recorded_chart: NatalChart,
  language: Language,
) -> None:
  chart = display_case(recorded_chart, 0, second=120, orb=6)
  output = format_chart(chart, load_catalog(), language=language)
  if language == "en":
    assert "Motion\nNone\n\nConfiguration" in output
    assert "Orb combination (identifier): None" in output
    assert "Aspect rule / base orb / object overrides: Conjunction / 6°00'00\" / None" in output
  else:
    assert "运动\n无\n\n配置" in output
    assert "容许度合成规则（标识）: 无" in output
    assert "相位规则 / 基础容许度 / 对象单独设置: 合相 / 6°00'00\" / 无" in output


@pytest.mark.parametrize(
  "longitude,expected_sign,expected_house",
  [
    (math.nextafter(360.0, 0.0), "pisces", 1),
    (0.0, "aries", 1),
    (math.nextafter(350.0, 0.0), "pisces", 12),
    (350.0, "pisces", 1),
  ],
)
def test_boundary_records_keep_sign_and_cusp_wrap(
  recorded_chart: NatalChart,
  longitude: float,
  expected_sign: str,
  expected_house: int,
) -> None:
  cusps = (350.0, *(float(index * 30 + 20) for index in range(11)))
  chart = display_case(recorded_chart, longitude, cusps=cusps)
  restored = loads_chart(dumps_chart(chart))
  assert restored == chart
  assert restored.placements[0].sign.value == expected_sign
  assert restored.placements[0].house == expected_house


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


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("angle,seconds", [(1 / 3600, "00"), (2 / 3600, "01")])
@pytest.mark.parametrize("negative", [False, True])
def test_exact_arcsecond_position_and_signed_deviation(
  recorded_chart: NatalChart, language: Language, angle: float, seconds: str, negative: bool
) -> None:
  chart = display_case(recorded_chart, angle if negative else 0, second=0 if negative else angle)
  rows = format_chart(chart, load_catalog(), language=language).splitlines()
  position = next(row for row in rows if ("[sun]" if negative else "[mars]") in row)
  assert position.split(" | ")[1] == (
    ("Aries" if language == "en" else "白羊座") + f" 0°00'{seconds}\""
  )
  aspect = next(row for row in rows if " | 720°00'00\" | " in row)
  sign = ("-" if negative else "+") if seconds != "00" else ""
  assert aspect.split(" | ")[4] == f"{sign}0°00'{seconds}\""
  motion = (
    ("applying" if negative else "separating")
    if language == "en"
    else ("入相" if negative else "离相")
  )
  assert aspect.split(" | ")[-1] == motion


@pytest.mark.parametrize("field,value", [("sign", "aries"), ("house", 1), ("sign_degree_deg", 30)])
def test_v1_exact_sign_and_cusp_ownership(
  recorded_chart: NatalChart, field: str, value: object
) -> None:
  chart = display_case(recorded_chart, 30)
  record = json.loads(dumps_chart(chart))
  record["placements"][0].update(sign="taurus", sign_degree_deg=0.0, house=2)
  restored = loads_chart(json.dumps(record))
  assert restored == chart
  assert restored.placements[0] == Placement(Body.SUN, Sign.TAURUS, 0, 2)
  record["placements"][0][field] = value
  with pytest.raises(ChartRecordError):
    loads_chart(json.dumps(record))


@pytest.mark.parametrize(
  "combination,limit",
  [
    (OrbCombination.MEAN_OF_ORBS, 8),
    (OrbCombination.BOTH_WITHIN_OWN_ORB, 6),
    (OrbCombination.EITHER_WITHIN_OWN_ORB, 10),
  ],
)
@pytest.mark.parametrize("exact", [False, True])
def test_v1_aspect_limit_and_motion(
  recorded_chart: NatalChart, combination: OrbCombination, limit: float, exact: bool
) -> None:
  chart = display_case(
    recorded_chart,
    0,
    second=0 if exact else limit,
    orb=6,
    object_orbs=(ObjectOrb(Body.SUN, 10),),
    combination=combination,
  )
  record = json.loads(dumps_chart(chart))
  record["aspects"] = [
    {
      "first": "sun",
      "second": "mars",
      "aspect": "conjunction",
      "branch_deg": 0.0,
      "deviation_deg": 0.0 if exact else limit,
      "orb_limit_deg": limit,
      "motion": "exact" if exact else "separating",
    }
  ]
  assert loads_chart(json.dumps(record)) == chart
  record["aspects"][0]["motion"] = "applying"
  with pytest.raises(ChartRecordError):
    loads_chart(json.dumps(record))
  record["aspects"] = []
  with pytest.raises(ChartRecordError, match="Stored aspects"):
    loads_chart(json.dumps(record))


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


@pytest.mark.parametrize(
  "identity,english,chinese",
  [
    (Sign.ARIES, "Aries", "白羊座"),
    (Sign.TAURUS, "Taurus", "金牛座"),
    (Sign.GEMINI, "Gemini", "双子座"),
    (Sign.CANCER, "Cancer", "巨蟹座"),
    (Sign.LEO, "Leo", "狮子座"),
    (Sign.VIRGO, "Virgo", "处女座"),
    (Sign.LIBRA, "Libra", "天秤座"),
    (Sign.SCORPIO, "Scorpio", "天蝎座"),
    (Sign.SAGITTARIUS, "Sagittarius", "射手座"),
    (Sign.CAPRICORN, "Capricorn", "摩羯座"),
    (Sign.AQUARIUS, "Aquarius", "水瓶座"),
    (Sign.PISCES, "Pisces", "双鱼座"),
  ],
)
def test_all_sign_names_use_the_catalog_relationship(
  identity: Sign, english: str, chinese: str
) -> None:
  from astrology.text import _name

  catalog = load_catalog()
  assert _name(identity, catalog, "en") == english
  assert _name(identity, catalog, "zh-CN") == chinese
  missing = Catalog("custom", (), (), (), ())
  with pytest.raises(KeyError):
    _name(identity, missing, "en")


def test_language_string_subclass_is_not_a_supported_plain_string(
  recorded_chart: NatalChart,
) -> None:
  class Label(str):
    pass

  with pytest.raises(ValueError):
    format_chart(recorded_chart, load_catalog(), language=Label("en"))  # type: ignore[arg-type]


def test_invalid_types(recorded_chart: NatalChart) -> None:
  with pytest.raises(TypeError):
    format_chart(None, load_catalog())  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    format_chart(recorded_chart, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
  "field",
  ["delta_t_model", "astrology_version", "celestial_version", "tzdata_version", "iana_version"],
)
def test_provenance_cannot_forge_table_rows(recorded_chart: NatalChart, field: str) -> None:
  payload = "foreign\\value|column\nFAKE ROW\r\u0085\u2028\u2029\x1b[2J"
  if field == "delta_t_model":
    changed = replace(
      recorded_chart, effective=replace(recorded_chart.effective, delta_t_model=payload)
    )
  elif field in ("astrology_version", "celestial_version"):
    changed = replace(
      recorded_chart,
      provenance=replace(recorded_chart.provenance, **{field: payload}),  # type: ignore[arg-type]
    )
  else:
    changed = replace(recorded_chart, resolved=replace(recorded_chart.resolved, **{field: payload}))  # type: ignore[arg-type]
  restored = loads_chart(dumps_chart(changed))
  assert restored == changed
  catalog = load_catalog()
  baseline = format_chart(recorded_chart, catalog)
  output = format_chart(restored, catalog)
  assert len(output.splitlines()) == len(baseline.splitlines())
  assert "FAKE ROW" not in output.splitlines()
  assert r"foreign\\value\|column\nFAKE ROW\r\x85\u2028\u2029\x1b[2J" in output
  assert all(character.isprintable() or character == "\n" for character in output)
  assert dumps_chart(restored) == dumps_chart(changed)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_catalog_names_cannot_forge_rows(recorded_chart: NatalChart, language: str) -> None:
  catalog = load_catalog()
  sun = catalog.concept("body.sun")
  payload = "Name|column\nFAKE ROW\u2028\x1b"
  name = replace(sun.name, en=payload) if language == "en" else replace(sun.name, zh=payload)
  supplied = replace(
    catalog,
    concepts=tuple(
      replace(concept, name=name) if concept is sun else concept for concept in catalog.concepts
    ),
  )
  baseline = format_chart(recorded_chart, catalog, language=language)  # type: ignore[arg-type]
  output = format_chart(recorded_chart, supplied, language=language)  # type: ignore[arg-type]
  assert len(output.splitlines()) == len(baseline.splitlines())
  assert r"Name\|column\nFAKE ROW\u2028\x1b" in output
  assert "FAKE ROW" not in output.splitlines()
