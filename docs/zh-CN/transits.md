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
速率单位为度/TT 日，直接保留上游事件值。`tangent` 表示与查询度数精确相切，
不承诺速率的位模式恰为零。

<!-- /usage: transits.hits -->

## 选择目标与相位

- `moving_objects` 按传入顺序选择天体或具名月交点，不要求它们出现在本命盘中。
  本次查询的移动侧不接纳四轴。
- `natal_objects` 选择已存天体或交点，也可显式加入 `Axis` 成员。顺序为源盘的已有位置顺序，
  再接上升、中天、下降、天底。四轴读取各自已存字段。
- `aspects` 选择 `MajorAspect` 身份，不传 `AspectRule` 容许度，也不继承本命盘相位规则。
  各项选择须非空且无重复；源盘中没有的本命对象直接拒绝。

例如，从 `astrology` 导入 `Axis` 后，设 `natal_objects=(Axis.ASCENDANT,)`，
便改查源盘已存上升点，而非太阳。本命目标始终固定，即使原记录带有黄经速率。

合相与对分相各有一个分支，其余主要相位搜索正负两个有向分支。`hit.branch_deg` 和
`hit.query_longitude_deg` 标明该次查询；`hit.longitude_deg` 保留事件黄经原值，
包括 360° 环绕的另一侧及微小数值残差，不要求与查询度数逐位相等。
自身日期黄经约定见{ref}`规则及坐标限度 <catalog-zh-cn-rule-project-exact-transit-hits>`。

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

`start_jde_tt` 与 `end_jde_tt` 保留转换后的搜索区间。每个 `TransitSource` 保存实际移动模型、
事件域端点、最长区间及上游说明。结果还保留 astrology 版本及明确的时间、位置坐标和历元政策。

命中按 TT 时刻、移动对象选择顺序、本命源盘顺序、相位角升序及负分支在前排序。
同一时刻的不同身份分别保留，不按容差合并相近穿越。时刻保留上游 2^-30 日的报告网格；
这个数值分辨率不是天文精度界。

序列复制为不可变元组。构造或读取给定结果不加载原生天文库。构造器检查类型、范围、
所选身份、查询度数及顺序，不认证天文原值、UTC/TT 对应关系或给定命中列表的完整性。

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

`TransitDomainError` 是 `ValueError`，保存 `operation`、可用时的移动身份及 TT 端点、
`upstream_message`，并以原异常为 cause，不伪造宫制。任一来源失败即整次失败，不返回部分列表。
成功但命中元组为空，表示完整的所选搜索没有找到事件。

出生记录仍走[出生准备](birth.md)；给钟点附加时区，不代表已在此解决夏令时空缺或重叠。
本操作搜索精确的移动对固定命中，不计算固定时刻行运盘、容许度进出窗口、返照、
两颗移动对象间的事件或解读。
