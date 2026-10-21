"""Immutable requested chart choices, without astronomy or rule evaluation.

不可变的排盘请求配置，不执行天文计算或规则求值。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from astrology._validation import finite_number


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
  """The five supported aspects; `astrology.aspects` defines their angles and evaluation.

  支持的五种相位；角度定义和判断函数在 `astrology.aspects` 里。
  """

  CONJUNCTION = "conjunction"
  SEXTILE = "sextile"
  SQUARE = "square"
  TRINE = "trine"
  OPPOSITION = "opposition"


class OrbCombination(StrEnum):
  """Combine two objects' orbs into one limit, without prescribing a tradition's rule.

  Each object has an orb for the aspect (its own override or the rule's orb). A pair
  is within the limit when its deviation from the exact angle satisfies the rule:
  either object's orb contains it (the larger orb), both objects' orbs contain it
  (the smaller orb), or the mean of the two orbs contains it. A limit is inclusive.

  将两个对象的容许度合成一个上限，不指定哪个规则属于哪个传统。每个对象使用单独设置的容许度，
  未单独设置时使用相位规则的容许度。三种合成方式分别取较大值、较小值或平均值；
  偏差的绝对值不超过该上限就算符合规则，等于上限也算。
  """

  EITHER_WITHIN_OWN_ORB = "either_within_own_orb"
  BOTH_WITHIN_OWN_ORB = "both_within_own_orb"
  MEAN_OF_ORBS = "mean_of_orbs"


def _orb(value: object) -> float:
  """Return a finite nonnegative orb as a float. 返回有限且非负的容许度，类型为 float。"""
  try:
    orb = finite_number(value, "orb_degrees")
  except ValueError as exc:
    raise ValueError("orb_degrees must be finite and nonnegative") from exc
  if orb < 0:
    raise ValueError("orb_degrees must be finite and nonnegative")
  return orb


@dataclass(frozen=True, slots=True)
class ObjectOrb:
  """One object's own orb for one aspect rule, in degrees; finite and nonnegative.

  为某个对象在一条相位规则中单独设置的容许度，单位为度，必须有限且非负。
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

  由调用方给出一种相位的容许度，也可以为对象单独设置。`orb_degrees` 必须有限、非负，
  单位为度。未在 `object_orbs` 中单独设置的对象使用这个值。条目复制为元组，
  每个对象只能出现一次。没有默认容许度；这个类型只保存规则，不计算相位。
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

  只保存排盘请求。对象和相位规则按原顺序复制为不可变元组，不受调用方后续修改列表的影响。
  必须指定宫制和至少一个对象，对象不能重复；相位规则也不能重复，但可以为空。
  `aspect_objects` 指定参与相位的对象，必须是 `objects` 的子集；省略时所有请求的对象都参与。
  只要有规则为对象单独设置容许度，就必须给出 `orb_combination`，否则不能给。
  单独设置容许度的对象必须参与相位。仅支持热带黄道和地心，不提供默认容许度或默认宫制，
  不记录实际计算模型，也不执行计算或提供替代策略。
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
    object.__setattr__(self, "objects", objects)
    object.__setattr__(self, "aspects", aspects)
    participants = self.aspect_participants()
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

  def aspect_participants(self) -> tuple[Body | LunarNode, ...]:
    """Return participants in requested object order, or an empty tuple without rules.

    按请求对象的顺序返回参与相位的对象；没有相位规则时返回空元组。
    """
    if not self.aspects:
      return ()
    return tuple(
      identity
      for identity in self.objects
      if self.aspect_objects is None or identity in self.aspect_objects
    )
