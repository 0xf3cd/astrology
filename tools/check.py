"""Run repository checks. 运行仓库检查。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from collections.abc import Sequence
from enum import Enum
from html.parser import HTMLParser
from inspect import isfunction
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

if __package__ in (None, ""):
  # Direct script invocation puts tools/, not the repository root, on sys.path.
  sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from markdown_it import MarkdownIt

import astrology
from astrology import knowledge
from astrology.knowledge import Concept, Entry, RuleVariant, Source, load_catalog
from astrology.knowledge.records import Language
from tools.catalog_docs import (
  catalog_anchor,
  check_catalog_data,
  configuration_reference,
  localized_texts,
)
from tools.docs_search import check_search_html

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILES = (
  "astrology/__init__.py",
  "astrology/_validation.py",
  "astrology/py.typed",
  "astrology/aspects.py",
  "astrology/birth.py",
  "astrology/celestial.py",
  "astrology/chart.py",
  "astrology/config.py",
  "astrology/houses.py",
  "astrology/serialization.py",
  "astrology/text.py",
  "astrology/zodiac.py",
  "astrology/knowledge/__init__.py",
  "astrology/knowledge/records.py",
  "astrology/knowledge/catalog.py",
  "astrology/knowledge/catalog.json",
)

# Files outside the package that the tests in the source distribution read.
# 源码分发包里的测试要读取、但不在包内的文件。
SDIST_FILES = (
  "tests/reference/natal_reference.json",
  "tests/reference/complete_chart_reference.json",
  "tests/reference/chart_record_v1.json",
)


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
  for directory, existing, counterparts in (
    (language_roots[0], page_sets[0], page_sets[1]),
    (language_roots[1], page_sets[1], page_sets[0]),
  ):
    for missing in sorted(counterparts - existing):
      path = (directory / missing).relative_to(root).as_posix()
      errors.append(f"Missing language counterpart: {path}")

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
  """Require executed bilingual development and API-guide examples.

  要求双语开发指南与 API 指南均有已执行的例子。
  """
  for language in ("en", "zh-CN"):
    for page in (
      "contributing",
      "birth",
      "configuration",
      "chart",
      "aspects",
      "records",
      "knowledge",
    ):
      marker = f"Document: docs/{language}/{page}\n"
      section = re.split(r"(?m)^Document: ", report.partition(marker)[2], maxsplit=1)[0]
      if not re.search(r"(?m)^[1-9]\d* tests? in \d+ items?\.$", section):
        raise ValueError(f"No executed documentation examples for {language}/{page}")


class _ApiHtml(HTMLParser):
  """Read rendered Sphinx signature names, not names embedded in raw directive text."""

  def __init__(self) -> None:
    super().__init__()
    self.names: set[str] = set()
    self.links: set[str] = set()
    self.language: str | None = None
    self._name_depth = 0
    self._name_parts: list[str] = []

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    attributes = dict(attrs)
    if tag == "html":
      self.language = attributes.get("lang")
    if tag == "a" and (target := attributes.get("href")):
      self.links.add(target)
    if self._name_depth:
      self._name_depth += 1
    elif tag == "span" and "sig-name" in (attributes.get("class") or "").split():
      self._name_depth = 1
      self._name_parts = []

  def handle_endtag(self, tag: str) -> None:
    if self._name_depth:
      self._name_depth -= 1
      if self._name_depth == 0:
        self.names.add("".join(self._name_parts).strip())

  def handle_data(self, data: str) -> None:
    if self._name_depth:
      self._name_parts.append(data)


def check_api_html(directory: Path) -> None:
  """Require rendered public signatures and enum members in both language views.

  要求两种语言视图均渲染公开签名和枚举成员。
  """
  expected = set(astrology.__all__) | set(knowledge.__all__)
  for module in (astrology, knowledge):
    for name in module.__all__:
      value = getattr(module, name)
      if isinstance(value, type) and issubclass(value, Enum):
        expected.update(value.__members__)
      if isinstance(value, type):
        expected.update(
          name
          for name, member in vars(value).items()
          if not name.startswith("_") and (isfunction(member) or isinstance(member, property))
        )
  for language, counterpart in (("en", "zh-CN"), ("zh-CN", "en")):
    page = directory / "docs" / language / "reference.html"
    if not page.is_file():
      raise ValueError(f"Missing API HTML for {language}")
    parser = _ApiHtml()
    parser.feed(page.read_text(encoding="utf-8"))
    missing = expected - parser.names
    if missing:
      raise ValueError(f"Missing rendered API names for {language}: {', '.join(sorted(missing))}")
    if parser.language != language:
      raise ValueError(f"Incorrect API HTML language for {language}")
    if f"../{counterpart}/reference.html" not in parser.links:
      raise ValueError(f"Missing API HTML counterpart navigation for {language}")


def check_package_files(root: Path = ROOT) -> None:
  """Require every file under the package source to be listed in PACKAGE_FILES.

  The wheel and sdist checks only look for the listed files, so an unlisted new
  module would be missing from the artifacts without any check noticing.

  要求包源码下的每个文件都列在 PACKAGE_FILES 里。wheel 和 sdist 的检查只找列出的文件，
  新增的模块如果没列进去，即使制品里缺了它，也不会有任何检查发现。
  """
  package = root / "src" / "astrology"
  present = {
    path.relative_to(package.parent).as_posix()
    for path in package.rglob("*")
    if path.is_file() and "__pycache__" not in path.parts
  }
  if unlisted := present - set(PACKAGE_FILES):
    raise ValueError(f"Package files missing from PACKAGE_FILES: {sorted(unlisted)}")
  from tools.installed_check import MODULES

  expected_modules = {
    name.removeprefix("astrology/").removesuffix(".py").removesuffix("/__init__").replace("/", ".")
    for name in PACKAGE_FILES
    if name.endswith(".py")
  } - {"__init__", "celestial"}
  if set(MODULES) != expected_modules or len(MODULES) != len(set(MODULES)):
    raise ValueError("Installed-consumer module coverage differs from PACKAGE_FILES")


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
    if missing := set(PACKAGE_FILES) - set(names):
      raise ValueError(f"Wheel is missing package resources: {sorted(missing)}")
    if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
      raise ValueError("Wheel is missing its license")


def check_sdist(sdist: Path) -> None:
  """Require the complete package, corpus and reference fixture in the source distribution.

  要求源码分发包里有完整的包、语料和参考夹具。
  """
  with tarfile.open(sdist) as archive:
    names = {name.partition("/")[2] for name in archive.getnames()}
  expected = {"src/" + name for name in PACKAGE_FILES} | set(SDIST_FILES)
  if missing := expected - names:
    raise ValueError(f"Sdist is missing package resources: {sorted(missing)}")


class _CatalogHtml(_ApiHtml):
  """Read record-local text and anchors from rendered sections, not directive source."""

  def __init__(self) -> None:
    super().__init__()
    self.records: dict[str, list[str]] = {}
    self.text: list[str] = []
    self._sections: list[list[str] | None] = []
    self.link_labels: dict[str, list[str]] = {}
    self._link: str | None = None
    self._label: list[str] = []

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    super().handle_starttag(tag, attrs)
    if tag == "a":
      self._link = dict(attrs).get("href")
      self._label = []
    if tag == "section":
      self._sections.append(None)
    identifier = dict(attrs).get("id")
    if identifier and identifier.startswith("catalog-") and self._sections:
      block: list[str] = []
      self.records[identifier] = block
      self._sections[-1] = block

  def handle_endtag(self, tag: str) -> None:
    super().handle_endtag(tag)
    if tag == "a" and self._link is not None:
      self.link_labels.setdefault(self._link, []).append("".join(self._label))
      self._link = None
    if tag == "section" and self._sections:
      self._sections.pop()

  def handle_data(self, data: str) -> None:
    super().handle_data(data)
    if self._link is not None:
      self._label.append(data)
    self.text.append(data)
    for section in self._sections:
      if section is not None:
        section.append(data)


def check_catalog_html(directory: Path) -> None:
  """Check complete rendered records, text, versions and bilingual navigation.

  检查完整渲染的记录、文本、版本及双语导航。
  """
  catalog = load_catalog()
  check_catalog_data(catalog)

  def content(value: str) -> str:
    typography = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
    return " ".join(value.translate(typography).split())

  code_version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
    "version"
  ]
  languages: tuple[Language, ...] = ("en", "zh-CN")
  for language in languages:
    counterpart = "zh-CN" if language == "en" else "en"
    page = directory / "docs" / language / "catalog.html"
    parser = _CatalogHtml()
    parser.feed(page.read_text(encoding="utf-8"))
    if parser.language != language or f"../{counterpart}/catalog.html" not in parser.links:
      raise ValueError(f"Incorrect catalog language or counterpart navigation: {language}")
    text = content("".join(parser.text))
    if f"code={code_version}" not in text or f"corpus={catalog.version}" not in text:
      raise ValueError("Missing code/corpus version in generated catalog")
    for group in (catalog.concepts, catalog.variants, catalog.sources, catalog.entries):
      for record in group:
        anchor = catalog_anchor(record.identifier, language)
        if anchor not in parser.records:
          raise ValueError(f"Missing rendered catalog record: {record.identifier} ({language})")
        block = content("".join(parser.records[anchor]))
        for path, value in localized_texts(record):
          selected = value.text(language)
          if selected is None or content(selected) not in block:
            raise ValueError(
              f"Missing rendered catalog text: {record.identifier}/{path} ({language})"
            )
        required = [record.identifier]
        if isinstance(record, Concept):
          required.extend(
            (*record.en_aliases, *record.zh_aliases, *record.related, f"kind={record.kind}")
          )
        elif isinstance(record, RuleVariant):
          required.extend(record.concept_ids)
        elif isinstance(record, Source):
          required.extend(
            (
              record.title,
              record.author,
              record.edition,
              f"language={record.language}",
              f"source_verification={record.verification}",
            )
          )
          if record.url not in parser.links:
            raise ValueError(f"Missing rendered source link: {record.identifier}")
          if record.url not in parser.link_labels.get(record.url, ()):
            raise ValueError(f"Changed rendered source URL label: {record.identifier}")
        elif isinstance(record, Entry):
          required.extend(
            (
              *record.concept_ids,
              *record.rule_ids,
              f"prerequisites={record.prerequisite_status}",
              f"output={record.output_eligibility}",
              f"chart={record.chart_applicability}",
            )
          )
          for citation in record.citations:
            required.extend((citation.source_id, citation.locator))
            if citation.excerpt is not None:
              required.extend(
                (citation.excerpt.en, citation.excerpt.translation_credit or "[missing]")
              )
        if isinstance(record, (Concept, RuleVariant)) and record.configuration is not None:
          required.extend(
            (configuration_reference(record.configuration), record.configuration.value)
          )
        if any(content(value) not in block for value in required):
          raise ValueError(f"Missing rendered catalog metadata: {record.identifier} ({language})")
    for target in parser.links:
      if target.startswith("#catalog-") and target[1:] not in parser.records:
        raise ValueError(f"Dangling rendered catalog link: {target}")


def check_distribution(directory: Path) -> None:
  """Build via sdist and test an isolated install. 经 sdist 构建并验证隔离安装。"""
  metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  artifacts = directory / "artifacts"
  run((sys.executable, "-m", "build", "--outdir", str(artifacts)))
  wheels = tuple(artifacts.glob("*.whl"))
  if len(wheels) != 1 or len(tuple(artifacts.glob("*.tar.gz"))) != 1:
    raise ValueError("Expected one wheel and one sdist")
  check_wheel(wheels[0], metadata["version"])
  check_sdist(next(artifacts.glob("*.tar.gz")))

  environment = directory / "consumer"
  run(("uv", "venv", "--python", sys.executable, str(environment)))
  python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
  run(("uv", "pip", "install", "--python", str(python), str(wheels[0])))
  corpus_version = load_catalog().version
  from tools.installed_check import acceptance_chart

  expected_chart = directory / "development-chart.json"
  expected_chart.write_text(astrology.dumps_chart(acceptance_chart()), encoding="utf-8")
  for mode in ((), ("-O",)):
    run(
      (
        str(python),
        *mode,
        "-I",
        str(ROOT / "tools/installed_check.py"),
        metadata["version"],
        corpus_version,
        "--knowledge-only",
      ),
      cwd=directory,
    )
    run(
      (
        str(python),
        *mode,
        "-I",
        str(ROOT / "tools/installed_check.py"),
        metadata["version"],
        corpus_version,
        "--expected-chart",
        str(expected_chart),
      ),
      cwd=directory,
    )


def main() -> None:
  """Run all checks, stopping on failure. 运行全部检查，失败即停止。"""
  commands = (
    ("-m", "ruff", "check", "."),
    ("-m", "ruff", "format", "--check", "."),
    ("-m", "mypy"),
    ("-m", "pytest", "--cov", "--cov-report=term-missing"),
    # Pytest rewrites test assertions under -O; this notice concerns other modules.
    # pytest 在 -O 下仍重写测试断言；此提示针对其他模块。
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
  check_package_files()
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
    check_api_html(directory / "html")
    check_catalog_html(directory / "html")
    check_search_html(directory / "html")
    results = (directory / "doctest/output.txt").read_text(encoding="utf-8")
    check_examples(results)
    check_distribution(directory)
  print("All checks passed.")


if __name__ == "__main__":
  main()
