"""Run repository checks. 运行仓库检查。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]


def run(command: Sequence[str], *, cwd: Path = ROOT) -> None:
  """Run a command and propagate failure. 执行命令并传播失败。"""
  print(f"+ {' '.join(command)}", flush=True)
  subprocess.run(command, cwd=cwd, check=True)


def document_errors(root: Path) -> tuple[str, ...]:
  """Check paired pages and local file links. 检查双语页面与本地文件链接。"""
  errors: list[str] = []
  language_roots = (root / "docs/en", root / "docs/zh-CN")
  page_sets = tuple(
    {p.relative_to(directory) for p in directory.rglob("*.md")} for directory in language_roots
  )
  if not all(page_sets):
    errors.append("Both documentation languages must contain pages")
  for missing in sorted(page_sets[0] ^ page_sets[1]):
    errors.append(f"Missing language counterpart: {missing}")

  parser = MarkdownIt("commonmark")
  pages = (root / "README.md", root / "README.zh-CN.md", *sorted((root / "docs").rglob("*.md")))
  for page in pages:
    if not page.is_file():
      errors.append(f"Missing document: {page.relative_to(root)}")
      continue
    for token in parser.parse(page.read_text(encoding="utf-8")):
      for child in token.children or ():
        target = child.attrGet("href") if child.type == "link_open" else child.attrGet("src")
        if not isinstance(target, str) or not target:
          continue
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
          continue
        if not (page.parent / unquote(url.path)).exists():
          errors.append(f"Broken local link in {page.relative_to(root)}: {target}")
  return tuple(errors)


def check_documents(root: Path = ROOT) -> None:
  """Reject incomplete document trees. 拒绝不完整的文档树。"""
  errors = document_errors(root)
  if errors:
    raise ValueError("\n".join(errors))


def check_examples(report: str) -> None:
  """Require executed examples in both languages. 要求两种语言均有已执行的例子。"""
  for language in ("en", "zh-CN"):
    marker = f"Document: docs/{language}/contributing\n"
    section = report.partition(marker)[2].split("Document:")[0]
    if not re.search(r"(?m)^[1-9]\d* tests? in \d+ items?\.$", section):
      raise ValueError(f"No executed documentation examples for {language}")


def check_wheel(wheel: Path, expected_version: str) -> None:
  """Validate wheel content and metadata. 校验 wheel 内容与元数据。"""
  from email.parser import Parser

  with ZipFile(wheel) as archive:
    names = archive.namelist()
    metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
    if len(metadata_paths) != 1:
      raise ValueError("Wheel must contain one METADATA file")
    metadata = Parser().parsestr(archive.read(metadata_paths[0]).decode("utf-8"))
    if metadata["Name"] != "astrology" or metadata["Version"] != expected_version:
      raise ValueError("Wheel identity differs from project metadata")
    if "astrology/py.typed" not in names or "astrology/__init__.py" not in names:
      raise ValueError("Wheel is missing the package or typing marker")
    if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
      raise ValueError("Wheel is missing its license")


def check_distribution(directory: Path) -> None:
  """Build via sdist and test an isolated install. 经 sdist 构建并验证隔离安装。"""
  metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  artifacts = directory / "artifacts"
  run((sys.executable, "-m", "build", "--outdir", str(artifacts)))
  wheels = tuple(artifacts.glob("*.whl"))
  if len(wheels) != 1 or len(tuple(artifacts.glob("*.tar.gz"))) != 1:
    raise ValueError("Expected one wheel and one sdist")
  check_wheel(wheels[0], metadata["version"])

  environment = directory / "consumer"
  run(("uv", "venv", "--python", sys.executable, str(environment)))
  python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
  run(("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheels[0])))
  for mode in ((), ("-O",)):
    run(
      (str(python), *mode, "-I", str(ROOT / "tools/installed_check.py"), metadata["version"]),
      cwd=directory,
    )


def main() -> None:
  """Run all checks, stopping on failure. 运行全部检查，失败即停止。"""
  commands = (
    ("-m", "ruff", "check", "."),
    ("-m", "ruff", "format", "--check", "."),
    ("-m", "mypy"),
    ("-m", "pytest", "--cov", "--cov-report=term-missing"),
    (
      "-O",
      "-m",
      "pytest",
      "-W",
      "ignore:assertions not in test modules or plugins:pytest.PytestConfigWarning",
    ),
  )
  for arguments in commands:
    run((sys.executable, *arguments))
  check_documents()
  with tempfile.TemporaryDirectory(
    prefix="astrology-check-", dir=os.environ.get("SCRATCH")
  ) as temporary:
    directory = Path(temporary)
    for builder in ("html", "doctest"):
      run(
        (
          sys.executable,
          "-m",
          "sphinx",
          "-E",
          "-a",
          "-n",
          "-W",
          "--keep-going",
          "-b",
          builder,
          "-c",
          "docs",
          ".",
          str(directory / builder),
        )
      )
    results = (directory / "doctest/output.txt").read_text(encoding="utf-8")
    check_examples(results)
    check_distribution(directory)
  print("All checks passed.")


if __name__ == "__main__":
  main()
