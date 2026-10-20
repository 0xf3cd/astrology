"""Verify the installed package in isolation. 隔离验证已安装的包。"""

import sys
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from importlib.metadata import distribution, version
from importlib.resources import files
from pathlib import Path
from typing import Literal

import astrology
from astrology.knowledge import Catalog, OutputEligibility, PrerequisiteStatus, SourceVerification


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
  if not catalog.list_concepts() or not catalog.list_variants(concept_id="body.sun"):
    raise ValueError("Installed knowledge listing is empty")
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
  from dataclasses import replace

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


def _check_natal_chart() -> None:
  """Calculate one synthetic natal chart in the installed environment.

  The chart is calculated after the isolation checks, so it also shows that the
  adapter is loaded by the calculation and not by the import. 在已安装环境中计算一张
  合成本命盘；此检查排在隔离检查之后，因此也表明适配层由计算加载，而非由导入加载。

  在已安装环境中计算一张合成本命盘。
  """
  if any(
    name in ("celestial_calendar", "astrology.celestial") or name.startswith("celestial_calendar.")
    for name in sys.modules
  ):
    raise ValueError("Chart calculation started with the astronomy adapter already loaded")
  record = astrology.BirthRecord(
    date(2026, 4, 5),
    time(1, 45),
    astrology.IanaTimezone("Australia/Lord_Howe"),
    astrology.Location(0, 0),
    astrology.TimePrecision.MINUTE,
    {"record": "synthetic"},
  )
  resolved = astrology.prepare_natal_input(record, fold=0)
  config = astrology.ChartConfig(astrology.HouseSystem.WHOLE_SIGN, (astrology.Body.SUN,), ())
  chart = astrology.natal_chart(resolved, config)
  if len(chart.positions) != 1 or chart.houses.system is not astrology.HouseSystem.WHOLE_SIGN:
    raise ValueError("Installed chart calculation did not return the requested result")
  if chart.provenance.celestial_version != version("celestial-calendar"):
    raise ValueError("Installed chart misreported the astronomy library version")
  if chart.effective.delta_t_model != "algo5":
    raise ValueError("Installed chart misreported the delta T model")


def main(
  expected_version: str, *, expected_corpus_version: str | None = None, knowledge_only: bool = False
) -> None:
  """Check installed identity, API and isolation; compare a supplied corpus version.

  None skips corpus comparison. CLI: CODE_VERSION CORPUS_VERSION [--knowledge-only].

  检查安装包身份、API 及隔离，并比较传入的语料版本。None 跳过语料版本比较。
  CLI 参数顺序：CODE_VERSION CORPUS_VERSION [--knowledge-only]。
  """
  metadata = distribution("astrology")
  for module in (
    astrology,
    *(
      import_module("astrology." + name)
      for name in (
        "birth",
        "chart",
        "config",
        "houses",
        "knowledge",
        "knowledge.catalog",
        "knowledge.records",
        "zodiac",
      )
    ),
  ):
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
  _check_natal_chart()
  print(f"Installed astrology {metadata.version}; optimized={sys.flags.optimize}")


if __name__ == "__main__":
  main(
    sys.argv[1],
    expected_corpus_version=sys.argv[2],
    knowledge_only="--knowledge-only" in sys.argv[3:],
  )
