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
  ObjectOrb,
  OrbCombination,
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


def aspect_config(
  rules: list[AspectRule],
  *,
  aspect_objects: list[Body | LunarNode] | None = None,
  orb_combination: OrbCombination | None = None,
) -> ChartConfig:
  return ChartConfig(
    HouseSystem.WHOLE_SIGN,
    (Body.SUN, Body.MOON, Body.MARS, LunarNode.MEAN_ASCENDING),
    rules,
    aspect_objects=aspect_objects,
    orb_combination=orb_combination,
  )


def test_object_orb_keeps_identity_and_degrees() -> None:
  value = ObjectOrb(Body.MOON, 13)
  assert value.identity is Body.MOON
  assert value.orb_degrees == 13.0
  assert type(value.orb_degrees) is float
  with pytest.raises(FrozenInstanceError):
    cast(Any, value).orb_degrees = 1


@pytest.mark.parametrize("orb", [-0.1, float("nan"), float("inf"), 10**400])
def test_object_orb_rejects_invalid_degrees(orb: float) -> None:
  with pytest.raises(ValueError):
    ObjectOrb(Body.MOON, orb)


@pytest.mark.parametrize("orb", [True, "3", None, 1j])
def test_object_orb_rejects_non_numbers(orb: object) -> None:
  with pytest.raises(TypeError):
    ObjectOrb(Body.MOON, cast(Any, orb))


@pytest.mark.parametrize("identity", ["moon", None, MajorAspect.TRINE])
def test_object_orb_requires_an_object_identity(identity: object) -> None:
  with pytest.raises(TypeError):
    ObjectOrb(cast(Any, identity), 3)


def test_aspect_rule_object_orbs_are_copied_and_optional() -> None:
  entries = [ObjectOrb(Body.MOON, 13), ObjectOrb(Body.SUN, 8)]
  rule = AspectRule(MajorAspect.TRINE, 3, entries)
  entries.clear()
  assert rule.object_orbs == (ObjectOrb(Body.MOON, 13), ObjectOrb(Body.SUN, 8))
  assert AspectRule(MajorAspect.TRINE, 3).object_orbs == ()
  assert inspect.signature(AspectRule).parameters["object_orbs"].default == ()


@pytest.mark.parametrize(
  "entries,error",
  [
    ("moon", TypeError),
    (None, TypeError),
    ([Body.MOON], TypeError),
    ([(Body.MOON, 13)], TypeError),
    ([ObjectOrb(Body.MOON, 13), ObjectOrb(Body.MOON, 2)], ValueError),
  ],
)
def test_aspect_rule_rejects_invalid_object_orbs(entries: object, error: type[Exception]) -> None:
  with pytest.raises(error):
    AspectRule(MajorAspect.TRINE, 3, cast(Any, entries))


def test_orb_combination_names_are_stable() -> None:
  assert [value.value for value in OrbCombination] == [
    "either_within_own_orb",
    "both_within_own_orb",
    "mean_of_orbs",
  ]


def test_aspect_objects_default_to_unset_and_keep_requested_subset() -> None:
  rules = [AspectRule(MajorAspect.TRINE, 3)]
  assert aspect_config(rules).aspect_objects is None
  chosen: list[Body | LunarNode] = [Body.MOON, Body.SUN]
  value = aspect_config(rules, aspect_objects=chosen)
  chosen.clear()
  assert value.aspect_objects == (Body.MOON, Body.SUN)
  assert isinstance(value.aspect_objects, tuple)


@pytest.mark.parametrize(
  "chosen,error",
  [
    ([], ValueError),
    ([Body.SUN, Body.SUN], ValueError),
    ([Body.VENUS], ValueError),
    ("sun", TypeError),
    (["sun"], TypeError),
    (3, TypeError),
  ],
)
def test_aspect_objects_must_be_a_unique_nonempty_subset(
  chosen: object, error: type[Exception]
) -> None:
  with pytest.raises(error):
    aspect_config([AspectRule(MajorAspect.TRINE, 3)], aspect_objects=cast(Any, chosen))


def test_aspect_objects_require_aspect_rules() -> None:
  with pytest.raises(ValueError, match="requires aspect rules"):
    aspect_config([], aspect_objects=[Body.SUN])


def test_orb_combination_is_required_exactly_with_object_orbs() -> None:
  with_orbs = [AspectRule(MajorAspect.TRINE, 3, [ObjectOrb(Body.MOON, 13)])]
  plain = [AspectRule(MajorAspect.TRINE, 3)]
  chosen = OrbCombination.MEAN_OF_ORBS
  assert aspect_config(with_orbs, orb_combination=chosen).orb_combination is chosen
  assert aspect_config(plain).orb_combination is None
  with pytest.raises(ValueError, match="required"):
    aspect_config(with_orbs)
  with pytest.raises(ValueError, match="requires aspect rules with object orbs"):
    aspect_config(plain, orb_combination=chosen)
  with pytest.raises(ValueError, match="requires aspect rules with object orbs"):
    aspect_config([], orb_combination=chosen)
  with pytest.raises(TypeError):
    aspect_config(with_orbs, orb_combination=cast(Any, "mean_of_orbs"))


def test_object_orbs_may_name_only_participating_objects() -> None:
  rules = [AspectRule(MajorAspect.TRINE, 3, [ObjectOrb(Body.MARS, 5)])]
  chosen = OrbCombination.EITHER_WITHIN_OWN_ORB
  assert aspect_config(rules, orb_combination=chosen).objects[2] is Body.MARS
  with pytest.raises(ValueError, match="take part"):
    aspect_config(rules, aspect_objects=[Body.SUN, Body.MOON], orb_combination=chosen)
  elsewhere = [AspectRule(MajorAspect.TRINE, 3, [ObjectOrb(Body.VENUS, 5)])]
  with pytest.raises(ValueError, match="take part"):
    aspect_config(elsewhere, orb_combination=chosen)
