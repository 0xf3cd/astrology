"""Failures the development checks must catch. 开发检查必须发现的失败。"""

import os
import subprocess
import sys
import tarfile
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from astrology.knowledge import load_catalog
from tools import check as checker
from tools import installed_check
from tools.check import (
  PACKAGE_FILES,
  SDIST_FILES,
  check_documents,
  check_examples,
  check_package_files,
  check_sdist,
  check_wheel,
  document_errors,
  run,
)

SDIST_PATHS = (*("src/" + name for name in PACKAGE_FILES), *SDIST_FILES)


@pytest.mark.parametrize(
  "modules",
  [
    installed_check.MODULES[:-1],
    (*installed_check.MODULES, "invented"),
    (*installed_check.MODULES, installed_check.MODULES[0]),
  ],
)
def test_consumer_module_guard_rejects_missing_extra_and_duplicate(
  monkeypatch: pytest.MonkeyPatch, modules: tuple[str, ...]
) -> None:
  monkeypatch.setattr(installed_check, "MODULES", modules)
  with pytest.raises(ValueError, match="module coverage"):
    check_package_files()


@pytest.fixture
def docs(tmp_path: Path) -> Path:
  for language in ("en", "zh-CN"):
    directory = tmp_path / "docs" / language
    directory.mkdir(parents=True)
    (directory / "index.md").write_text("# Index\n", encoding="utf-8")
  for name in ("README.md", "README.zh-CN.md"):
    (tmp_path / name).write_text("[Guide](docs/en/index.md)\n", encoding="utf-8")
  return tmp_path


def test_valid_documents(docs: Path) -> None:
  check_documents(docs)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_missing_counterpart(docs: Path, language: str) -> None:
  (docs / f"docs/{language}/index.md").unlink()
  with pytest.raises(ValueError, match=rf"Missing language counterpart: docs/{language}/index.md"):
    check_documents(docs)


def test_empty_document_tree(tmp_path: Path) -> None:
  with pytest.raises(ValueError, match="Both documentation languages"):
    check_documents(tmp_path)


@pytest.mark.parametrize(
  "link", ["[missing](lost.md)", "![image](lost.png)", "[ref][r]\n\n[r]: lost.md"]
)
def test_broken_local_link(docs: Path, link: str) -> None:
  (docs / "README.md").write_text(link, encoding="utf-8")
  with pytest.raises(ValueError, match="Broken local link"):
    check_documents(docs)


def test_code_is_not_a_link(docs: Path) -> None:
  (docs / "README.md").write_text("`[sample](absent.md)`\n", encoding="utf-8")
  check_documents(docs)


def test_external_links_and_fragments(docs: Path) -> None:
  (docs / "README.md").write_text("[web](https://example.org) [anchor](#index)", encoding="utf-8")
  check_documents(docs)


def test_encoded_local_path(docs: Path) -> None:
  (docs / "a b.md").write_text("text", encoding="utf-8")
  (docs / "README.md").write_text("[file](a%20b.md)", encoding="utf-8")
  check_documents(docs)


def test_missing_readme(docs: Path) -> None:
  (docs / "README.zh-CN.md").unlink()
  assert any("Missing document" in error for error in document_errors(docs))


def test_command_failure_propagates(tmp_path: Path) -> None:
  with pytest.raises(subprocess.CalledProcessError) as caught:
    run((sys.executable, "-c", "raise SystemExit(7)"), cwd=tmp_path)
  assert caught.value.returncode == 7


def test_direct_script_import_path() -> None:
  source = """
import runpy
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path[:] = [str(root / 'tools'), *(p for p in sys.path if p and Path(p).resolve() != root)]
runpy.run_path(str(root / 'tools/check.py'), run_name='script_startup_probe')
"""
  result = subprocess.run(
    [sys.executable, "-c", source, str(checker.ROOT)], capture_output=True, text=True
  )
  assert result.returncode == 0, result.stdout + result.stderr


def valid_example_report() -> str:
  return "".join(
    f"Document: docs/{language}/{page}\n2 tests in 1 items.\n"
    for language in ("en", "zh-CN")
    for page in (
      "contributing",
      "birth",
      "configuration",
      "chart",
      "aspects",
      "records",
      "knowledge",
    )
  )


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize(
  "page", ["contributing", "birth", "configuration", "chart", "aspects", "records", "knowledge"]
)
@pytest.mark.parametrize("count", [None, 0])
def test_examples_cannot_be_empty(language: str, page: str, count: int | None) -> None:
  section = f"Document: docs/{language}/{page}\n2 tests in 1 items.\n"
  replacement = "" if count is None else section.replace("2 tests", "0 tests")
  report = valid_example_report().replace(section, replacement)
  with pytest.raises(ValueError, match=f"{language}/{page}"):
    check_examples(report)


@pytest.mark.parametrize("word", ["item", "items"])
def test_executed_examples(word: str) -> None:
  check_examples(valid_example_report().replace("items.", f"{word}."))


def test_document_word_in_doctest_group() -> None:
  check_examples(
    valid_example_report().replace(
      "2 tests in 1 items.\n",
      "1 item passed all tests:\n   2 tests in Document: group\n2 tests in 1 item.\n",
    )
  )


def _package_tree(root: Path, names: Sequence[str]) -> None:
  for name in names:
    path = root / "src" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def test_every_package_file_is_listed() -> None:
  check_package_files()


def test_a_listed_package_tree_passes(tmp_path: Path) -> None:
  _package_tree(tmp_path, PACKAGE_FILES)
  pycache = tmp_path / "src" / "astrology" / "__pycache__"
  pycache.mkdir()
  (pycache / "module.cpython-314.pyc").write_bytes(b"")
  check_package_files(tmp_path)


@pytest.mark.parametrize("extra", ["astrology/new_module.py", "astrology/knowledge/data.json"])
def test_an_unlisted_package_file_is_rejected(tmp_path: Path, extra: str) -> None:
  _package_tree(tmp_path, (*PACKAGE_FILES, extra))
  with pytest.raises(ValueError, match="PACKAGE_FILES") as caught:
    check_package_files(tmp_path)
  assert extra in str(caught.value)


@pytest.mark.parametrize("missing", [*PACKAGE_FILES, "a.dist-info/licenses/LICENSE"])
def test_incomplete_wheel(tmp_path: Path, missing: str) -> None:
  wheel = tmp_path / "test.whl"
  with ZipFile(wheel, "w") as archive:
    for path in (*PACKAGE_FILES, "a.dist-info/licenses/LICENSE"):
      if path != missing:
        archive.writestr(path, "")
    archive.writestr("a.dist-info/METADATA", "Name: astrology\nVersion: 0.0.0\n")
  with pytest.raises(ValueError, match="missing"):
    check_wheel(wheel, "0.0.0")


@pytest.mark.parametrize("name, version", [("astrology", "9.0.0"), ("other", "0.0.0")])
def test_wrong_wheel_identity(tmp_path: Path, name: str, version: str) -> None:
  wheel = tmp_path / "test.whl"
  with ZipFile(wheel, "w") as archive:
    for path in ("astrology/__init__.py", "astrology/py.typed", "a.dist-info/licenses/LICENSE"):
      archive.writestr(path, "")
    archive.writestr("a.dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")
  with pytest.raises(ValueError, match="identity"):
    check_wheel(wheel, "0.0.0")


@pytest.mark.parametrize("count", [0, 2])
def test_wheel_metadata_count(tmp_path: Path, count: int) -> None:
  wheel = tmp_path / "test.whl"
  with ZipFile(wheel, "w") as archive:
    for index in range(count):
      archive.writestr(f"{index}.dist-info/METADATA", "Name: astrology\nVersion: 0.0.0\n")
  with pytest.raises(ValueError, match="one METADATA"):
    check_wheel(wheel, "0.0.0")


def test_main_keeps_required_validation_stages(monkeypatch: pytest.MonkeyPatch) -> None:
  commands: list[tuple[str, ...]] = []

  def capture(command: Sequence[str], *, cwd: Path = checker.ROOT) -> None:
    commands.append(tuple(command))
    if "-b" in command and command[command.index("-b") + 1] == "doctest":
      directory = Path(command[-1])
      directory.mkdir(parents=True)
      (directory / "output.txt").write_text(valid_example_report(), encoding="utf-8")

  monkeypatch.setattr(checker, "run", capture)
  monkeypatch.setattr(checker, "check_documents", lambda: commands.append(("documents",)))
  monkeypatch.setattr(checker, "check_api_html", lambda directory: commands.append(("api_html",)))
  monkeypatch.setattr(
    checker, "check_catalog_html", lambda directory: commands.append(("catalog_html",))
  )
  monkeypatch.setattr(
    checker, "check_search_html", lambda directory: commands.append(("search_html",))
  )
  monkeypatch.setattr(
    checker, "check_distribution", lambda directory: commands.append(("distribution",))
  )
  checker.main()
  assert any(command[:3] == (sys.executable, "-m", "pytest") for command in commands)
  assert any(command[:4] == (sys.executable, "-O", "-m", "pytest") for command in commands)
  assert [command[command.index("-b") + 1] for command in commands if "-b" in command] == [
    "html",
    "doctest",
  ]
  assert all(
    {"-E", "-a", "-n", "-W", "--keep-going"}.issubset(command)
    for command in commands
    if "sphinx" in command
  )
  assert ("documents",) in commands
  assert ("api_html",) in commands
  assert ("catalog_html",) in commands
  assert ("search_html",) in commands
  assert ("distribution",) in commands


def test_distribution_keeps_dependency_install_and_both_consumer_modes(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n', encoding="utf-8")
  commands: list[tuple[str, ...]] = []

  def capture(command: Sequence[str], *, cwd: Path = checker.ROOT) -> None:
    commands.append(tuple(command))
    if "build" in command:
      artifacts = Path(command[-1])
      artifacts.mkdir(parents=True)
      with tarfile.open(artifacts / "astrology.tar.gz", "w:gz") as archive:
        for name in SDIST_PATHS:
          archive.addfile(tarfile.TarInfo("astrology/" + name), BytesIO())
      with ZipFile(artifacts / "astrology.whl", "w") as archive:
        for name in (*PACKAGE_FILES, "a.dist-info/licenses/LICENSE"):
          archive.writestr(name, "")
        archive.writestr("a.dist-info/METADATA", "Name: astrology\nVersion: 0.0.0\n")

  monkeypatch.setattr(checker, "ROOT", tmp_path)
  monkeypatch.setattr(checker, "run", capture)
  checker.check_distribution(tmp_path)
  install = next(command for command in commands if command[:3] == ("uv", "pip", "install"))
  environment = tmp_path / "consumer"
  python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
  assert ("uv", "venv", "--python", sys.executable, str(environment)) in commands
  assert install == (
    "uv",
    "pip",
    "install",
    "--python",
    str(python),
    str(tmp_path / "artifacts/astrology.whl"),
  )
  consumers = [
    command for command in commands if str(tmp_path / "tools/installed_check.py") in command
  ]
  assert len(consumers) == 4
  assert all(command[0] == str(python) for command in consumers)
  assert all("-I" in command and "0.0.0" in command for command in consumers)
  assert all(load_catalog().version in command for command in consumers)
  assert ["-O" in command for command in consumers] == [False, False, True, True]
  assert ["--knowledge-only" in command for command in consumers] == [True, False, True, False]
  assert ["--expected-chart" in command for command in consumers] == [False, True, False, True]
  assert all(
    str(tmp_path / "development-chart.json") in command
    for command in consumers
    if "--expected-chart" in command
  )
  assert (tmp_path / "development-chart.json").is_file()


@pytest.mark.parametrize("missing", [None, *SDIST_PATHS])
def test_sdist_resource_contents(tmp_path: Path, missing: str | None) -> None:
  sdist = tmp_path / "package.tar.gz"
  with tarfile.open(sdist, "w:gz") as archive:
    for name in SDIST_PATHS:
      if name != missing:
        archive.addfile(tarfile.TarInfo("astrology/" + name), BytesIO())
  if missing is None:
    check_sdist(sdist)
  else:
    with pytest.raises(ValueError, match="Sdist is missing"):
      check_sdist(sdist)
