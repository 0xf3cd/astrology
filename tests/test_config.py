"""Explicit requested configurations and immutable ownership."""

import inspect
from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from astrology import (
  AspectRule,
  Body,
  ChartConfig,
  HouseSystem,
  LunarNode,
  MajorAspect,
  NodeDefinition,
)


def config() -> ChartConfig:
  return ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ())


@pytest.mark.parametrize("system", list(HouseSystem))
def test_all_approved_house_identities_are_preserved(system: HouseSystem) -> None:
  value = replace(config(), house_system=system)
  assert value.house_system is system
  assert value.zodiac == "tropical"
  assert value.center == "geocentric"


def test_physical_bodies_and_named_mathematical_nodes_are_distinct() -> None:
  bodies = tuple(Body)
  nodes = tuple(LunarNode)
  value = ChartConfig(HouseSystem.PLACIDUS, (*bodies, *nodes), ())
  assert len(bodies) == 10
  assert len(nodes) == 4
  assert value.objects == (*bodies, *nodes)
  assert not any(isinstance(node, Body) for node in nodes)
  assert {node.definition for node in nodes} == set(NodeDefinition)
  assert LunarNode.MEAN_ASCENDING.definition is NodeDefinition.MEAN
  assert LunarNode.MEAN_DESCENDING.definition is NodeDefinition.MEAN
  assert LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING.definition is NodeDefinition.MEEUS_FIVE_TERM_TRUE
  assert LunarNode.MEEUS_FIVE_TERM_TRUE_DESCENDING.definition is NodeDefinition.MEEUS_FIVE_TERM_TRUE


def test_caller_owned_configuration_sequences_are_isolated() -> None:
  objects: list[Body | LunarNode] = [Body.SUN, LunarNode.MEAN_ASCENDING]
  aspects = [AspectRule(MajorAspect.CONJUNCTION, 0)]
  value = ChartConfig(HouseSystem.EQUAL, objects, aspects)
  objects.clear()
  aspects.clear()
  assert value.objects == (Body.SUN, LunarNode.MEAN_ASCENDING)
  assert value.aspects == (AspectRule(MajorAspect.CONJUNCTION, 0),)
  assert isinstance(value.objects, tuple)
  assert isinstance(value.aspects, tuple)
  with pytest.raises(FrozenInstanceError):
    cast(Any, value).house_system = HouseSystem.PLACIDUS
  with pytest.raises(FrozenInstanceError):
    cast(Any, value.aspects[0]).orb_degrees = 1


@pytest.mark.parametrize("aspect", list(MajorAspect))
def test_explicit_aspect_identity_and_orb(aspect: MajorAspect) -> None:
  rule = AspectRule(aspect, 0)
  value = replace(config(), aspects=(rule,))
  assert value.aspects[0].aspect is aspect
  assert value.aspects[0].orb_degrees == 0.0


def test_no_house_objects_aspect_or_orb_defaults_are_invented() -> None:
  for field in ("house_system", "objects", "aspects"):
    assert inspect.signature(ChartConfig).parameters[field].default is inspect.Parameter.empty
  assert inspect.signature(AspectRule).parameters["orb_degrees"].default is inspect.Parameter.empty
  with pytest.raises(TypeError):
    cast(Any, AspectRule)(MajorAspect.CONJUNCTION)


@pytest.mark.parametrize("orb", [-1, float("nan"), float("inf"), -float("inf"), 10**1000])
def test_invalid_orb_values(orb: float) -> None:
  with pytest.raises(ValueError, match="finite and nonnegative"):
    AspectRule(MajorAspect.CONJUNCTION, orb)


@pytest.mark.parametrize("orb", [True, "1", None])
def test_invalid_orb_types(orb: object) -> None:
  with pytest.raises(TypeError):
    AspectRule(MajorAspect.CONJUNCTION, cast(Any, orb))


def test_aspect_requires_a_named_identity() -> None:
  with pytest.raises(TypeError):
    AspectRule(cast(Any, "conjunction"), 0)


def test_mutable_string_subclass_is_not_a_mode_value() -> None:
  class MutableText(str):
    pass

  with pytest.raises(TypeError):
    replace(config(), zodiac=cast(Any, MutableText("tropical")))


@pytest.mark.parametrize(
  "field,value",
  [
    ("house_system", "placidus"),
    ("house_system", "unknown"),
    ("zodiac", "sidereal"),
    ("center", "topocentric"),
    ("zodiac", None),
    ("center", 1),
    ("objects", ()),
    ("objects", "sun"),
    ("objects", None),
    ("objects", ["sun"]),
    ("objects", [Body.SUN, Body.SUN]),
    ("aspects", "conjunction"),
    ("aspects", None),
    ("aspects", [MajorAspect.CONJUNCTION]),
    ("aspects", [AspectRule(MajorAspect.CONJUNCTION, 0), AspectRule(MajorAspect.CONJUNCTION, 1)]),
  ],
)
def test_unsupported_or_inconsistent_requests_fail(field: str, value: object) -> None:
  with pytest.raises((ValueError, TypeError)):
    replace(config(), **cast(Any, {field: value}))
