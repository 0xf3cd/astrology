# 精确行运命中

[English](../en/transits.md) · [文档](index.md) · [API](reference.md)

`transit_hits` 在 UTC 区间内搜索所选对象与已有本命盘的全部精确相位，返回 `TransitHits`。
结果保留原盘、搜索输入、模型溯源及每次穿越或接触。命中时刻为 JDE(TT)，即 TT 时标的儒略日，
不是 UTC 钟点。

只接纳本命盘及日月的查询，以及选择命中和地点后建盘的用法，见[日月返照](returns.md)。

## 搜索一个区间

固定源盘也可以是 `MomentChart`；`natal_objects` 命名固定参考侧的角色，不是出生输入类型。
两种来源的黄经约定相同，因此 `TransitHits.epoch_policy` 均保留
`fixed_natal_degree_against_moving_of_date_longitude`。真实来源类型及输入仍保存在 `result.chart`。
时刻盘的构造与读取见[时刻盘](moments.md)。

<!-- usage: transits.hits -->

下面用合成出生资料计算一颗已存本命太阳。移动侧只需对象选择和区间，不需要出生地点或宫位。
两端点须为有时区的内建 `datetime`，归一为 UTC 后不早于 1972-01-01。
带本地偏移的值会归一为 UTC；无时区值直接拒绝。

```{doctest}
>>> from datetime import UTC, date, datetime, time, timedelta
>>> from astrology import (
...   BirthRecord, Body, ChartConfig, FixedOffset, HouseSystem, Location,
...   MajorAspect, natal_chart, prepare_natal_input, transit_hits,
... )
>>> record = BirthRecord(date(2000, 4, 10), time(12), FixedOffset(timedelta(0)),
...   Location(0, 0), source={"example": "synthetic"})
>>> chart = natal_chart(prepare_natal_input(record),
...   ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ()))
>>> result = transit_hits(chart,
...   start_utc=datetime(2024, 3, 1, tzinfo=UTC),
...   end_utc=datetime(2024, 6, 1, tzinfo=UTC),
...   moving_objects=(Body.MERCURY,), natal_objects=(Body.SUN,),
...   aspects=(MajorAspect.CONJUNCTION,))
>>> for hit in result.hits:
...   print(f"{hit.moving_object.value} {hit.aspect.value} {hit.natal_object.value} "
...         f"{hit.jde_tt:.5f} {hit.direction.value} {hit.longitude_rate_deg_per_tt_day:+.3f}")
mercury conjunction sun 2460392.23731 increasing +1.208
mercury conjunction sun 2460414.61236 decreasing -0.744
mercury conjunction sun 2460437.45999 increasing +0.812
```

水星三次到达固定的本命太阳度数：黄经递增时一次，逆行时一次，恢复递增后又一次。
速率单位为度/TT 日，直接保留上游事件值。`tangent` 表示到达查询黄经后相切而未穿越，
报告的速率不必恰为零。

<!-- /usage: transits.hits -->

显示普通 UTC 钟点时，可将 `jde_to_utc` 返回的民用字段转为有时区的 `datetime`。
`fraction` 是当天已过时间占 UTC 日的比例：

```{doctest}
>>> from celestial_calendar import jde_to_utc
>>> civil = jde_to_utc(result.hits[0].jde_tt)
>>> displayed = datetime(civil.year, civil.month, civil.day, tzinfo=UTC) + timedelta(days=civil.fraction)
>>> displayed.isoformat(timespec="seconds")
'2024-03-22T17:40:34+00:00'
```

仍应保留原始 `jde_tt` 作为事件时刻；这里只显示到秒，会损失精度。从 UTC 转为 TT 再转回时，
上游不保证在闰秒及 1972 年模型交界处还原原始民用字段，Python `datetime` 也不能表示闰秒。

## 选择目标与相位

- `moving_objects` 按传入顺序选择天体或具名月交点，不要求它们出现在本命盘中。
  本次查询的移动侧不接纳四轴。
- `natal_objects` 选择已存天体或交点，也可显式加入 `Axis` 成员。顺序为源盘的已有位置顺序，
  再接上升、中天、下降、天底。四轴读取各自已存字段。
- `aspects` 选择 `MajorAspect` 身份，不传 `AspectRule` 容许度，也不继承本命盘相位规则。
  各项选择须非空且无重复；源盘中没有的本命对象直接拒绝。结果中的相位按角度升序保存。

例如，从 `astrology` 导入 `Axis` 后，设 `natal_objects=(Axis.ASCENDANT,)`，
替换上例的 `natal_objects` 参数，便改查源盘已存上升点，而非太阳。每张 `NatalChart` 都保存四轴，
不受所选天体影响；在上例区间内，这个上升点查询没有命中。本命目标始终固定，即使已存位置带有黄经速率。

合相与对分相各有一个分支，其余主要相位搜索正负两个有向分支。`hit.branch_deg` 是加在本命度数上的
有向角：合相为 0°，对分相为 180°，其余为正负相位角。`hit.query_longitude_deg` 是两者相加后归入
[0°, 360°) 的结果，即搜索要达到的移动黄经。`hit.longitude_deg` 保留事件黄经原值，可能有微小数值残差，
或位于 0°/360° 的另一侧。
自身日期黄经约定见{ref}`规则及坐标限度 <catalog-zh-cn-rule-project-exact-transit-hits>`。

## 搜索耗时

上游区间扫描次数为：

`移动对象数 × 本命目标数 × 所选相位的有向分支总数`

五种主要相位合计八个分支，不是五个。各项只选实际需要的对象和相位，先从短区间开始。
调用没有进度回调，所有所选扫描成功后才返回，不返回部分结果。

2026-11-07 在一台 16 核 Linux 机器上，以 celestial-calendar 1.1.1、Python 3.14.9
实测得到以下近似耗时，不作为保证。对木星、天王星、金星、土星、火星、水星，单条黄经扫描
365 TT 日约需 2–11 秒，水星最慢；太阳和月亮各不到 0.1 秒。另一次一年区间搜索，
移动侧选土星和木星，本命侧选太阳、月亮、上升点，相位选合相、四分相、对分相，约需 74 秒，
共 `2 × 3 × (1 + 2 + 1) = 24` 次扫描。

十颗移动天体对十颗本命天体及四轴，选五种主要相位，共需 `10 × 14 × 8 = 1120` 次扫描。
将每颗移动天体的单次实测耗时等量外推到所有本命目标和分支，这样的一年请求约需一小时；
没有对完整请求计时。耗时取决于目标、区间、机器和负载，不应由这些样本假定耗时随区间长度线性增长。

## 读取和保留结果

```{doctest}
>>> result.chart is chart
True
>>> result.start_utc.isoformat()
'2024-03-01T00:00:00+00:00'
>>> result.sources[0].model_kind, result.sources[0].model_identity
('position_source', 3)
>>> result.celestial_version
'1.1.1'
```

`('position_source', 3)` 是本次水星搜索实际使用的上游模型键；
`result.sources[0].model_description` 提供其名称及说明。

`start_jde_tt` 与 `end_jde_tt` 保留转换后的搜索区间。每个 `TransitSource` 保存实际移动模型、
事件域端点、最长区间及上游说明。结果还保留 astrology 版本及明确的时间、位置参考系和历元政策。
这里的版本描述本次行运计算；`result.chart.provenance` 描述原本命计算，两处版本可以不同。

命中按 TT 时刻、移动对象选择顺序、本命源盘顺序、相位角升序及负分支在前排序。
同一时刻的不同身份分别保留，不按容差合并相近穿越。报告时刻为 2^-30 日的整数倍；
这个数值分辨率不是天文精度界。

序列复制为不可变元组。构造或读取给定结果不加载原生天文库。
调用方所给结果会经过哪些检查，见[构造校验合同](architecture.md#可复现性)。

## 限制与失败

搜索区间为**半开区间**：包含 TT 起点，排除 TT 终点；最长 **3660 TT 日**。
这个上限在 UTC 转为 TT 后检查；闰秒变化可能使民用时间的 3660 日区间超过 TT 上限。
每个所选移动来源都必须接纳整个区间。这与本命快照的联合有效域分开：只选太阳时，
可以查询冥王星不能求值的日期。UTC 转换使用上游固定闰秒表，在表尾之后保留最后偏移，
不预测未来闰秒。已知闰秒跨越可使 TT 长度不同于民用钟点的经过时长。

| 失败情形 | 异常 |
|---|---|
| Python 类型或枚举类型不正确 | `TypeError` |
| 无 UTC 偏移、顺序错误、选择为空/重复/不可用，或归一后日期溢出 | `ValueError` |
| 归一后的 UTC 早于 1972 年 | `HistoricalTimeError` |
| 上游拒绝 UTC 转换、转换后的 TT 区间或所选速率域 | `TransitDomainError` |
| 原生计算、资源或内部失败 | 保持上游 `CelestialError` |
| 已安装分发包元数据缺失 | `importlib.metadata.PackageNotFoundError` |

`TransitDomainError` 是 `ValueError`，保存 `operation`、可用时的移动身份及 TT 端点、
`upstream_message`，并以原异常为 cause。任一来源失败即整次失败，不返回部分列表。
成功但命中元组为空，表示完整的所选搜索没有找到事件。

端点使用 `datetime.utcoffset()` 返回的偏移，包括其 `fold` 设置。此函数不检测或拒绝不存在或有歧义的本地钟点。
传入端点前，先处理夏令时空缺或重叠；相关说明见[出生时间准备](birth.md)。

本操作搜索精确的移动对固定命中，不计算固定时刻行运盘、容许度进出窗口、返照、
两颗移动对象间的事件或解读。
若要查一个指定时刻的相位及局部运动，用 [moment_chart 与 transit_aspects](moments.md)。
不需要运动标签时，仍可用[静态双盘相位](cross_aspects.md#比较两张示例盘)。两者都按
[源盘兼容约定](cross_aspects.md#源盘兼容与计算边界)比较各自日期的已存黄经。
