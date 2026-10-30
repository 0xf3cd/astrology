"""Installed-consumer rejection cases. 安装后消费者的拒绝用例。"""

import builtins
import json
import sys
from collections.abc import Iterator, Sequence
from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Literal, cast

import pytest

import astrology
from tools import installed_check


def _is_astronomy(name: str) -> bool:
  """Report whether a module name belongs to the astronomy adapter. 判断模块名是否属于天文适配层。"""
  return name in ("celestial_calendar", "astrology.celestial") or name.startswith(
    "celestial_calendar."
  )


@pytest.fixture(autouse=True)
def consumer_process_without_astronomy() -> Iterator[None]:
  """Model a consumer process that has not loaded the astronomy adapter.

  模拟尚未加载天文适配层的消费者进程。
  """
  removed = {name: sys.modules.pop(name) for name in list(sys.modules) if _is_astronomy(name)}
  yield
  for name in list(sys.modules):
    if _is_astronomy(name):
      del sys.modules[name]
  sys.modules.update(removed)


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
  for name in installed_check.MODULES:
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


def test_wrong_chart_distribution_version_is_rejected(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  original = astrology.natal_chart

  def wrong_version(
    resolved: astrology.ResolvedBirth, config: astrology.ChartConfig
  ) -> astrology.NatalChart:
    chart = original(resolved, config)
    return replace(chart, provenance=replace(chart.provenance, astrology_version="0.0.0"))

  monkeypatch.setattr(astrology, "natal_chart", wrong_version)
  with pytest.raises(ValueError, match="distribution version"):
    installed_check.main(version("celestial-astrology"))


@pytest.mark.parametrize("defect", ["none", "present", "wrong-distribution", "accepts"])
def test_missing_metadata_consumer_checks_calculation_not_just_initial_lookup(
  recorded_chart: astrology.NatalChart,
  monkeypatch: pytest.MonkeyPatch,
  defect: str,
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


@pytest.mark.parametrize(
  "module",
  ["astrology." + name for name in installed_check.MODULES],
)
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


@pytest.mark.parametrize(
  "field,value,message",
  [
    ("utc", datetime(2026, 4, 4, tzinfo=UTC), "selected fold"),
    ("record", astrology.BirthRecord(date(2000, 1, 1)), "selected fold"),
    ("fold", 2, "selected fold"),
    ("timezone_source", "system", "IANA data source"),
    ("timezone_key", "UTC", "IANA data source"),
    ("tzdata_version", "invented", "package version"),
    ("iana_version", "invented", "IANA release"),
  ],
)
def test_installed_consumer_rejects_wrong_resolution_metadata(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object, message: str
) -> None:
  original = astrology.prepare_natal_input

  def incorrect(
    record: astrology.BirthRecord, *, fold: Literal[0, 1] | None = None
  ) -> astrology.ResolvedBirth:
    result = original(record, fold=fold)
    attributes = {
      name: getattr(result, name)
      for name in (
        "utc",
        "record",
        "fold",
        "timezone_source",
        "timezone_key",
        "tzdata_version",
        "iana_version",
      )
    }
    attributes[field] = value
    return cast(astrology.ResolvedBirth, SimpleNamespace(**attributes))

  monkeypatch.setattr(astrology, "prepare_natal_input", incorrect)
  with pytest.raises(ValueError, match=message):
    installed_check.main(version("celestial-astrology"))


def test_installed_consumer_rejects_automatic_fold_choice(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  original = astrology.resolve_birth_time

  def chooses_first(
    record: astrology.BirthRecord, *, fold: Literal[0, 1] | None = None
  ) -> astrology.ResolvedBirth:
    return original(record, fold=0)

  monkeypatch.setattr(astrology, "resolve_birth_time", chooses_first)
  with pytest.raises(ValueError, match="ambiguous input"):
    installed_check.main(version("celestial-astrology"))


@pytest.mark.parametrize("defect", ["utc", "provenance"])
def test_installed_consumer_rejects_fixed_offset_faults(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
  original = astrology.resolve_birth_time

  def incorrect(
    record: astrology.BirthRecord, *, fold: Literal[0, 1] | None = None
  ) -> astrology.ResolvedBirth:
    result = original(record, fold=fold)
    if not isinstance(record.timezone, astrology.FixedOffset):
      return result
    attributes = {
      name: getattr(result, name)
      for name in (
        "utc",
        "timezone_source",
        "timezone_key",
        "fold",
        "tzdata_version",
        "iana_version",
      )
    }
    if defect == "utc":
      attributes["utc"] = result.utc + timedelta(minutes=1)
    else:
      attributes["tzdata_version"] = "unexpected-database-version"
    return cast(astrology.ResolvedBirth, SimpleNamespace(**attributes))

  monkeypatch.setattr(astrology, "resolve_birth_time", incorrect)
  message = "UTC date rollover" if defect == "utc" else "timezone-database provenance"
  with pytest.raises(ValueError, match=message):
    installed_check.main(version("celestial-astrology"))


def test_installed_consumer_rejects_missing_location_acceptance(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  original = astrology.prepare_natal_input

  def accepts_partial(
    record: astrology.BirthRecord, *, fold: Literal[0, 1] | None = None
  ) -> astrology.ResolvedBirth:
    if record.location is None:
      return astrology.resolve_birth_time(record, fold=fold)
    return original(record, fold=fold)

  monkeypatch.setattr(astrology, "prepare_natal_input", accepts_partial)
  with pytest.raises(ValueError, match="missing location"):
    installed_check.main(version("celestial-astrology"))


def test_installed_consumer_rejects_missing_coordinate_validation(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  original = astrology.Location

  def accepts_nan(latitude: float, longitude: float) -> astrology.Location:
    return original(0, longitude)

  monkeypatch.setattr(astrology, "Location", accepts_nan)
  with pytest.raises(ValueError, match="accepted NaN"):
    installed_check.main(version("celestial-astrology"))


@pytest.mark.parametrize("defect", ["alias", "house"])
def test_installed_consumer_rejects_configuration_defects(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
  original = astrology.ChartConfig

  def incorrect(
    house_system: astrology.HouseSystem,
    objects: Sequence[astrology.Body | astrology.LunarNode],
    aspects: Sequence[astrology.AspectRule],
  ) -> astrology.ChartConfig:
    if defect == "alias":
      return cast(
        astrology.ChartConfig, SimpleNamespace(objects=objects, house_system=house_system)
      )
    return original(astrology.HouseSystem.EQUAL, objects, aspects)

  monkeypatch.setattr(astrology, "ChartConfig", incorrect)
  with pytest.raises(ValueError, match=r"mutable input alias|substituted"):
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
  assert len(calls) == 3
  assert calls[0].house_system is astrology.HouseSystem.WHOLE_SIGN
  assert calls[1].house_system is astrology.HouseSystem.WHOLE_SIGN
  assert calls[1].aspect_objects == tuple(astrology.Axis)
  assert calls[1].orb_combination is None
  assert calls[2].house_system is astrology.HouseSystem.PLACIDUS
  assert calls[0].aspects
  assert calls[0].orb_combination is astrology.OrbCombination.MEAN_OF_ORBS


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
  consumer: Path,
  monkeypatch: pytest.MonkeyPatch,
  field: str,
  changed: bool,
) -> None:
  expected = consumer.parent / "expected-observations.json"
  original = installed_check.chart_observations

  def observe(chart: astrology.NatalChart) -> str:
    packed = original(chart)
    values = json.loads(packed)
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
    if not changed:
      expected.write_text(packed, encoding="utf-8")
      return packed
    if field == "positions":
      longitude = values[field][0][1]
      values[field][0][1] += 1e-6
      assert astrology.truncate_display(longitude) == astrology.truncate_display(
        values[field][0][1]
      )
    else:
      values[field] = "different"
    expected.write_text(json.dumps(values, sort_keys=True, allow_nan=False), encoding="utf-8")
    return packed

  monkeypatch.setattr(installed_check, "chart_observations", observe)
  if changed:
    with pytest.raises(ValueError, match="differs from the development"):
      installed_check.main(version("celestial-astrology"), expected_observations=expected)
  else:
    installed_check.main(version("celestial-astrology"), expected_observations=expected)


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


def test_installed_consumer_rejects_a_misreported_astronomy_version(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  original = astrology.natal_chart

  def incorrect(
    resolved: astrology.ResolvedBirth, config: astrology.ChartConfig
  ) -> astrology.NatalChart:
    chart = original(resolved, config)
    return replace(chart, provenance=replace(chart.provenance, celestial_version="0.0.0"))

  monkeypatch.setattr(astrology, "natal_chart", incorrect)
  with pytest.raises(ValueError, match="astronomy library version"):
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


def test_self_consistent_changed_corpus_version_rejected(consumer: Path) -> None:
  path = consumer / "knowledge/catalog.json"
  data = json.loads(path.read_text(encoding="utf-8"))
  expected = data["version"]
  installed_check._check_knowledge(expected)
  data["version"] = "different-but-self-consistent"
  path.write_text(json.dumps(data), encoding="utf-8")
  with pytest.raises(ValueError, match="differs from the source corpus"):
    installed_check._check_knowledge(expected)


def test_knowledge_only_does_not_run_birth_consumer(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  def forbidden() -> None:
    pytest.fail("Knowledge-only consumer reached birth calculations")

  monkeypatch.setattr(installed_check, "_check_birth_and_configuration", forbidden)
  monkeypatch.setattr(installed_check, "_check_cross_chart", forbidden)
  monkeypatch.setattr(installed_check, "_check_knowledge", lambda expected: None)
  monkeypatch.setattr(
    sys,
    "modules",
    {
      name: module
      for name, module in sys.modules.items()
      if not name.startswith(("tzdata", "zoneinfo", "celestial", "ctypes"))
    },
  )
  installed_check.main(version("celestial-astrology"), knowledge_only=True)


def test_cross_consumer_rejects_a_missing_hand_worked_pair(monkeypatch: pytest.MonkeyPatch) -> None:
  result = installed_check.acceptance_cross_aspects()
  monkeypatch.setattr(
    installed_check,
    "acceptance_cross_aspects",
    lambda: SimpleNamespace(hits=result.hits[:-1]),
  )
  with pytest.raises(ValueError, match="hand-worked geometry"):
    installed_check._check_cross_chart()


def test_axis_consumer_rejects_incorrect_cross_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
  original = astrology.cross_chart_aspects

  def incorrect(*args: object, **kwargs: object) -> astrology.CrossChartAspects:
    result = original(*args, **kwargs)  # type: ignore[arg-type]
    return cast(
      astrology.CrossChartAspects,
      SimpleNamespace(
        hits=(replace(result.hits[0], deviation_deg=0),), left_objects=result.left_objects
      ),
    )

  monkeypatch.setattr(astrology, "cross_chart_aspects", incorrect)
  with pytest.raises(ValueError, match="wrong source or field"):
    installed_check._check_axes()


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
  "field",
  [
    "chart_left",
    "chart_right",
    "left_objects",
    "right_objects",
    "rules",
    "combination",
    "hits",
  ],
)
@pytest.mark.parametrize("changed", [False, True])
def test_cross_observations_cover_every_field_and_both_complete_sources(
  tmp_path: Path, field: str, changed: bool
) -> None:
  result = installed_check.acceptance_cross_aspects()
  observations = json.loads(
    installed_check.comparison_observations(
      result, installed_check.acceptance_house_overlays(), astrology.load_catalog()
    )
  )
  values = observations["aspects"]
  assert set(values) == {f.name for f in fields(result)}
  assert values["chart_left"] == json.loads(installed_check.chart_observations(result.chart_left))
  assert values["chart_right"] == json.loads(installed_check.chart_observations(result.chart_right))
  assert values["left_objects"] == list(result.left_objects)
  assert values["right_objects"] == list(result.right_objects)
  assert values["rules"] == repr(result.rules)
  assert values["combination"] == result.combination
  assert values["hits"] == [[getattr(hit, f.name) for f in fields(hit)] for hit in result.hits]
  if changed:
    if field == "hits":
      values[field][0][4] += 1e-12
    elif field in ("chart_left", "chart_right"):
      values[field]["provenance"] = "changed provenance"
    else:
      values[field] = "different"
  expected = tmp_path / "cross-observations.json"
  expected.write_text(json.dumps(observations, sort_keys=True, allow_nan=False), encoding="utf-8")
  if changed:
    with pytest.raises(ValueError, match="comparison observations differ from the development"):
      installed_check._check_cross_chart(expected)
  else:
    installed_check._check_cross_chart(expected)


def test_overlay_consumer_rejects_missing_hand_worked_direction(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  result = installed_check.acceptance_house_overlays()
  monkeypatch.setattr(
    installed_check,
    "acceptance_house_overlays",
    lambda: SimpleNamespace(placements=result.placements[:-3]),
  )
  with pytest.raises(ValueError, match="house overlays differ from hand-worked geometry"):
    installed_check._check_cross_chart()


@pytest.mark.parametrize("name", ["format_house_overlays", "format_cross_aspects"])
def test_comparison_consumer_rejects_missing_text(
  name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
  monkeypatch.setattr(astrology, name, lambda *args, **kwargs: "")
  with pytest.raises(ValueError, match="text lost"):
    installed_check._check_cross_chart()


@pytest.mark.parametrize("name", ["format_house_overlays", "format_cross_aspects"])
def test_comparison_consumer_blocks_native_import_after_inputs_and_restores_guard(
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


@pytest.mark.parametrize(
  "field", ["chart_left", "chart_right", "left_objects", "right_objects", "placements"]
)
@pytest.mark.parametrize("changed", [False, True])
def test_overlay_observations_cover_all_fields_and_sources(
  tmp_path: Path, field: str, changed: bool
) -> None:
  overlays = installed_check.acceptance_house_overlays()
  values = json.loads(
    installed_check.comparison_observations(
      installed_check.acceptance_cross_aspects(), overlays, astrology.load_catalog()
    )
  )
  observed = values["overlays"]
  assert set(observed) == {f.name for f in fields(overlays)}
  for side in ("left", "right"):
    assert observed[f"chart_{side}"] == json.loads(
      installed_check.chart_observations(getattr(overlays, f"chart_{side}"))
    )
    assert observed[f"{side}_objects"] == list(getattr(overlays, f"{side}_objects"))
  assert observed["placements"] == [
    [getattr(p, f.name) for f in fields(p)] for p in overlays.placements
  ]
  if changed:
    if field == "placements":
      observed[field][0][3] += 1
    elif field in ("chart_left", "chart_right"):
      observed[field]["provenance"] = "changed provenance"
    else:
      observed[field] = "different"
  expected = tmp_path / "comparison-observations.json"
  expected.write_text(json.dumps(values, sort_keys=True, allow_nan=False), encoding="utf-8")
  if changed:
    with pytest.raises(ValueError, match="comparison observations differ from the development"):
      installed_check._check_cross_chart(expected)
  else:
    installed_check._check_cross_chart(expected)


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


@pytest.mark.parametrize(
  "defect",
  [
    "body_link",
    "rule_link",
    "alias",
    "translation",
    "source_condition",
    "prerequisite_status",
    "output_eligibility",
    "verification",
  ],
)
def test_installed_knowledge_defects(consumer: Path, defect: str) -> None:
  path = consumer / "knowledge/catalog.json"
  data = json.loads(path.read_text(encoding="utf-8"))
  example = next(row for row in data["entries"] if row["identifier"] == "entry.equinoctial_example")
  source = next(row for row in data["sources"] if row["identifier"] == "source.ptolemy.ashmand1822")
  if defect == "body_link":
    next(row for row in data["entries"] if row["identifier"] == "entry.body_requests")[
      "concept_ids"
    ] = ["body.moon"]
  elif defect == "rule_link":
    rule = next(row for row in data["variants"] if row["identifier"] == "rule.house.whole_sign")
    rule["configuration"] = {"enum": "Body", "member": "SUN"}
    rule["concept_ids"] = ["body.sun"]
  elif defect == "alias":
    next(row for row in data["concepts"] if row["identifier"] == "body.sun")["en_aliases"] = [
      "different"
    ]
  elif defect == "translation":
    del example["citations"][0]["excerpt"]["zh"]
  elif defect == "source_condition":
    example["citations"][0]["excerpt"]["en"] = "Truncated quotation."
  elif defect == "verification":
    source["verification"] = "unverified"
  else:
    example[defect] = "complete" if defect == "prerequisite_status" else "eligible"
  path.write_text(json.dumps(data), encoding="utf-8")
  with pytest.raises(ValueError):
    installed_check._check_knowledge()


@pytest.mark.parametrize("defect", ["concept_link", "rule_link", "translation", "status", "output"])
def test_installed_ashmand_knowledge_defects(consumer: Path, defect: str) -> None:
  path = consumer / "knowledge/catalog.json"
  data = json.loads(path.read_text(encoding="utf-8"))
  entry = next(row for row in data["entries"] if row["identifier"] == "entry.ashmand_sign_groups")
  if defect == "concept_link":
    entry["concept_ids"] = entry["concept_ids"][1:]
  elif defect == "rule_link":
    entry["rule_ids"] = ["rule.project.tropical_sign_sectors"]
  elif defect == "translation":
    del entry["citations"][0]["excerpt"]["zh"]
    del entry["citations"][0]["excerpt"]["translation_credit"]
  elif defect == "status":
    entry["prerequisite_status"] = "unresolved"
  else:
    entry["output_eligibility"] = "eligible"
  path.write_text(json.dumps(data), encoding="utf-8")
  with pytest.raises(ValueError, match="Ashmand"):
    installed_check._check_knowledge()


@pytest.mark.parametrize(
  "defect",
  [
    "entry_link",
    "rule_link",
    "source_status",
    "source_link",
    "output",
    "prerequisites",
    "status_kind",
  ],
)
def test_installed_dignity_knowledge_defects(consumer: Path, defect: str) -> None:
  path = consumer / "knowledge/catalog.json"
  data = json.loads(path.read_text(encoding="utf-8"))
  entry = next(e for e in data["entries"] if e["identifier"] == "entry.essential_dignities")
  if defect == "entry_link":
    entry["rule_ids"] = []
  elif defect == "rule_link":
    rule = next(
      v for v in data["variants"] if v["identifier"] == "rule.lilly1647.essential_dignities"
    )
    rule["concept_ids"] = rule["concept_ids"][:-1]
  elif defect == "source_status":
    source = next(
      s for s in data["sources"] if s["identifier"] == "source.lilly.christian-astrology-1647"
    )
    source["verification"] = "unverified"
  elif defect == "source_link":
    entry["citations"][0]["source_id"] = "source.rudhyar.lunation-birthday"
  elif defect == "output":
    entry["output_eligibility"] = "eligible"
  elif defect == "prerequisites":
    entry["prerequisite_status"] = "unresolved"
  else:
    concept = next(c for c in data["concepts"] if c["identifier"] == "dignity_status.fall")
    concept["kind"] = "element"
  path.write_text(json.dumps(data), encoding="utf-8")
  with pytest.raises(ValueError, match="Installed dignity knowledge"):
    installed_check._check_dignities()


@pytest.mark.parametrize(
  "defect",
  [
    "entry_link",
    "rule_link",
    "configuration",
    "source_link",
    "source_status",
    "source_url",
    "output",
    "prerequisites",
    "translation",
  ],
)
def test_installed_overlay_knowledge_defects(consumer: Path, defect: str) -> None:
  path = consumer / "knowledge/catalog.json"
  data = json.loads(path.read_text(encoding="utf-8"))
  entry = next(e for e in data["entries"] if e["identifier"] == "entry.cross_house_overlays")
  rule = next(v for v in data["variants"] if v["identifier"] == "rule.project.cross_house_overlays")
  source = next(
    s for s in data["sources"] if s["identifier"] == "source.astrology.house_overlays.f269d14"
  )
  if defect == "entry_link":
    entry["rule_ids"] = ["rule.project.cusp_ownership"]
  elif defect == "rule_link":
    rule["concept_ids"] = rule["concept_ids"][:-1]
  elif defect == "configuration":
    rule["configuration"] = {"enum": "HouseSystem", "member": "EQUAL"}
  elif defect == "source_link":
    entry["citations"][0]["source_id"] = "source.astrology.cross_aspects.0d7122a"
  elif defect == "source_status":
    source["verification"] = "unverified"
  elif defect == "source_url":
    source["url"] = "https://github.com/0xf3cd/astrology/tree/main"
  elif defect == "output":
    entry["output_eligibility"] = "eligible"
  elif defect == "prerequisites":
    entry["prerequisite_status"] = "unresolved"
  else:
    rule["definition"]["revision"] = 2
  path.write_text(json.dumps(data), encoding="utf-8")
  with pytest.raises(ValueError, match="Installed overlay knowledge"):
    installed_check._check_knowledge()


def test_installed_ashmand_lookup_defect_is_rejected(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  monkeypatch.setattr(
    astrology, "ashmand_sign_group", lambda sign: astrology.AshmandSignGroup.FIXED
  )
  with pytest.raises(ValueError, match="four-group partition"):
    installed_check._check_knowledge()
