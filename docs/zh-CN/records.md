# 命盘结果与文本显示

[English](../en/records.md) · [排盘](chart.md) · [API](reference.md)

`natal_chart` 返回内存中的不可变 `NatalChart`。可以直接查看结构化结果，或显式提供知识目录，
交给 `format_chart` 显示。包不提供命盘存取接口或保存格式；接口撤回说明见[发行说明](releases.md)。

生成本命轮或相位矩阵时，把同一结果传给 [SVG 函数](svg.md)。

## 一个完整例子

<!-- usage: records.output -->

这份合成记录落在豪勋爵岛时钟回拨后重复的半小时内。用 `fold=0` 选择较早的一次。
地点另行指定，不按时区推定。相位没有默认容许度。

```{doctest}
>>> from datetime import date, time
>>> from astrology import (AspectRule, BirthRecord, Body, ChartConfig, HouseSystem,
...   IanaTimezone, Location, LunarNode, MajorAspect, ObjectOrb, OrbCombination,
...   TimePrecision, format_chart, load_catalog, natal_chart, prepare_natal_input)
>>> record = BirthRecord(date(2026, 4, 5), time(1, 45), IanaTimezone("Australia/Lord_Howe"),
...   Location(0, 0), TimePrecision.MINUTE, {"record": "synthetic"})
>>> config = ChartConfig(HouseSystem.WHOLE_SIGN, (*Body, LunarNode.MEAN_ASCENDING),
...   tuple(AspectRule(a, 6, (ObjectOrb(Body.SUN, 10),)) for a in MajorAspect),
...   aspect_objects=tuple(reversed(tuple(Body))), orb_combination=OrbCombination.MEAN_OF_ORBS)
>>> chart = natal_chart(prepare_natal_input(record, fold=0), config)
>>> chart.resolved.utc.isoformat()
'2026-04-04T14:45:00+00:00'
>>> len(chart.positions), bool(chart.aspects), sorted({h.orb_limit_deg for h in chart.aspects})
(11, True, [6.0, 8.0])
>>> catalog = load_catalog()
>>> table = format_chart(chart, catalog, language="zh-CN")
>>> print("\n".join(table.splitlines()[7:10]))
太阳 [sun] | 白羊座 14°50'21" | 9 | D
月亮 [moon] | 天蝎座 13°32'41" | 4 | D
水星 [mercury] | 双鱼座 17°05'04" | 8 | D
```

太阳的容许度为 10°，其他对象用 6°；取平均后，含太阳的对象对上限为 8°，其他对象对为 6°。
显式参与列表不含交点，并以反序列出各天体；实际参与顺序仍按请求对象的顺序。

完整表格包括全部请求对象、四轴、十二宫头、带方向分支及偏差、上限和运动状态的相位，
以及请求配置、实际配置和来源。省略 `language` 或传入 `"en"` 可显示英文。
传入的目录须包含所选语言的当前名称；缺译或名称对应不唯一时会报错，不回退到另一种语言。
加载目录须显式进行，显示本身不读取资源。

<!-- /usage: records.output -->

## 查看结构化结果

- `resolved.record` 保留原始公历日期、钟点、声明的精度、时区形式、地点和来源元数据。
  `resolved` 另存 UTC、偏移量、IANA 标识、fold 和两种时区数据版本。
- `requested` 保留对象及规则顺序、按对象容许度、合成规则，以及省略相位参与对象
  （`None`）和显式指定之间的区别。`effective.aspect_objects` 先按请求顺序列出天体和交点，
  再按上升、中天、下降、天底顺序列出显式所选轴。
- `positions` 保留未舍入的黄经、黄纬（度）、物理距离（AU）和黄经速率（度/TT 日）。
  月交点没有距离（`None`）。`times` 保留 JD(UT1) 和 JDE(TT)。`houses` 保留四轴黄经与十二宫头，
  单位为度；`placements` 给出星座与落宫。每条相位都保留分支、带符号偏差、上限和运动状态。
- `provenance` 保留 astrology、celestial-calendar 版本、位置坐标约定及 UT1 推导方式；
  `effective` 保留已确定的 ΔT 模型及求值方式。

直接构造 `NatalChart` 时检查字段类型、范围及纯推导结果一致性：星座、落宫和相位须与位置、已存四轴、宫头及规则吻合。
这不认证所提供的时区选择、天文值、天文值与所称 UTC/地点之间的关系，或软件版本标签。
从已解析输入计算天文值，请使用 `natal_chart`。

参与对象、容许度覆盖及命中中用到的轴名与天体名一样，取自传入目录。
原有只含天体或交点的请求不要求目录提供轴概念；四轴几何行仍使用已有的固定双语标签。

调用 `natal_chart(chart.resolved, chart.requested)` 按当前实现计算新结果，并记录本次来源。
它保留已解析出生输入，不再查时区。新结果可能与用不同代码算得的旧结果不同。
分发包必须已安装：缺少 `celestial-astrology` 元数据时抛出
`importlib.metadata.PackageNotFoundError`，不编造版本号。
仅凭版本标签不能唯一标识源码修订，也不保证不同代码树的结果逐位相等。

## 显示不改分类

角度沿用具名的 `truncate_display` 规则，向零截断到整角秒。
白羊座 29.9999999° 显示为白羊座 29°59'59"，不会显示成金牛座 0°00'00"。
宫位及相位运动标签取自未舍入结果：对象的显示黄经可以与宫头相同，但未舍入位置仍在前一宫；
非零偏差显示为零后，也可能仍为入相或离相。位置表最后一列的 `R` 表示对象黄经减小，
`D` 表示黄经增大，`S` 表示速率恰为零，均按未舍入速率判断。
文本是降低精度后的显示，不是无损交换格式。

## 验证与限度

源码／安装包比较检查打包一致性，不证明数值正确。独立 Swiss 状态与项目回归样本承担不同的检查；
有限容差包含模型差异，不能确立全域精度。接近宫头时，参考比较可能接受相邻两宫之一，
不将其认定为独立的精确宫号。夹具、约定、容差及转载限度见
[参与开发](contributing.md#完整盘数值参考)。
