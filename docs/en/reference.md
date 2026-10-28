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

Object identities live in `astrology.objects`; existing imports of `Body`,
`LunarNode` and `NodeDefinition` from `astrology.config` remain aliases to the
same enum classes. `Axis` is also available from `astrology`.

```{eval-rst}
.. automodule:: astrology.objects
   :members: Body, NodeDefinition, LunarNode, Axis, AstronomicalObject, ChartObject
   :undoc-members:
   :member-order: bysource
```

```{eval-rst}
.. automodule:: astrology.config
   :members: HouseSystem, MajorAspect, OrbCombination, ObjectOrb, AspectRule, ChartConfig
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
   :members: format_chart, format_sign_distribution, format_lunar_phase, format_house_rulers, format_house_overlays, format_cross_aspects
```

## Zodiac classification

```{eval-rst}
.. automodule:: astrology.zodiac
   :members: Sign, AshmandSignGroup, Element, Modality, ashmand_sign_group, element_of, modality_of, sign_of, sign_degree, truncate_display
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

## Cross-chart house overlays

See [directional placements and text](cross_aspects.md#find-houses-in-the-other-chart).

```{eval-rst}
.. automodule:: astrology.house_overlays
   :members: HouseOverlay, CrossChartHouseOverlays, cross_chart_house_overlays
   :undoc-members:
   :member-order: bysource
```

## Chart summaries and lunar phase

See the [summary guide](summaries.md) for explicit populations, source conventions and errors.
The [dignity guide](dignities.md) covers the house-ruler records.

```{eval-rst}
.. automodule:: astrology.lunar_phase
   :members: LunationType, LunarPhaseResult, lunar_phase
   :undoc-members:
   :member-order: bysource
```

```{eval-rst}
.. automodule:: astrology.summaries
   :members: SignDistribution, sign_distribution, chart_sign_distribution, natal_lunar_phase, HouseRuler, HouseRulers
   :undoc-members:
   :member-order: bysource
```

## Traditional rulership and dignities

See [the dignity guide](dignities.md) for the named source, simultaneous statuses and missing placements.

```{eval-rst}
.. automodule:: astrology.dignities
   :members: DignityStatus, sign_ruler, essential_dignities
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
