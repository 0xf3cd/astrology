# Requested chart configuration

[简体中文](../zh-CN/configuration.md) · [Documentation](index.md) · [API reference](reference.md)

`ChartConfig` is an immutable request, not a calculated chart or resolved
astronomy metadata. The only admitted modes are `tropical` and `geocentric`.
House system, object selection, and aspect rules must be supplied explicitly.
An empty aspect sequence requests no aspect rules; object selection cannot be
empty. There is no default house system or orb.

## Preserve the selected identities

`HouseSystem` admits Whole Sign, Equal, and Placidus. This layer preserves the
selection; it neither calculates geometry nor substitutes a different system.
The [chart guide](chart.md) reports unavailable requested geometry explicitly.

`Body` identifies the ten physical bodies from Sun and Moon through Pluto.
`LunarNode` identifies mathematical ascending/descending nodes with either the
mean or Meeus five-term true definition. The definition is part of each node's
identity, not an accuracy flag or an interchangeable model. Both definitions
may be selected explicitly in one request.

These are requested identities; the [chart adapter](chart.md) binds them to the
astronomical definitions and models. No node formula is implemented in this
layer.

```{doctest}
>>> from astrology import Body, ChartConfig, HouseSystem, LunarNode
>>> objects = [Body.SUN, Body.MOON, LunarNode.MEAN_ASCENDING]
>>> request = ChartConfig(HouseSystem.WHOLE_SIGN, objects, ())
>>> objects.clear()
>>> tuple(value.value for value in request.objects)
('sun', 'moon', 'mean_ascending_node')
>>> request.house_system.value
'whole_sign'
>>> LunarNode.MEAN_ASCENDING.definition.value
'mean'
>>> LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING.definition.value
'meeus_five_term_true'
```

Object and rule sequences are copied into tuples, preserving order. Source lists
can change without changing the request. Duplicate objects or duplicate aspect
identities are rejected rather than silently merged. Enum value strings such as
`"sun"` are not enum instances and are not implicitly converted.

## Request aspects

`MajorAspect` names conjunction, sextile, square, trine, and opposition.
`AspectRule` carries a caller-supplied finite nonnegative `orb_degrees` value in
degrees. This layer stores the request. It does not calculate aspects or choose a
tradition's orb policy; the [aspect guide](aspects.md) explains how the request is
judged.

```{doctest}
>>> from astrology import AspectRule, MajorAspect
>>> rules = [AspectRule(MajorAspect.CONJUNCTION, 0)]
>>> request = ChartConfig(HouseSystem.PLACIDUS, (Body.SUN, Body.MOON), rules)
>>> rules.clear()
>>> (request.aspects[0].aspect.value, request.aspects[0].orb_degrees)
('conjunction', 0.0)
>>> (request.zodiac, request.center)
('tropical', 'geocentric')
```

The zero orb above is an explicit synthetic request value, not a library default
or recommendation.

## Give an object its own orb, and choose who takes part

An `AspectRule` may carry `ObjectOrb` entries. An object with an entry uses it in
that rule; any other object uses the rule's `orb_degrees`. When some rule has
object orbs, `orb_combination` must say how the two orbs of a pair combine, and when
none has, it must be left out. `aspect_objects` names the objects that take part in
aspects, as a subset of `objects`; left out, all requested objects take part. An
object orb may name only a participating object.

```{doctest}
>>> from astrology import LunarNode, ObjectOrb, OrbCombination
>>> rules = [AspectRule(MajorAspect.TRINE, 3, [ObjectOrb(Body.MOON, 13)])]
>>> objects = (Body.SUN, Body.MOON, LunarNode.MEAN_ASCENDING)
>>> request = ChartConfig(
...   HouseSystem.PLACIDUS, objects, rules,
...   aspect_objects=[Body.SUN, Body.MOON],
...   orb_combination=OrbCombination.EITHER_WITHIN_OWN_ORB,
... )
>>> [value.value for value in request.aspect_objects]
['sun', 'moon']
>>> request.orb_combination.value
'either_within_own_orb'
>>> ChartConfig(HouseSystem.PLACIDUS, objects, rules)
Traceback (most recent call last):
...
ValueError: orb_combination is required when aspect rules have object orbs
```

NaN, infinity, negative orbs, booleans, unsupported modes, and inconsistent
selections fail under normal Python and `python -O`.

The defining enums and API contracts are generated in the [reference](reference.md).
Actual astronomy models, versions, time scales, and effective calculation
settings belong to the chart result; they are not invented here to complete a
metadata record. The [chart guide](chart.md) shows how a request becomes that
result, and the [knowledge guide](knowledge.md) covers queries that need no
chart at all.
