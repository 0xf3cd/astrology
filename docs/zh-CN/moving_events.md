# 移动对象对事件

[English](../en/moving_events.md) · [API](reference.md#移动对象对事件) · [精确固定源行运](transits.md)

用 `moving_aspect_events` 搜索两个移动天体或具名月球交点之间的精确主要相位。
搜索不需要本命盘或地点。

## 查新月与满月

<!-- usage: moving.events -->

两侧黄经都在变化。下例将月亮放在第一侧、太阳放在第二侧，相对角度与速率因此为
**太阳减月亮**：

```{doctest}
>>> from datetime import UTC, datetime
>>> from astrology import (Body, MajorAspect, moving_aspect_events, moving_hit_utc,
...     format_moving_events, load_catalog)
>>> events = moving_aspect_events(
...     pairs=((Body.MOON, Body.SUN),),
...     aspects=(MajorAspect.CONJUNCTION, MajorAspect.OPPOSITION),
...     start_utc=datetime(2024, 1, 1, tzinfo=UTC),
...     end_utc=datetime(2024, 2, 1, tzinfo=UTC))
>>> [(moving_hit_utc(hit).isoformat(timespec="seconds"), hit.aspect.value,
...   hit.direction.value) for hit in events.hits]
[('2024-01-11T11:57:27+00:00', 'conjunction', 'decreasing'), ('2024-01-25T17:54:00+00:00', 'opposition', 'decreasing')]
>>> table = format_moving_events(events, load_catalog(), language="zh-CN")
>>> print(table.splitlines()[0])
精确移动对象对事件
>>> for row in table.splitlines():
...     if row.startswith(("UTC |", "2024-")):
...         print(" | ".join(row.split(" | ")[:6]))
UTC | 第一侧移动对象 | 第二侧移动对象 | 相位 | 分支 | 相对方向
2024-01-11T11:57:27+00:00 | 月亮 [moon] | 太阳 [sun] | 合相 | 0°00'00" | 角距减小
2024-01-25T17:54:00+00:00 | 月亮 [moon] | 太阳 [sun] | 对分相 | +180°00'00" | 角距减小
```

<!-- /usage: moving.events -->

完整表还包含原始 TT、相对速率、查询区间、两侧模型及计算版本。使用 `language="en"`
可改为给定目录中的英文词汇。UTC 沿用既有{ref}`事件显示转换 <event-display-zh-cn>`，
包括固定闰秒偏移、1972 限制、微秒舍入及表格整秒显示。显示精度不改变事件的区间归属。

USNO 将精确新月与满月分别定义为月亮减太阳的视黄经差 0°、180°。交换顺序后，
0° 仍为 0°，-180° 按约定记为 180°，因此这两个目标不变。示例中的 `(Moon, Sun)` 对象对
使用反向的太阳减月亮角距。
[知识条目](catalog.md) `entry.moving_aspect_events` 将该来源与项目的模型及搜索约定分开记录。

## 读取几何

`pairs` 是非空的有序 `(第一侧, 第二侧)` 身份序列，`aspects` 须显式给出非空的
`MajorAspect` 选择。不允许重复的有序对象对、重复相位或自身配对；逆序属于另一项请求。
十个 `Body` 及四个具名 `LunarNode` 均可在来源接纳的范围内查询；四轴不是移动事件来源。
其他主要相位使用 `MajorAspect.SEXTILE`、`MajorAspect.SQUARE` 或 `MajorAspect.TRINE`。
每个身份都使用一个计算模型，各有支持的 TT 时段及最长搜索区间。模型名及这些限制保留在
`events.sources` 中，见[事件来源记录](transits.md#读取和保留结果)。

| 结果 | 含义 |
|---|---|
| `hit.first_object`、`hit.second_object` | 两侧均为移动角色 |
| `hit.branch_deg` | 第二侧减第一侧的目标：合相及对分相各一支，其他主要相位各两支 |
| `hit.signed_difference_deg` | 未改动的上游第一侧减第二侧角度 |
| `hit.separation_deg`、`hit.deviation_deg` | 第二侧减第一侧的规范角度，及其相对分支的带符号偏差，归入 (-180, 180] |
| `hit.first_longitude_deg`、`hit.second_longitude_deg` | 同一事件 TT 的原始地心视热带黄经，以度计 |
| `hit.first_rate_deg_per_tt_day`、`hit.second_rate_deg_per_tt_day` | 原始速率；`relative_rate_deg_per_tt_day` 为第二侧减第一侧 |
| `hit.direction` | `RelativeDirection`：角距增大、减小或相切，不是任一天体自身的顺逆行 |
| `events.sources` | 每个不同请求身份一个 `TransitSource`，按首次出现排序 |

交换顺序后，对分相仍记为 180°。相切是角距到达请求分支却没有穿过它；
报告的相对速率不一定恰为零。命中按原始 TT、请求对象对顺序、相位角及分支排序。
两个请求对象对在同一 TT 命中时，各自保留一个命中；来源给出的相近时刻也不按容差合并。
方向沿第二侧减第一侧的连续黄经差判断，越过周界时不折回，也不按规范角距的绝对值判断。

## 空结果与失败

UTC 端点须为有时区的内建 datetime，且归一后不早于 1972-01-01 UTC。
搜索使用转换后的**左闭右开 TT 区间**，最长 3660 TT 日，并受两侧事件来源求值域限制。

恒定不等（关系始终不成立）是合法空结果。例如，平升交点与平降交点不会合相：

```{doctest}
>>> from astrology import LunarNode
>>> empty = moving_aspect_events(
...     pairs=((LunarNode.MEAN_ASCENDING, LunarNode.MEAN_DESCENDING),),
...     aspects=(MajorAspect.CONJUNCTION,),
...     start_utc=events.start_utc, end_utc=events.end_utc)
>>> empty.hits
()
>>> print(format_moving_events(empty, load_catalog(), language="zh-CN").splitlines()[-1])
给定区间内没有精确移动对象对事件
```

平升交点和平降交点持续成立的对分相会被拒绝，不会表示为无限事件列表。类型无效抛 `TypeError`；
选择、自身配对或端点顺序无效抛 `ValueError`，早于 1972 年的 UTC 抛 `HistoricalTimeError`。
域或区间拒绝抛出 `MovingEventDomainError`，它是 `ValueError` 的子类；
可用时保留操作、两侧身份及 TT 端点，还保留上游原始文本与异常因果链。
原生 `CelestialError` 直接向外抛出。任一对象对或分支失败即整次失败，包括已有其他成功结果的情况；
失败不会变成空结果或部分列表。

导入包、查询知识、构造给定结果及格式化空结果不初始化原生库。搜索延迟初始化原生天文；
读取或显示非空命中仅初始化时刻转换。

## 为事件建盘

计算宫位时才提供地点与配置：

```{doctest}
>>> from astrology import ChartConfig, HouseSystem, Location, moment_chart
>>> hit = events.hits[0]
>>> chart = moment_chart(hit, Location(0, 0),
...     ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ()))
>>> chart.moment.source_jde_tt == hit.jde_tt
True
>>> chart.moment.utc == moving_hit_utc(hit)
True
```

[时刻盘求值域](moments.md#从保留的精确命中建盘) 与事件求值域分开。建盘失败不使保留的事件失效；
来源事件 TT 与命盘导出的计算 TT 也保持区分。

## 搜索耗时

在一次测量中，全年的水日合相查询约需 13 秒，尽管只返回六次命中。
成本不与命中数成正比；该测量不保证响应时间。

独立数值夹具及重生成方法见[贡献指南](contributing.md#正确性)。
