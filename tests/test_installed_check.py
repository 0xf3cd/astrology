"""Installed-consumer rejection cases. 安装后消费者的拒绝用例。"""

import json
import sys
from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from importlib import import_module
from importlib.metadata import version
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
    installed_check.main(version("astrology"))


def test_wrong_installed_version_rejected(consumer: Path) -> None:
  with pytest.raises(ValueError, match="Installed version"):
    installed_check.main("unrelated-version")


@pytest.mark.parametrize(
  "module",
  ["astrology." + name for name in installed_check.MODULES],
)
def test_submodule_outside_consumer_rejected(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
  monkeypatch.setattr(import_module(module), "__file__", str(consumer.parent.parent / "outside.py"))
  with pytest.raises(ValueError, match="outside the consumer environment"):
    installed_check.main(version("astrology"))


def test_missing_installed_typing_marker_rejected(consumer: Path) -> None:
  (consumer / "py.typed").unlink()
  with pytest.raises(ValueError, match=r"missing py\.typed"):
    installed_check.main(version("astrology"))


@pytest.mark.parametrize(
  "module", ["celestial_calendar", "celestial_calendar._binding", "astrology.celestial"]
)
def test_loaded_astronomy_rejected(
  consumer: Path, monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
  monkeypatch.setitem(sys.modules, module, ModuleType(module))
  with pytest.raises(ValueError, match="astronomy adapter"):
    installed_check.main(version("astrology"))


def test_similar_module_name_allowed(consumer: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setitem(
    sys.modules, "celestial_calendar_extra", ModuleType("celestial_calendar_extra")
  )
  installed_check.main(version("astrology"))


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
    installed_check.main(version("astrology"))


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
    installed_check.main(version("astrology"))


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
    installed_check.main(version("astrology"))


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
    installed_check.main(version("astrology"))


def test_installed_consumer_rejects_missing_coordinate_validation(
  consumer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  original = astrology.Location

  def accepts_nan(latitude: float, longitude: float) -> astrology.Location:
    return original(0, longitude)

  monkeypatch.setattr(astrology, "Location", accepts_nan)
  with pytest.raises(ValueError, match="accepted NaN"):
    installed_check.main(version("astrology"))


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
    installed_check.main(version("astrology"))


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
  installed_check.main(version("astrology"))
  assert len(calls) == 2
  assert calls[0].house_system is astrology.HouseSystem.WHOLE_SIGN
  assert calls[1].house_system is astrology.HouseSystem.PLACIDUS
  assert calls[0].aspects
  assert calls[0].orb_combination is astrology.OrbCombination.MEAN_OF_ORBS


def test_installed_comparison_rejects_different_development_output(consumer: Path) -> None:
  expected = consumer.parent / "wrong-chart.json"
  expected.write_text("{}", encoding="utf-8")
  with pytest.raises(ValueError, match="differs from the development"):
    installed_check.main(version("astrology"), expected_chart=expected)


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
    installed_check.main(version("astrology"))


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
    installed_check.main(version("astrology"))


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
  installed_check.main(version("astrology"), knowledge_only=True)


@pytest.mark.parametrize(
  "defect",
  [
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
  if defect == "alias":
    data["concepts"][0]["en_aliases"] = ["different"]
  elif defect == "translation":
    del data["entries"][-1]["citations"][0]["excerpt"]["zh"]
  elif defect == "source_condition":
    data["entries"][-1]["citations"][0]["excerpt"]["en"] = "Truncated quotation."
  elif defect == "verification":
    data["sources"][-1]["verification"] = "unverified"
  else:
    data["entries"][-1][defect] = "complete" if defect == "prerequisite_status" else "eligible"
  path.write_text(json.dumps(data), encoding="utf-8")
  with pytest.raises(ValueError):
    installed_check._check_knowledge()
