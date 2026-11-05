"""Verify the installed package in isolation. 隔离验证已安装的包。"""

import builtins
import json
import sys
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from importlib.metadata import PackageNotFoundError, distribution, version
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

import astrology
from astrology.knowledge import Catalog


def module_names() -> tuple[str, ...]:
  """Discover installed Python modules, deferring the astronomy adapter.

  The consumer imports these modules; the source-side package inventory
  independently detects files omitted from a distribution.

  查找安装包中的 Python 模块，天文适配层留待显式计算时导入。
  消费者导入这些模块；源码侧的包清单独立检测分发包遗漏的文件。
  """
  names = set()
  for directory in astrology.__path__:
    root = Path(directory)
    for path in root.rglob("*.py"):
      relative = path.relative_to(root)
      if "__pycache__" in relative.parts:
        continue
      parts = relative.with_suffix("").parts
      if parts[-1] == "__init__":
        parts = parts[:-1]
      if parts and parts != ("celestial",):
        names.add(".".join(parts))
  return tuple(sorted(names))


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
  """Capture exact same-revision check values.

  取得同一源码修订的精确检查值。
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


def acceptance_transits(chart: astrology.NatalChart) -> astrology.TransitHits:
  """Calculate the same selected transit search in both environments.

  在两个环境中执行同一组所选行运搜索。
  """
  return astrology.transit_hits(
    chart,
    start_utc=datetime(2024, 4, 1, tzinfo=UTC),
    end_utc=datetime(2024, 4, 10, tzinfo=UTC),
    moving_objects=(astrology.Body.SUN,),
    natal_objects=(astrology.Body.SUN, astrology.Axis.ASCENDANT),
    aspects=(astrology.MajorAspect.CONJUNCTION, astrology.MajorAspect.SQUARE),
  )


def calculation_observations(
  chart: astrology.NatalChart,
  transits: astrology.TransitHits,
) -> str:
  """Capture supplied natal and transit values without recalculating them.

  记录给定的本命及行运值，不重新计算。
  """
  return json.dumps(
    {"chart": json.loads(chart_observations(chart)), "transits": repr(transits)},
    sort_keys=True,
    allow_nan=False,
  )


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
  """Compare two synthetic in-memory sources.

  比较两张合成内存源盘。
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
  catalog = astrology.load_catalog()
  original_import = builtins.__import__

  def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
    if name == "astrology.celestial" or name.startswith(
      ("celestial_calendar", "tzdata", "zoneinfo")
    ):
      raise ValueError("Supplied comparison attempted to initialize astronomy or time data")
    return original_import(name, *args, **kwargs)

  builtins.__import__ = guarded
  try:
    observed = comparison_observations(
      acceptance_cross_aspects(), acceptance_house_overlays(), catalog
    )
  finally:
    builtins.__import__ = original_import
  if expected_observations is not None and observed != expected_observations.read_text(
    encoding="utf-8"
  ):
    raise ValueError("Installed comparison observations differ from the development entry point")
  _check_native_isolation()


def _check_native_isolation() -> None:
  if any(
    name in ("celestial_calendar", "astrology.celestial") or name.startswith("celestial_calendar.")
    for name in sys.modules
  ):
    raise ValueError("Import initialized the astronomy adapter")


def _check_knowledge() -> None:
  before = set(sys.modules)
  resource = files("astrology.knowledge").joinpath("catalog.json")
  if not Path(str(resource)).resolve().is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Knowledge resource is outside the consumer environment")
  catalog = astrology.load_catalog()
  catalog.lookup("Sol")
  catalog.lookup("日轮")
  catalog.citations("entry.equinoctial_example")
  if any(
    name.startswith(("tzdata", "zoneinfo", "celestial", "ctypes"))
    for name in set(sys.modules) - before
  ):
    raise ValueError("Knowledge query initialized time or native machinery")
  _check_native_isolation()


def _check_natal_chart(expected_observations: Path | None = None) -> None:
  """Calculate a synthetic natal chart and transits in the installed environment.

  The chart is calculated after the isolation checks, so it also shows that the
  adapter is loaded by the calculation and not by the import.

  在已安装的环境里计算合成本命盘及行运。这一步排在隔离检查之后，因此也能说明适配层是由
  计算加载的，而不是由导入加载的。
  """
  _check_native_isolation()
  chart = acceptance_chart()
  if chart.provenance.celestial_version != version("celestial-calendar"):
    raise ValueError("Installed chart misreported the astronomy library version")
  if chart.provenance.astrology_version != distribution("celestial-astrology").version:
    raise ValueError("Installed chart misreported the astrology distribution version")
  adapter = Path(str(import_module("astrology.celestial").__file__)).resolve()
  if not adapter.is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Imported astrology.celestial from outside the consumer environment")
  transits = acceptance_transits(chart)
  if expected_observations is not None and calculation_observations(
    chart, transits
  ) != expected_observations.read_text(encoding="utf-8"):
    raise ValueError("Installed chart differs from the development entry point")


def check_missing_metadata() -> None:
  """Check import, knowledge and calculation with project metadata hidden.

  Script CLI: --missing-metadata alone, without CODE_VERSION.

  隐藏项目分发包元数据后，检查导入、知识查询和计算。
  脚本 CLI：只传 --missing-metadata，不传 CODE_VERSION。
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
  knowledge_only: bool = False,
  expected_observations: Path | None = None,
  expected_cross_observations: Path | None = None,
) -> None:
  """Check installed identity and isolation; compare optional source observations.

  CLI: CODE_VERSION [--knowledge-only] [--expected-observations PATH]
  [--expected-cross-observations PATH]. Observation files contain raw natal and
  comparison values, input/configuration/provenance, and bilingual comparison text.

  检查安装包身份与隔离，并比较可选的源码检查值。
  CLI 参数：CODE_VERSION [--knowledge-only] [--expected-observations PATH]
  [--expected-cross-observations PATH]。检查文件包含本命及双盘的原始数值、输入、配置、
  来源，以及双语比较文本。
  """
  metadata = distribution("celestial-astrology")
  for module in (astrology, *(import_module("astrology." + name) for name in module_names())):
    origin = Path(str(module.__file__)).resolve()
    if not origin.is_relative_to(Path(sys.prefix).resolve()):
      raise ValueError(f"Imported {module.__name__} from outside the consumer environment")
  if metadata.version != expected_version:
    raise ValueError("Installed version differs from the built version")
  if not Path(str(astrology.__file__)).with_name("py.typed").is_file():
    raise ValueError("Installed package is missing py.typed")
  _check_native_isolation()
  _check_knowledge()
  if knowledge_only:
    if any(name.startswith(("tzdata", "zoneinfo", "celestial", "ctypes")) for name in sys.modules):
      raise ValueError("Knowledge-only consumer loaded time or native machinery")
    print(f"Installed knowledge corpus; optimized={sys.flags.optimize}")
    return
  _check_cross_chart(expected_cross_observations)
  _check_natal_chart(expected_observations)
  print(f"Installed celestial-astrology {metadata.version}; optimized={sys.flags.optimize}")


if __name__ == "__main__":
  if sys.argv[1] == "--missing-metadata":
    check_missing_metadata()
  else:
    main(
      sys.argv[1],
      knowledge_only="--knowledge-only" in sys.argv[2:],
      expected_observations=Path(sys.argv[sys.argv.index("--expected-observations") + 1])
      if "--expected-observations" in sys.argv[2:]
      else None,
      expected_cross_observations=Path(
        sys.argv[sys.argv.index("--expected-cross-observations") + 1]
      )
      if "--expected-cross-observations" in sys.argv[2:]
      else None,
    )
