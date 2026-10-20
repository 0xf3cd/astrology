# Public API reference

[简体中文](../zh-CN/reference.md) · [Documentation](index.md)

These development APIs are rendered from their defining modules. Public summaries
and contracts are bilingual; both language views use the same definitions.
See [birth inputs](birth.md), [requested configuration](configuration.md) and
[the chart guide](chart.md) for executed input examples. The
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
   :members: HouseSystem, Body, NodeDefinition, LunarNode, MajorAspect, AspectRule, ChartConfig
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

## Independent knowledge

Field roles are explained in the
[record guide](knowledge.md#records-and-ownership).

```{eval-rst}
.. automodule:: astrology.knowledge
   :members:
   :imported-members:
   :undoc-members:
   :member-order: bysource
```
