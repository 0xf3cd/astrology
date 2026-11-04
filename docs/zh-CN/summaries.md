# 星座分布与出生月相

[English](../en/summaries.md) · [API](reference.md) · [知识](knowledge.md)

这些接口可以按星座元素或模式统计所选落点，也可以对给定日月位置做月相分类。

## 查星座分类并统计所选对象

<!-- usage: summaries.population -->

把要统计的落点传给 `sign_distribution`。本例对太阳和月亮等权计数，并输出全部元素和模式类别：

```{doctest}
>>> from astrology import (Body, Element, Modality, Placement, Sign, element_of,
...     modality_of, sign_distribution, format_sign_distribution, load_catalog)
>>> element_of(Sign.ARIES) is Element.FIRE
True
>>> modality_of(Sign.CANCER) is Modality.CARDINAL
True
>>> placements = [Placement(Body.SUN, Sign.ARIES, 10, 1),
...               Placement(Body.MOON, Sign.CANCER, 10, 4)]
>>> result = sign_distribution(placements)
>>> placements.clear()
>>> result.objects, result.total
((<Body.SUN: 'sun'>, <Body.MOON: 'moon'>), 2)
>>> result.element_counts[Element.FIRE], result.element_proportions[Element.FIRE]
(1, 0.5)
>>> result.modality_counts[Modality.CARDINAL]
2
>>> catalog = load_catalog()
>>> print(format_sign_distribution(result, catalog, language="zh-CN"))
星座分布（等权计数）
计数对象: 太阳 [sun], 月亮 [moon]
总数 / 分母: 2
规则: rule.zodiac.elements, rule.zodiac.modalities
类别 | 计数 / 总数 | 比例
火元素 | 1/2 | 50.00%
土元素 | 0/2 | 0.00%
风元素 | 0/2 | 0.00%
水元素 | 1/2 | 50.00%
基本模式 | 2/2 | 100.00%
固定模式 | 0/2 | 0.00%
变动模式 | 0/2 | 0.00%
```

每个所选对象计一次，总数保存在 `total` 中，也是所有比例的分母。上例共两个对象，
太阳属于火元素，月亮属于水元素，所以两类各占 50%；它们都属于基本模式，所以基本模式占 100%。
所有类别都会列出，包括计数为零的类别。百分比显示为两位小数，同时保留计数和总数。
这里不设置行星权重，也不计算主导评分。

传入非空、身份各不相同的 `Placement` 记录序列，并自行确认它们来自同一来源，例如同一张盘。
校验的范围见[校验边界](architecture.md#可复现性)。
`SignDistribution` 按输入顺序将其复制为不可变元组，计数、比例和总数都由这个快照推导。
`element_of` 和 `modality_of` 接受 `Sign` 成员。校验错误见[摘要 API 参考](reference.md#命盘摘要与月相)。

<!-- /usage: summaries.population -->

分类来源及它们与历史星座分组的区别，见[知识说明](knowledge.md#元素模式与月相类型)。

## 对给定日月位置分类

<!-- usage: summaries.lunar_phase -->

按太阳在前、月亮在后的顺序传入黄经，单位为度；两者须采用同一时刻和坐标约定。
函数沿黄经递增方向，从太阳量到月亮，返回这个角度和对应的月相类型：

```{doctest}
>>> from astrology import lunar_phase, format_lunar_phase
>>> phase = lunar_phase(sun_longitude_deg=350, moon_longitude_deg=10)
>>> phase.elongation_deg, phase.phase.value, phase.direction
(20.0, 'new_moon', 'waxing')
>>> print(format_lunar_phase(phase, catalog, language="zh-CN"))
月相类型: 新月型
月亮减太阳（黄经，度）: 20.0
角度方向: 盈
规则: rule.lunation.rudhyar1950
每型覆盖一段区间，不表示精确事件；不计算照亮比例。
>>> lunar_phase(10, 350).direction, lunar_phase(0, 180).direction
('waning', 'turning')
```

有向差为 `(月亮 - 太阳) mod 360`，单位为度。
有限的黄经可以超出一圈，计算时会约去整圈。
传入的数值本身不带时刻或坐标信息，函数无法发现是否混用了不同的坐标约定。

参见{ref}`生成区间表 <catalog-zh-cn-rule-lunation-rudhyar1950>`和[来源说明](knowledge.md#元素模式与月相类型)。
每型跨度为 45°。本项目采用半开区间：包含起点，不包含终点，恰在边界时归入后一型，360° 回到 0°。
角度在 `(0, 180)` 内为 `waxing`（盈），在 `(180, 360)` 内为 `waning`（亏），
恰为 0° 或 180° 时为 `turning`（转折点）。这些端点归属和方向标签由本项目定义。

`LunarPhaseResult` 不可变，类型、方向及规则标识从角度推导；直接构造要求 `[0, 360)`。
20° 的新月型结果不是精确合日。不计算照亮比例、三维相角或精确事件搜索，也不作性格解读。
方向描述当前弧，不是根据速率作出的运动预测。

<!-- /usage: summaries.lunar_phase -->

## 从已有本命盘组合

下面先用合成资料排一张盘，再用 `chart_sign_distribution` 统计所选对象，
用 `natal_lunar_phase` 读取出生月相。后两个函数读取盘中已有的位置和落点：

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (BirthRecord, FixedOffset, Location, ChartConfig, HouseSystem,
...     natal_chart, prepare_natal_input, chart_sign_distribution, natal_lunar_phase)
>>> record = BirthRecord(date(2000, 1, 1), time(12), FixedOffset(timedelta(0)), Location(0, 0))
>>> chart = natal_chart(prepare_natal_input(record),
...     ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ()))
>>> summary = chart_sign_distribution(chart, objects=(Body.MOON, Body.SUN))
>>> summary.objects == chart.requested.objects
True
>>> summary.total
2
>>> natal_lunar_phase(chart) == lunar_phase(chart.positions[0].longitude_deg,
...                                       chart.positions[1].longitude_deg)
True
```

`objects` 须为非空选择，只能选择盘中已有且身份不同的天体或交点。
结果按源盘顺序，而非选择顺序排列。统计全部请求对象时，须显式传
`objects=chart.requested.objects`。不加入未选天体、交点或四轴。四轴不是落点，即使显式选择也不能参与这项统计。
`natal_lunar_phase` 要求日月齐备；缺位置时会报错并列出缺失身份，不补算。
完整错误契约见[摘要 API 参考](reference.md#命盘摘要与月相)。

目录条目仍是 `reference_only`，已声明完整前提 `complete`，而命盘适用性为 `not_assessed`。
来源已核不代表目录查询会判断命盘。

## 数值角度与显示

输入先转为浮点数，函数再用这些二进制值的精确比值计算差值，避免相减溢出或把角度算到边界的另一侧。
结果通常取最近的浮点值；若舍入会把原本在边界一侧的角度变成边界值，就改取正确一侧的相邻浮点值。
例如 `lunar_phase(5e-324, 0)` 返回 `359.99999999999994`，不会变成 360° 或误判为精确合日。
结果是数值近似，不是精确实数角度。两黄经同时旋转保持数学上的差不变，但旋转浮点数时可能
已经舍入输入，因此不保证结果逐位相同。

月相格式化函数不截断到角秒，而是显示存储的浮点值。标签不从舍入文本推断。`format_sign_distribution` 和 `format_lunar_phase`
都要求所选语言（`en` 或 `zh-CN`）的目录名称为当前版本。名称缺失或过期时会报错，不改用另一语言。
名称的表格分隔符及非打印字符会转义显示。格式化的错误行为见[文本 API 参考](reference.md#命盘文本)。
