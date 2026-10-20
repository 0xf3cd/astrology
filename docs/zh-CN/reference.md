# 公开 API 参考

[English](../en/reference.md) · [文档](index.md)

这些开发期 API 从定义模块渲染。公开概述与合同保留双语；两种语言视图使用同一份定义。
已执行的例子、校验行为和支持范围见[出生输入](birth.md)、[请求配置](configuration.md)
与[排盘指南](chart.md)。独立查询见[知识指南](knowledge.md)。

## 出生记录与时刻解析

```{eval-rst}
.. automodule:: astrology.birth
   :members: MissingBirthDataError, AmbiguousBirthTimeError, NonexistentBirthTimeError, HistoricalTimeError, TimePrecision, Location, IanaTimezone, FixedOffset, BirthRecord, ResolvedBirth, resolve_birth_time, prepare_natal_input
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 请求配置

```{eval-rst}
.. automodule:: astrology.config
   :members: HouseSystem, Body, NodeDefinition, LunarNode, MajorAspect, OrbCombination, ObjectOrb, AspectRule, ChartConfig
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 本命盘组合

```{eval-rst}
.. automodule:: astrology.chart
   :members: ChartDomainError, ChartTimes, EclipticPosition, ChartHouses, Placement, EffectiveConfiguration, ChartProvenance, NatalChart, natal_chart
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 星座归属

```{eval-rst}
.. automodule:: astrology.zodiac
   :members: Sign, sign_of, sign_degree, truncate_display
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 落宫

```{eval-rst}
.. automodule:: astrology.houses
   :members: house_of
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 独立知识查询

字段职责见[记录指南](knowledge.md#记录与归属)。

```{eval-rst}
.. automodule:: astrology.knowledge
   :members:
   :imported-members:
   :undoc-members:
   :member-order: bysource
   :no-index:
```
