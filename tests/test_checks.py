"""Failures the development checks must catch. 开发检查必须发现的失败。"""

import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.check import check_documents, check_examples, check_wheel, document_errors, run


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


def test_missing_counterpart(docs: Path) -> None:
  (docs / "docs/zh-CN/index.md").unlink()
  with pytest.raises(ValueError, match="Missing language counterpart"):
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


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("count", [None, 0])
def test_examples_cannot_be_empty(language: str, count: int | None) -> None:
  report = ""
  for current in ("en", "zh-CN"):
    if current == language and count is None:
      continue
    report += f"Document: docs/{current}/contributing\n"
    report += f"{count if current == language else 2} tests in 1 item.\n"
  with pytest.raises(ValueError, match=language):
    check_examples(report)


@pytest.mark.parametrize("word", ["item", "items"])
def test_executed_examples(word: str) -> None:
  check_examples(
    "".join(
      f"Document: docs/{language}/contributing\n2 tests in 1 {word}.\n"
      for language in ("en", "zh-CN")
    )
  )


@pytest.mark.parametrize(
  "missing", ["astrology/__init__.py", "astrology/py.typed", "a.dist-info/licenses/LICENSE"]
)
def test_incomplete_wheel(tmp_path: Path, missing: str) -> None:
  wheel = tmp_path / "test.whl"
  with ZipFile(wheel, "w") as archive:
    for path in ("astrology/__init__.py", "astrology/py.typed", "a.dist-info/licenses/LICENSE"):
      if path != missing:
        archive.writestr(path, "")
    archive.writestr("a.dist-info/METADATA", "Name: astrology\nVersion: 0.0.0\n")
  with pytest.raises(ValueError, match="missing"):
    check_wheel(wheel, "0.0.0")


def test_wrong_wheel_version(tmp_path: Path) -> None:
  wheel = tmp_path / "test.whl"
  with ZipFile(wheel, "w") as archive:
    archive.writestr("a.dist-info/METADATA", "Name: astrology\nVersion: 9.0.0\n")
  with pytest.raises(ValueError, match="identity"):
    check_wheel(wheel, "0.0.0")
