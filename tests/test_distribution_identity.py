"""Distribution lookup and metadata-free imports. 分发包查询与不读取元数据的导入。"""

import subprocess
import sys
import tomllib
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from pathlib import Path

import pytest

import astrology
from astrology import _distribution


def test_chart_persistence_is_not_a_public_or_importable_api() -> None:
  removed = {
    "dumps_chart",
    "loads_chart",
    "recompute_chart",
    "ChartRecordError",
    "ChartReplayError",
  }
  assert not removed.intersection(astrology.__all__)
  assert not any(hasattr(astrology, name) for name in removed)
  assert find_spec("astrology.serialization") is None


def test_packaging_and_installed_identity_agree_without_changing_import_name() -> None:
  project = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
  )["project"]
  assert project["name"] == "celestial-astrology"
  assert project["version"] == "0.3.0"
  assert project["name"] == _distribution.DISTRIBUTION_NAME
  assert version("celestial-astrology") == project["version"]
  assert project["dependencies"] == ["celestial-calendar==0.8.0", "tzdata==2026.5"]


def test_version_lookup_is_explicit_and_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
  calls: list[str] = []

  def lookup(name: str) -> str:
    calls.append(name)
    return str(len(calls))

  monkeypatch.setattr(_distribution, "version", lookup)
  assert _distribution.installed_version() == "1"
  assert _distribution.installed_version() == "2"
  assert calls == ["celestial-astrology", "celestial-astrology"]


def test_identity_lookup_keeps_missing_metadata_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
  missing = PackageNotFoundError("celestial-astrology")

  def lookup(name: str) -> str:
    raise missing

  monkeypatch.setattr(_distribution, "version", lookup)
  with pytest.raises(PackageNotFoundError) as error:
    _distribution.installed_version()
  assert error.value is missing


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_import_and_knowledge_need_no_metadata(
  mode: tuple[str, ...],
) -> None:
  source = """
import importlib.metadata as metadata
import sys
def forbidden(*args, **kwargs):
  raise RuntimeError('Import and knowledge must not read distribution metadata')
metadata.version = forbidden
metadata.distribution = forbidden
import astrology
if astrology.load_catalog().lookup('Sun')[0].identifier != 'body.sun':
  raise RuntimeError('Knowledge lookup changed')
if any(name.startswith(('celestial_calendar', 'astrology.celestial')) for name in sys.modules):
  raise RuntimeError('Metadata-free import or knowledge initialized astronomy')
"""
  result = subprocess.run(
    [sys.executable, *mode, "-c", source],
    capture_output=True,
    text=True,
    encoding="utf-8",
  )
  assert result.returncode == 0, result.stdout + result.stderr
