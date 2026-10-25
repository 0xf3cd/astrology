"""Sourced vocabulary and editorial states, without chart evaluation.

有出处的词汇与整理状态，不判断命盘。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, TypeVar, get_args

from astrology.config import Body, HouseSystem, LunarNode, MajorAspect, NodeDefinition

Language = Literal["en", "zh-CN"]
_LANGUAGES: tuple[Language, ...] = get_args(Language)
ConfigurationIdentity = Body | HouseSystem | LunarNode | MajorAspect | NodeDefinition
_T = TypeVar("_T")
CONFIGURATION_TYPES = (Body, HouseSystem, LunarNode, MajorAspect, NodeDefinition)


def _text(value: str) -> None:
  if type(value) is not str:
    raise TypeError("Text must be a plain string")
  if not value.strip():
    raise ValueError("Text must not be empty")


def _identifier(value: str) -> None:
  _text(value)
  if not re.fullmatch(r"[a-z][a-z0-9_.-]*", value):
    raise ValueError(f"Invalid language-independent identifier: {value!r}")


def _language(value: Language) -> None:
  if type(value) is not str or value not in _LANGUAGES:
    raise ValueError("Language must be en or zh-CN")


def _tuple(value: Sequence[_T], expected: type[_T]) -> tuple[_T, ...]:
  if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
    raise TypeError("Expected a sequence, not text or an iterator")
  result = tuple(value)
  if any(type(item) is not expected for item in result):
    raise TypeError(f"Sequence members must be {expected.__name__} values")
  return result


def _ids(value: Sequence[str]) -> tuple[str, ...]:
  result = _tuple(value, str)
  for item in result:
    _identifier(item)
  if len(result) != len(set(result)):
    raise ValueError("References must not repeat an identifier")
  return result


def _configuration(value: ConfigurationIdentity | None) -> None:
  if value is not None and type(value) not in CONFIGURATION_TYPES:
    raise TypeError("Configuration references must use an owning config enum member")


class ConceptKind(StrEnum):
  """Vocabulary categories, not astronomical object classes. 词汇分类，不替代天文对象类型。"""

  BODY = "body"
  SIGN = "sign"
  SIGN_GROUP = "sign_group"
  HOUSE_SYSTEM = "house_system"
  NODE_DEFINITION = "node_definition"
  LUNAR_NODE = "lunar_node"
  ASPECT = "aspect"


class SourceVerification(StrEnum):
  """Editorial source inspection, not truth or applicability. 出处查核状态，不代表真实或适用。"""

  VERIFIED = "verified"
  UNVERIFIED = "unverified"


class PrerequisiteStatus(StrEnum):
  """Whether prerequisites are represented, not satisfied by a chart.

  前提是否已表达完整，不表示命盘已满足前提。
  """

  COMPLETE = "complete"
  UNRESOLVED = "unresolved"


class OutputEligibility(StrEnum):
  """Editorial eligibility, independent of source checks and chart matching.

  整理层面的输出资格，独立于出处查核与命盘判别。
  """

  ELIGIBLE = "eligible"
  REFERENCE_ONLY = "reference_only"


class TranslationStatus(StrEnum):
  """Translation coverage of a semantic revision. 译文覆盖语义修订的状态。"""

  CURRENT = "current"
  STALE = "stale"
  MISSING = "missing"


@dataclass(frozen=True, slots=True)
class LocalizedText:
  """English canonical text and an optional credited Chinese translation.

  Revisions are positive integers; an older Chinese revision is retained as stale.
  Missing Chinese text returns None, never English fallback. Raise TypeError or
  ValueError for invalid fields, including inconsistent translation metadata.

  英文为基准文本，中文译文可缺失但须署名。修订为正整数；旧译保留并标为过期。
  缺译返回 None，不回退为英文；字段或译文元数据不合法时抛出 TypeError 或 ValueError。
  """

  en: str
  zh: str | None = None
  revision: int = 1
  zh_revision: int | None = None
  translation_credit: str | None = None

  def __post_init__(self) -> None:
    _text(self.en)
    if type(self.revision) is not int or self.revision < 1:
      raise ValueError("Semantic revision must be a positive integer")
    if self.zh is None:
      if self.zh_revision is not None or self.translation_credit is not None:
        raise ValueError("Missing translation must not claim a revision or credit")
    else:
      _text(self.zh)
      if type(self.zh_revision) is not int or not 1 <= self.zh_revision <= self.revision:
        raise ValueError("Translation revision must be positive and not newer than its original")
      if self.translation_credit is None:
        raise ValueError("A translation must identify its translator")
      _text(self.translation_credit)

  def status(self, language: Language) -> TranslationStatus:
    """Return current, stale or missing without substituting text. 返回当前、过期或缺失，不替换文本。"""
    _language(language)
    if language == "en":
      return TranslationStatus.CURRENT
    if self.zh is None:
      return TranslationStatus.MISSING
    if self.zh_revision != self.revision:
      return TranslationStatus.STALE
    return TranslationStatus.CURRENT

  def text(self, language: Language) -> str | None:
    """Return the requested text, including stale text or None. 返回所选文本，可能是旧译或 None。"""
    _language(language)
    return self.en if language == "en" else self.zh


@dataclass(frozen=True, slots=True)
class Concept:
  """One stable vocabulary identity; names do not merge different definitions.

  Alias and related-ID sequences are copied into immutable tuples. Configuration
  links refer only to existing request identities, never to an invented algorithm.
  Invalid types/references raise TypeError/ValueError; cross-record links are checked by Catalog.

  一个稳定的词汇身份，同名不合并定义。别名及关联标识序列复制为不可变元组。
  配置链接仅指向已有请求标识，不虚构算法。非法类型或引用抛出 TypeError 或 ValueError；
  跨记录引用由 Catalog 核验。
  """

  identifier: str
  kind: ConceptKind
  name: LocalizedText
  description: LocalizedText
  en_aliases: Sequence[str] = ()
  zh_aliases: Sequence[str] = ()
  related: Sequence[str] = ()
  configuration: ConfigurationIdentity | None = None

  def __post_init__(self) -> None:
    _identifier(self.identifier)
    if type(self.kind) is not ConceptKind:
      raise TypeError("kind must be a ConceptKind")
    if type(self.name) is not LocalizedText or type(self.description) is not LocalizedText:
      raise TypeError("Concept names and descriptions must be LocalizedText")
    for field in ("en_aliases", "zh_aliases"):
      aliases = _tuple(getattr(self, field), str)
      for alias in aliases:
        _text(alias)
      object.__setattr__(self, field, aliases)
    object.__setattr__(self, "related", _ids(self.related))
    _configuration(self.configuration)
    expected = {
      ConceptKind.BODY: Body,
      ConceptKind.HOUSE_SYSTEM: HouseSystem,
      ConceptKind.NODE_DEFINITION: NodeDefinition,
      ConceptKind.LUNAR_NODE: LunarNode,
      ConceptKind.ASPECT: MajorAspect,
    }.get(self.kind)
    if self.configuration is not None and type(self.configuration) is not expected:
      raise ValueError("Configuration reference does not belong to the concept kind")


@dataclass(frozen=True, slots=True)
class RuleVariant:
  """Named definition and scope; a config reference is not executable astronomy.

  Concept IDs are isolated tuples; Catalog rejects dangling links. Raise TypeError
  or ValueError for invalid values. No formula, orb, default or chart evaluation is supplied.

  具名定义及范围；配置引用不表示天文算法已实现。概念标识隔离为元组，悬空引用由 Catalog 拒绝。
  非法值抛出 TypeError 或 ValueError；不提供公式、容许度、默认值或命盘判断。
  """

  identifier: str
  name: LocalizedText
  concept_ids: Sequence[str]
  definition: LocalizedText
  tradition: LocalizedText
  limits: LocalizedText
  configuration: ConfigurationIdentity | None = None

  def __post_init__(self) -> None:
    _identifier(self.identifier)
    for value in (self.name, self.definition, self.tradition, self.limits):
      if type(value) is not LocalizedText:
        raise TypeError("Variant text must be LocalizedText")
    object.__setattr__(self, "concept_ids", _ids(self.concept_ids))
    if not self.concept_ids:
      raise ValueError("A variant must identify its concepts")
    _configuration(self.configuration)


@dataclass(frozen=True, slots=True)
class Source:
  """An edition, lineage and bounded rights/verification record.

  Title, author, edition and language preserve bibliographic identity. Scope and
  rights are editorial records, not a copyright guarantee or chart conclusion.
  Invalid fields raise TypeError/ValueError.

  一个版本、谱系及有限的转载与查核记录。书名、作者、版本与语言保留书目身份。
  范围及权限是整理记录，不是版权保证或命盘结论；非法字段抛出 TypeError 或 ValueError。
  """

  identifier: str
  title: str
  author: str
  edition: str
  language: str
  lineage: LocalizedText
  rights: LocalizedText
  scope: LocalizedText
  verification: SourceVerification
  url: str

  def __post_init__(self) -> None:
    _identifier(self.identifier)
    for value in (self.title, self.author, self.edition, self.language, self.url):
      _text(value)
    for block in (self.lineage, self.rights, self.scope):
      if type(block) is not LocalizedText:
        raise TypeError("Source lineage, rights and scope must be LocalizedText")
    if type(self.verification) is not SourceVerification:
      raise TypeError("verification must be SourceVerification")


@dataclass(frozen=True, slots=True)
class Citation:
  """Edition-specific locator and optional English excerpt with labeled translation.

  The excerpt's English is source text, not project explanation; Chinese credit
  and revision identify its translation. Catalog checks the source ID. Invalid
  values raise TypeError/ValueError.

  版本内定位及可选英文原文与具名译文。引文英文属于来源原文，不是项目说明；中文署名及修订
  标识其译文。来源标识由 Catalog 核验，非法值抛出 TypeError 或 ValueError。
  """

  source_id: str
  locator: str
  excerpt: LocalizedText | None = None

  def __post_init__(self) -> None:
    _identifier(self.source_id)
    _text(self.locator)
    if self.excerpt is not None and type(self.excerpt) is not LocalizedText:
      raise TypeError("excerpt must be LocalizedText or None")


@dataclass(frozen=True, slots=True)
class Entry:
  """Project statement, citations and independent editorial states; never a chart match.

  All sequences are copied into tuples. Prerequisite completeness does not mean
  satisfied premises; output eligibility does not mean applicability. Queries
  always leave chart applicability not_assessed. Catalog checks cross-record links.
  Invalid values raise TypeError/ValueError even under python -O.

  项目陈述、引用及相互独立的整理状态，不表示命盘命中。所有序列复制为元组。
  前提完整不等于前提已满足；输出资格不等于适用。查询始终将命盘适用性留为 not_assessed。
  Catalog 核验跨记录引用，非法值即使在 python -O 下也抛出 TypeError 或 ValueError。
  """

  identifier: str
  statement: LocalizedText
  concept_ids: Sequence[str]
  rule_ids: Sequence[str]
  citations: Sequence[Citation]
  prerequisites: Sequence[LocalizedText]
  exceptions: LocalizedText
  limits: LocalizedText
  prerequisite_status: PrerequisiteStatus
  output_eligibility: OutputEligibility

  def __post_init__(self) -> None:
    _identifier(self.identifier)
    for value in (self.statement, self.exceptions, self.limits):
      if type(value) is not LocalizedText:
        raise TypeError("Entry text must be LocalizedText")
    object.__setattr__(self, "concept_ids", _ids(self.concept_ids))
    object.__setattr__(self, "rule_ids", _ids(self.rule_ids))
    object.__setattr__(self, "citations", _tuple(self.citations, Citation))
    object.__setattr__(self, "prerequisites", _tuple(self.prerequisites, LocalizedText))
    if not self.concept_ids or not self.citations:
      raise ValueError("Entries must identify concepts and cite at least one source")
    if type(self.prerequisite_status) is not PrerequisiteStatus:
      raise TypeError("prerequisite_status must be PrerequisiteStatus")
    if type(self.output_eligibility) is not OutputEligibility:
      raise TypeError("output_eligibility must be OutputEligibility")

  @property
  def chart_applicability(self) -> Literal["not_assessed"]:
    """Retrieval has not evaluated any chart. 检索未判断任何命盘。"""
    return "not_assessed"
