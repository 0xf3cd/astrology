# 精确行运命中

[English](../en/transits.md) · [文档](index.md) · [API](reference.md)

`transit_hits` 在 UTC 区间内搜索所选对象与已有本命盘的全部精确相位，返回 `TransitHits`。
结果保留原盘、搜索输入、模型溯源及每次穿越或接触。命中时刻为 JDE(TT)，即 TT 时标的儒略日，
不是 UTC 钟点。

## 搜索一个区间

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
...   print(f"{hit.jde_tt:.5f} {hit.direction.value} {hit.longitude_rate_deg_per_tt_day:+.3f}")
2460392.23731 increasing +1.208
2460414.61236 decreasing -0.744
2460437.45999 increasing +0.812
```

水星三次到达固定的本命太阳度数：黄经递增时一次，逆行时一次，恢复递增后又一次。
速率单位为度/TT 日，直接保留上游事件值。`tangent` 表示到达查询黄经后相切而未穿越，
报告的速率不必恰为零。

如需显示 UTC 日期，从 `celestial_calendar` 导入 `jde_to_utc`，调用 `jde_to_utc(hit.jde_tt)`，
取得 UTC 民用字段 `year`、`month`、`day`、`fraction`；`fraction` 是当天已过时间占 UTC 日的比例。
仍应保留原始 `jde_tt` 作为事件时刻：上游不保证在闰秒及 1972 年模型交界处精确往返，
最后一条闰秒记录之后也只保留最后已知偏移。

<!-- /usage: transits.hits -->

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

每组移动对象、本命目标和有向相位分支都要单独调用上游扫描区间。
先选择实际需要的对象和相位；同时扩大三项选择会使工作量相乘。

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
事件域端点、最长区间及上游说明。结果还保留 astrology 版本及明确的时间、位置坐标和历元政策。
这里的版本描述本次行运计算；`result.chart.provenance` 描述原本命计算，两处版本可以不同。

命中按 TT 时刻、移动对象选择顺序、本命源盘顺序、相位角升序及负分支在前排序。
同一时刻的不同身份分别保留，不按容差合并相近穿越。报告时刻为 2^-30 日的整数倍；
这个数值分辨率不是天文精度界。

序列复制为不可变元组。构造或读取给定结果不加载原生天文库。
调用方所给结果会经过哪些检查，见[构造校验合同](architecture.md#可复现性)。

## 限制与失败

搜索区间为**半开区间**：包含 TT 起点，排除 TT 终点；最长 **3660 TT 日**。
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
