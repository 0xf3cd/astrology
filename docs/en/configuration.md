# Requested chart configuration

[简体中文](../zh-CN/configuration.md) · [Documentation](index.md) · [API reference](reference.md)

`ChartConfig` specifies the house system, bodies or nodes to return, and aspect rules.
It cannot be changed after construction. It stores a request without calculating
a chart; the [chart result](records.md) records the models and other calculation details.
Only the tropical zodiac (`tropical`) and geocentric positions (`geocentric`) are supported.
Supply the house system, objects and aspect rules explicitly. The object selection
cannot be empty; pass `aspects=()` to skip aspects. There is no default house system or orb.

## Choose the house system and output objects

<!-- usage: configuration.objects -->

For example, this request uses Whole Sign houses and asks for positions of the
Sun, Moon and mean ascending node. `house_system` selects the house system,
`objects` selects the bodies or nodes to return, and `aspects=()` skips aspects:

```{doctest}
>>> from astrology import Body, ChartConfig, HouseSystem, LunarNode
>>> objects = [Body.SUN, Body.MOON, LunarNode.MEAN_ASCENDING]
>>> request = ChartConfig(
...   house_system=HouseSystem.WHOLE_SIGN,
...   objects=objects,
...   aspects=(),
... )
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

`HouseSystem` supports Whole Sign, Equal and Placidus. If the selected system cannot
be calculated at the given time or location, calculation fails without switching
systems; see the [chart guide](chart.md) for the supported range.
`Body` includes ten physical bodies: the Sun, Moon, and Mercury through Pluto.
Lunar nodes are mathematical points, selected with `LunarNode`. It offers mean and
Meeus five-term true definitions, each with ascending and descending nodes.
The definition selects which node to calculate, not an accuracy level. The two
definitions cannot substitute for each other, but you can select both in one request.
The chart result records the astronomical models used.

Object and rule sequences are copied into tuples, preserving order. Source lists
can change without changing the request. Duplicate objects or duplicate aspect
identities are rejected rather than silently merged. Enum value strings such as
`"sun"` are not enum instances and are not implicitly converted.

<!-- /usage: configuration.objects -->

## Request aspects

`MajorAspect` names conjunction, sextile, square, trine, and opposition.
Use `AspectRule` to give an aspect an orb in degrees, `orb_degrees`, which must be
finite and nonnegative. Configuration does not calculate aspects or choose a
tradition's orbs for you. See the [aspect guide](aspects.md) for the calculation.

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

The zero orb above was chosen for this example; it is not a library default or recommendation.

## Choose who takes part in aspects

<!-- usage: configuration.participants -->

This request asks for Sun and Moon positions, with aspects only between the Sun
and Ascendant:

```{doctest}
>>> from astrology import AspectRule, Axis, Body, ChartConfig, HouseSystem, MajorAspect
>>> with_axes = ChartConfig(
...   HouseSystem.WHOLE_SIGN,
...   objects=(Body.SUN, Body.MOON),
...   aspects=(AspectRule(MajorAspect.SEXTILE, 3),),
...   aspect_objects=(Body.SUN, Axis.ASCENDANT),
... )
>>> [value.value for value in with_axes.aspect_participants()]
['sun', 'ascendant']
>>> [value.value for value in with_axes.objects]
['sun', 'moon']
```

`objects` selects astronomical outputs and accepts only `Body` and `LunarNode`.
`aspect_objects` selects participants from those bodies/nodes and may explicitly
add axes. The Moon above still has a position, but takes part in no aspect. If
`aspect_objects` is omitted, all requested bodies/nodes take part and no axes are added.

Requested bodies/nodes keep their original order; selected axes follow in
Ascendant/Midheaven/Descendant/Imum Coeli (ASC/MC/DSC/IC) order, independently of
the selection argument's order. Axes can
also be the only aspect participants, but `objects` must still contain at least
one body/node. See [axis geometry and pairing](aspects.md#select-axes-explicitly).

<!-- /usage: configuration.participants -->

## Give an object its own orb

<!-- usage: configuration.orbs -->

Use `ObjectOrb` to set an object's orb separately; other objects use the rule's
`orb_degrees`. If any rule uses `ObjectOrb`, you must choose `orb_combination` to
combine the pair's orbs into one limit. Otherwise, leave `orb_combination` out.
You can set a separate orb only for a body, node or axis selected to participate.

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

<!-- /usage: configuration.orbs -->

See the [API reference](reference.md) for enum members, parameters and return values.
For calculated models, versions, time scales and effective settings, read the
[chart result](records.md). For queries without a chart, see [knowledge](knowledge.md).
