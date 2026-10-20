"""Immutable requested chart choices, without astronomy or rule evaluation.

不可变的排盘请求配置，不执行天文计算或规则求值。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Literal, cast


class HouseSystem(StrEnum):
  """Requested house identity; unavailable geometry must not be substituted.

  请求的宫制标识；几何不可用时不得静默替换。
  """

  WHOLE_SIGN = "whole_sign"
  EQUAL = "equal"
  PLACIDUS = "placidus"


class Body(StrEnum):
  """Physical natal bodies, distinct from mathematical nodes. 本命盘物理天体，与数学交点区分。"""

  SUN = "sun"
  MOON = "moon"
  MERCURY = "mercury"
  VENUS = "venus"
  MARS = "mars"
  JUPITER = "jupiter"
  SATURN = "saturn"
  URANUS = "uranus"
  NEPTUNE = "neptune"
  PLUTO = "pluto"


class NodeDefinition(StrEnum):
  """Named lunar-node definitions, not accuracy settings. 具名月交点定义，不是精度档位。"""

  MEAN = "mean"
  MEEUS_FIVE_TERM_TRUE = "meeus_five_term_true"


class LunarNode(StrEnum):
  """Mathematical nodes whose identity includes their definition and direction.

  数学月交点，其标识同时包含定义与升降方向。
  """

  MEAN_ASCENDING = "mean_ascending_node"
  MEAN_DESCENDING = "mean_descending_node"
  MEEUS_FIVE_TERM_TRUE_ASCENDING = "meeus_five_term_true_ascending_node"
  MEEUS_FIVE_TERM_TRUE_DESCENDING = "meeus_five_term_true_descending_node"

  @property
  def definition(self) -> NodeDefinition:
    """Return the identity's named definition. 返回该标识对应的具名定义。"""
    return {
      LunarNode.MEAN_ASCENDING: NodeDefinition.MEAN,
      LunarNode.MEAN_DESCENDING: NodeDefinition.MEAN,
      LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING: NodeDefinition.MEEUS_FIVE_TERM_TRUE,
      LunarNode.MEEUS_FIVE_TERM_TRUE_DESCENDING: NodeDefinition.MEEUS_FIVE_TERM_TRUE,
    }[self]


class MajorAspect(StrEnum):
  """The five admitted aspect identities; angles and evaluation live in `astrology.aspects`.

  接纳的五种相位标识；角度与判断在 `astrology.aspects` 里。
  """

  CONJUNCTION = "conjunction"
  SEXTILE = "sextile"
  SQUARE = "square"
  TRINE = "trine"
  OPPOSITION = "opposition"


class OrbCombination(StrEnum):
  """How two objects' orbs give the limit of one pair; named rules, not tradition claims.

  Each object has an orb for the aspect (its own override or the rule's orb). A pair
  is within the limit when its deviation from the exact angle satisfies the rule:
  either object's orb contains it (the larger orb), both objects' orbs contain it
  (the smaller orb), or the mean of the two orbs contains it. A limit is inclusive.

  两个对象的容许度如何合成一对对象的限度；具名规则，不是对传统的断言。每个对象在该相位
  下有自己的容许度（自己的覆盖值，或规则的容许度）。一对对象与精确角度的偏差满足所选规则时
  算在限度内：任一对象的容许度包含它（取较大者）、两个对象的容许度都包含它（取较小者），
  或两个容许度的平均值包含它。限度包含端点。
  """

  EITHER_WITHIN_OWN_ORB = "either_within_own_orb"
  BOTH_WITHIN_OWN_ORB = "both_within_own_orb"
  MEAN_OF_ORBS = "mean_of_orbs"


def _orb(value: object) -> float:
  """Return a finite nonnegative orb as a float. 返回有限且非负的容许度，类型为 float。"""
  if type(value) not in (int, float):
    raise TypeError("orb_degrees must be a number, not bool")
  try:
    orb = float(cast("int | float", value))
  except OverflowError as exc:
    raise ValueError("orb_degrees must be finite and nonnegative") from exc
  if not isfinite(orb) or orb < 0:
    raise ValueError("orb_degrees must be finite and nonnegative")
  return orb


@dataclass(frozen=True, slots=True)
class ObjectOrb:
  """One object's own orb for one aspect rule, in degrees; finite and nonnegative.

  某个对象在某条相位规则下自己的容许度，以度为单位，有限且非负。
  """

  identity: Body | LunarNode
  orb_degrees: float

  def __post_init__(self) -> None:
    if not isinstance(self.identity, (Body, LunarNode)):
      raise TypeError("identity must be a Body or LunarNode")
    object.__setattr__(self, "orb_degrees", _orb(self.orb_degrees))


@dataclass(frozen=True, slots=True)
class AspectRule:
  """An explicit caller-supplied orb for one aspect, with optional per-object orbs.

  `orb_degrees` is finite, nonnegative and in degrees; it applies to every object
  without an entry in `object_orbs`. The entries are copied into a tuple and name
  each object once. There is no default orb, and this type does not evaluate.

  调用方显式给出的单个相位的容许度，可另给按对象的容许度。`orb_degrees` 有限、非负、
  以度为单位，适用于 `object_orbs` 里没有条目的所有对象。条目复制为元组，每个对象
  只能出现一次。没有默认容许度，这个类型也不做判断。
  """

  aspect: MajorAspect
  orb_degrees: float
  object_orbs: Sequence[ObjectOrb] = ()

  def __post_init__(self) -> None:
    if not isinstance(self.aspect, MajorAspect):
      raise TypeError("aspect must be a MajorAspect")
    object.__setattr__(self, "orb_degrees", _orb(self.orb_degrees))
    if not isinstance(self.object_orbs, Sequence) or isinstance(self.object_orbs, (str, bytes)):
      raise TypeError("object_orbs must be a sequence of ObjectOrb values")
    object_orbs = tuple(self.object_orbs)
    if any(type(value) is not ObjectOrb for value in object_orbs):
      raise TypeError("object_orbs must contain only ObjectOrb values")
    if len({value.identity for value in object_orbs}) != len(object_orbs):
      raise ValueError("object_orbs must not repeat an object")
    object.__setattr__(self, "object_orbs", object_orbs)


@dataclass(frozen=True, slots=True)
class ChartConfig:
  """Requested choices only, preserving order in isolated immutable tuples.

  Select a house system, nonempty unique objects, and explicit unique aspect rules.
  An empty aspect sequence is allowed. Aspects are judged among `aspect_objects`,
  which must be a subset of `objects`; omitted, it means all requested objects.
  `orb_combination` is required exactly when some rule has per-object orbs, and a
  per-object orb may name only a participating object. Only tropical/geocentric is
  admitted. No orb or house defaults, effective-model claims, computation, or
  fallback are supplied.

  仅保存请求选择，按原顺序存入隔离的不可变元组。宫制、非空且不重复的对象及不重复的显式相位规则
  均须给出，相位序列可以为空。相位只在 `aspect_objects` 之间判断，它必须是 `objects` 的子集；
  省略时表示所有已请求的对象。有规则带按对象的容许度时，必须给出 `orb_combination`，反之不能给；
  按对象的容许度只能指名参与相位的对象。仅支持热带黄道和地心。不提供容许度或宫制默认值、
  实际模型声明、计算或替代策略。
  """

  house_system: HouseSystem
  objects: Sequence[Body | LunarNode]
  aspects: Sequence[AspectRule]
  zodiac: Literal["tropical"] = "tropical"
  center: Literal["geocentric"] = "geocentric"
  aspect_objects: Sequence[Body | LunarNode] | None = None
  orb_combination: OrbCombination | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.house_system, HouseSystem):
      raise TypeError("house_system must be a HouseSystem")
    if type(self.zodiac) is not str or type(self.center) is not str:
      raise TypeError("zodiac and center must be plain strings")
    if self.zodiac != "tropical" or self.center != "geocentric":
      raise ValueError("Only tropical, geocentric chart requests are supported")
    if not isinstance(self.objects, Sequence) or isinstance(self.objects, (str, bytes)):
      raise TypeError("objects must be a sequence of Body or LunarNode values")
    objects = tuple(self.objects)
    if not objects:
      raise ValueError("objects must not be empty")
    if any(not isinstance(value, (Body, LunarNode)) for value in objects):
      raise TypeError("objects must contain only Body or LunarNode values")
    if len(set(objects)) != len(objects):
      raise ValueError("objects must not contain duplicate identities")
    if not isinstance(self.aspects, Sequence) or isinstance(self.aspects, (str, bytes)):
      raise TypeError("aspects must be a sequence of AspectRule values")
    aspects = tuple(self.aspects)
    if any(type(value) is not AspectRule for value in aspects):
      raise TypeError("aspects must contain only AspectRule values")
    if len({value.aspect for value in aspects}) != len(aspects):
      raise ValueError("aspects must not repeat an aspect identity")
    if self.aspect_objects is not None:
      if not aspects:
        raise ValueError("aspect_objects requires aspect rules")
      if not isinstance(self.aspect_objects, Sequence) or isinstance(
        self.aspect_objects, (str, bytes)
      ):
        raise TypeError("aspect_objects must be a sequence of Body or LunarNode values")
      participants = tuple(self.aspect_objects)
      if not participants:
        raise ValueError("aspect_objects must not be empty")
      if any(not isinstance(value, (Body, LunarNode)) for value in participants):
        raise TypeError("aspect_objects must contain only Body or LunarNode values")
      if len(set(participants)) != len(participants):
        raise ValueError("aspect_objects must not contain duplicate identities")
      if not set(participants) <= set(objects):
        raise ValueError("aspect_objects must be a subset of objects")
      object.__setattr__(self, "aspect_objects", participants)
    else:
      participants = objects
    has_object_orbs = any(rule.object_orbs for rule in aspects)
    if self.orb_combination is not None and not isinstance(self.orb_combination, OrbCombination):
      raise TypeError("orb_combination must be an OrbCombination")
    if has_object_orbs and self.orb_combination is None:
      raise ValueError("orb_combination is required when aspect rules have object orbs")
    if not has_object_orbs and self.orb_combination is not None:
      raise ValueError("orb_combination requires aspect rules with object orbs")
    for rule in aspects:
      if any(entry.identity not in participants for entry in rule.object_orbs):
        raise ValueError("object orbs may name only objects that take part in aspects")
    object.__setattr__(self, "objects", objects)
    object.__setattr__(self, "aspects", aspects)
