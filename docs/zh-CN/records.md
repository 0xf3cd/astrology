# 保存、恢复、重算和查看命盘

[English](../en/records.md) · [排盘](chart.md) · [API](reference.md)

`NatalChart.resolved` 保留实际使用的已解析出生输入，其中包含原始记录。
用 `dumps_chart` 保存，用 `loads_chart` 恢复存储值；需要重新计算时，显式调用
`recompute_chart`。恢复不会重新解析时区，也不会导入原生天文库。

## 一个完整例子

这份合成记录落在豪勋爵岛时钟回拨后重复的半小时内。用 `fold=0` 选择较早的一次。
这里的地点是另行指定的合成数据，不是按时区推定的。相位没有默认容许度。

```{doctest}
>>> from datetime import date, time
>>> from astrology import (AspectRule, BirthRecord, Body, ChartConfig, HouseSystem,
...   IanaTimezone, Location, LunarNode, MajorAspect, ObjectOrb, OrbCombination,
...   TimePrecision, dumps_chart, format_chart, load_catalog, loads_chart,
...   natal_chart, prepare_natal_input, recompute_chart)
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
>>> packed = dumps_chart(chart)
>>> restored = loads_chart(packed)
>>> restored == chart, dumps_chart(restored) == packed
(True, True)
>>> recompute_chart(restored) == chart
True
>>> catalog = load_catalog()
>>> table = format_chart(restored, catalog, language="zh-CN")
>>> print("\n".join(table.splitlines()[7:10]))
太阳 [sun] | 白羊座 14°50'21" | 9 | D
月亮 [moon] | 天蝎座 13°32'41" | 4 | D
水星 [mercury] | 双鱼座 17°05'04" | 8 | D
```

完整表格还包括全部请求对象、四轴、十二宫头、带方向分支及偏差、上限和运动状态的相位，
以及请求配置、实际配置和来源。省略 `language` 或传入 `"en"` 可显示英文。
传入的目录须包含所选语言的当前名称；缺译或名称对应不唯一时会报错，不回退到另一种语言。
加载目录须显式进行，显示本身不读取资源。

## 结构版本 v1 保存什么

JSON 根字段为 `schema_version`、`input`、`requested`、`effective`、`provenance`、
`times`、`positions`、`houses`、`placements` 和 `aspects`，保存对应的公开结果值，
不是已舍入的文本表格。

- `input.record` 保留公历日期、钟点、声明的精度、时区形式、地点和字符串来源元数据。
  `input.resolved` 另存 UTC、偏移量、IANA 标识、fold 和两种时区数据版本。
  日期和钟点使用规范 ISO 文本；UTC 显式写 `+00:00`。偏移量用带符号的整数微秒，
  不用浮点秒。
- `requested` 保留对象及规则顺序、按对象容许度、合成规则，以及省略相位参与对象
  （`null`）和显式指定之间的区别。`effective.aspect_objects` 按请求对象顺序列出实际参与者。
- `positions` 保留未舍入的黄经、黄纬（度）、物理距离（AU）和黄经速率（度/TT 日）。
  月交点没有距离（`null`）。`times` 保留 JD(UT1) 和 JDE(TT)。四轴、宫头、归属结果及
  每条相位的分支、带符号偏差、上限和运动状态都会保存。
- `provenance` 保留 astrology、celestial-calendar 版本、位置坐标约定及 UT1 推导方式；
  `effective` 保留已确定的 ΔT 模型及求值方式。

输出的 JSON 对象键排序，格式确定；数组保留顺序，有限浮点数不做十进制舍入，带符号的零也保留。
输入 JSON 可以使用不同的空白和对象键顺序，但时间文本须为规范形式。接口接收字符串，
不读取文件或解释任意字节编码。文件、网络 I/O，以及不可信输入所需的资源限制，由调用方负责。

## 恢复不等于重算

重复、未知或缺失字段、类型错误（包括拿布尔值当数值）、非有限数、不支持的结构版本、
枚举或坐标标识，以及纯推导结果不一致，都会使 `loads_chart` 抛出 `ChartRecordError`。
直接构造结果也要经过同样的领域检查：星座、落宫及相位必须与所存位置和规则一致。
检查不会用新值替换存储值。

这**不认证**原来的时区选择、天文值、天文值与所称 UTC/地点之间的关系，或所称的软件版本。
恢复不执行原生时刻或宫位计算。以后若改变纯规则，须明确处理结构版本兼容，不能悄悄改变旧值的含义。

未知但非空的包版本或 ΔT 模型字符串仍可恢复，以便查看存储结果。
未知的位置坐标约定、UT1 推导方式或求值方式则不能按 v1 恢复，因为无法确定数值的含义。

```{doctest}
>>> import json
>>> from dataclasses import replace
>>> from astrology import ChartRecordError, ChartReplayError
>>> unsupported = json.loads(packed)
>>> unsupported["schema_version"] = 999
>>> try:
...   loads_chart(json.dumps(unsupported))
... except ChartRecordError as error:
...   print(type(error).__name__)
ChartRecordError
>>> old_model = replace(chart, effective=replace(chart.effective, delta_t_model="unavailable"))
>>> old_model = loads_chart(dumps_chart(old_model))
>>> old_model.effective.delta_t_model
'unavailable'
>>> try:
...   recompute_chart(old_model)
... except ChartReplayError as error:
...   print(type(error).__name__)
ChartReplayError
```

重算要求 astrology、celestial-calendar 版本一致，并且固定的 ΔT 模型可用。
它使用记录中的已解析 UTC 和请求，不查今天的时区库；返回新盘，不改存储盘。
版本或模型不可用时抛出 `ChartReplayError`；请求超出上游计算域时仍抛出 `ChartDomainError`，
不替换宫制。版本相等只是一项兼容性检查：开发版本号 `0.0.0` 不能唯一标识代码修订，
也不保证不同代码树的结果逐位相等。

## 显示不改分类

角度沿用具名的 `truncate_display` 规则，向零截断到整角秒。
白羊座 29.9999999° 显示为白羊座 29°59'59"，不会显示成金牛座 0°00'00"。
宫位及相位运动标签始终取自存储结果：显示角度相同，不代表落在同一宫；非零偏差显示为零后，
也可能仍为入相或离相。`R` 按未舍入速率的负号判断，`D` 表示黄经增大，`S` 表示速率恰为零。
文本不能代替无损 JSON。

## 验证与限度

[完整检查](contributing.md) 经 sdist 构建，在源码树之外安装 wheel，并逐字比较安装环境完整盘的
JSON 与开发入口输出，不删来源字段。还会执行恢复、重算、双语显示、不可用模型及请求 Placidus
失败的用例，并检查导入来源，包括显式加载后的原生适配层。

`tests/reference/chart_record_v1.json` 是项目计算的重算夹具，不是独立天文参考。
重算采用绝对容差：角度 1e-8 度、距离 1e-9 AU、速率 1e-9 度/TT 日、儒略日 1e-8 日；
标识及分类须相同。精确保真的恢复测试另做，不使用这些容差。

`tests/reference/complete_chart_reference.json` 保存独立执行 Swiss Ephemeris 2.10.03 /
pyswisseph 2.10.3.2 得到的四个合成时刻的数值，每个时刻包含三种宫制。
其中记录轮子哈希、标志、坐标和时标约定、来源 URL、独立的校准样本及各字段容差。
显式请求 Moshier，并检查 `calc` 返回的实际标志。Swiss 宫位使用 Swiss 自己的 UT1 和 ΔT，
不是 Algo5；容差包含这部分时刻模型差异。星座、二维黄经落宫、相位及运动状态是对 Swiss 状态
另写算术推导的项目结果，不是 Swiss 自带的相位表。平均交点黄经及速率按具名模型比较，
不假定公式完全相同。交点距离和真交点不作等价比较，交点零黄纬只作定义级检查。

参考点到宫头的距离若不超过黄经与宫头容差之和，比较就容许相邻两宫之一，
不把该点当作独立的精确落宫证据。

[Swiss 文档](https://www.astro.com/swisseph/swisseph.htm) 说明了 Moshier 的精度级别。
所列阈值包含两实现的模型差异及有限校准，不是全域精度保证。来源工具单独隔离运行，
不作为运行或开发依赖。仓内只收生成数值和项目编写的元数据，不收 Swiss 代码或星历数据文件；
依据见 [GNU 输出 FAQ](https://www.gnu.org/licenses/gpl-faq.html#WhatCaseIsOutputGPL)。
这不改变项目 MIT 许可，也不是对所有使用方式的法律保证。
