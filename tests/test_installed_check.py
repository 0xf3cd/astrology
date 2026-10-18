"""Installed-consumer rejection cases. 安装后消费者的拒绝用例。"""

import sys
from importlib.metadata import version
from pathlib import Path
from types import ModuleType

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
  monkeypatch.setattr(sys, "prefix", str(tmp_path))
  return package


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
