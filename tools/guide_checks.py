"""Check required bilingual explanations and their executable examples.

检查必需的双语说明及其可执行示例。
"""

from __future__ import annotations

import doctest
import re
from itertools import pairwise
from pathlib import Path
from typing import get_args

from markdown_it import MarkdownIt

from astrology.knowledge.records import Language

REQUIRED_TOPICS = frozenset(
  {
    "birth.resolution",
    "chart.calculation",
    "configuration.objects",
    "configuration.participants",
    "configuration.orbs",
    "aspects.longitudes",
    "aspects.orbs",
    "cross.selection",
    "cross.orbs",
    "knowledge.lookup",
    "knowledge.editorial_states",
    "summaries.population",
    "summaries.lunar_phase",
    "records.output",
    "dignities.lookup",
    "svg.rendering",
    "contributing.checks",
  }
)
_MARKER = re.compile(r"<!-- (?P<closing>/)?usage: (?P<topic>[a-z][a-z0-9_.-]*) -->")


def _pages(root: Path) -> tuple[tuple[Language, Path], ...]:
  return tuple(
    (language, page)
    for language in get_args(Language)
    for page in sorted((root / "docs" / language).rglob("*.md"))
  )


def _blocks(text: str, page: Path) -> tuple[tuple[str, str], ...]:
  lines = text.splitlines(keepends=True)
  active: tuple[str, int] | None = None
  blocks = []
  for token in MarkdownIt("commonmark").parse(text):
    if token.type != "html_block" or token.map is None:
      continue
    for offset, line in enumerate(token.content.splitlines()):
      stripped = line.strip()
      if not stripped.startswith(("<!-- usage:", "<!-- /usage:")):
        continue
      match = _MARKER.fullmatch(stripped)
      if match is None:
        raise ValueError(f"Invalid usage marker in {page}: {stripped}")
      topic = match["topic"]
      position = token.map[0] + offset
      if not match["closing"]:
        if active is not None:
          raise ValueError(f"Nested usage block in {page}: {topic}")
        active = topic, position + 1
      else:
        if active is None or active[0] != topic:
          raise ValueError(f"Unmatched usage marker in {page}: {topic}")
        blocks.append((topic, "".join(lines[active[1] : position])))
        active = None
  if active is not None:
    raise ValueError(f"Unclosed usage block in {page}: {active[0]}")
  return tuple(blocks)


def check_guide_content(root: Path, required: frozenset[str] = REQUIRED_TOPICS) -> None:
  """Require each topic's explanation and one runnable example in both languages.

  Markers identify content, not wording or headings. The structural check does
  not establish equivalent meaning; translations still need semantic review.

  要求每个主题在两种语言中均有说明和一个可运行示例。
  标记确定内容身份，不固定措辞或标题；结构检查不能证明含义等价，译文仍须语义审阅。
  """
  if not required:
    raise ValueError("Required guide topics must not be empty")
  seen: dict[Language, set[str]] = {language: set() for language in get_args(Language)}
  for language, page in _pages(root):
    for topic, body in _blocks(page.read_text(encoding="utf-8"), page):
      if topic not in required:
        raise ValueError(f"Unknown guide topic in {page}: {topic}")
      if topic in seen[language]:
        raise ValueError(f"Duplicate guide topic for {language}: {topic}")
      seen[language].add(topic)
      tokens = MarkdownIt("commonmark").parse(body)
      prose = any(
        child.type == "text" and any(character.isalpha() for character in child.content)
        for previous, token in pairwise(tokens)
        if previous.type == "paragraph_open" and token.type == "inline"
        for child in token.children or ()
      )
      examples = [token for token in tokens if token.type == "fence" and token.info == "{doctest}"]
      if (
        not prose
        or len(examples) != 1
        or not doctest.DocTestParser().get_examples(examples[0].content)
      ):
        raise ValueError(f"Guide topic needs prose and one executable example: {language}/{topic}")
  for language, topics in seen.items():
    if missing := required - topics:
      raise ValueError(
        f"Missing required guide topics for {language}: {', '.join(sorted(missing))}"
      )


def example_documents(root: Path) -> tuple[tuple[str, int], ...]:
  """Count source doctests by document without another page inventory.

  按文档统计源码中的 doctest，不再维护另一份页面清单。
  """
  documents = []
  parser = doctest.DocTestParser()
  for _language, page in _pages(root):
    count = sum(
      len(parser.get_examples(token.content))
      for token in MarkdownIt("commonmark").parse(page.read_text(encoding="utf-8"))
      if token.type == "fence" and token.info == "{doctest}"
    )
    if count:
      documents.append((page.relative_to(root).with_suffix("").as_posix(), count))
  return tuple(documents)


def check_examples(report: str, root: Path) -> None:
  """Match executed doctest counts to the actual source examples.

  将已执行的 doctest 数量与实际源码示例核对。
  """
  documents = example_documents(root)
  if not documents:
    raise ValueError("No executable documentation examples in the source")
  for name, expected in documents:
    marker = f"Document: {name}\n"
    section = re.split(r"(?m)^Document: ", report.partition(marker)[2], maxsplit=1)[0]
    match = re.search(r"(?m)^(\d+) tests? in \d+ items?\.$", section)
    if match is None or int(match[1]) != expected:
      raise ValueError(f"Executed documentation examples differ for {name}: expected {expected}")
