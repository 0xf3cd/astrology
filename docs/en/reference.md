# Public API reference

[简体中文](../zh-CN/reference.md) · [Documentation](index.md)

These development APIs are rendered from their defining modules. Public summaries
and contracts are bilingual; both language views use the same definitions.
See [birth inputs](birth.md) and [requested configuration](configuration.md) for
executed input examples. The [knowledge guide](knowledge.md) covers chart-independent
queries. No chart-calculation API is provided yet.

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

## Independent knowledge

```{eval-rst}
.. automodule:: astrology.knowledge
   :members:
   :imported-members:
   :undoc-members:
   :member-order: bysource
```
