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

Use `ObjectOrb` to set an object's orb separately; other objects use the rule's
`orb_degrees`. If any rule uses `ObjectOrb`, you must choose `orb_combination` to
combine the pair's orbs into one limit. Otherwise, leave `orb_combination` out.
`aspect_objects` selects requested bodies/nodes and may also explicitly add `Axis`
members. If omitted, all requested bodies/nodes take part and no axes are added.
You can set a separate orb only for a participating identity, including an axis.
`objects` itself still accepts only `Body` and `LunarNode`, not axes.

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

```{doctest}
>>> from astrology import Axis
>>> with_axes = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,),
...   (AspectRule(MajorAspect.SEXTILE, 3),),
...   aspect_objects=(Axis.IMUM_COELI, Body.SUN, Axis.MIDHEAVEN))
>>> [value.value for value in with_axes.aspect_participants()]
['sun', 'midheaven', 'imum_coeli']
```

Requested bodies/nodes keep their original order; selected axes follow in
ASC/MC/DSC/IC order, independently of the selection argument's order. Axes can
also be the only aspect participants, but `objects` must still contain at least
one body/node. See [axis geometry and pairing](aspects.md#select-axes-explicitly).

The defining enums and API contracts are generated in the [reference](reference.md).
Actual astronomy models, versions, time scales, and effective calculation
settings belong to the chart result; they are not invented here to complete a
metadata record. The [chart guide](chart.md) shows how a request becomes that
result, and the [knowledge guide](knowledge.md) covers queries that need no
chart at all.
