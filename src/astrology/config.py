"""Immutable requested chart choices, without astronomy or rule evaluation.

不可变的排盘请求配置，不执行天文计算或规则求值。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Literal


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
  """The five admitted aspect identities; calculation belongs to the aspect feature.

  接纳的五种相位标识；计算归后续相位功能。
  """

  CONJUNCTION = "conjunction"
  SEXTILE = "sextile"
  SQUARE = "square"
  TRINE = "trine"
  OPPOSITION = "opposition"


@dataclass(frozen=True, slots=True)
class AspectRule:
  """An explicit caller-supplied, finite nonnegative orb in degrees; no default or evaluation.

  调用方显式给出以度为单位、有限且非负的容许度；不提供默认值，也不执行判断。
  """

  aspect: MajorAspect
  orb_degrees: float

  def __post_init__(self) -> None:
    if not isinstance(self.aspect, MajorAspect):
      raise TypeError("aspect must be a MajorAspect")
    if type(self.orb_degrees) not in (int, float):
      raise TypeError("orb_degrees must be a number, not bool")
    try:
      orb = float(self.orb_degrees)
    except OverflowError as exc:
      raise ValueError("orb_degrees must be finite and nonnegative") from exc
    if not isfinite(orb) or orb < 0:
      raise ValueError("orb_degrees must be finite and nonnegative")
    object.__setattr__(self, "orb_degrees", orb)


@dataclass(frozen=True, slots=True)
class ChartConfig:
  """Requested choices only, preserving order in isolated immutable tuples.

  Select a house system, nonempty unique objects, and explicit unique aspect rules.
  An empty aspect sequence is allowed.
  Only tropical/geocentric is admitted. No orb or house defaults, effective-model
  claims, computation, or fallback are supplied.

  仅保存请求选择，按原顺序存入隔离的不可变元组。宫制、非空且不重复的对象及不重复的显式相位规则
  均须给出，相位序列可以为空；仅支持热带黄道和地心。不提供容许度或宫制默认值、实际模型声明、计算或替代策略。
  """

  house_system: HouseSystem
  objects: Sequence[Body | LunarNode]
  aspects: Sequence[AspectRule]
  zodiac: Literal["tropical"] = "tropical"
  center: Literal["geocentric"] = "geocentric"

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
    object.__setattr__(self, "objects", objects)
    object.__setattr__(self, "aspects", aspects)
