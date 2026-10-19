"""Installed-consumer rejection cases. 安装后消费者的拒绝用例。"""

import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Literal, cast

import pytest

import astrology
from tools import installed_check


@pytest.fixture
def consumer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
  package = tmp_path / "astrology"
  package.mkdir()
  (package / "__init__.py").touch()
  (package / "py.typed").touch()
  monkeypatch.setattr(astrology, "__file__", str(package / "__init__.py"))
  for name in ("birth", "config"):
    monkeypatch.setattr(import_module(f"astrology.{name}"), "__file__", str(package / f"{name}.py"))
  monkeypatch.setattr(sys, "prefix", str(tmp_path))
  return package


def test_import_outside_consumer_rejected(consumer: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(sys, "prefix", str(consumer.parent / "other-environment"))
  with pytest.raises(ValueError, match="outside the consumer environment"):
    installed_check.main(version("astrology"))


def test_wrong_installed_version_rejected(consumer: Path) -> None:
  with pytest.raises(ValueError, match="Installed version"):
    installed_check.main("unrelated-version")


@pytest.mark.parametrize("module", ["astrology.birth", "astrology.config"])
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


@pytest.mark.parametrize("module", ["celestial_calendar", "celestial_calendar._binding"])
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
  with pytest.raises(ValueError, match=r"UTC date rollover|timezone-database provenance"):
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
