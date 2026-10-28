# 星座分布与出生月相

[English](../en/summaries.md) · [API](reference.md) · [知识](knowledge.md)

这些源码接口计划随 0.3.0 交付，尚不在已发布的 0.2.0 包中。它们对给定值分类，不调用天文库，
也不改变源盘。格式化函数接受已加载的目录，不读取资源。

## 查星座分类并统计所选对象

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

每个所选的不同身份计一次，共同分母为 `total`；每类都保留，包括零计数。百分比显示为两位
小数，同时保留精确的计数／总数。不设置行星权重或主导评分。

`sign_distribution` 与 `SignDistribution` 将序列复制为不可变的落点元组，保留输入顺序。
空集合或重复身份抛出 `ValueError`；`None`、迭代器和非 `Placement` 成员抛出 `TypeError`。
低层落点的共同来源由调用方负责保证，本记录无法核实。计数及比例从快照推导，不能另行
传入与之矛盾的总数。`element_of` 和 `modality_of` 只接受 `Sign`，不接受字符串或其他枚举。

{ref}`元素 <catalog-zh-cn-rule-zodiac-elements>`及
{ref}`模式 <catalog-zh-cn-rule-zodiac-modalities>`参考表读取可执行定义。来源为
Astrodienst 无日期的编辑页面，依据记录中的 2025-12-28 快照核验。来源的 `Sagitarius`
拼写单独记录，规范身份仍为 `Sign.SAGITTARIUS`。`Modality` 与 `AshmandSignGroup` 身份分开：
两者固定集合相同，现代变动集合与 Ashmand 双体集合相同；Ashmand 至点、分点两对合起来是
现代基本模式集合。这种成员关系不合并它们的名称或历史定义。

两个 `FIXED` 成员的字符串值都是 `"fixed"`；按 `StrEnum` 的字符串语义，它们比较相等，
hash 也相同。要在同一映射中保留二者，请用 `(type(member), member.value)` 作键，
或使用各自带类别前缀的目录 ID。

## 对给定日月位置分类

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

公开参数顺序是**太阳在前、月亮在后**，有向差为 `(月亮 - 太阳) mod 360`，单位为度。
有限输入可包含整圈。布尔值、字符串及其他类型抛出 `TypeError`，非有限值抛出 `ValueError`。
调用方须保证同一时刻及坐标约定。裸数值不携带这两项信息，标量函数无法发现坐标约定混用。

分类采用 Rudhyar 的八种月相类型，依据 *Your Lunation Birthday* 第四部分在线转录。
页面自述初刊于 *Horoscope Magazine* 1950 年 1 月，未核杂志原件。
{ref}`生成区间表及来源 <catalog-zh-cn-rule-lunation-rudhyar1950>`可供查阅。每型跨度为 45°。
项目将所有区间定为半开：精确边界归后型，360° 回到 0°。严格 `(0, 180)` 为 `waxing`（盈），
严格 `(180, 360)` 为 `waning`（亏），0°／180° 为 `turning`（转折点）。端点及方向标签是项目政策。

`LunarPhaseResult` 不可变，类型、方向及规则标识从角度推导；直接构造要求 `[0, 360)`。
20° 的新月型结果不是精确合日。不计算照亮比例、三维相角或精确事件搜索，也不作性格解读。
方向描述当前弧，不是根据速率作出的运动预测。

### 数值角度与显示

输入沿用数值校验器的浮点转换。函数以这些二进制值的精确比值计算，避免相减溢出或丢失
边界一侧。通常返回最近的浮点值；若此转换抹去区间一侧，就移到正确一侧的相邻浮点值。
例如 `lunar_phase(5e-324, 0)` 返回 `359.99999999999994`，不会变成 360° 或误判为精确合日。
结果是数值近似，不是精确实数角度。两黄经同时旋转保持数学上的差不变，但旋转浮点数时可能
已经舍入输入，因此不保证逐 bit 相同。

月相格式化函数不截断到角秒，而是显示存储的浮点值。标签不从舍入文本推断。两种格式化函数
都要求所选语言（`en` 或 `zh-CN`）的目录名称为当前版本。名称缺失或过期抛出 `ValueError`，
标识缺失抛出 `KeyError`，结果或目录类型错误抛出 `TypeError`。名称的表格分隔符及非打印字符
会转义显示。

## 从已有本命盘组合

本例只计算一次合成命盘。后面的摘要调用仅读取已有位置和落点，使用一张盘的共同坐标约定：

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

`objects` 必填且非空。`None`、字符串或错误身份类型抛出 `TypeError`，重复或不可用身份抛出
`ValueError`。结果按源盘顺序，而非选择顺序排列。统计全部请求对象时，须显式传
`objects=chart.requested.objects`。不加入未选天体、交点或四轴。四轴不是落点，即使显式选择也不能参与这项统计。
`natal_lunar_phase` 要求日月齐备；
缺位置抛出 `ValueError` 并列出缺失身份，不补算。两个入口对非 `NatalChart` 输入均抛出
`TypeError`。这些检查在 `python -O` 下同样有效。

目录条目仍是 `reference_only`，已声明完整前提 `complete`，而命盘适用性为 `not_assessed`。
来源已核不代表目录查询会判断命盘。
