# 日返照与月返照

[English](../en/returns.md) · [时刻盘](moments.md) · [API](reference.md)

用 `return_hits` 查找显式 UTC 区间内太阳或月亮到达其已存本命黄经的时刻。它返回
`TransitHits`，与精确的同星体合相搜索结果相同。再选择事件，用 `moment_chart` 建盘。
本页示例按顺序连续执行。

## 搜索区间内全部返照

<!-- usage: returns.search -->

本命盘须保存所选日月星体。这个合成样例保存两者，再搜索 2024 年 1 月至 3 月的三次月返照：

```{doctest}
>>> from datetime import UTC, date, datetime, time, timedelta
>>> from astrology import (
...     BirthRecord, Body, ChartConfig, FixedOffset, HouseSystem, Location,
...     moment_chart, natal_chart, prepare_natal_input, return_hits,
... )
>>> birthplace = Location(0, 0)
>>> config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ())
>>> record = BirthRecord(date(2000, 2, 29), time(12), FixedOffset(timedelta(0)), birthplace)
>>> natal = natal_chart(prepare_natal_input(record), config)
>>> start = datetime(2024, 1, 1, tzinfo=UTC)
>>> end = datetime(2024, 4, 1, tzinfo=UTC)
>>> events = return_hits(natal, Body.MOON, start_utc=start, end_utc=end)
>>> type(events).__name__, len(events.hits)
('TransitHits', 3)
>>> events.chart is natal
True
>>> events.moving_objects == events.natal_objects == (Body.MOON,)
True
>>> solar = return_hits(natal, Body.SUN, start_utc=start, end_utc=end)
>>> len(solar.hits)
1
```

<!-- /usage: returns.search -->

区间为 `[start_utc, end_utc)`：起点命中纳入，终点命中排除。按时间顺序返回全部命中；
没有返照时，`hits == ()`。区间由调用方选择，不推断生日、公历月或最近返照窗口。
在上面的区间内，闰日样例只有一次日返照。若出生时刻接近年界，按一个公历年搜索时，可能在该年
开头与结尾附近各找到一次日返照，两次都保留。闰日出生无需指定替代周年日期。

参考值是所选星体**已存的本命地心视热带黄经**，与移动星体在其自身日期的黄经比较，
沿用[精确行运约定](transits.md#选择目标与相位)。`return_hits` 只进行一次同星体合相查询，
原样返回完整结果：

```{doctest}
>>> from astrology import MajorAspect, transit_hits
>>> explicit = transit_hits(
...     natal, start_utc=start, end_utc=end, moving_objects=(Body.MOON,),
...     natal_objects=(Body.MOON,), aspects=(MajorAspect.CONJUNCTION,),
... )
>>> events == explicit
True
```

## 选择事件并显式给出地点

<!-- usage: returns.chart -->

`events.hits` 中的时刻是 JDE(TT)，不是 UTC 钟表读数。直接将命中交给 `moment_chart`；
它在建盘入口转换时刻，并将原值保存在 `moment.source_jde_tt`。

```{doctest}
>>> hit = events.hits[0]
>>> site = Location(40, 100)
>>> returned = moment_chart(hit, site, config)
>>> type(returned).__name__
'MomentChart'
>>> returned.moment.source_jde_tt == hit.jde_tt
True
>>> returned.moment.location == site
True
>>> at_birthplace = moment_chart(hit, birthplace, config)
>>> returned.positions == at_birthplace.positions
True
>>> returned.times == at_birthplace.times
True
>>> returned.houses == at_birthplace.houses
False
```

<!-- /usage: returns.chart -->

换地点不改变地心事件及星位，但会改变当地四轴与宫位。要用出生地，就像上例一样显式传入；
不推断当前位置。排盘配置也须显式提供，可以与本命配置不同，也可以不含返照星体；
搜索结果仍保存所选星体及其已存本命黄经。不暗加对象或替换宫制。

要保存完整计算，须**同时保留 `events` 与 `returned`**。`events` 保存本命盘、所选星体、
区间、事件模型、版本及每次命中。`returned` 保存地点、请求与有效排盘配置、来源记录及原始
事件 TT，后者与归一后的 UTC、导出的 `ChartTimes` 分开。来源 TT 不要求等于排盘计算导出的 TT，
见[时刻转换](moments.md#从保留的精确命中建盘)。

## 阅读或比较返照盘

结果是普通的 `MomentChart`，没有虚构的出生记录，已有命盘消费者可直接使用：

```{doctest}
>>> from astrology import (
...     AspectRule, HouseRulers, chart_dispositors, chart_sign_distribution,
...     cross_chart_aspects, cross_chart_house_overlays, format_chart,
...     load_catalog, transit_aspects,
... )
>>> rules = (AspectRule(MajorAspect.CONJUNCTION, 1),)
>>> comparison = cross_chart_aspects(
...     returned, natal, rules, left_objects=(Body.MOON,), right_objects=(Body.MOON,),
... )
>>> len(comparison.hits)
1
>>> overlays = cross_chart_house_overlays(
...     returned, natal, left_objects=(Body.MOON,), right_objects=(),
... )
>>> len(overlays.placements)
1
>>> len(transit_aspects(returned, natal, rules,
...     moving_objects=(Body.MOON,), natal_objects=(Body.MOON,)).hits)
1
>>> len(HouseRulers(returned).houses)
12
>>> chart_dispositors(returned, objects=(Body.MOON,)).chart is returned
True
>>> chart_sign_distribution(returned, objects=(Body.MOON,)).total
1
>>> catalog = load_catalog()
>>> format_chart(returned, catalog).splitlines()[0]
'Tropical geocentric moment chart'
```

静态双盘相位与固定时刻行运的运动语义不同，见[时刻盘比较](moments.md#比较移动对象与本命盘)。
这些调用提供几何与文本，不提供返照解读。

## 错误与来源

- `natal` 须为 `NatalChart`，不能是 `MomentChart`；`body` 须为 `Body`。
  类型不符抛 `TypeError`；`SUN`、`MOON` 以外的星体抛 `ValueError`，本命盘缺少所选星体也抛
  `ValueError`。
- 有时区端点、现代 UTC、最长区间、模型域及计算失败沿用
  [行运搜索](transits.md#限制与失败)。其中 `TransitDomainError` 保留上游拒绝，不转为空结果。
- 找到事件不保证能建盘。缺地点抛 `TypeError`，宫位几何不可用抛 `ChartDomainError`，
  不启用替代宫制。事件转换及排盘计算的有效域沿用[时刻盘输入约定](moments.md#按给定时刻建盘)。

[目录](catalog.md)中的 `entry.solar_lunar_returns` 记录定义、原文短引及分开的中文翻译、
地点实践与项目约定。不用命盘或原生天文也能读取：

```{doctest}
>>> entry = catalog.entry("entry.solar_lunar_returns")
>>> entry.prerequisite_status.value, entry.output_eligibility.value, entry.chart_applicability
('complete', 'reference_only', 'not_assessed')
>>> len(catalog.citations(entry.identifier))
5
```

`complete` 表示条目已写明所需前提，`reference_only` 表示仅供参考，`not_assessed` 表示
查询条目不判断某张命盘是否满足这些前提。这三种状态的区别见[知识状态说明](knowledge.md#状态需要分开表达)。
