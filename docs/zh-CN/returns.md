# 行星返照

[English](../en/returns.md) · [时刻盘](moments.md) · [API](reference.md)

用 `return_hits` 在显式 UTC 区间内，查找十个 `Body` 身份中任一星体在本命 TT 之后
到达其已存本命黄经的时刻。它返回 `TransitHits`，保存搜索溯源及保留的本命后命中。
再选择事件，用 `moment_chart` 建盘。本页示例按顺序连续执行。

## 搜索区间内全部返照

<!-- usage: returns.search -->

本命盘须保存所选星体。这个合成样例保存太阳、月亮和水星，再搜索 2024 年 1 月至 3 月：
月亮有三次返照，太阳与水星各一次：

```{doctest}
>>> from datetime import UTC, date, datetime, time, timedelta
>>> from astrology import (
...     BirthRecord, Body, ChartConfig, FixedOffset, HouseSystem, Location,
...     moment_chart, natal_chart, prepare_natal_input, return_hits,
... )
>>> birthplace = Location(0, 0)
>>> config = ChartConfig(
...     HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON, Body.MERCURY), ()
... )
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
>>> mercury = return_hits(natal, Body.MERCURY, start_utc=start, end_utc=end)
>>> len(mercury.hits)
1
```

<!-- /usage: returns.search -->

给定区间为 `[start_utc, end_utc)`，转为 TT 后判断事件归属。全部保留命中按原始 TT
排序。provider 接纳的顺行、逆行及相切事件都会保留；逆行造成的短期再次穿越也是返照，
不要求等待完整公转周期。区间内没有本命后的返照时，`hits == ()`。不推断生日、公历月、
最近返照窗口或完整周期。按一个公历年搜索时，可能在年初与年末附近各找到一次日返照；
闰日出生也无需替代周年日期。

参考值是所选星体**已存的本命地心视热带黄经**，与移动星体在其自身日期的黄经比较，
沿用[精确行运约定](transits.md#选择目标与相位)。`return_hits` 先进行一次同星体合相查询，
再只保留原始 `jde_tt` 严格晚于 `natal.times.jde_tt` 的命中：

```{doctest}
>>> from astrology import MajorAspect, transit_hits
>>> explicit = transit_hits(
...     natal, start_utc=start, end_utc=end, moving_objects=(Body.MOON,),
...     natal_objects=(Body.MOON,), aspects=(MajorAspect.CONJUNCTION,),
... )
>>> events.hits == tuple(
...     hit for hit in explicit.hits if hit.jde_tt > natal.times.jde_tt
... )
True
```

本命前及恰好位于本命 TT 的命中不计入。不同的 provider 事件不按时间容差合并，
所以包含本命时刻的区间可能保留紧邻本命、稍晚于本命 TT 的数值根；不希望保留该事件时，
请选择之后所关心的返照附近区间。结果其余部分仍保存原盘、给定 UTC 与转换后 TT 区间、
所选星体、实际模型、有效域及版本。

(return-tables-zh-cn)=
## 读取 UTC 并输出事件表

用 `transit_hit_utc` 把保留命中读成带时区的 UTC `datetime`，无需地点或建盘。
`format_return_hits` 可输出英文或中文返照表，包含给定 UTC 与转换后 TT 区间、
模型身份及版本：

```{doctest}
>>> from astrology import format_return_hits, load_catalog, transit_hit_utc
>>> catalog = load_catalog()
>>> transit_hit_utc(mercury.hits[0]).isoformat(timespec="seconds")
'2024-03-01T02:18:31+00:00'
>>> print(format_return_hits(mercury, catalog))
Planetary returns
Supplied UTC interval [start, end): [2024-01-01T00:00:00+00:00, 2024-04-01T00:00:00+00:00)
Converted TT interval [start, end): [2460310.500800741, 2460401.500800741)
Event models: Mercury [mercury]: position_source/3
astrology / celestial-calendar versions: 0.5.0 / 1.1.1
<BLANKLINE>
UTC | Returning body | Direction | JDE(TT)
2024-03-01T02:18:31+00:00 | Mercury [mercury] | increasing | 2460370.5969953192
>>> print(format_return_hits(mercury, catalog, language="zh-CN"))
行星返照
给定 UTC 区间 [start, end): [2024-01-01T00:00:00+00:00, 2024-04-01T00:00:00+00:00)
转换后 TT 区间 [start, end): [2460310.500800741, 2460401.500800741)
事件模型: 水星 [mercury]: position_source/3
astrology / celestial-calendar 版本: 0.5.0 / 1.1.1
<BLANKLINE>
UTC | 返照星体 | 方向 | JDE(TT)
2024-03-01T02:18:31+00:00 | 水星 [mercury] | 黄经增大 | 2460370.5969953192
```

先转换为微秒精度的 `datetime`，再截断到秒显示。原始 TT 仍是区间归属、排序和分类依据；
闰秒内部的 UTC 显示可能出现异常顺序。显示错误、转换副作用及空表行为见
{ref}`事件 UTC 与表格 <event-display-zh-cn>`。

同一格式化函数也能输出年度日返照表。在这个闰日样例中：

```{doctest}
>>> print(format_return_hits(solar, catalog, language="zh-CN").splitlines()[-1])
2024-02-29T07:39:12+00:00 | 太阳 [sun] | 黄经增大 | 2460369.819691605
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
区间、事件模型、版本及每次本命后的命中。`returned` 保存地点、请求与有效排盘配置、
来源记录及原始事件 TT，后者与归一后的 UTC、导出的 `ChartTimes` 分开。来源 TT 不要求
等于排盘计算导出的 TT，见[时刻转换](moments.md#从保留的精确命中建盘)。

## 阅读或比较返照盘

结果是普通的 `MomentChart`，没有虚构的出生记录，已有命盘消费者可直接使用。
本例中，返照月亮落入本命盘第八宫：

```{doctest}
>>> from astrology import (
...     AspectRule, HouseRulers, chart_dispositors, chart_sign_distribution,
...     cross_chart_aspects, cross_chart_house_overlays, format_chart,
...     transit_aspects,
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
>>> overlays.placements[0].identity is Body.MOON
True
>>> overlays.placements[0].house
8
>>> len(transit_aspects(returned, natal, rules,
...     moving_objects=(Body.MOON,), natal_objects=(Body.MOON,)).hits)
1
>>> len(HouseRulers(returned).houses)
12
>>> chart_dispositors(returned, objects=(Body.MOON,)).chart is returned
True
>>> chart_sign_distribution(returned, objects=(Body.MOON,)).total
1
>>> format_chart(returned, catalog).splitlines()[0]
'Tropical geocentric moment chart'
```

静态双盘相位与固定时刻行运的运动语义不同，见[时刻盘比较](moments.md#比较移动对象与本命盘)。
这些调用提供几何与文本，不提供返照解读。

## 错误与来源

- `natal` 须为 `NatalChart`，不能是 `MomentChart`；`body` 须为 `Body`。
  类型不符抛 `TypeError`。本命盘缺少所选星体时，以返照接口的措辞抛 `ValueError`。
- 有时区端点、现代 UTC、最长区间、模型域及计算失败沿用
  [行运搜索](transits.md#限制与失败)。其中 `TransitDomainError` 保留上游拒绝，不转为空结果。
- 找到事件不保证能建盘。缺地点抛 `TypeError`，宫位几何不可用抛 `ChartDomainError`，
  不启用替代宫制。事件转换及排盘计算的有效域沿用[时刻盘输入约定](moments.md#按给定时刻建盘)。
- UTC 显示可抛 `EventDisplayError`，包括转换得到上游 1972 年前 UT1 替代值的情形；
  保留的原始 TT 不受影响。

[目录](catalog.md)中的 `entry.solar_lunar_returns` 保留稳定身份，现覆盖十体项目约定。
条目记录一般返照定义、原文短引及分开的中文翻译、地点实践、本命后过滤和根邻事件的限度；
不定义交点返照，也不提供十套不同的解读传统。不用命盘或原生天文也能读取：

```{doctest}
>>> entry = catalog.entry("entry.solar_lunar_returns")
>>> entry.prerequisite_status.value, entry.output_eligibility.value, entry.chart_applicability
('complete', 'reference_only', 'not_assessed')
>>> len(catalog.citations(entry.identifier))
5
```

`complete` 表示条目已写明所需前提，`reference_only` 表示仅供参考，`not_assessed` 表示
查询条目不判断某张命盘是否满足这些前提。这三种状态的区别见[知识状态说明](knowledge.md#状态需要分开表达)。
