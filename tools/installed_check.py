"""Verify the installed package in isolation. 隔离验证已安装的包。"""

import builtins
import json
import sys
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from importlib import import_module
from importlib.metadata import PackageNotFoundError, distribution, version
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal, cast

import astrology
from astrology.knowledge import (
  Catalog,
  ConceptKind,
  OutputEligibility,
  PrerequisiteStatus,
  SourceVerification,
  TranslationStatus,
)

MODULES = (
  "_distribution",
  "_validation",
  "aspects",
  "birth",
  "chart",
  "config",
  "cross_aspects",
  "dignities",
  "house_overlays",
  "houses",
  "knowledge",
  "knowledge.catalog",
  "knowledge.records",
  "lunar_phase",
  "objects",
  "summaries",
  "text",
  "zodiac",
)


def acceptance_chart() -> astrology.NatalChart:
  """Calculate the same complete synthetic example in source and installed environments.

  在源码及安装环境中计算同一个完整合成例子。
  """
  record = astrology.BirthRecord(
    date(2026, 4, 5),
    time(1, 45),
    astrology.IanaTimezone("Australia/Lord_Howe"),
    astrology.Location(0, 0),
    astrology.TimePrecision.MINUTE,
    {"record": "synthetic"},
  )
  config = astrology.ChartConfig(
    astrology.HouseSystem.WHOLE_SIGN,
    (*astrology.Body, astrology.LunarNode.MEAN_ASCENDING),
    tuple(
      astrology.AspectRule(aspect, 6, (astrology.ObjectOrb(astrology.Body.SUN, 10),))
      for aspect in astrology.MajorAspect
    ),
    aspect_objects=tuple(reversed(tuple(astrology.Body))),
    orb_combination=astrology.OrbCombination.MEAN_OF_ORBS,
  )
  return astrology.natal_chart(astrology.prepare_natal_input(record, fold=0), config)


def chart_observations(chart: astrology.NatalChart) -> str:
  """Capture exact same-revision check values, without a chart restoration path.

  取得同一源码修订的精确检查值，不提供恢复命盘的路径。
  """
  values = {
    "resolved": repr(chart.resolved),
    "requested": repr(chart.requested),
    "effective": repr(chart.effective),
    "provenance": repr(chart.provenance),
    "times": [chart.times.jd_ut1, chart.times.jde_tt],
    "positions": [
      [
        p.identity.value,
        p.longitude_deg,
        p.latitude_deg,
        p.distance_au,
        p.longitude_rate_deg_per_tt_day,
      ]
      for p in chart.positions
    ],
    "houses": [
      chart.houses.system.value,
      chart.houses.ascendant_deg,
      chart.houses.midheaven_deg,
      chart.houses.descendant_deg,
      chart.houses.imum_coeli_deg,
      chart.houses.cusps_deg,
    ],
    "placements": [
      [p.identity.value, p.sign.value, p.sign_degree_deg, p.house] for p in chart.placements
    ],
    "aspects": [
      [
        a.first.value,
        a.second.value,
        a.aspect.value,
        a.branch_deg,
        a.deviation_deg,
        a.orb_limit_deg,
        a.motion.value,
      ]
      for a in chart.aspects
    ],
  }
  return json.dumps(values, sort_keys=True, allow_nan=False)


def _cross_source(
  year: int,
  label: str,
  coordinates: tuple[tuple[astrology.Body | astrology.LunarNode, float], ...],
  *,
  axes: tuple[float, float, float, float] = (0, 270, 180, 90),
  house_system: astrology.HouseSystem = astrology.HouseSystem.WHOLE_SIGN,
  cusps_deg: tuple[float, ...] | None = None,
) -> astrology.NatalChart:
  """Construct a pure synthetic source, not a calculated astronomical reference.

  纯构造合成源盘，不把它当作计算所得的天文参考。
  """
  record = astrology.BirthRecord(
    date(year, 1, 1),
    time(0),
    astrology.FixedOffset(timedelta(0)),
    astrology.Location(0, 0),
    source={"record": "synthetic", "side": label},
  )
  resolved = astrology.ResolvedBirth(
    record, datetime(year, 1, 1, tzinfo=UTC), timedelta(0), None, None, None, None
  )
  config = astrology.ChartConfig(house_system, tuple(identity for identity, _ in coordinates), ())
  houses = astrology.ChartHouses(
    config.house_system,
    *axes,
    tuple(float(n) for n in range(0, 360, 30)) if cusps_deg is None else cusps_deg,
  )
  positions = tuple(
    astrology.EclipticPosition(
      identity, longitude, 0, None if isinstance(identity, astrology.LunarNode) else 1, 1
    )
    for identity, longitude in coordinates
  )
  return astrology.NatalChart(
    resolved,
    config,
    astrology.EffectiveConfiguration(
      config.house_system, "synthetic-model", "fixed_fourteen_object_joint_snapshot", (), None
    ),
    astrology.ChartProvenance(
      "synthetic-" + label,
      "apparent_geocentric_true_ecliptic_of_date",
      "delta_t_model_from_civil_utc",
      "synthetic-" + label,
    ),
    astrology.ChartTimes(2451544.5, 2451544.5),
    positions,
    houses,
    tuple(
      astrology.Placement(
        p.identity,
        astrology.sign_of(p.longitude_deg),
        astrology.sign_degree(p.longitude_deg),
        astrology.house_of(p.longitude_deg, houses.cusps_deg),
      )
      for p in positions
    ),
    (),
  )


def acceptance_house_overlays() -> astrology.CrossChartHouseOverlays:
  """Compose a synthetic bidirectional case with unequal source systems and stored axes.

  组合一个合成双向用例，源盘宫制不同，并显式选择已存四轴。
  """
  sun, venus, node = astrology.Body.SUN, astrology.Body.VENUS, astrology.LunarNode.MEAN_ASCENDING
  left = _cross_source(
    2000, "left", ((sun, 15), (venus, 210), (node, 359)), axes=(22, 111, 204, 291)
  )
  right = _cross_source(
    2001,
    "right",
    ((sun, 345), (venus, 0), (node, 45)),
    axes=(15, 105, 195, 285),
    house_system=astrology.HouseSystem.EQUAL,
    cusps_deg=tuple(float(n) for n in range(15, 360, 30)),
  )
  return astrology.cross_chart_house_overlays(
    left, right, left_objects=(*left.requested.objects, *astrology.Axis)
  )


def acceptance_cross_aspects() -> astrology.CrossChartAspects:
  """Compare two synthetic in-memory sources without astronomy or time resolution.

  比较两张合成内存源盘，不调用天文库或时刻解析。
  """
  chart_left = _cross_source(
    2000,
    "left",
    (
      (astrology.Body.MOON, 350),
      (astrology.Body.SUN, 10),
      (astrology.LunarNode.MEAN_ASCENDING, 190),
    ),
  )
  chart_right = _cross_source(
    2001,
    "right",
    (
      (astrology.Body.SUN, 68),
      (astrology.Body.MOON, 8),
      (astrology.LunarNode.MEAN_ASCENDING, 10),
    ),
  )
  rules = tuple(
    astrology.AspectRule(aspect, 3, (astrology.ObjectOrb(astrology.Body.MOON, 5),))
    for aspect in (
      astrology.MajorAspect.OPPOSITION,
      astrology.MajorAspect.SEXTILE,
      astrology.MajorAspect.CONJUNCTION,
    )
  )
  return astrology.cross_chart_aspects(
    chart_left=chart_left,
    chart_right=chart_right,
    rules=rules,
    combination=astrology.OrbCombination.MEAN_OF_ORBS,
  )


def comparison_observations(
  aspects: astrology.CrossChartAspects,
  overlays: astrology.CrossChartHouseOverlays,
  catalog: Catalog,
) -> str:
  """Capture both comparison results and bilingual text from supplied inputs.

  从给定输入取得两种比较结果及双语文本的检查值。
  """
  languages: tuple[Literal["en", "zh-CN"], ...] = ("en", "zh-CN")
  values = {
    "aspects": {
      "chart_left": json.loads(chart_observations(aspects.chart_left)),
      "chart_right": json.loads(chart_observations(aspects.chart_right)),
      "left_objects": [identity.value for identity in aspects.left_objects],
      "right_objects": [identity.value for identity in aspects.right_objects],
      "rules": repr(aspects.rules),
      "combination": aspects.combination,
      "hits": [
        [
          h.left_object.value,
          h.right_object.value,
          h.aspect.value,
          h.branch_deg,
          h.deviation_deg,
          h.orb_limit_deg,
        ]
        for h in aspects.hits
      ],
    },
    "overlays": {
      "chart_left": json.loads(chart_observations(overlays.chart_left)),
      "chart_right": json.loads(chart_observations(overlays.chart_right)),
      "left_objects": [identity.value for identity in overlays.left_objects],
      "right_objects": [identity.value for identity in overlays.right_objects],
      "placements": [
        [p.object_owner, p.house_owner, p.identity.value, p.house] for p in overlays.placements
      ],
    },
    "text": {
      language: {
        "aspects": astrology.format_cross_aspects(aspects, catalog, language=language),
        "overlays": astrology.format_house_overlays(overlays, catalog, language=language),
      }
      for language in languages
    },
  }
  return json.dumps(values, sort_keys=True, allow_nan=False)


def _check_cross_chart(expected_observations: Path | None = None) -> None:
  _check_native_isolation()
  result = acceptance_cross_aspects()
  overlays = acceptance_house_overlays()
  catalog = astrology.load_catalog()
  node = astrology.LunarNode.MEAN_ASCENDING
  sun, moon = astrology.Body.SUN, astrology.Body.MOON
  expected = [
    (sun, sun, astrology.MajorAspect.SEXTILE, 60.0, -2.0, 3.0),
    (sun, moon, astrology.MajorAspect.CONJUNCTION, 0.0, -2.0, 4.0),
    (sun, node, astrology.MajorAspect.CONJUNCTION, 0.0, 0.0, 3.0),
    (node, moon, astrology.MajorAspect.OPPOSITION, 180.0, -2.0, 4.0),
    (node, node, astrology.MajorAspect.OPPOSITION, 180.0, 0.0, 3.0),
  ]
  if [
    (h.left_object, h.right_object, h.aspect, h.branch_deg, h.deviation_deg, h.orb_limit_deg)
    for h in result.hits
  ] != expected:
    raise ValueError("Installed cross aspects differ from hand-worked geometry")
  expected_placements = [
    ("left", "right", sun, 1),
    ("left", "right", astrology.Body.VENUS, 7),
    ("left", "right", node, 12),
    ("left", "right", astrology.Axis.ASCENDANT, 1),
    ("left", "right", astrology.Axis.MIDHEAVEN, 4),
    ("left", "right", astrology.Axis.DESCENDANT, 7),
    ("left", "right", astrology.Axis.IMUM_COELI, 10),
    ("right", "left", sun, 12),
    ("right", "left", astrology.Body.VENUS, 1),
    ("right", "left", node, 2),
  ]
  if [
    (p.object_owner, p.house_owner, p.identity, p.house) for p in overlays.placements
  ] != expected_placements:
    raise ValueError("Installed house overlays differ from hand-worked geometry")
  original_import = builtins.__import__

  def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
    if name == "astrology.celestial" or name.startswith(
      ("celestial_calendar", "tzdata", "zoneinfo")
    ):
      raise ValueError("Supplied comparison attempted to initialize astronomy or time data")
    return original_import(name, *args, **kwargs)

  builtins.__import__ = guarded
  try:
    if (
      astrology.cross_chart_house_overlays(
        overlays.chart_left,
        overlays.chart_right,
        left_objects=overlays.left_objects,
        right_objects=overlays.right_objects,
      )
      != overlays
    ):
      raise ValueError("Installed supplied overlay calculation changed")
    if (
      astrology.cross_chart_aspects(
        result.chart_left,
        result.chart_right,
        result.rules,
        left_objects=result.left_objects,
        right_objects=result.right_objects,
        combination=result.combination,
      )
      != result
    ):
      raise ValueError("Installed supplied cross-aspect calculation changed")
    observed = comparison_observations(result, overlays, catalog)
  finally:
    builtins.__import__ = original_import
  texts = json.loads(observed)["text"]
  for language, required in (
    ("en", "Left | Venus [venus] | Right | 7"),
    ("zh-CN", "左盘 | 金星 [venus] | 右盘 | 7"),
  ):
    output = texts[language]
    if required not in output["overlays"].splitlines():
      raise ValueError("Installed overlay text lost ownership or placement")
    aspect_rows = [line for line in output["aspects"].splitlines() if "] |" in line]
    if len(aspect_rows) != len(expected):
      raise ValueError("Installed cross-aspect text lost static hits")
  if expected_observations is not None and observed != expected_observations.read_text(
    encoding="utf-8"
  ):
    raise ValueError("Installed comparison observations differ from the development entry point")
  _check_native_isolation()


def _check_axes() -> None:
  """Check all stored axis fields with independent synthetic natal/cross expectations.

  用独立的合成本命和双盘期望核验全部已存轴字段。
  """
  axes = (10.5, 100.25, 202.75, 301.125)
  other_axes = (50.25, 140.0, 230.5, 320.75)
  catalog = astrology.load_catalog()
  rule = astrology.AspectRule(astrology.MajorAspect.SEXTILE, 3)
  for axis, longitude in zip(astrology.Axis, axes, strict=True):
    source = _cross_source(
      2000, "axis-left", ((astrology.Body.SUN, (longitude + 57.5) % 360),), axes=axes
    )
    expected = astrology.AspectHit(
      astrology.Body.SUN,
      axis,
      astrology.MajorAspect.SEXTILE,
      -60,
      2.5,
      3,
      astrology.AspectMotion.INDETERMINATE,
    )
    config = astrology.ChartConfig(
      source.requested.house_system,
      source.requested.objects,
      (rule,),
      aspect_objects=(axis, astrology.Body.SUN),
    )
    natal = replace(
      source,
      requested=config,
      effective=replace(source.effective, aspect_objects=(astrology.Body.SUN, axis)),
      aspects=(expected,),
    )
    if natal.aspects != (expected,) or natal.positions != source.positions:
      raise ValueError("Installed natal axis geometry differs from independent expectations")
    right = _cross_source(
      2001, "axis-right", ((astrology.Body.SUN, (longitude + 57.5) % 360),), axes=other_axes
    )
    cross = astrology.cross_chart_aspects(
      source, right, (rule,), left_objects=(axis,), right_objects=(astrology.Body.SUN,)
    )
    if cross.hits != (
      astrology.CrossAspectHit(
        axis, astrology.Body.SUN, astrology.MajorAspect.SEXTILE, 60, -2.5, 3
      ),
    ):
      raise ValueError("Installed cross axes use the wrong source or field")
    if cross.left_objects != (axis,) or hasattr(cross.hits[0], "motion"):
      raise ValueError("Installed cross-axis selection or static contract changed")
    for language in ("en", "zh-CN"):
      selected: Literal["en", "zh-CN"] = language
      concept = catalog.concept(f"axis.{axis.value}")
      name = concept.name.text(selected)
      if (
        concept.configuration is not axis
        or name is None
        or name not in astrology.format_chart(natal, catalog, language=selected)
      ):
        raise ValueError("Installed axis vocabulary or text binding is missing")
    bad = cast(Any, axis)
    for call in (
      partial(astrology.ChartConfig, source.requested.house_system, (bad,), ()),
      partial(astrology.EclipticPosition, bad, 10, 0, 1, 1),
      partial(astrology.Placement, bad, astrology.Sign.ARIES, 10, 1),
      partial(astrology.chart_sign_distribution, source, objects=(bad,)),
    ):
      try:
        call()
      except TypeError:
        pass
      else:
        raise ValueError("Installed narrow boundary admitted an axis")
  exact = astrology.find_aspects(
    (
      astrology.AspectObject(astrology.Axis.ASCENDANT, 10, None),
      astrology.AspectObject(astrology.Axis.DESCENDANT, 190, None),
    ),
    (astrology.AspectRule(astrology.MajorAspect.OPPOSITION, 0),),
  )
  if len(exact) != 1 or exact[0].motion is not astrology.AspectMotion.EXACT:
    raise ValueError("Installed opposite-axis exactness or pair admission changed")


def _check_summaries() -> None:
  """Exercise pure and composed summaries with independent synthetic expectations.

  用独立的合成期望核验纯查询及命盘组合摘要。
  """
  catalog = astrology.load_catalog()
  chart = _cross_source(2000, "summary", ((astrology.Body.MOON, 100), (astrology.Body.SUN, 10)))
  result = astrology.chart_sign_distribution(
    chart, objects=(astrology.Body.SUN, astrology.Body.MOON)
  )
  if (
    result.objects != (astrology.Body.MOON, astrology.Body.SUN)
    or result.total != 2
    or result.element_counts
    != {
      astrology.Element.FIRE: 1,
      astrology.Element.EARTH: 0,
      astrology.Element.AIR: 0,
      astrology.Element.WATER: 1,
    }
    or result.modality_counts[astrology.Modality.CARDINAL] != 2
    or result.element_proportions[astrology.Element.FIRE] != 0.5
    or result.modality_proportions[astrology.Modality.CARDINAL] != 1
    or astrology.sign_distribution(chart.placements) != result
    or astrology.element_of(astrology.Sign.ARIES) is not astrology.Element.FIRE
    or astrology.modality_of(astrology.Sign.CANCER) is not astrology.Modality.CARDINAL
  ):
    raise ValueError("Installed sign summary differs from hand-worked population")
  phase = astrology.natal_lunar_phase(chart)
  if (
    phase != astrology.lunar_phase(sun_longitude_deg=10, moon_longitude_deg=100)
    or phase.elongation_deg != 90
    or phase.phase is not astrology.LunationType.FIRST_QUARTER
    or phase.direction != "waxing"
    or phase.rule_id != "rule.lunation.rudhyar1950"
  ):
    raise ValueError("Installed lunar phase differs from hand-worked arc")
  for language, object_name, phase_name in (
    ("en", "Sun [sun]", "First Quarter Type"),
    ("zh-CN", "太阳 [sun]", "上弦月型"),
  ):
    selected: Literal["en", "zh-CN"] = language  # type: ignore[assignment]
    text = astrology.format_sign_distribution(result, catalog, language=selected)
    if object_name not in text or "1/2 | 50.00%" not in text:
      raise ValueError("Installed distribution text is incomplete")
    if phase_name not in astrology.format_lunar_phase(phase, catalog, language=selected):
      raise ValueError("Installed phase text is incomplete")
  for call in (
    lambda: astrology.chart_sign_distribution(chart, objects=()),
    lambda: astrology.chart_sign_distribution(chart, objects=(astrology.Body.PLUTO,)),
    lambda: astrology.lunar_phase(True, 0),
  ):
    try:
      call()
    except (TypeError, ValueError):
      pass
    else:
      raise ValueError("Installed summary accepted an invalid input")


def _check_dignities() -> None:
  """Check installed rulership, simultaneous/empty/missing statuses and text.

  核验安装包的守护、并存、空及缺失状态与文本。
  """
  sun, mercury, mars = astrology.Body.SUN, astrology.Body.MERCURY, astrology.Body.MARS
  chart = _cross_source(2000, "rulers", ((mercury, 150), (sun, 30), (mars, 280)))
  result = astrology.HouseRulers(chart)
  status = astrology.DignityStatus
  expected_rulers = (
    mars,
    astrology.Body.VENUS,
    mercury,
    astrology.Body.MOON,
    sun,
    mercury,
    astrology.Body.VENUS,
    mars,
    astrology.Body.JUPITER,
    astrology.Body.SATURN,
    astrology.Body.SATURN,
    astrology.Body.JUPITER,
  )
  if (
    tuple(astrology.sign_ruler(sign) for sign in astrology.Sign) != expected_rulers
    or astrology.essential_dignities(mercury, astrology.Sign.VIRGO)
    != (status.DOMICILE, status.EXALTATION)
    or astrology.essential_dignities(mercury, astrology.Sign.PISCES)
    != (status.DETRIMENT, status.FALL)
    or astrology.essential_dignities(sun, astrology.Sign.TAURUS) != ()
  ):
    raise ValueError("Installed dignity queries differ from sourced sign expectations")
  if (
    result.chart is not chart
    or result.rule_id != "rule.lilly1647.essential_dignities"
    or tuple(r.house for r in result.houses) != tuple(range(1, 13))
    or tuple(r.ruler for r in result.houses) != expected_rulers
    or result.houses[5].placement is not chart.placements[0]
    or result.houses[5].statuses != (status.DOMICILE, status.EXALTATION)
    or result.houses[4].statuses != ()
    or result.houses[9].placement is not None
    or result.houses[9].statuses is not None
  ):
    raise ValueError("Installed house rulers lost source, placements or status distinctions")
  catalog = astrology.load_catalog()
  entry = catalog.entry("entry.essential_dignities")
  variant = catalog.variant(result.rule_id)
  source = catalog.source("source.lilly.christian-astrology-1647")
  status_concepts = catalog.list_concepts(kind=ConceptKind.DIGNITY_STATUS)
  status_ids = {f"dignity_status.{s.value}" for s in status}
  linked = (
    status_ids
    | {f"sign.{s.value}" for s in astrology.Sign}
    | {f"body.{b.value}" for b in expected_rulers}
  )
  if (
    entry.rule_ids != (result.rule_id,)
    or set(entry.concept_ids) != linked
    or set(variant.concept_ids) != linked
    or variant.configuration is not None
    or {c.identifier for c in status_concepts} != status_ids
    or any(c.configuration is not None for c in status_concepts)
    or entry.prerequisite_status.value != "complete"
    or entry.output_eligibility.value != "reference_only"
    or entry.chart_applicability != "not_assessed"
    or source.verification.value != "verified"
    or {c.source_id for c in entry.citations} != {source.identifier}
  ):
    raise ValueError("Installed dignity knowledge lost rule/source links or reference status")
  for language, labels in (
    ("en", ("Domicile, Exaltation", "None of these four", "Not calculated")),
    ("zh-CN", ("入庙, 擢升", "这四项均未命中", "未计算")),
  ):
    selected: Literal["en", "zh-CN"] = language  # type: ignore[assignment]
    text = astrology.format_house_rulers(result, catalog, language=selected)
    if len(text.splitlines()) != 16 or any(label not in text for label in labels):
      raise ValueError("Installed house-ruler text is incomplete")
    expected_row = (
      "1 | Aries | Mars | Capricorn 10.0° / House 10 | Exaltation"
      if language == "en"
      else "1 | 白羊座 | 火星 | 摩羯座 10.0° / 宫位 10 | 擢升"
    )
    if text.splitlines()[4] != expected_row:
      raise ValueError("Installed house-ruler placement text differs from the supplied placement")
  for call, error in (
    (lambda: astrology.sign_ruler("aries"), TypeError),  # type: ignore[arg-type]
    (lambda: astrology.essential_dignities(astrology.Body.PLUTO, astrology.Sign.ARIES), ValueError),
    (lambda: astrology.HouseRuler(True, astrology.Sign.ARIES, None), TypeError),
    (lambda: astrology.HouseRulers(None), TypeError),  # type: ignore[arg-type]
  ):
    try:
      call()
    except error:
      pass
    else:
      raise ValueError("Installed dignity checks accepted an invalid input")


def _check_native_isolation() -> None:
  if any(
    name in ("celestial_calendar", "astrology.celestial") or name.startswith("celestial_calendar.")
    for name in sys.modules
  ):
    raise ValueError("Import initialized the astronomy adapter")


def _check_knowledge(expected_corpus_version: str | None = None) -> None:
  before = set(sys.modules)
  resource = files("astrology.knowledge").joinpath("catalog.json")
  if not Path(str(resource)).resolve().is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Knowledge resource is outside the consumer environment")
  catalog = astrology.load_catalog()
  if expected_corpus_version is not None and catalog.version != expected_corpus_version:
    raise ValueError("Installed corpus version differs from the source corpus")
  if (
    catalog.lookup("Sol") != catalog.lookup("日轮")
    or catalog.lookup("日轮")[0].identifier != "body.sun"
  ):
    raise ValueError("Installed bilingual lookup did not preserve identity")
  if (
    not catalog.list_concepts()
    or catalog.concept("body.sun").configuration is not astrology.Body.SUN
    or "body.sun" not in catalog.entry("entry.body_requests").concept_ids
    or tuple(v.identifier for v in catalog.list_variants(concept_id="body.sun"))
    != ("rule.lilly1647.essential_dignities",)
  ):
    raise ValueError("Installed knowledge listing is empty")
  if (
    catalog.variant("rule.house.whole_sign").configuration is not astrology.HouseSystem.WHOLE_SIGN
    or catalog.variant("rule.node_definition.mean").configuration
    is not astrology.NodeDefinition.MEAN
    or catalog.variant("rule.aspect.conjunction").configuration
    is not astrology.MajorAspect.CONJUNCTION
  ):
    raise ValueError("Installed knowledge lost a named rule configuration")
  if not catalog.filter_sources(verification=SourceVerification.VERIFIED):
    raise ValueError("Installed source filtering lost verified sources")
  entry = catalog.entry("entry.equinoctial_example")
  if entry not in catalog.filter_entries(source_id="source.ptolemy.ashmand1822"):
    raise ValueError("Installed entry filtering lost the worked source example")
  citation, source = catalog.citations(entry.identifier)[0]
  if source.verification is not SourceVerification.VERIFIED or citation.excerpt is None:
    raise ValueError("Installed citations lost source verification or original text")
  if citation.excerpt.zh is None or not citation.excerpt.en.endswith(
    "makes the day and night equal."
  ):
    raise ValueError("Installed source example lost a translation or source condition")
  if (
    entry.prerequisite_status is not PrerequisiteStatus.UNRESOLVED
    or entry.output_eligibility is not OutputEligibility.REFERENCE_ONLY
    or entry.chart_applicability != "not_assessed"
  ):
    raise ValueError(
      "Installed retrieval collapsed editorial states or claimed chart applicability"
    )
  groups = tuple(astrology.ashmand_sign_group(sign) for sign in astrology.Sign)
  if (
    len(astrology.AshmandSignGroup) != 4
    or any(type(group) is not astrology.AshmandSignGroup for group in groups)
    or sorted(groups.count(group) for group in astrology.AshmandSignGroup) != [2, 2, 4, 4]
  ):
    raise ValueError("Installed Ashmand lookup lost its four-group partition")
  group_concepts = tuple(
    catalog.concept(f"sign_group.ashmand1822.{group.value}") for group in astrology.AshmandSignGroup
  )
  expected_ids = {f"sign.{sign.value}" for sign in astrology.Sign} | {
    concept.identifier for concept in group_concepts
  }
  historical = catalog.entry("entry.ashmand_sign_groups")
  if (
    set(historical.concept_ids) != expected_ids
    or historical.rule_ids != ("rule.ptolemy_ashmand.sign_groups",)
    or set(catalog.variant(historical.rule_ids[0]).concept_ids) != expected_ids
    or historical.prerequisite_status is not PrerequisiteStatus.COMPLETE
    or historical.output_eligibility is not OutputEligibility.REFERENCE_ONLY
    or historical.chart_applicability != "not_assessed"
  ):
    raise ValueError("Installed Ashmand knowledge lost rule links or separate editorial states")
  excerpts = [c.excerpt for c in historical.citations if c.excerpt is not None]
  if len(excerpts) != 3 or any(text.zh is None or not text.translation_credit for text in excerpts):
    raise ValueError("Installed Ashmand definitions lost credited translations")
  overlay = catalog.entry("entry.cross_house_overlays")
  overlay_rule = catalog.variant("rule.project.cross_house_overlays")
  overlay_ids = {f"house.{system.value}" for system in astrology.HouseSystem} | {
    f"axis.{axis.value}" for axis in astrology.Axis
  }
  overlay_citation, overlay_source = catalog.citations(overlay.identifier)[0]
  if (
    overlay.rule_ids != (overlay_rule.identifier, "rule.project.cusp_ownership")
    or set(overlay.concept_ids) != overlay_ids
    or set(overlay_rule.concept_ids) != overlay_ids
    or overlay_rule.configuration is not None
    or overlay.prerequisite_status is not PrerequisiteStatus.COMPLETE
    or overlay.output_eligibility is not OutputEligibility.REFERENCE_ONLY
    or overlay.chart_applicability != "not_assessed"
    or overlay_source.identifier != "source.astrology.house_overlays.f269d14"
    or not overlay_source.url.endswith("/f269d148b8a3e58bc559e7d89be77a03aae6b289")
    or overlay_source.verification is not SourceVerification.VERIFIED
    or overlay_citation.excerpt is not None
    or overlay_rule.definition.status("zh-CN") is not TranslationStatus.CURRENT
    or overlay.statement.status("zh-CN") is not TranslationStatus.CURRENT
  ):
    raise ValueError("Installed overlay knowledge lost rule links, source or editorial states")
  aliases = ["isolated alias"]
  concept = replace(catalog.concepts[0], en_aliases=aliases)
  aliases.clear()
  if tuple(concept.en_aliases) != ("isolated alias",):
    raise ValueError("Installed knowledge retained a caller-owned alias list")
  try:
    Catalog(
      catalog.version,
      (*catalog.concepts, catalog.concepts[0]),
      catalog.variants,
      catalog.sources,
      catalog.entries,
    )
  except ValueError:
    pass
  else:
    raise ValueError("Installed catalog accepted duplicate identities")
  if any(
    name.startswith(("tzdata", "zoneinfo", "celestial", "ctypes"))
    for name in set(sys.modules) - before
  ):
    raise ValueError("Knowledge query initialized time or native machinery")
  _check_native_isolation()


def _check_birth_and_configuration() -> None:
  record = astrology.BirthRecord(
    date(2026, 4, 5),
    time(1, 45),
    astrology.IanaTimezone("Australia/Lord_Howe"),
    astrology.Location(0, 0),
    astrology.TimePrecision.MINUTE,
    {"record": "synthetic"},
  )
  try:
    astrology.resolve_birth_time(record)
  except astrology.AmbiguousBirthTimeError:
    pass
  else:
    raise ValueError("Installed time resolution did not reject an ambiguous input")
  expected = (datetime(2026, 4, 4, 14, 45, tzinfo=UTC), datetime(2026, 4, 4, 15, 15, tzinfo=UTC))
  folds: tuple[Literal[0, 1], ...] = (0, 1)
  for fold in folds:
    result = astrology.prepare_natal_input(record, fold=fold)
    if result.utc != expected[fold] or result.record != record or result.fold != fold:
      raise ValueError("Installed birth API did not preserve the selected fold and record")
    if result.timezone_source != "tzdata" or result.timezone_key != "Australia/Lord_Howe":
      raise ValueError("Installed time resolution did not identify the IANA data source")
    if result.tzdata_version != version("tzdata"):
      raise ValueError("Installed time resolution misreported the tzdata package version")
    if result.iana_version != import_module("tzdata").IANA_VERSION:
      raise ValueError("Installed time resolution misreported the IANA release")

  fixed = astrology.BirthRecord(
    date(2026, 4, 5), time(0, 15), astrology.FixedOffset(timedelta(minutes=345))
  )
  result = astrology.resolve_birth_time(fixed)
  if result.utc != datetime(2026, 4, 4, 18, 30, tzinfo=UTC):
    raise ValueError("Installed fixed-offset resolution did not preserve UTC date rollover")
  if result.timezone_source != "fixed_offset" or any(
    value is not None
    for value in (result.timezone_key, result.fold, result.tzdata_version, result.iana_version)
  ):
    raise ValueError("Installed fixed-offset resolution claimed timezone-database provenance")
  try:
    astrology.prepare_natal_input(fixed)
  except astrology.MissingBirthDataError:
    pass
  else:
    raise ValueError("Installed natal preparation accepted a missing location")
  try:
    astrology.Location(float("nan"), 0)
  except ValueError:
    pass
  else:
    raise ValueError("Installed coordinate validation accepted NaN")

  objects: list[astrology.Body | astrology.LunarNode] = [
    astrology.Body.SUN,
    astrology.LunarNode.MEAN_ASCENDING,
  ]
  config = astrology.ChartConfig(astrology.HouseSystem.PLACIDUS, objects, ())
  objects.clear()
  if config.objects != (astrology.Body.SUN, astrology.LunarNode.MEAN_ASCENDING):
    raise ValueError("Installed configuration retained a mutable input alias")
  if config.house_system is not astrology.HouseSystem.PLACIDUS:
    raise ValueError("Installed configuration substituted the requested house system")


def _check_natal_chart(expected_observations: Path | None = None) -> None:
  """Calculate one synthetic natal chart in the installed environment.

  The chart is calculated after the isolation checks, so it also shows that the
  adapter is loaded by the calculation and not by the import.

  在已安装的环境里计算一张合成本命盘。这一步排在隔离检查之后，因此也能说明适配层是由
  计算加载的，而不是由导入加载的。
  """
  if any(
    name in ("celestial_calendar", "astrology.celestial") or name.startswith("celestial_calendar.")
    for name in sys.modules
  ):
    raise ValueError("Chart calculation started with the astronomy adapter already loaded")
  chart = acceptance_chart()
  if len(chart.positions) != 11 or chart.houses.system is not astrology.HouseSystem.WHOLE_SIGN:
    raise ValueError("Installed chart calculation did not return the requested result")
  if chart.provenance.celestial_version != version("celestial-calendar"):
    raise ValueError("Installed chart misreported the astronomy library version")
  if chart.provenance.astrology_version != distribution("celestial-astrology").version:
    raise ValueError("Installed chart misreported the astrology distribution version")
  if chart.effective.delta_t_model != "algo5":
    raise ValueError("Installed chart misreported the delta T model")
  adapter = Path(str(import_module("astrology.celestial").__file__)).resolve()
  if not adapter.is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Imported astrology.celestial from outside the consumer environment")
  if {hit.orb_limit_deg for hit in chart.aspects} != {6.0, 8.0}:
    raise ValueError("Installed aspects did not exercise per-object orbs")
  if chart.effective.aspect_objects != tuple(astrology.Body):
    raise ValueError("Installed aspect participants lost requested object order")
  if expected_observations is not None and chart_observations(
    chart
  ) != expected_observations.read_text(encoding="utf-8"):
    raise ValueError("Installed chart differs from the development entry point")
  catalog = astrology.load_catalog()
  if "Sun [sun]" not in astrology.format_chart(chart, catalog):
    raise ValueError("Installed English chart output is incomplete")
  if "太阳 [sun]" not in astrology.format_chart(chart, catalog, language="zh-CN"):
    raise ValueError("Installed Chinese chart output is incomplete")
  axis_chart = astrology.natal_chart(
    chart.resolved,
    replace(
      chart.requested,
      aspects=(astrology.AspectRule(astrology.MajorAspect.OPPOSITION, 1),),
      aspect_objects=tuple(astrology.Axis),
      orb_combination=None,
    ),
  )
  if axis_chart.positions != chart.positions or axis_chart.effective.aspect_objects != tuple(
    astrology.Axis
  ):
    raise ValueError("Installed native composition changed raw outputs or lost selected axes")
  if {(hit.first, hit.second) for hit in axis_chart.aspects} != {
    (astrology.Axis.ASCENDANT, astrology.Axis.DESCENDANT),
    (astrology.Axis.MIDHEAVEN, astrology.Axis.IMUM_COELI),
  }:
    raise ValueError("Installed native composition lost an opposite-axis pair")
  polar = replace(
    chart.resolved, record=replace(chart.resolved.record, location=astrology.Location(75, 0))
  )
  try:
    astrology.natal_chart(
      polar, replace(chart.requested, house_system=astrology.HouseSystem.PLACIDUS)
    )
  except astrology.ChartDomainError as exc:
    if exc.house_system is not astrology.HouseSystem.PLACIDUS:
      raise ValueError("Installed domain failure lost the requested house system") from exc
  else:
    raise ValueError("Installed Placidus calculation did not report undefined geometry")


def check_missing_metadata() -> None:
  """Check import, knowledge and calculation with project metadata hidden.

  隐藏项目分发包元数据后，检查导入、知识查询和计算。
  """
  package = "celestial-astrology"
  _check_knowledge()
  _check_native_isolation()
  _check_cross_chart()
  try:
    distribution(package)
  except PackageNotFoundError:
    pass
  else:
    raise ValueError("Missing-metadata case still has installed metadata")
  try:
    acceptance_chart()
  except PackageNotFoundError as exc:
    if exc.name != package:
      raise ValueError("Calculation reported a different missing distribution") from exc
  else:
    raise ValueError("Calculation invented an installed distribution version")
  print(f"Missing {package} metadata rejected; optimized={sys.flags.optimize}")


def main(
  expected_version: str,
  *,
  expected_corpus_version: str | None = None,
  knowledge_only: bool = False,
  expected_observations: Path | None = None,
  expected_cross_observations: Path | None = None,
) -> None:
  """Check installed identity, API and isolation; compare a supplied corpus version.

  None skips corpus comparison. CLI: CODE_VERSION CORPUS_VERSION [--knowledge-only]
  [--expected-observations PATH] [--expected-cross-observations PATH]. Optional
  check-run files hold exact source observations, including raw numbers, input,
  configuration and provenance for natal and comparison results, plus bilingual
  comparison text.

  检查安装包身份、API 及隔离，并比较传入的语料版本。None 跳过语料版本比较。
  CLI 参数顺序：CODE_VERSION CORPUS_VERSION [--knowledge-only] [--expected-observations PATH]。
  另可给 --expected-cross-observations PATH。可选的本次检查文件分别保存本命及双盘的源码
  精确检查值，包括原始数值、输入、配置和来源，以及双语比较文本。
  """
  metadata = distribution("celestial-astrology")
  for module in (astrology, *(import_module("astrology." + name) for name in MODULES)):
    origin = Path(str(module.__file__)).resolve()
    if not origin.is_relative_to(Path(sys.prefix).resolve()):
      raise ValueError(f"Imported {module.__name__} from outside the consumer environment")
  if metadata.version != expected_version:
    raise ValueError("Installed version differs from the built version")
  if not Path(str(astrology.__file__)).with_name("py.typed").is_file():
    raise ValueError("Installed package is missing py.typed")
  _check_native_isolation()
  _check_knowledge(expected_corpus_version)
  if knowledge_only:
    _check_summaries()
    _check_dignities()
    _check_axes()
    if any(name.startswith(("tzdata", "zoneinfo", "celestial", "ctypes")) for name in sys.modules):
      raise ValueError("Knowledge-only consumer loaded time or native machinery")
    print(f"Installed knowledge corpus; optimized={sys.flags.optimize}")
    return
  _check_birth_and_configuration()
  _check_axes()
  _check_summaries()
  _check_dignities()
  _check_native_isolation()
  _check_cross_chart(expected_cross_observations)
  _check_natal_chart(expected_observations)
  print(f"Installed celestial-astrology {metadata.version}; optimized={sys.flags.optimize}")


if __name__ == "__main__":
  if sys.argv[1] == "--missing-metadata":
    check_missing_metadata()
  else:
    main(
      sys.argv[1],
      expected_corpus_version=sys.argv[2],
      knowledge_only="--knowledge-only" in sys.argv[3:],
      expected_observations=Path(sys.argv[sys.argv.index("--expected-observations") + 1])
      if "--expected-observations" in sys.argv[3:]
      else None,
      expected_cross_observations=Path(
        sys.argv[sys.argv.index("--expected-cross-observations") + 1]
      )
      if "--expected-cross-observations" in sys.argv[3:]
      else None,
    )
