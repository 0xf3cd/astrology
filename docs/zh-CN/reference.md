# 公开 API 参考

[English](../en/reference.md) · [文档](index.md)

这些 API 从定义模块渲染。公开概述与合同保留双语；两种语言视图使用同一份定义。
已执行的例子、校验行为和支持范围见[出生输入](birth.md)、[请求配置](configuration.md)、
[排盘指南](chart.md)、[相位指南](aspects.md)及[命盘结果](records.md)。独立查询见[知识指南](knowledge.md)。

## 出生记录与时刻解析

```{eval-rst}
.. automodule:: astrology.birth
   :members: MissingBirthDataError, AmbiguousBirthTimeError, NonexistentBirthTimeError, HistoricalTimeError, TimePrecision, Location, IanaTimezone, FixedOffset, BirthRecord, ResolvedBirth, resolve_birth_time, prepare_natal_input
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 请求配置

对象身份定义在 `astrology.objects`；原来从 `astrology.config` 导入的 `Body`、
`LunarNode` 和 `NodeDefinition` 仍是同一枚举类的别名。也可从 `astrology` 导入 `Axis`。

```{eval-rst}
.. automodule:: astrology.objects
   :members: Body, NodeDefinition, LunarNode, Axis, AstronomicalObject, ChartObject
   :undoc-members:
   :member-order: bysource
   :no-index:
```

```{eval-rst}
.. automodule:: astrology.config
   :members: HouseSystem, MajorAspect, OrbCombination, ObjectOrb, AspectRule, ChartConfig
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

## 命盘文本

本命盘的输出方法见[完整结果与文本例子](records.md)，双盘相位和落宫的输出方法见[输出比较文本](cross_aspects.md#输出比较文本)。

```{eval-rst}
.. automodule:: astrology.text
   :members: format_chart, format_sign_distribution, format_lunar_phase, format_house_rulers, format_house_overlays, format_cross_aspects
   :no-index:
```

## 星座归属

```{eval-rst}
.. automodule:: astrology.zodiac
   :members: Sign, AshmandSignGroup, Element, Modality, ashmand_sign_group, element_of, modality_of, sign_of, sign_degree, truncate_display
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

## 相位

```{eval-rst}
.. automodule:: astrology.aspects
   :members: AspectMotion, AspectObject, AspectHit, aspect_angle, find_aspects
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 静态双盘交叉相位

用法及静态相位的含义见[双盘相位与落宫](cross_aspects.md)。

```{eval-rst}
.. automodule:: astrology.cross_aspects
   :members: CrossAspectHit, CrossChartAspects, cross_chart_aspects
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 双盘落宫

计算方法见[双盘落宫示例](cross_aspects.md#查询对象落入另一张盘的哪一宫)，文本输出见[比较文本示例](cross_aspects.md#输出比较文本)。

```{eval-rst}
.. automodule:: astrology.house_overlays
   :members: HouseOverlay, CrossChartHouseOverlays, cross_chart_house_overlays
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 命盘摘要与月相

显式选定对象的统计、来源约定及错误行为见[摘要指南](summaries.md)。
宫主星记录见[尊贵指南](dignities.md)。

```{eval-rst}
.. automodule:: astrology.lunar_phase
   :members: LunationType, LunarPhaseResult, lunar_phase
   :undoc-members:
   :member-order: bysource
   :no-index:
```

```{eval-rst}
.. automodule:: astrology.summaries
   :members: SignDistribution, sign_distribution, chart_sign_distribution, natal_lunar_phase, HouseRuler, HouseRulers
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 传统守护与本质尊贵

具名来源、同时命中和缺失落点见[尊贵指南](dignities.md)。

```{eval-rst}
.. automodule:: astrology.dignities
   :members: DignityStatus, sign_ruler, essential_dignities
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## SVG 图形

从给定结果生成轮盘与矩阵，见 [SVG 输出](svg.md)。

```{eval-rst}
.. automodule:: astrology.svg
   :members: render_natal_wheel, render_natal_matrix, render_cross_matrix
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 独立知识查询

字段职责见[知识记录字段](knowledge.md#记录与归属)。

```{eval-rst}
.. automodule:: astrology.knowledge
   :members:
   :imported-members:
   :undoc-members:
   :member-order: bysource
   :no-index:
```
