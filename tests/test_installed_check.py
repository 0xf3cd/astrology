"""Installed-consumer rejection cases. 安装后消费者的拒绝用例。"""

import builtins
import json
import runpy
import sys
from collections.abc import Iterator
from dataclasses import fields, replace
from importlib import import_module, resources
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from types import ModuleType
from typing import Literal

import pytest

import astrology
from tools import installed_check


def test_module_discovery_reads_files_without_importing_the_adapter(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  for name in (
    "__init__.py",
    "celestial.py",
    "_validation.py",
    "extra.py",
    "knowledge/__init__.py",
    "knowledge/catalog.py",
    "__pycache__/ignored.py",
  ):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("raise ImportError('discovery must not import this file')\n", encoding="utf-8")
  monkeypatch.setattr(astrology, "__path__", [str(tmp_path)])
  assert installed_check.module_names() == (
    "_validation",
    "extra",
    "knowledge",
    "knowledge.catalog",
  )


def _is_astronomy(name: str) -> bool:
  return name in ("celestial_calendar", "astrology.celestial") or name.startswith(
    "celestial_calendar."
  )


@pytest.fixture(autouse=True)
def consumer_process_without_astronomy() -> Iterator[None]:
  """Model a consumer process without the adapter. 模拟尚未加载适配层的消费者进程。"""
  removed = {name: sys.modules.pop(name) for name in list(sys.modules) if _is_astronomy(name)}
  original_adapter = astrology.__dict__.get("celestial")
  yield
  for name in list(sys.modules):
    if _is_astronomy(name):
      del sys.modules[name]
  sys.modules.update(removed)
  if original_adapter is None:
    astrology.__dict__.pop("celestial", None)
  else:
    astrology.__dict__["celestial"] = original_adapter


@pytest.fixture
def consumer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
  package = tmp_path / "astrology"
  package.mkdir()
  (package / "__init__.py").touch()
  (package / "py.typed").touch()
  corpus = files("astrology.knowledge").joinpath("catalog.json").read_bytes()
  knowledge = package / "knowledge"
  knowledge.mkdir()
  (knowledge / "catalog.json").write_bytes(corpus)
  monkeypatch.setattr(astrology, "__file__", str(package / "__init__.py"))
  for name in installed_check.module_names():
    monkeypatch.setattr(import_module(f"astrology.{name}"), "__file__", str(package / f"{name}.py"))
  monkeypatch.setattr(sys, "prefix", str(tmp_path))
  original_chart = astrology.natal_chart

  def chart_with_consumer_origin(
    resolved: astrology.ResolvedBirth, config: astrology.ChartConfig
  ) -> astrology.NatalChart:
    result = original_chart(resolved, config)
    monkeypatch.setattr(
      import_module("astrology.celestial"), "__file__", str(package / "celestial.py")
    )
    return result

  monkeypatch.setattr(astrology, "natal_chart", chart_with_consumer_origin)
  monkeypatch.setattr(installed_check, "files", lambda package: knowledge)
  monkeypatch.setattr(
    import_module("astrology.knowledge.catalog"), "files", lambda package: knowledge
  )
  return package


def test_import_outside_consumer_rejected(consumer: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(sys, "prefix", str(consumer.parent / "other-environment"))
  with pytest.raises(ValueError, match="outside the consumer environment"):
    installed_check.main(version("celestial-astrology"))


def test_wrong_installed_version_rejected(consumer: Path) -> None:
  with pytest.raises(ValueError, match="Installed version"):
    installed_check.main("unrelated-version")


@pytest.mark.parametrize(
  "field,message",
  [
    ("astrology_version", "distribution version"),
    ("celestial_version", "astronomy library version"),
  ],
)
def test_misreported_provenance_version_rejected(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, field: str, message: str
) -> None:
  original = astrology.natal_chart

  def wrong_version(
    resolved: astrology.ResolvedBirth, config: astrology.ChartConfig
  ) -> astrology.NatalChart:
    chart = original(resolved, config)
    provenance = (
      replace(chart.provenance, astrology_version="0.0.0")
      if field == "astrology_version"
      else replace(chart.provenance, celestial_version="0.0.0")
    )
    return replace(chart, provenance=provenance)

  monkeypatch.setattr(astrology, "natal_chart", wrong_version)
  with pytest.raises(ValueError, match=message):
    installed_check.main(version("celestial-astrology"))


@pytest.mark.parametrize("defect", ["none", "present", "wrong-distribution", "accepts"])
def test_missing_metadata_consumer_checks_calculation_not_just_initial_lookup(
  recorded_chart: astrology.NatalChart, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
  monkeypatch.setattr(installed_check, "_check_knowledge", lambda: None)
  monkeypatch.setattr(installed_check, "_check_native_isolation", lambda: None)

  def metadata(name: str) -> object:
    if defect == "present":
      return object()
    raise PackageNotFoundError(name)

  def calculate(
    resolved: astrology.ResolvedBirth, config: astrology.ChartConfig
  ) -> astrology.NatalChart:
    if defect == "accepts":
      return recorded_chart
    raise PackageNotFoundError("other" if defect == "wrong-distribution" else "celestial-astrology")

  monkeypatch.setattr(installed_check, "distribution", metadata)
  monkeypatch.setattr(astrology, "natal_chart", calculate)
  if defect == "none":
    installed_check.check_missing_metadata()
  else:
    with pytest.raises(ValueError, match=r"still has|different missing|invented"):
      installed_check.check_missing_metadata()


@pytest.mark.parametrize("module", ["astrology." + name for name in installed_check.module_names()])
def test_submodule_outside_consumer_rejected(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
  monkeypatch.setattr(import_module(module), "__file__", str(consumer.parent.parent / "outside.py"))
  with pytest.raises(ValueError, match="outside the consumer environment"):
    installed_check.main(version("celestial-astrology"))


def test_missing_installed_typing_marker_rejected(consumer: Path) -> None:
  (consumer / "py.typed").unlink()
  with pytest.raises(ValueError, match=r"missing py\.typed"):
    installed_check.main(version("celestial-astrology"))


@pytest.mark.parametrize(
  "module", ["celestial_calendar", "celestial_calendar._binding", "astrology.celestial"]
)
def test_loaded_astronomy_rejected(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
  monkeypatch.setitem(sys.modules, module, ModuleType(module))
  with pytest.raises(ValueError, match="astronomy adapter"):
    installed_check.main(version("celestial-astrology"))


def test_similar_module_name_allowed(consumer: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setitem(
    sys.modules, "celestial_calendar_extra", ModuleType("celestial_calendar_extra")
  )
  installed_check.main(version("celestial-astrology"))


def test_installed_consumer_calculates_a_chart(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  calls: list[astrology.ChartConfig] = []
  original = astrology.natal_chart

  def record(
    resolved: astrology.ResolvedBirth, config: astrology.ChartConfig
  ) -> astrology.NatalChart:
    calls.append(config)
    return original(resolved, config)

  monkeypatch.setattr(astrology, "natal_chart", record)
  installed_check.main(version("celestial-astrology"))
  assert len(calls) == 1


def test_installed_comparison_rejects_different_development_output(consumer: Path) -> None:
  expected = consumer.parent / "wrong-chart.json"
  expected.write_text("{}", encoding="utf-8")
  with pytest.raises(ValueError, match="differs from the development"):
    installed_check.main(version("celestial-astrology"), expected_observations=expected)


@pytest.mark.parametrize(
  "field",
  [
    "resolved",
    "requested",
    "effective",
    "provenance",
    "positions",
    "times",
    "houses",
    "placements",
    "aspects",
  ],
)
@pytest.mark.parametrize("changed", [False, True])
def test_installed_comparison_keeps_raw_values_and_metadata(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, field: str, changed: bool
) -> None:
  expected = consumer.parent / "expected-observations.json"
  original = installed_check.calculation_observations

  def observe(
    chart: astrology.NatalChart,
    transits: astrology.TransitHits,
    moments: tuple[astrology.MomentChart, astrology.MomentChart],
    returns: tuple[tuple[astrology.TransitHits, astrology.MomentChart], ...],
    catalog: astrology.Catalog,
  ) -> str:
    packed = original(chart, transits, moments, returns, catalog)
    envelope = json.loads(packed)
    values = envelope["chart"]
    assert set(values) == {field.name for field in fields(chart)}
    for name in ("resolved", "requested", "effective", "provenance"):
      assert values[name] == repr(getattr(chart, name))
    for name in ("times", "houses"):
      instance = getattr(chart, name)
      assert values[name] == [
        list(value) if isinstance(value, tuple) else value
        for field in fields(instance)
        for value in (getattr(instance, field.name),)
      ]
    for name in ("positions", "placements", "aspects"):
      assert values[name] == [
        [getattr(instance, field.name) for field in fields(instance)]
        for instance in getattr(chart, name)
      ]
    if changed:
      if field == "positions":
        longitude = values[field][0][1]
        values[field][0][1] += 1e-6
        assert astrology.truncate_display(longitude) == astrology.truncate_display(
          values[field][0][1]
        )
      else:
        values[field] = "different"
    expected.write_text(json.dumps(envelope, sort_keys=True, allow_nan=False), encoding="utf-8")
    return packed

  monkeypatch.setattr(installed_check, "calculation_observations", observe)
  if changed:
    with pytest.raises(ValueError, match="differs from the development"):
      installed_check.main(version("celestial-astrology"), expected_observations=expected)
  else:
    installed_check.main(version("celestial-astrology"), expected_observations=expected)


@pytest.mark.parametrize(
  "field",
  [
    "moment",
    "positions",
    "times",
    "houses",
    "placements",
    "aspects",
    "requested",
    "effective",
    "provenance",
  ],
)
def test_installed_consumer_compares_each_moment_field(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
  original = installed_check.calculation_observations
  expected = consumer.parent / "expected-moment-observations.json"

  def observe(
    chart: astrology.NatalChart,
    transits: astrology.TransitHits,
    moments: tuple[astrology.MomentChart, astrology.MomentChart],
    returns: tuple[tuple[astrology.TransitHits, astrology.MomentChart], ...],
    catalog: astrology.Catalog,
  ) -> str:
    values = json.loads(original(chart, transits, moments, returns, catalog))
    assert len(values["moments"]) == 2
    assert moments[0].moment.source_jde_tt is None
    assert moments[1].moment.source_jde_tt == transits.hits[0].jde_tt
    assert all(
      set(packed) == {f.name for f in fields(moment)}
      for packed, moment in zip(values["moments"], moments, strict=True)
    )
    values["moments"][1][field] = "corrupted moment observation"
    expected.write_text(
      json.dumps(values, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return original(chart, transits, moments, returns, catalog)

  monkeypatch.setattr(installed_check, "calculation_observations", observe)
  with pytest.raises(ValueError, match="Installed calculation differs"):
    installed_check.main(version("celestial-astrology"), expected_observations=expected)


@pytest.mark.parametrize("field", ["fixed_aspects", "fixed_text", "moment_text", "returns"])
def test_installed_consumer_compares_new_operation_outputs(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
  original = installed_check.calculation_observations
  expected = consumer.parent / "expected-operation-observations.json"

  def observe(
    chart: astrology.NatalChart,
    transits: astrology.TransitHits,
    moments: tuple[astrology.MomentChart, astrology.MomentChart],
    returns: tuple[tuple[astrology.TransitHits, astrology.MomentChart], ...],
    catalog: astrology.Catalog,
  ) -> str:
    packed = original(chart, transits, moments, returns, catalog)
    values = json.loads(packed)
    values[field] = "corrupted operation output"
    expected.write_text(
      json.dumps(values, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return packed

  monkeypatch.setattr(installed_check, "calculation_observations", observe)
  with pytest.raises(ValueError, match="Installed calculation differs"):
    installed_check.main(version("celestial-astrology"), expected_observations=expected)


@pytest.mark.parametrize("changed", [False, True])
def test_installed_consumer_executes_and_compares_transit_values(
  consumer: Path,
  monkeypatch: pytest.MonkeyPatch,
  changed: bool,
) -> None:
  expected = consumer.parent / "expected-calculations.json"
  original = installed_check.calculation_observations
  calls: list[astrology.TransitHits] = []

  def observe(
    chart: astrology.NatalChart,
    transits: astrology.TransitHits,
    moments: tuple[astrology.MomentChart, astrology.MomentChart],
    returns: tuple[tuple[astrology.TransitHits, astrology.MomentChart], ...],
    catalog: astrology.Catalog,
  ) -> str:
    calls.append(transits)
    packed = original(chart, transits, moments, returns, catalog)
    values = json.loads(packed)
    assert values["transits"] == repr(transits)
    assert transits.chart is chart
    if changed:
      values["transits"] = "different transit observations"
    expected.write_text(json.dumps(values, sort_keys=True, allow_nan=False), encoding="utf-8")
    return packed

  monkeypatch.setattr(installed_check, "calculation_observations", observe)
  if changed:
    with pytest.raises(ValueError, match="differs from the development"):
      installed_check.main(version("celestial-astrology"), expected_observations=expected)
  else:
    installed_check.main(version("celestial-astrology"), expected_observations=expected)
  assert len(calls) == 1 and calls[0].hits


def test_raw_observations_distinguish_identical_text(recorded_chart: astrology.NatalChart) -> None:
  positions = (
    replace(
      recorded_chart.positions[0], longitude_deg=recorded_chart.positions[0].longitude_deg + 1e-6
    ),
    *recorded_chart.positions[1:],
  )
  placements = tuple(
    astrology.Placement(
      p.identity,
      astrology.sign_of(p.longitude_deg),
      astrology.sign_degree(p.longitude_deg),
      astrology.house_of(p.longitude_deg, recorded_chart.houses.cusps_deg),
    )
    for p in positions
  )
  aspects = astrology.find_aspects(
    [
      astrology.AspectObject(p.identity, p.longitude_deg, p.longitude_rate_deg_per_tt_day)
      for p in positions
      if p.identity in recorded_chart.effective.aspect_objects
    ],
    recorded_chart.requested.aspects,
    recorded_chart.requested.orb_combination,
  )
  changed = replace(recorded_chart, positions=positions, placements=placements, aspects=aspects)
  catalog = astrology.load_catalog()
  languages: tuple[Literal["en", "zh-CN"], ...] = ("en", "zh-CN")
  for language in languages:
    assert astrology.format_chart(changed, catalog, language=language) == astrology.format_chart(
      recorded_chart,
      catalog,
      language=language,
    )
  assert installed_check.chart_observations(changed) != installed_check.chart_observations(
    recorded_chart
  )


def test_installed_consumer_checks_native_adapter_origin(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  original = astrology.natal_chart

  def outside(
    resolved: astrology.ResolvedBirth, config: astrology.ChartConfig
  ) -> astrology.NatalChart:
    chart = original(resolved, config)
    monkeypatch.setattr(
      import_module("astrology.celestial"), "__file__", str(consumer.parent.parent / "outside.py")
    )
    return chart

  monkeypatch.setattr(astrology, "natal_chart", outside)
  with pytest.raises(ValueError, match=r"astrology\.celestial from outside"):
    installed_check.main(version("celestial-astrology"))


def test_knowledge_resource_outside_consumer_rejected(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  monkeypatch.setattr(installed_check, "files", lambda package: consumer.parent.parent)
  with pytest.raises(ValueError, match="resource is outside"):
    installed_check._check_knowledge()


def test_missing_installed_corpus_rejected(consumer: Path) -> None:
  (consumer / "knowledge/catalog.json").unlink()
  with pytest.raises(FileNotFoundError):
    installed_check._check_knowledge()


@pytest.mark.parametrize(
  "module", ["celestial_calendar", "tzdata.extra", "zoneinfo.extra", "ctypes.extra"]
)
def test_knowledge_smoke_rejects_time_or_native_initialization(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
  original = astrology.load_catalog

  def polluted() -> astrology.Catalog:
    catalog = original()
    monkeypatch.setitem(sys.modules, module, ModuleType(module))
    return catalog

  monkeypatch.setattr(astrology, "load_catalog", polluted)
  with pytest.raises(ValueError, match="Knowledge query initialized"):
    installed_check._check_knowledge()


def test_knowledge_only_does_not_run_chart_consumers(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  def forbidden(*args: object) -> None:
    pytest.fail("Knowledge-only consumer reached chart calculations")

  monkeypatch.setattr(installed_check, "_check_natal_chart", forbidden)
  monkeypatch.setattr(installed_check, "_check_cross_chart", forbidden)
  monkeypatch.setattr(installed_check, "_check_knowledge", lambda: None)
  for name in tuple(sys.modules):
    if name.startswith(("tzdata", "zoneinfo", "celestial", "ctypes")):
      monkeypatch.delitem(sys.modules, name)
  installed_check.main(version("celestial-astrology"), knowledge_only=True)


@pytest.mark.parametrize(
  "flag", ["--knowledge-only", "--expected-observations", "--expected-cross-observations"]
)
def test_cli_reads_flags_after_the_package_version(
  consumer: Path,
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
  flag: str,
) -> None:
  original_files = resources.files

  def consumer_resource(package: str) -> Traversable:
    return consumer / "knowledge" if package == "astrology.knowledge" else original_files(package)

  monkeypatch.setattr(resources, "files", consumer_resource)
  for name in tuple(sys.modules):
    if name.startswith(("tzdata", "zoneinfo", "celestial", "ctypes")):
      monkeypatch.delitem(sys.modules, name)
  arguments = ["installed_check.py", version("celestial-astrology"), flag]
  if flag == "--knowledge-only":

    def forbidden(*args: object, **kwargs: object) -> None:
      pytest.fail("Knowledge-only CLI reached chart calculation")

    monkeypatch.setattr(astrology, "natal_chart", forbidden)
  else:
    expected = consumer.parent / "wrong-observations.json"
    expected.write_text("{}", encoding="utf-8")
    arguments.append(str(expected))
  monkeypatch.setattr(sys, "argv", arguments)
  if flag == "--knowledge-only":
    runpy.run_path(str(Path(installed_check.__file__)), run_name="__main__")
    assert "Installed knowledge corpus" in capsys.readouterr().out
  else:
    message = (
      "Installed calculation differs"
      if flag == "--expected-observations"
      else "comparison observations differ"
    )
    with pytest.raises(ValueError, match=message):
      runpy.run_path(str(Path(installed_check.__file__)), run_name="__main__")


def test_cross_consumer_rejects_native_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
  original = installed_check.acceptance_cross_aspects

  def polluted() -> astrology.CrossChartAspects:
    result = original()
    monkeypatch.setitem(sys.modules, "astrology.celestial", ModuleType("astrology.celestial"))
    return result

  monkeypatch.setattr(installed_check, "acceptance_cross_aspects", polluted)
  with pytest.raises(ValueError, match="initialized"):
    installed_check._check_cross_chart()


def test_main_forwards_the_cross_observation_file(consumer: Path) -> None:
  expected = consumer.parent / "wrong-cross-observations.json"
  expected.write_text("{}", encoding="utf-8")
  with pytest.raises(ValueError, match="comparison observations differ from the development"):
    installed_check.main(version("celestial-astrology"), expected_cross_observations=expected)


@pytest.mark.parametrize(
  "kind,field",
  [
    *(
      ("aspects", field)
      for field in (
        "chart_left",
        "chart_right",
        "left_objects",
        "right_objects",
        "rules",
        "combination",
        "hits",
      )
    ),
    *(
      ("overlays", field)
      for field in ("chart_left", "chart_right", "left_objects", "right_objects", "placements")
    ),
  ],
)
@pytest.mark.parametrize("changed", [False, True])
def test_comparison_observations_cover_every_field_and_both_complete_sources(
  tmp_path: Path, kind: str, field: str, changed: bool
) -> None:
  aspects = installed_check.acceptance_cross_aspects()
  overlays = installed_check.acceptance_house_overlays()
  result = aspects if kind == "aspects" else overlays
  observations = json.loads(
    installed_check.comparison_observations(aspects, overlays, astrology.load_catalog())
  )
  values = observations[kind]
  assert set(values) == {f.name for f in fields(result)}
  for side in ("left", "right"):
    assert values[f"chart_{side}"] == json.loads(
      installed_check.chart_observations(getattr(result, f"chart_{side}"))
    )
    assert values[f"{side}_objects"] == list(getattr(result, f"{side}_objects"))
  if kind == "aspects":
    assert values["rules"] == repr(aspects.rules)
    assert values["combination"] == aspects.combination
    assert values["hits"] == [[getattr(hit, f.name) for f in fields(hit)] for hit in aspects.hits]
  else:
    assert values["placements"] == [
      [getattr(p, f.name) for f in fields(p)] for p in overlays.placements
    ]
  if changed:
    if field == "hits":
      values[field][0][4] += 1e-12
    elif field == "placements":
      values[field][0][3] += 1
    elif field in ("chart_left", "chart_right"):
      values[field]["provenance"] = "changed provenance"
    else:
      values[field] = "different"
  expected = tmp_path / "comparison-observations.json"
  expected.write_text(json.dumps(observations, sort_keys=True, allow_nan=False), encoding="utf-8")
  if changed:
    with pytest.raises(ValueError, match="comparison observations differ from the development"):
      installed_check._check_cross_chart(expected)
  else:
    installed_check._check_cross_chart(expected)


@pytest.mark.parametrize("name", ["format_house_overlays", "format_cross_aspects"])
def test_comparison_consumer_blocks_native_import_and_restores_guard(
  name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
  original = builtins.__import__

  def native_attempt(*args: object, **kwargs: object) -> str:
    __import__("celestial_calendar")
    raise RuntimeError("Native import was not blocked")

  monkeypatch.setattr(astrology, name, native_attempt)
  with pytest.raises(ValueError, match="attempted to initialize astronomy"):
    installed_check._check_cross_chart()
  assert builtins.__import__ is original


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("kind", ["overlays", "aspects"])
def test_comparison_observations_reject_changed_bilingual_text(
  tmp_path: Path, language: str, kind: str
) -> None:
  values = json.loads(
    installed_check.comparison_observations(
      installed_check.acceptance_cross_aspects(),
      installed_check.acceptance_house_overlays(),
      astrology.load_catalog(),
    )
  )
  values["text"][language][kind] += "\nFORGED ROW"
  expected = tmp_path / "comparison-observations.json"
  expected.write_text(json.dumps(values, sort_keys=True, allow_nan=False), encoding="utf-8")
  with pytest.raises(ValueError, match="comparison observations differ from the development"):
    installed_check._check_cross_chart(expected)
