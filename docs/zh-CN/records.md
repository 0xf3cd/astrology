# 命盘结果与文本显示

[English](../en/records.md) · [排盘](chart.md) · [API](reference.md)

`natal_chart` 返回内存中的不可变 `NatalChart`。可以直接查看结构化结果，或显式提供知识目录，
交给 `format_chart` 显示。包不提供命盘存取接口或保存格式；接口撤回说明见[发行说明](releases.md)。

## 一个完整例子

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

## 查看结构化结果

- `resolved.record` 保留原始公历日期、钟点、声明的精度、时区形式、地点和来源元数据。
  `resolved` 另存 UTC、偏移量、IANA 标识、fold 和两种时区数据版本。
- `requested` 保留对象及规则顺序、按对象容许度、合成规则，以及省略相位参与对象
  （`None`）和显式指定之间的区别。`effective.aspect_objects` 按请求对象顺序列出实际参与者。
- `positions` 保留未舍入的黄经、黄纬（度）、物理距离（AU）和黄经速率（度/TT 日）。
  月交点没有距离（`None`）。`times` 保留 JD(UT1) 和 JDE(TT)。四轴、宫头、星座与落宫结果及
  每条相位的分支、带符号偏差、上限和运动状态都可直接查看。
- `provenance` 保留 astrology、celestial-calendar 版本、位置坐标约定及 UT1 推导方式；
  `effective` 保留已确定的 ΔT 模型及求值方式。

直接构造 `NatalChart` 时检查字段类型、范围及纯推导结果一致性：星座、落宫和相位须与位置、宫头及规则吻合。
这不认证所提供的时区选择、天文值、天文值与所称 UTC/地点之间的关系，或软件版本标签。
从已解析输入计算天文值，请使用 `natal_chart`。

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

[完整检查](contributing.md) 经 sdist 构建，在源码树之外安装 wheel，并对同一源码修订的完整数值结果、
已解析输入、请求／实际配置及来源与源码结果作精确比较。还会执行双语显示及请求 Placidus
失败的用例，并检查导入来源，包括显式加载后的原生适配层。

`tests/reference/chart_regression.json` 保留两份项目计算的合成整宫制样本数值：
`0.0.0` 开发树中的 IANA 输入、非统一相位容许度案例，以及正式发布 v0.1.0 wheel 中的
固定偏移、两个天体且无相位的案例。提取来源包括原样本哈希，以及发布 wheel／manifest 摘要、
源码提交及生成方法。它们是回归样本，不是独立天文参考。测试显式构造各案例的输入，不恢复已保存命盘。

数值回归检查模型、坐标约定、配置、标识及分类，不要求历史包版本相等。
绝对容差为角度 1e-8 度、距离 1e-9 AU、速率 1e-9 度/TT 日、儒略日 1e-8 日。
模型变化须另行说明适用的比较方法。这些有限案例不能证明全域精度。

`tests/reference/complete_chart_reference.json` 保存独立执行 Swiss Ephemeris 2.10.03 /
pyswisseph 2.10.3.2 得到的四个合成时刻的数值，每个时刻包含三种宫制。
其中记录 pyswisseph Python wheel 文件的 SHA-256 哈希、标志、坐标和时标约定、来源 URL、
独立的校准样本及各字段容差。显式请求 Moshier，并检查 `calc` 返回的实际标志。
Swiss 宫位使用 Swiss 自己的 UT1 和 ΔT，不是适配层固定使用的 Algo5 ΔT 模型；
容差包含这部分时刻模型差异。星座、二维黄经落宫（只用黄经，不用对象黄纬）、相位及运动状态
是对 Swiss 状态另写算术推导的项目结果，不是 Swiss 自带的相位表。
平均交点黄经及速率按具名模型比较，不假定公式完全相同。
交点距离和真交点不作等价比较，交点零黄纬只作定义级检查。

参考点到宫头的距离若不超过黄经与宫头容差之和，比较就容许相邻两宫之一，
不把该点当作独立的精确落宫证据。

[Swiss 文档](https://www.astro.com/swisseph/swisseph.htm) 说明了 Moshier 的精度级别。
所列阈值包含两实现的模型差异及有限校准，不是全域精度保证。来源工具单独隔离运行，
不作为运行或开发依赖。仓内只收生成数值和项目编写的元数据，不收 Swiss 代码或星历数据文件；
依据见 [GNU 输出 FAQ](https://www.gnu.org/licenses/gpl-faq.html#WhatCaseIsOutputGPL)。
这不改变项目 MIT 许可，也不是对所有使用方式的法律保证。
