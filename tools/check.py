"""Run repository checks. 运行仓库检查。"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from collections.abc import Mapping, Sequence
from enum import Enum
from html.parser import HTMLParser
from inspect import isfunction
from pathlib import Path
from typing import get_args
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

if __package__ in (None, ""):
  # Direct script invocation puts tools/, not the repository root, on sys.path.
  sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from markdown_it import MarkdownIt

import astrology
from astrology import knowledge
from astrology.dignities import _RULE_ID as _DIGNITY_RULE_ID
from astrology.knowledge import Concept, Entry, RuleVariant, Source, load_catalog
from astrology.knowledge.records import Language
from tools.catalog_docs import (
  ASHMAND_RULE_ID,
  ashmand_group_concept,
  catalog_anchor,
  check_catalog_data,
  configuration_reference,
  dignity_rows,
  localized_texts,
)
from tools.docs_search import check_search_html

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILES = (
  "astrology/__init__.py",
  "astrology/_distribution.py",
  "astrology/_validation.py",
  "astrology/py.typed",
  "astrology/aspects.py",
  "astrology/birth.py",
  "astrology/celestial.py",
  "astrology/chart.py",
  "astrology/config.py",
  "astrology/cross_aspects.py",
  "astrology/dignities.py",
  "astrology/houses.py",
  "astrology/lunar_phase.py",
  "astrology/objects.py",
  "astrology/summaries.py",
  "astrology/text.py",
  "astrology/zodiac.py",
  "astrology/knowledge/__init__.py",
  "astrology/knowledge/records.py",
  "astrology/knowledge/catalog.py",
  "astrology/knowledge/catalog.json",
)

# Build, documentation and test inputs outside the package itself.
# 不在包内的构建、文档和测试输入。
SDIST_FILES = (
  ".gitattributes",
  ".github/workflows/checks.yml",
  ".github/workflows/release.yml",
  "pyproject.toml",
  "uv.lock",
  "MANIFEST.in",
  "README.md",
  "README.zh-CN.md",
  "docs/conf.py",
  "docs/_templates/site_index.html",
  "tools/check.py",
  "tools/installed_check.py",
  "tools/release.py",
  "tools/fetch_reference.py",
  "tools/catalog_docs.py",
  "tools/docs_search.py",
  "tests/reference/natal_reference.json",
  "tests/reference/complete_chart_reference.json",
  "tests/reference/chart_regression.json",
  "tests/reference/constructed_chart.en.txt",
  "tests/reference/constructed_chart.zh-CN.txt",
)


def run(command: Sequence[str], *, cwd: Path = ROOT, env: Mapping[str, str] | None = None) -> None:
  """Run a command and propagate failure. 执行命令并传播失败。"""
  print(f"+ {' '.join(command)}", flush=True)
  subprocess.run(command, cwd=cwd, env=env, check=True)


class _LinkHtml(HTMLParser):
  def __init__(self) -> None:
    super().__init__()
    self.targets: list[str] = []

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    self.targets.extend(value for name, value in attrs if name in ("href", "src") and value)


def _link_targets(text: str) -> tuple[str, ...]:
  targets: list[str] = []
  html = _LinkHtml()
  for token in MarkdownIt("commonmark").parse(text):
    if token.type == "html_block":
      html.feed(token.content)
    for child in token.children or ():
      if child.type == "html_inline":
        html.feed(child.content)
      target = child.attrGet("href") if child.type == "link_open" else child.attrGet("src")
      if isinstance(target, str) and target:
        targets.append(target)
  return (*targets, *html.targets)


def readme_links(text: str) -> tuple[str, ...]:
  """Require context-independent web URLs in package-index Markdown.

  要求包索引中的 Markdown 使用不依赖当前页面位置的网页 URL。
  """
  targets = _link_targets(text)
  if not targets:
    raise ValueError("README must link to its documentation")
  for target in targets:
    url = urlsplit(target)
    if url.username is not None or url.password is not None:
      raise ValueError("README URLs must not embed credentials")
    if url.scheme not in ("https", "http") or not url.netloc:
      raise ValueError(f"README link must be an absolute HTTP(S) URL: {target}")
  return targets


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

  pages = (root / "README.md", root / "README.zh-CN.md", *sorted((root / "docs").rglob("*.md")))
  for page in pages:
    if not page.is_file():
      errors.append(f"Missing document: {page.relative_to(root)}")
      continue
    for target in _link_targets(page.read_text(encoding="utf-8")):
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
  for language in get_args(Language):
    for page in (
      "contributing",
      "birth",
      "configuration",
      "chart",
      "aspects",
      "cross_aspects",
      "summaries",
      "dignities",
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
    self.identifiers: set[str] = set()
    self.language: str | None = None
    self._name_depth = 0
    self._name_parts: list[str] = []

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    attributes = dict(attrs)
    if identifier := attributes.get("id"):
      self.identifiers.add(identifier)
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
  for language in get_args(Language):
    counterpart = "zh-CN" if language == "en" else "en"
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

  # The root is checked directly; the astronomy adapter is checked after explicit calculation.
  # 包根单独检查；天文适配层在显式计算之后检查。
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
    if any(
      name == "astrology/serialization.py" or name.startswith("astrology/serialization/")
      for name in names
    ):
      raise ValueError("Wheel contains withdrawn chart persistence")
    metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
    if len(metadata_paths) != 1:
      raise ValueError("Wheel must contain one METADATA file")
    metadata = Parser().parsestr(archive.read(metadata_paths[0]).decode("utf-8"))
    if metadata["Name"] != "celestial-astrology" or metadata["Version"] != expected_version:
      raise ValueError("Wheel identity differs from project metadata")
    if missing := set(PACKAGE_FILES) - set(names):
      raise ValueError(f"Wheel is missing package resources: {sorted(missing)}")
    if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
      raise ValueError("Wheel is missing its license")
    if (metadata["Description-Content-Type"] or "").split(";", 1)[0].strip() != "text/markdown":
      raise ValueError("Wheel README must declare Markdown content")
    description = metadata.get_payload()
    if not isinstance(description, str):
      raise ValueError("Wheel README must be text")
    readme_links(description)


def check_sdist(sdist: Path) -> None:
  """Require package resources and the inputs for source builds, docs and tests.

  要求源码分发包包含包资源及构建、文档和测试所需的输入。
  """
  with tarfile.open(sdist) as archive:
    names = {name.partition("/")[2] for name in archive.getnames()}
  if any(
    name == "src/astrology/serialization.py"
    or name.startswith("src/astrology/serialization/")
    or name == "tests/test_serialization.py"
    or name.startswith("tests/reference/chart_record_")
    for name in names
  ):
    raise ValueError("Sdist contains withdrawn chart persistence")
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
    self.rows: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    self._row: list[str] | None = None
    self._row_links: list[str] = []

  def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    super().handle_starttag(tag, attrs)
    if tag == "tr":
      self._row = []
      self._row_links = []
    if tag == "a":
      self._link = dict(attrs).get("href")
      self._label = []
      if self._row is not None and self._link is not None:
        self._row_links.append(self._link)
    if tag == "section":
      self._sections.append(None)
    identifier = dict(attrs).get("id")
    if identifier and identifier.startswith("catalog-") and self._sections:
      block: list[str] = []
      self.records[identifier] = block
      self._sections[-1] = block

  def handle_endtag(self, tag: str) -> None:
    super().handle_endtag(tag)
    if self._row is not None:
      if tag in ("td", "th"):
        self._row.append(" ")
      if tag == "tr":
        for identifier, block in self.records.items():
          if any(section is block for section in self._sections):
            self.rows.setdefault(identifier, []).append(
              ("".join(self._row), tuple(self._row_links))
            )
        self._row = None
    if tag == "a" and self._link is not None:
      self.link_labels.setdefault(self._link, []).append("".join(self._label))
      self._link = None
    if tag == "section" and self._sections:
      self._sections.pop()

  def handle_data(self, data: str) -> None:
    super().handle_data(data)
    if self._row is not None:
      self._row.append(data)
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
  languages: tuple[Language, ...] = get_args(Language)
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
    expected_rows: list[tuple[str, tuple[str, ...]]] = [
      ("Sign Group" if language == "en" else "星座 分组", ())
    ]
    for sign in astrology.Sign:
      sign_concept = catalog.concept(f"sign.{sign.value}")
      group_concept = ashmand_group_concept(catalog, astrology.ashmand_sign_group(sign))
      expected_rows.append(
        (
          content(f"{sign_concept.name.text(language)} {group_concept.name.text(language)}"),
          (
            f"#{catalog_anchor(sign_concept.identifier, language)}",
            f"#{catalog_anchor(group_concept.identifier, language)}",
          ),
        )
      )
    rows = parser.rows.get(catalog_anchor(ASHMAND_RULE_ID, language), [])
    if [(content(text), links) for text, links in rows] != expected_rows:
      raise ValueError(
        f"Rendered Ashmand sign-group rows differ from the executable rule: {language}"
      )
    expected_dignities = [(content(" ".join(row)), ()) for row in dignity_rows(catalog, language)]
    rows = parser.rows.get(catalog_anchor(_DIGNITY_RULE_ID, language), [])
    if [(content(text), links) for text, links in rows] != expected_dignities:
      raise ValueError(f"Rendered dignity rows differ from the executable rule: {language}")
    for target in parser.links:
      if target.startswith("#catalog-") and target[1:] not in parser.records:
        raise ValueError(f"Dangling rendered catalog link: {target}")


def check_site_html(directory: Path, *, root: Path = ROOT, source_revision: str = "") -> None:
  """Check the bilingual root and resolve both README paths against the built site.

  检查双语根入口，并在构建产物中解析两份 README 的链接路径。
  """
  project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  base = project["urls"]["Documentation"]
  repository = project["urls"]["Repository"]
  index = directory / "index.html"
  if not index.is_file():
    raise ValueError("Missing site-root index.html")
  parser = _CatalogHtml()
  parser.feed(index.read_text(encoding="utf-8"))
  text = " ".join("".join(parser.text).split())
  if f"{project['name']} {project['version']}" not in text or not all(
    phrase in text for phrase in ("Source documentation snapshot", "源码文档快照")
  ):
    raise ValueError("Site root must identify its version and bilingual source snapshot")
  if not {"docs/en/index.html", "docs/zh-CN/index.html"}.issubset(parser.links):
    raise ValueError("Site root must link both languages")
  if source_revision:
    source_url = repository + "/tree/" + source_revision
    archive_url = repository + "/archive/" + source_revision + ".zip"
    if (
      source_url not in parser.links
      or source_revision not in text
      or archive_url not in text
      or "安装这一源码快照" not in text
    ):
      raise ValueError("Site root is missing its fixed source or bilingual snapshot installation")
  counterparts = {base + "README.html", base + "README.zh-CN.html"}
  sections = (
    ("README.md", "en", ("Install from source", "First chart", "First knowledge lookup")),
    ("README.zh-CN.md", "zh-CN", ("从源码安装", "第一张命盘", "第一次查询知识")),
  )
  for name, language, required in sections:
    content = (root / name).read_text(encoding="utf-8")
    tokens = MarkdownIt("commonmark").parse(content)
    headings = {
      tokens[i + 1].content for i, token in enumerate(tokens) if token.type == "heading_open"
    }
    if not set(required).issubset(headings):
      raise ValueError(f"Missing installation/first-use sections: {name}")
    links = readme_links(content)
    expected = counterparts | {
      base + f"docs/{language}/reference.html",
      base + f"docs/{language}/catalog.html",
    }
    if not expected.issubset(links):
      raise ValueError(f"Missing readable references or counterpart navigation: {name}")
    for target in links:
      if target.startswith(base):
        url = urlsplit(target)
        relative = unquote(url.path.removeprefix(urlsplit(base).path)) or "index.html"
        page = (directory / relative).resolve()
        if not page.is_relative_to(directory.resolve()) or not page.is_file():
          raise ValueError(f"README links to an absent built page: {target}")
        if url.fragment:
          destination = _ApiHtml()
          destination.feed(page.read_text(encoding="utf-8"))
          if unquote(url.fragment) not in destination.identifiers:
            raise ValueError(f"README links to an absent built anchor: {target}")
      elif target.startswith(repository + "/blob/main/"):
        relative = unquote(urlsplit(target).path.partition("/blob/main/")[2])
        page = (root / relative).resolve()
        if not page.is_relative_to(root.resolve()) or not page.is_file():
          raise ValueError(f"README links to an absent repository file: {target}")


def readme_examples(text: str) -> tuple[tuple[str, str], ...]:
  """Read Python scripts and their immediately following output fences.

  读取 Python 脚本及紧随其后的输出代码块。
  """
  fences = [token for token in MarkdownIt("commonmark").parse(text) if token.type == "fence"]
  examples: list[tuple[str, str]] = []
  for index, token in enumerate(fences):
    if token.info.strip() != "python":
      continue
    if index + 1 == len(fences) or fences[index + 1].info.strip() != "text":
      raise ValueError("Every README Python script must have a following text output block")
    examples.append((token.content, fences[index + 1].content))
  if len(examples) < 2:
    raise ValueError("README must execute chart and knowledge examples")
  return tuple(examples)


def check_readme_examples(root: Path, python: Path, directory: Path, mode: tuple[str, ...]) -> None:
  """Execute both READMEs against the isolated installed package and compare output.

  使用隔离安装包执行两份 README，并比较实际输出。
  """
  for name in ("README.md", "README.zh-CN.md"):
    for index, (code, expected) in enumerate(
      readme_examples((root / name).read_text(encoding="utf-8"))
    ):
      script = directory / f"{name}-{index}.py"
      script.write_text(code, encoding="utf-8")
      result = subprocess.run(
        (str(python), *mode, "-I", "-X", "utf8", str(script)),
        cwd=directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
      )
      if result.stdout.rstrip("\n") != expected.rstrip("\n") or result.stderr:
        raise ValueError(f"README example output differs: {name}, example {index}")


def check_missing_metadata(environment: Path, python: Path, consumer_script: Path) -> None:
  """Hide project metadata in a disposable install and restore it on exit.

  在一次性安装环境中隐藏项目分发包元数据，并在退出时恢复。
  """
  locate = """
import json, sys
from importlib.metadata import distribution
metadata = distribution(sys.argv[1])
paths = [metadata.locate_file(p).parent for p in metadata.files or ()
         if str(p).endswith('.dist-info/METADATA')]
if len(paths) != 1:
  raise RuntimeError('Expected one installed dist-info directory')
print(json.dumps(str(paths[0])))
"""
  output = subprocess.check_output(
    (str(python), "-I", "-c", locate, "celestial-astrology"), text=True, encoding="utf-8"
  )
  value: object = json.loads(output)
  if not isinstance(value, str):
    raise ValueError("Installed metadata location must be a path")
  metadata = Path(value).resolve()
  hidden = metadata.with_name(metadata.name + ".hidden")
  if (
    not metadata.is_relative_to(environment.resolve())
    or metadata.suffix != ".dist-info"
    or not metadata.is_dir()
    or hidden.exists()
  ):
    raise ValueError("Unsafe disposable metadata location")
  metadata.rename(hidden)
  try:
    for mode in ((), ("-O",)):
      run(
        (str(python), *mode, "-I", str(consumer_script), "--missing-metadata"),
        cwd=environment.parent,
      )
  finally:
    hidden.rename(metadata)


def check_installed_wheel(source: Path, wheel: Path, version: str, directory: Path) -> None:
  """Check an isolated wheel install in ordinary and optimized modes.

  在隔离环境中安装 wheel，并以普通和优化模式检查。
  """
  from tools.installed_check import (
    acceptance_chart,
    acceptance_cross_aspects,
    chart_observations,
    cross_observations,
  )

  environment = directory / "consumer"
  run(("uv", "venv", "--python", sys.executable, str(environment)), cwd=directory)
  python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
  run(("uv", "pip", "install", "--python", str(python), str(wheel)), cwd=directory)
  corpus_version = load_catalog().version
  observations = directory / "expected-observations.json"
  observations.write_text(chart_observations(acceptance_chart()), encoding="utf-8")
  cross_values = directory / "expected-cross-observations.json"
  cross_values.write_text(cross_observations(acceptance_cross_aspects()), encoding="utf-8")
  script = source / "tools/installed_check.py"
  for mode in ((), ("-O",)):
    run(
      (str(python), *mode, "-I", str(script), version, corpus_version, "--knowledge-only"),
      cwd=directory,
    )
    check_readme_examples(source, python, directory, mode)
    run(
      (
        str(python),
        *mode,
        "-I",
        str(script),
        version,
        corpus_version,
        "--expected-observations",
        str(observations),
        "--expected-cross-observations",
        str(cross_values),
      ),
      cwd=directory,
    )
  check_missing_metadata(environment, python, script)


def check_distribution(directory: Path) -> None:
  """Build the wheel and docs from an extracted sdist, then test an isolated install.

  从解压后的源码分发包构建 wheel 和文档，再验证隔离安装。
  """
  metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  artifacts = directory / "artifacts"
  run((sys.executable, "-m", "build", "--sdist", "--outdir", str(artifacts)))
  sdists = tuple(artifacts.glob("*.tar.gz"))
  if len(sdists) != 1:
    raise ValueError("Expected one sdist")
  check_sdist(sdists[0])
  source_directory = directory / "source"
  with tarfile.open(sdists[0]) as archive:
    archive.extractall(source_directory, filter="data")
  roots = tuple(source_directory.iterdir())
  if len(roots) != 1 or not roots[0].is_dir():
    raise ValueError("Sdist must contain one source directory")
  source = roots[0]
  run((sys.executable, "-m", "build", "--wheel", "--outdir", str(artifacts)), cwd=source)
  wheels = tuple(artifacts.glob("*.whl"))
  if len(wheels) != 1:
    raise ValueError("Expected one wheel")
  check_wheel(wheels[0], metadata["version"])

  source_environment = {**os.environ, "PYTHONPATH": str(source / "src")}
  run(
    (
      sys.executable,
      "-c",
      "from pathlib import Path\nimport astrology\n"
      "actual = Path(astrology.__file__).resolve()\n"
      "expected = (Path.cwd() / 'src').resolve()\n"
      "if not actual.is_relative_to(expected):\n"
      "  raise RuntimeError(f'astrology imported from {actual}, expected source under {expected}')",
    ),
    cwd=source,
    env=source_environment,
  )
  check_documents(source)
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
        str(directory / f"source-{builder}"),
      ),
      cwd=source,
      env=source_environment,
    )
  check_api_html(directory / "source-html")
  check_catalog_html(directory / "source-html")
  check_search_html(directory / "source-html")
  check_site_html(
    directory / "source-html",
    root=source,
    source_revision=os.environ.get("ASTROLOGY_DOCS_SOURCE_SHA", ""),
  )
  check_examples((directory / "source-doctest/output.txt").read_text(encoding="utf-8"))

  check_installed_wheel(source, wheels[0], metadata["version"], directory)


def main(*, artifacts_dir: Path | None = None) -> None:
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
    check_site_html(
      directory / "html", source_revision=os.environ.get("ASTROLOGY_DOCS_SOURCE_SHA", "")
    )
    results = (directory / "doctest/output.txt").read_text(encoding="utf-8")
    check_examples(results)
    check_distribution(directory)
    if artifacts_dir is not None:
      artifacts_dir.mkdir(parents=True)
      for artifact in (directory / "artifacts").iterdir():
        shutil.copyfile(artifact, artifacts_dir / artifact.name)
  print("All checks passed.")


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    "--artifacts-dir", type=Path, help="Retain checked distributions in a new directory"
  )
  main(artifacts_dir=parser.parse_args().artifacts_dir)
