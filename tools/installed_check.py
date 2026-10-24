"""Verify the installed package in isolation. 隔离验证已安装的包。"""

import json
import sys
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from importlib.metadata import PackageNotFoundError, distribution, version
from importlib.resources import files
from pathlib import Path
from typing import Literal

import astrology
from astrology.knowledge import Catalog, OutputEligibility, PrerequisiteStatus, SourceVerification

MODULES = (
  "_distribution",
  "_validation",
  "aspects",
  "birth",
  "chart",
  "config",
  "houses",
  "knowledge",
  "knowledge.catalog",
  "knowledge.records",
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
    or catalog.list_variants(concept_id="body.sun") != ()
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
  if catalog.filter_entries(source_id="source.ptolemy.ashmand1822")[-1] != entry:
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
) -> None:
  """Check installed identity, API and isolation; compare a supplied corpus version.

  None skips corpus comparison. CLI: CODE_VERSION CORPUS_VERSION [--knowledge-only]
  [--expected-observations PATH]. The optional check-run file holds exact source
  observations, including raw numbers, input, configuration and provenance.

  检查安装包身份、API 及隔离，并比较传入的语料版本。None 跳过语料版本比较。
  CLI 参数顺序：CODE_VERSION CORPUS_VERSION [--knowledge-only] [--expected-observations PATH]。
  可选的本次检查文件包含源码产出的精确检查值，包括原始数值、输入、配置和来源。
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
    if any(name.startswith(("tzdata", "zoneinfo", "celestial", "ctypes")) for name in sys.modules):
      raise ValueError("Knowledge-only consumer loaded time or native machinery")
    print(f"Installed knowledge corpus; optimized={sys.flags.optimize}")
    return
  _check_birth_and_configuration()
  _check_native_isolation()
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
    )
