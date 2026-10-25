# Public API reference

[简体中文](../zh-CN/reference.md) · [Documentation](index.md)

These APIs are rendered from their defining modules. Public summaries
and contracts are bilingual; both language views use the same definitions.
See [birth inputs](birth.md), [requested configuration](configuration.md),
[charts](chart.md), [aspects](aspects.md) and [chart results](records.md) for executed examples. The
[knowledge guide](knowledge.md) covers chart-independent queries.

## Birth records and resolution

```{eval-rst}
.. automodule:: astrology.birth
   :members: MissingBirthDataError, AmbiguousBirthTimeError, NonexistentBirthTimeError, HistoricalTimeError, TimePrecision, Location, IanaTimezone, FixedOffset, BirthRecord, ResolvedBirth, resolve_birth_time, prepare_natal_input
   :undoc-members:
   :member-order: bysource
```

## Requested configuration

```{eval-rst}
.. automodule:: astrology.config
   :members: HouseSystem, Body, NodeDefinition, LunarNode, MajorAspect, OrbCombination, ObjectOrb, AspectRule, ChartConfig
   :undoc-members:
   :member-order: bysource
```

## Natal chart composition

```{eval-rst}
.. automodule:: astrology.chart
   :members: ChartDomainError, ChartTimes, EclipticPosition, ChartHouses, Placement, EffectiveConfiguration, ChartProvenance, NatalChart, natal_chart
   :undoc-members:
   :member-order: bysource
```

## Chart text

See the [complete result and text example](records.md).

```{eval-rst}
.. automodule:: astrology.text
   :members: format_chart
```

## Zodiac classification

```{eval-rst}
.. automodule:: astrology.zodiac
   :members: Sign, sign_of, sign_degree, truncate_display
   :undoc-members:
   :member-order: bysource
```

## House placement

```{eval-rst}
.. automodule:: astrology.houses
   :members: house_of
   :undoc-members:
   :member-order: bysource
```

## Aspects

```{eval-rst}
.. automodule:: astrology.aspects
   :members: AspectMotion, AspectObject, AspectHit, aspect_angle, find_aspects
   :undoc-members:
   :member-order: bysource
```

## Static cross-chart aspects

See the [two-chart example and static contract](cross_aspects.md).

```{eval-rst}
.. automodule:: astrology.cross_aspects
   :members: CrossAspectHit, CrossChartAspects, cross_chart_aspects
   :undoc-members:
   :member-order: bysource
```

## Independent knowledge

Field roles are explained in the
[knowledge record fields](knowledge.md#records-and-ownership).

```{eval-rst}
.. automodule:: astrology.knowledge
   :members:
   :imported-members:
   :undoc-members:
   :member-order: bysource
```
