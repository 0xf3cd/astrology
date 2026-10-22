"""Failures the development checks must catch. 开发检查必须发现的失败。"""

import ast
import inspect
import json
import os
import subprocess
import sys
import tarfile
from collections.abc import Mapping, Sequence
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
_EXAMPLE_PAGES = (
  "contributing",
  "birth",
  "configuration",
  "chart",
  "aspects",
  "records",
  "knowledge",
)


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


def test_command_receives_explicit_environment(tmp_path: Path) -> None:
  run(
    (
      sys.executable,
      "-c",
      "import os; raise SystemExit(0 if os.environ['ASTROLOGY_CHECK_TEST'] == 'source' else 1)",
    ),
    cwd=tmp_path,
    env={**os.environ, "ASTROLOGY_CHECK_TEST": "source"},
  )


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
    for page in _EXAMPLE_PAGES
  )


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("page", _EXAMPLE_PAGES)
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
    archive.writestr("a.dist-info/METADATA", "Name: celestial-astrology\nVersion: 0.0.0\n")
  with pytest.raises(ValueError, match="missing"):
    check_wheel(wheel, "0.0.0")


@pytest.mark.parametrize(
  "name, version",
  [("celestial-astrology", "9.0.0"), ("astrology", "0.0.0"), ("other", "0.0.0")],
)
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
      archive.writestr(f"{index}.dist-info/METADATA", "Name: celestial-astrology\nVersion: 0.0.0\n")
  with pytest.raises(ValueError, match="one METADATA"):
    check_wheel(wheel, "0.0.0")


def test_main_keeps_required_validation_stages(monkeypatch: pytest.MonkeyPatch) -> None:
  commands: list[tuple[str, ...]] = []
  monkeypatch.setenv("ASTROLOGY_DOCS_SOURCE_SHA", "a" * 40)

  def site(directory: Path, *, source_revision: str) -> None:
    assert source_revision == "a" * 40
    commands.append(("site_html",))

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
  monkeypatch.setattr(checker, "check_site_html", site)
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
  assert ("site_html",) in commands
  assert ("distribution",) in commands


def test_distribution_keeps_dependency_install_and_both_consumer_modes(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n', encoding="utf-8")
  commands: list[tuple[str, ...]] = []
  contexts: list[tuple[Path, Mapping[str, str] | None]] = []
  validations: list[tuple[str, Path]] = []
  readme_calls: list[tuple[Path, Path, Path, tuple[str, ...]]] = []
  metadata_calls: list[tuple[Path, Path, Path, Path]] = []
  site_calls: list[tuple[Path, Path, str]] = []
  monkeypatch.setenv("ASTROLOGY_DOCS_SOURCE_SHA", "b" * 40)

  def site(directory: Path, *, root: Path, source_revision: str) -> None:
    site_calls.append((directory, root, source_revision))

  def capture(
    command: Sequence[str], *, cwd: Path = checker.ROOT, env: Mapping[str, str] | None = None
  ) -> None:
    commands.append(tuple(command))
    contexts.append((cwd, env))
    if "--sdist" in command:
      artifacts = Path(command[-1])
      artifacts.mkdir(parents=True)
      with tarfile.open(artifacts / "astrology.tar.gz", "w:gz") as archive:
        for name in SDIST_PATHS:
          archive.addfile(tarfile.TarInfo("astrology/" + name), BytesIO())
    if "--wheel" in command:
      artifacts = Path(command[-1])
      with ZipFile(artifacts / "astrology.whl", "w") as archive:
        for name in (*PACKAGE_FILES, "a.dist-info/licenses/LICENSE"):
          archive.writestr(name, "")
        archive.writestr(
          "a.dist-info/METADATA",
          "Name: celestial-astrology\nVersion: 0.0.0\n"
          "Description-Content-Type: text/markdown\n\n[Docs](https://example.org/)\n",
        )
    if "-b" in command and command[command.index("-b") + 1] == "doctest":
      output = Path(command[-1])
      output.mkdir(parents=True)
      (output / "output.txt").write_text(valid_example_report(), encoding="utf-8")

  monkeypatch.setattr(checker, "ROOT", tmp_path)
  monkeypatch.setattr(checker, "run", capture)
  original_check_sdist = checker.check_sdist

  def validate_sdist(sdist: Path) -> None:
    original_check_sdist(sdist)
    validations.append(("sdist", sdist))

  monkeypatch.setattr(checker, "check_sdist", validate_sdist)
  monkeypatch.setattr(
    checker, "check_documents", lambda root: validations.append(("documents", root))
  )
  monkeypatch.setattr(checker, "check_api_html", lambda root: validations.append(("api", root)))
  monkeypatch.setattr(
    checker, "check_catalog_html", lambda root: validations.append(("catalog", root))
  )
  monkeypatch.setattr(
    checker, "check_search_html", lambda root: validations.append(("search", root))
  )
  monkeypatch.setattr(checker, "check_site_html", site)
  monkeypatch.setattr(
    checker,
    "check_readme_examples",
    lambda root, python, directory, mode: readme_calls.append((root, python, directory, mode)),
  )
  monkeypatch.setattr(
    checker,
    "check_missing_metadata",
    lambda environment, python, script, chart: metadata_calls.append(
      (environment, python, script, chart)
    ),
  )
  checker.check_distribution(tmp_path)
  source = tmp_path / "source/astrology"
  wheel_index = next(index for index, command in enumerate(commands) if "--wheel" in command)
  assert contexts[wheel_index][0] == source
  documentation = [
    (command, context)
    for command, context in zip(commands, contexts, strict=True)
    if "sphinx" in command
  ]
  assert [command[command.index("-b") + 1] for command, _ in documentation] == [
    "html",
    "doctest",
  ]
  for command, (cwd, env) in documentation:
    assert cwd == source
    assert env is not None and env["PYTHONPATH"] == str(source / "src")
    assert {"-E", "-a", "-n", "-W", "--keep-going"}.issubset(command)
    assert command[-4:-1] == ("-c", "docs", ".")
  assert ("sdist", tmp_path / "artifacts/astrology.tar.gz") in validations
  assert ("documents", source) in validations
  assert {name for name, path in validations if path == tmp_path / "source-html"} == {
    "api",
    "catalog",
    "search",
  }
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
    command for command in commands if str(source / "tools/installed_check.py") in command
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
  assert site_calls == [(tmp_path / "source-html", source, "b" * 40)]
  assert readme_calls == [
    (source, python, tmp_path, ()),
    (source, python, tmp_path, ("-O",)),
  ]
  assert metadata_calls == [
    (environment, python, source / "tools/installed_check.py", tmp_path / "development-chart.json")
  ]


@pytest.mark.parametrize(
  ("stage", "shape", "message"),
  [
    ("sdist", "empty", "Expected one sdist"),
    ("sdist", "multiple", "Expected one sdist"),
    ("source", "multiple", "Sdist must contain one source directory"),
    ("source", "file", "Sdist must contain one source directory"),
    ("wheel", "empty", "Expected one wheel"),
    ("wheel", "multiple", "Expected one wheel"),
  ],
)
def test_distribution_rejects_malformed_build_outputs(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, shape: str, message: str
) -> None:
  (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n', encoding="utf-8")

  def capture(
    command: Sequence[str], *, cwd: Path = checker.ROOT, env: Mapping[str, str] | None = None
  ) -> None:
    artifacts = tmp_path / "artifacts"
    if "--sdist" in command:
      artifacts.mkdir()
      count = (0 if shape == "empty" else 2) if stage == "sdist" else 1
      for index in range(count):
        with tarfile.open(artifacts / f"source-{index}.tar.gz", "w:gz") as archive:
          roots = 2 if stage == "source" else 1
          if stage == "source" and shape == "file":
            archive.addfile(tarfile.TarInfo("not-a-directory"), BytesIO())
          else:
            for root in range(roots):
              member = tarfile.TarInfo(f"source-{root}")
              member.type = tarfile.DIRTYPE
              archive.addfile(member)
    elif "--wheel" in command:
      count = (0 if shape == "empty" else 2) if stage == "wheel" else 1
      for index in range(count):
        (artifacts / f"wheel-{index}.whl").write_bytes(b"")

  monkeypatch.setattr(checker, "ROOT", tmp_path)
  monkeypatch.setattr(checker, "run", capture)
  monkeypatch.setattr(checker, "check_sdist", lambda _sdist: None)
  with pytest.raises(ValueError, match=message):
    checker.check_distribution(tmp_path)


@pytest.mark.parametrize("mode", ["direct", "alias", "outside"])
def test_sdist_import_guard_resolves_both_paths_and_rejects_outside_imports(
  tmp_path: Path, mode: str
) -> None:
  tree = ast.parse(inspect.getsource(checker.check_distribution))
  scripts = [
    node.value
    for node in ast.walk(tree)
    if isinstance(node, ast.Constant)
    and isinstance(node.value, str)
    and node.value.startswith("from pathlib import Path\nimport astrology\n")
  ]
  assert len(scripts) == 1
  source = tmp_path / "source"
  source.mkdir()
  actual = source / "src/astrology/__init__.py"
  cwd = source
  if mode == "alias":
    cwd = tmp_path / "alias"
    try:
      cwd.symlink_to(source, target_is_directory=True)
    except OSError as exc:
      pytest.skip(f"Directory symlinks unavailable: {exc}")
  elif mode == "outside":
    actual = tmp_path / "other/astrology/__init__.py"
  prefix = (
    "import sys\nfrom pathlib import Path\nimport astrology\n"
    "astrology.__file__ = sys.argv[1]\n"
    "Path.cwd = classmethod(lambda cls: Path(sys.argv[2]))\n"
  )
  result = subprocess.run(
    [sys.executable, "-c", prefix + scripts[0], str(actual), str(cwd)],
    capture_output=True,
    text=True,
  )
  if mode == "outside":
    assert result.returncode == 1
    assert "astrology imported from" in result.stderr
  else:
    assert result.returncode == 0, result.stdout + result.stderr


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


@pytest.mark.parametrize("failure", [False, True])
def test_metadata_is_hidden_separately_and_restored_on_failure(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
  environment = tmp_path / "consumer"
  environment.mkdir()
  packages = ("celestial-astrology", "celestial-calendar")
  paths = {package: environment / f"{package}.dist-info" for package in packages}
  for path in paths.values():
    path.mkdir()
    (path / "METADATA").write_text("original", encoding="utf-8")
  commands: list[tuple[str, ...]] = []

  def locate(command: Sequence[str], **kwargs: object) -> str:
    assert "-I" in command
    return json.dumps(str(paths[command[-1]]))

  def execute(command: Sequence[str], *, cwd: Path) -> None:
    package = command[-2]
    assert cwd == tmp_path
    assert not paths[package].exists()
    assert paths[package].with_suffix(".dist-info.hidden").is_dir()
    assert all(paths[other].is_dir() for other in packages if other != package)
    commands.append(tuple(command))
    if failure:
      raise subprocess.CalledProcessError(7, command)

  monkeypatch.setattr(subprocess, "check_output", locate)
  monkeypatch.setattr(checker, "run", execute)
  arguments = (environment, Path(sys.executable), tmp_path / "consumer.py", tmp_path / "chart.json")
  if failure:
    with pytest.raises(subprocess.CalledProcessError):
      checker.check_missing_metadata(*arguments)
  else:
    checker.check_missing_metadata(*arguments)
    assert [command[-2] for command in commands] == [
      packages[0],
      packages[0],
      packages[1],
      packages[1],
    ]
    assert ["-O" in command for command in commands] == [False, True, False, True]
  assert all(
    path.is_dir() and (path / "METADATA").read_text(encoding="utf-8") == "original"
    for path in paths.values()
  )
  assert not list(environment.glob("*.hidden"))


@pytest.mark.parametrize("defect", ["outside", "suffix", "file", "occupied", "non-string"])
def test_metadata_hiding_refuses_unsafe_locations(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
  environment = tmp_path / "consumer"
  environment.mkdir()
  path = (tmp_path if defect == "outside" else environment) / "package.dist-info"
  if defect == "suffix":
    path = environment / "package"
  if defect == "file":
    path.touch()
  else:
    path.mkdir()
  if defect == "occupied":
    path.with_suffix(".dist-info.hidden").mkdir()
  monkeypatch.setattr(
    subprocess,
    "check_output",
    lambda *args, **kwargs: json.dumps(None if defect == "non-string" else str(path)),
  )
  with pytest.raises(ValueError, match="metadata location"):
    checker.check_missing_metadata(
      environment, Path(sys.executable), tmp_path / "script.py", tmp_path / "chart.json"
    )
  assert path.exists()
