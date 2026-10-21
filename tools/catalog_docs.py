"""Generate knowledge references and check translation coverage.

生成知识参考并检查翻译覆盖。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from typing import get_args

from astrology.aspects import aspect_angle
from astrology.config import HouseSystem, LunarNode, MajorAspect, NodeDefinition
from astrology.knowledge import Catalog, LocalizedText, TranslationStatus
from astrology.knowledge.records import CONFIGURATION_TYPES, ConfigurationIdentity, Language


def localized_texts(value: object, path: str = "catalog") -> Iterator[tuple[str, LocalizedText]]:
  """Visit every localized field, including nested citations. 遍历所有本地化字段，含嵌套引用。"""
  if type(value) is LocalizedText:
    yield path, value
  elif is_dataclass(value) and not isinstance(value, type):
    for field in fields(value):
      yield from localized_texts(getattr(value, field.name), f"{path}.{field.name}")
  elif isinstance(value, (tuple, list)):
    for index, item in enumerate(value):
      yield from localized_texts(item, f"{path}[{index}]")


def check_catalog_data(catalog: Catalog) -> None:
  """Check concept/rule config coverage, node ownership and current bilingual text.

  检查概念和规则的配置覆盖、交点定义归属及语料的当前双语文本。
  """
  expected = {(type(member), member.name) for enum in CONFIGURATION_TYPES for member in enum}
  actual = [
    (type(concept.configuration), concept.configuration.name)
    for concept in catalog.concepts
    if concept.configuration is not None
  ]
  if set(actual) != expected or len(actual) != len(expected):
    raise ValueError("Catalog must cover each actual configuration identity exactly once")
  rule_types = (HouseSystem, NodeDefinition, MajorAspect)
  expected_rules = {(type(member), member.name) for enum in rule_types for member in enum}
  actual_rules = [
    (type(variant.configuration), variant.configuration.name)
    for variant in catalog.variants
    if variant.configuration is not None
  ]
  if set(actual_rules) != expected_rules or len(actual_rules) != len(expected_rules):
    raise ValueError("Catalog must cover each rule-bearing configuration exactly once")
  definition_ids = {
    concept.configuration: concept.identifier
    for concept in catalog.concepts
    if isinstance(concept.configuration, NodeDefinition)
  }
  for concept in catalog.concepts:
    if isinstance(concept.configuration, LunarNode) and (
      definition_ids[concept.configuration.definition] not in concept.related
    ):
      raise ValueError(f"Missing owning node-definition relation: {concept.identifier}")
  for path, text in localized_texts(catalog):
    for language in get_args(Language):
      if text.status(language) is not TranslationStatus.CURRENT:
        raise ValueError(f"Required translation {language} is {text.status(language)}: {path}")


def catalog_anchor(identifier: str, language: Language = "en") -> str:
  """Return a stable record anchor qualified by page language. 返回带页面语言的稳定记录锚点。"""
  return f"catalog-{language.lower()}-" + identifier.replace(".", "-").replace("_", "-")


def configuration_reference(value: ConfigurationIdentity) -> str:
  """Read a request symbol from its owning enum. 从所属枚举读取请求符号。"""
  return f"astrology.config.{type(value).__name__}.{value.name}"


def render_catalog(catalog: Catalog, language: Language, code_version: str) -> str:
  """Render every admitted record with stable links and visibly missing/stale text.

  渲染全部接纳记录及稳定链接，显式显示缺失或过期的译文。
  """
  lines = [f"`code={code_version}` · `corpus={catalog.version}`", ""]
  identifiers = [
    item.identifier
    for group in (catalog.concepts, catalog.variants, catalog.sources, catalog.entries)
    for item in group
  ]
  anchors = [catalog_anchor(identifier, language) for identifier in identifiers]
  if len(anchors) != len(set(anchors)):
    raise ValueError("Catalog IDs collide after HTML anchor normalization")

  def text(value: LocalizedText, selected: Language = language) -> str:
    state = value.status(selected)
    content = value.text(selected)
    if state is TranslationStatus.MISSING:
      return "[missing]"
    return f"[stale] {content}" if state is TranslationStatus.STALE else str(content)

  def heading(identifier: str, title: str) -> None:
    lines.extend([f"({catalog_anchor(identifier, language)})=", f"## {identifier} · {title}", ""])

  def link(identifier: str) -> str:
    return f"{{ref}}`{identifier} <{catalog_anchor(identifier, language)}>`"

  def config(value: ConfigurationIdentity | None) -> None:
    if value is not None:
      symbol = configuration_reference(value)
      lines.extend(
        [
          f"Configuration request / 配置请求：[`{symbol}`](reference.md) = `{value.value}`",
          "",
        ]
      )
      if isinstance(value, MajorAspect):
        lines.extend([f"Exact angle / 精确角度：{aspect_angle(value):g}°", ""])

  for concept in catalog.concepts:
    heading(concept.identifier, text(concept.name))
    lines.extend([f"`kind={concept.kind}`", "", text(concept.description), ""])
    lines.extend(
      [
        "English names / 英文名称：" + ", ".join((text(concept.name, "en"), *concept.en_aliases)),
        "",
        "Chinese names / 中文名称："
        + "、".join((text(concept.name, "zh-CN"), *concept.zh_aliases)),
        "",
      ]
    )
    config(concept.configuration)
    if concept.related:
      lines.extend(["Related / 关联：" + ", ".join(map(link, concept.related)), ""])
  for variant in catalog.variants:
    heading(variant.identifier, text(variant.name))
    lines.extend(
      [text(variant.definition), "", text(variant.tradition), "", text(variant.limits), ""]
    )
    lines.extend(["Concepts / 概念：" + ", ".join(map(link, variant.concept_ids)), ""])
    config(variant.configuration)
  for source in catalog.sources:
    heading(source.identifier, source.title)
    lines.extend(
      [
        f"{source.author}. {source.edition}. `language={source.language}`",
        "",
        f"`source_verification={source.verification}`",
        "",
        f"[`{source.url}`]({source.url})",
        "",
        text(source.lineage),
        "",
        text(source.rights),
        "",
        text(source.scope),
        "",
      ]
    )
  for entry in catalog.entries:
    heading(entry.identifier, "Statement / 陈述")
    lines.extend(
      [
        text(entry.statement),
        "",
        f"`prerequisites={entry.prerequisite_status}` · "
        f"`output={entry.output_eligibility}` · `chart={entry.chart_applicability}`",
        "",
        "Concepts / 概念：" + ", ".join(map(link, entry.concept_ids)),
        "",
        "Variants / 变体：" + ", ".join(map(link, entry.rule_ids)),
        "",
      ]
    )
    lines.extend(["Prerequisites / 前提：", ""])
    lines.extend(f"- {text(premise)}" for premise in entry.prerequisites)
    if not entry.prerequisites:
      lines.append("No prerequisites recorded / 未记录前提")
    lines.extend(
      [
        "",
        "Exceptions / 例外：" + text(entry.exceptions),
        "",
        "Limits / 限度：" + text(entry.limits),
        "",
      ]
    )
    for citation in entry.citations:
      lines.extend([f"{link(citation.source_id)}: {citation.locator}", ""])
      if citation.excerpt is not None:
        excerpt = citation.excerpt
        lines.extend(
          [
            "Original excerpt (English) / 原文引述（英文）：",
            "",
            f"> {excerpt.en}",
            "",
            f"Chinese translation / 中文译文: `{excerpt.status('zh-CN')}`, "
            f"revision={excerpt.zh_revision}; {excerpt.translation_credit or '[missing]'}",
            "",
            f"> {excerpt.zh or '[missing]'}",
            "",
          ]
        )
  return "\n".join(lines)
