"""Verify the installed package in isolation. 隔离验证已安装的包。"""

import json
import sys
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from importlib.metadata import distribution, version
from importlib.resources import files
from pathlib import Path
from typing import Literal

import astrology
from astrology.knowledge import Catalog, OutputEligibility, PrerequisiteStatus, SourceVerification

MODULES = (
  "_validation",
  "aspects",
  "birth",
  "chart",
  "config",
  "houses",
  "knowledge",
  "knowledge.catalog",
  "knowledge.records",
  "serialization",
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


def _check_natal_chart(expected_chart: Path | None = None) -> None:
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
  if chart.effective.delta_t_model != "algo5":
    raise ValueError("Installed chart misreported the delta T model")
  adapter = Path(str(import_module("astrology.celestial").__file__)).resolve()
  if not adapter.is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Imported astrology.celestial from outside the consumer environment")
  if {hit.orb_limit_deg for hit in chart.aspects} != {6.0, 8.0}:
    raise ValueError("Installed aspects did not exercise per-object orbs")
  if chart.effective.aspect_objects != tuple(astrology.Body):
    raise ValueError("Installed aspect participants lost requested object order")
  packed = astrology.dumps_chart(chart)
  if expected_chart is not None and packed != expected_chart.read_text(encoding="utf-8"):
    raise ValueError("Installed chart differs from the development entry point")
  restored = astrology.loads_chart(packed)
  if restored != chart or astrology.dumps_chart(restored) != packed:
    raise ValueError("Installed chart restoration lost stored values")
  unsupported_schema = json.loads(packed)
  unsupported_schema["schema_version"] = 2
  duplicate_schema = packed.replace(
    '"schema_version": 1', '"schema_version": 1, "schema_version": 1'
  )
  for invalid_record in (json.dumps(unsupported_schema), duplicate_schema):
    try:
      astrology.loads_chart(invalid_record)
    except astrology.ChartRecordError:
      pass
    else:
      raise ValueError("Installed restoration accepted an unsupported schema or duplicate key")
  if astrology.recompute_chart(restored) != chart:
    raise ValueError("Installed replay differs from the calculated chart")
  catalog = astrology.load_catalog()
  if "Sun [sun]" not in astrology.format_chart(chart, catalog):
    raise ValueError("Installed English chart output is incomplete")
  if "太阳 [sun]" not in astrology.format_chart(chart, catalog, language="zh-CN"):
    raise ValueError("Installed Chinese chart output is incomplete")
  unsupported = replace(chart, effective=replace(chart.effective, delta_t_model="unavailable"))
  try:
    astrology.recompute_chart(astrology.loads_chart(astrology.dumps_chart(unsupported)))
  except astrology.ChartReplayError:
    pass
  else:
    raise ValueError("Installed replay silently substituted an unavailable model")
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


def main(
  expected_version: str,
  *,
  expected_corpus_version: str | None = None,
  knowledge_only: bool = False,
  expected_chart: Path | None = None,
) -> None:
  """Check installed identity, API and isolation; compare a supplied corpus version.

  None skips corpus comparison. CLI: CODE_VERSION CORPUS_VERSION [--knowledge-only]
  [--expected-chart PATH]. The chart file holds development-entry-point JSON.

  检查安装包身份、API 及隔离，并比较传入的语料版本。None 跳过语料版本比较。
  CLI 参数顺序：CODE_VERSION CORPUS_VERSION [--knowledge-only] [--expected-chart PATH]。
  命盘文件保存开发入口产出的 JSON。
  """
  metadata = distribution("astrology")
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
  _check_natal_chart(expected_chart)
  print(f"Installed astrology {metadata.version}; optimized={sys.flags.optimize}")


if __name__ == "__main__":
  main(
    sys.argv[1],
    expected_corpus_version=sys.argv[2],
    knowledge_only="--knowledge-only" in sys.argv[3:],
    expected_chart=Path(sys.argv[sys.argv.index("--expected-chart") + 1])
    if "--expected-chart" in sys.argv[3:]
    else None,
  )
