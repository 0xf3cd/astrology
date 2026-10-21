"""Immutable catalog queries and explicit packaged-corpus loading.

不可变的目录查询与显式的包内语料加载。
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, replace
from importlib.resources import files
from typing import Any

from astrology.config import LunarNode, NodeDefinition
from astrology.knowledge.records import (
  _LANGUAGES,
  CONFIGURATION_TYPES,
  Citation,
  Concept,
  ConceptKind,
  ConfigurationIdentity,
  Entry,
  Language,
  LocalizedText,
  OutputEligibility,
  PrerequisiteStatus,
  RuleVariant,
  Source,
  SourceVerification,
  _identifier,
  _language,
  _text,
  _tuple,
)
from astrology.zodiac import Sign


def _name_key(name: str) -> str:
  _text(name)
  return unicodedata.normalize("NFC", name).strip().casefold()


@dataclass(frozen=True, slots=True)
class Catalog:
  """Validated immutable records; construction performs no I/O or chart calculation.

  Copy all record sequences. Reject duplicate IDs, dangling links, inconsistent
  config links and aliases shared by different concepts (TypeError/ValueError).
  Equal display names are allowed and lookup returns every matching identity.
  Records can retain missing/stale translations without treating them as current.
  Malformed string IDs raise ValueError; non-string IDs raise TypeError.
  Unknown well-formed IDs raise KeyError.

  经核验的不可变记录；构造不做 I/O 或排盘。复制全部记录序列；重复标识、悬空链接、
  不一致的配置链接及不同概念共享别名均抛出 TypeError 或 ValueError。
  允许显示名称相同，查询返回所有命中的身份；缺译及旧译可保留，但不算当前译文。
  格式不合法的字符串标识抛出 ValueError，非字符串标识抛出 TypeError。
  格式正确但未知的标识抛出 KeyError。
  """

  version: str
  concepts: Sequence[Concept]
  variants: Sequence[RuleVariant]
  sources: Sequence[Source]
  entries: Sequence[Entry]

  def __post_init__(self) -> None:
    _text(self.version)
    for name, expected in (
      ("concepts", Concept),
      ("variants", RuleVariant),
      ("sources", Source),
      ("entries", Entry),
    ):
      object.__setattr__(self, name, _tuple(getattr(self, name), expected))
    all_ids = [
      item.identifier
      for group in (self.concepts, self.variants, self.sources, self.entries)
      for item in group
    ]
    if len(all_ids) != len(set(all_ids)):
      raise ValueError("Duplicate catalog identifier")
    concept_ids = {item.identifier for item in self.concepts}
    variant_ids = {item.identifier for item in self.variants}
    source_ids = {item.identifier for item in self.sources}
    for concept in self.concepts:
      if set(concept.related) - concept_ids:
        raise ValueError(f"Dangling concept reference in {concept.identifier}")
    for variant in self.variants:
      if set(variant.concept_ids) - concept_ids:
        raise ValueError(f"Dangling concept reference in {variant.identifier}")
      if variant.configuration is not None and not any(
        self.concept(key).configuration is variant.configuration for key in variant.concept_ids
      ):
        raise ValueError(f"Variant config reference has no linked concept: {variant.identifier}")
    for entry in self.entries:
      if set(entry.concept_ids) - concept_ids or set(entry.rule_ids) - variant_ids:
        raise ValueError(f"Dangling concept/rule reference in {entry.identifier}")
      if any(citation.source_id not in source_ids for citation in entry.citations):
        raise ValueError(f"Dangling source reference in {entry.identifier}")
      for citation in entry.citations:
        if citation.excerpt is not None and self.source(citation.source_id).language != "en":
          raise ValueError(
            "This corpus schema supports English originals with Chinese translations"
          )
    names: dict[str, set[str]] = {}
    aliases: dict[str, str] = {}
    for concept in self.concepts:
      for language in _LANGUAGES:
        if (display := concept.name.text(language)) is not None:
          names.setdefault(_name_key(display), set()).add(concept.identifier)
    for concept in self.concepts:
      for alias in (*concept.en_aliases, *concept.zh_aliases):
        key = _name_key(alias)
        if (key in aliases and aliases[key] != concept.identifier) or (
          names.get(key, set()) - {concept.identifier}
        ):
          raise ValueError(f"Conflicting alias: {alias}")
        aliases[key] = concept.identifier

  def concept(self, identifier: str) -> Concept:
    """Get a concept by exact ID; see Catalog for ID errors. 按精确标识取概念，标识错误规则见 Catalog。"""
    _identifier(identifier)
    for item in self.concepts:
      if item.identifier == identifier:
        return item
    raise KeyError(identifier)

  def variant(self, identifier: str) -> RuleVariant:
    """Get a variant by exact ID; see Catalog for ID errors. 按精确标识取变体，标识错误规则见 Catalog。"""
    _identifier(identifier)
    for item in self.variants:
      if item.identifier == identifier:
        return item
    raise KeyError(identifier)

  def source(self, identifier: str) -> Source:
    """Get an edition record; see Catalog for ID errors. 取来源版本记录，标识错误规则见 Catalog。"""
    _identifier(identifier)
    for item in self.sources:
      if item.identifier == identifier:
        return item
    raise KeyError(identifier)

  def entry(self, identifier: str) -> Entry:
    """Get a statement, not a chart conclusion; see Catalog for ID errors.

    取陈述而非命盘结论，标识错误规则见 Catalog。
    """
    _identifier(identifier)
    for item in self.entries:
      if item.identifier == identifier:
        return item
    raise KeyError(identifier)

  def list_concepts(self, *, kind: ConceptKind | None = None) -> tuple[Concept, ...]:
    """List concepts in corpus order, optionally by kind; reject raw strings.

    按语料顺序列概念，可按类别筛选；不接受字符串代替枚举。
    """
    if kind is not None and type(kind) is not ConceptKind:
      raise TypeError("kind must be ConceptKind or None")
    return tuple(item for item in self.concepts if kind is None or item.kind is kind)

  def list_variants(self, *, concept_id: str | None = None) -> tuple[RuleVariant, ...]:
    """List definitions, optionally for a concept; see Catalog for ID errors.

    列定义，可限定概念；标识错误规则见 Catalog。
    """
    if concept_id is not None:
      self.concept(concept_id)
    return tuple(
      item for item in self.variants if concept_id is None or concept_id in item.concept_ids
    )

  def lookup(self, name: str, *, language: Language | None = None) -> tuple[Concept, ...]:
    """Find exact names/aliases after NFC, trim and casefold; no match returns ().

    An omitted language searches both. Ambiguous display names return all identities;
    this is neither fuzzy documentation search nor chart matching. Invalid language
    raises ValueError, invalid/blank names TypeError/ValueError.

    经 NFC、去首尾空白及大小写折叠后精确查询名称与别名，无匹配返回 ()。未选语言则查两种语言；
    歧义名称返回所有身份，不做模糊文档搜索或命盘判别。非法语言抛出 ValueError，
    非法或空名称抛出 TypeError 或 ValueError。
    """
    key = _name_key(name)
    languages = _LANGUAGES if language is None else (language,)
    if language is not None:
      _language(language)
    result = []
    for concept in self.concepts:
      for selected in languages:
        display = concept.name.text(selected)
        aliases = concept.en_aliases if selected == "en" else concept.zh_aliases
        values = (*aliases, *((display,) if display is not None else ()))
        if any(_name_key(value) == key for value in values):
          result.append(concept)
          break
    return tuple(result)

  def filter_entries(
    self,
    *,
    concept_id: str | None = None,
    source_id: str | None = None,
    prerequisite_status: PrerequisiteStatus | None = None,
    output_eligibility: OutputEligibility | None = None,
  ) -> tuple[Entry, ...]:
    """Apply all requested editorial filters without evaluating prerequisites.

    ID errors follow Catalog; raw status strings raise TypeError.
    Source verification must be inspected on Source, not inferred from this result.

    同时应用所选整理筛选，不判断前提。标识错误规则见 Catalog，
    字符串状态抛出 TypeError。来源查核状态须查 Source，不从查询结果推断。
    """
    if concept_id is not None:
      self.concept(concept_id)
    if source_id is not None:
      self.source(source_id)
    if prerequisite_status is not None and type(prerequisite_status) is not PrerequisiteStatus:
      raise TypeError("prerequisite_status must be PrerequisiteStatus or None")
    if output_eligibility is not None and type(output_eligibility) is not OutputEligibility:
      raise TypeError("output_eligibility must be OutputEligibility or None")
    return tuple(
      item
      for item in self.entries
      if (concept_id is None or concept_id in item.concept_ids)
      and (source_id is None or any(c.source_id == source_id for c in item.citations))
      and (prerequisite_status is None or item.prerequisite_status is prerequisite_status)
      and (output_eligibility is None or item.output_eligibility is output_eligibility)
    )

  def filter_sources(self, *, verification: SourceVerification | None = None) -> tuple[Source, ...]:
    """Filter editions by their inspection state, not applicability; reject raw strings.

    按版本的查核状态筛选，不判断适用；不接受字符串代替枚举。
    """
    if verification is not None and type(verification) is not SourceVerification:
      raise TypeError("verification must be SourceVerification or None")
    return tuple(
      item for item in self.sources if verification is None or item.verification is verification
    )

  def citations(self, entry_id: str) -> tuple[tuple[Citation, Source], ...]:
    """Resolve an entry's citations to editions; see Catalog for ID errors.

    将条目引用解析至版本记录，标识错误规则见 Catalog。
    """
    return tuple(
      (citation, self.source(citation.source_id)) for citation in self.entry(entry_id).citations
    )


def _sign_concept(catalog: Catalog, sign: Sign) -> Concept:
  return catalog.concept(f"sign.{sign.value}")


def _config_reference(raw: Any) -> ConfigurationIdentity | None:
  if raw is None:
    return None
  for enum in CONFIGURATION_TYPES:
    if enum.__name__ == raw["enum"]:
      return enum[raw["member"]]
  raise ValueError("Unknown owning configuration enum")


def load_catalog() -> Catalog:
  """Read and validate the packaged corpus on each explicit call; no cache or network.

  Resource/JSON errors propagate; invalid records/references raise TypeError,
  ValueError or KeyError. Queries need no birth input, timezone data or astronomy.
  The returned catalog owns immutable snapshots, not the decoded containers.

  每次显式调用均读取并核验包内语料，不使用缓存或网络。资源及 JSON 错误直接传播；
  非法记录或引用抛出 TypeError、ValueError 或 KeyError。查询不需出生输入、时区数据或天文库。
  返回目录持有不可变快照，不共享解码所得容器。
  """
  data = json.loads(
    files("astrology.knowledge").joinpath("catalog.json").read_text(encoding="utf-8")
  )

  def localized(raw: dict[str, Any]) -> LocalizedText:
    defaults = dict(data["text_defaults"])
    if raw.get("zh") is None:
      defaults.pop("zh_revision", None)
      defaults.pop("translation_credit", None)
    return LocalizedText(**dict(defaults, **raw))

  concepts = tuple(
    Concept(
      identifier=row["identifier"],
      kind=ConceptKind(row["kind"]),
      name=localized(row["name"]),
      description=localized(row["description"]),
      en_aliases=row.get("en_aliases", ()),
      zh_aliases=row.get("zh_aliases", ()),
      related=row.get("related", ()),
      configuration=_config_reference(row.get("configuration")),
    )
    for row in data["concepts"]
  )
  definition_ids = {
    concept.configuration: concept.identifier
    for concept in concepts
    if isinstance(concept.configuration, NodeDefinition)
  }
  concepts = tuple(
    replace(concept, related=(definition_ids[concept.configuration.definition], *concept.related))
    if isinstance(concept.configuration, LunarNode)
    else concept
    for concept in concepts
  )
  variants = tuple(
    RuleVariant(
      identifier=row["identifier"],
      name=localized(row["name"]),
      concept_ids=row["concept_ids"],
      definition=localized(row["definition"]),
      tradition=localized(row["tradition"]),
      limits=localized(row["limits"]),
      configuration=_config_reference(row.get("configuration")),
    )
    for row in data["variants"]
  )
  sources = tuple(
    Source(
      identifier=row["identifier"],
      title=row["title"],
      author=row["author"],
      edition=row["edition"],
      language=row["language"],
      lineage=localized(row["lineage"]),
      rights=localized(row["rights"]),
      scope=localized(row["scope"]),
      verification=SourceVerification(row["verification"]),
      url=row["url"],
    )
    for row in data["sources"]
  )
  entries = tuple(
    Entry(
      identifier=row["identifier"],
      statement=localized(row["statement"]),
      concept_ids=row["concept_ids"],
      rule_ids=row["rule_ids"],
      citations=tuple(
        Citation(
          c["source_id"],
          c["locator"],
          localized(c["excerpt"]) if c.get("excerpt") is not None else None,
        )
        for c in row["citations"]
      ),
      prerequisites=tuple(localized(text) for text in row["prerequisites"]),
      exceptions=localized(row["exceptions"]),
      limits=localized(row["limits"]),
      prerequisite_status=PrerequisiteStatus(row["prerequisite_status"]),
      output_eligibility=OutputEligibility(row["output_eligibility"]),
    )
    for row in data["entries"]
  )
  catalog = Catalog(data["version"], concepts, variants, sources, entries)
  sign_concepts = tuple(_sign_concept(catalog, sign) for sign in Sign)
  if any(concept.kind is not ConceptKind.SIGN for concept in sign_concepts) or set(
    catalog.list_concepts(kind=ConceptKind.SIGN)
  ) != set(sign_concepts):
    raise ValueError("The built-in catalog must map exactly the twelve Sign identities")
  return catalog
