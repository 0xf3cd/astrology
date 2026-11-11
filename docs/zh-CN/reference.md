# 公开 API 参考

[English](../en/reference.md) · [文档](index.md)

这些 API 从定义模块渲染。公开概述与合同保留双语；两种语言视图使用同一份定义。
已执行的例子、校验行为和支持范围见[出生输入](birth.md)、[请求配置](configuration.md)、
[排盘指南](chart.md)、[相位指南](aspects.md)及[命盘结果](records.md)。独立查询见[知识指南](knowledge.md)。

计算边界：[初始化与 I/O](architecture.md#副作用边界)、[构造校验](architecture.md#可复现性)及
[宫制失败](architecture.md#组合与失败)。

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

## 本命盘与时刻盘组合

```{eval-rst}
.. automodule:: astrology.chart
   :members: ChartDomainError, ChartTimes, EclipticPosition, ChartHouses, Placement, EffectiveConfiguration, ChartProvenance, NatalChart, MomentInput, MomentChart, Chart, natal_chart, moment_chart
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 命盘文本

本命盘的输出方法见[完整结果与文本例子](records.md)，双盘相位和落宫的输出方法见[输出比较文本](cross_aspects.md#输出比较文本)。

```{eval-rst}
.. automodule:: astrology.text
   :members: format_chart, format_sign_distribution, format_lunar_phase, format_house_rulers, format_house_overlays, format_cross_aspects, format_transit_aspects
   :no-index:
```

## 星座归属

`Modality.FIXED` 与 `AshmandSignGroup.FIXED` 的字符串值都是 `"fixed"`，按 `StrEnum`
语义比较相等，hash 也相同。要在同一 Python 映射中保留二者，请用 `(type(member), member.value)`
作键，或使用各自带类别前缀的目录 ID。两套分类及其历史含义仍有区别。

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

## 固定时刻行运相位

固定时刻比较及双语输出见[时刻盘](moments.md)。

```{eval-rst}
.. automodule:: astrology.transit_aspects
   :members: TransitAspectHit, TransitAspects, transit_aspects
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 精确行运命中

UTC 区间搜索及结果字段见[精确行运命中](transits.md)。

```{eval-rst}
.. automodule:: astrology.transits
   :members: TransitDirection, TransitDomainError, TransitSource, TransitHit, TransitHits, transit_hits
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 日返照与月返照

事件搜索、显式地点及命盘消费见[返照指南](returns.md)。

```{eval-rst}
.. automodule:: astrology.returns
   :members: return_hits
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
   :members: SignDistribution, sign_distribution, chart_sign_distribution, natal_lunar_phase
   :undoc-members:
   :member-order: bysource
   :no-index:
```

## 传统守护与本质尊贵

星座查询、宫主星及定位星链见[尊贵指南](dignities.md)。

```{eval-rst}
.. automodule:: astrology.dignities
   :members: DignityStatus, sign_ruler, essential_dignities, HouseRuler, HouseRulers, Dispositors, chart_dispositors
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
