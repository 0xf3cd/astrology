# 排盘请求配置

[English](../en/configuration.md) · [文档](index.md) · [API 参考](reference.md)

`ChartConfig` 是不可变请求，不是已计算的命盘或已解析的天文元数据。
仅接纳 `tropical` 和 `geocentric`。宫制、对象选择及相位规则均须显式提供。
空相位序列表示未请求相位规则；对象选择不能为空。不提供宫制或容许度默认值。

## 选择宫制与输出对象

<!-- usage: configuration.objects -->

选择 `HouseSystem`，再把要计算的天体或交点放入 `objects`。
下面请求太阳、月亮和平均升交点，不请求相位：

```{doctest}
>>> from astrology import Body, ChartConfig, HouseSystem, LunarNode
>>> objects = [Body.SUN, Body.MOON, LunarNode.MEAN_ASCENDING]
>>> request = ChartConfig(HouseSystem.WHOLE_SIGN, objects, ())
>>> objects.clear()
>>> tuple(value.value for value in request.objects)
('sun', 'moon', 'mean_ascending_node')
>>> request.house_system.value
'whole_sign'
>>> LunarNode.MEAN_ASCENDING.definition.value
'mean'
>>> LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING.definition.value
'meeus_five_term_true'
```

`HouseSystem` 接纳 Whole Sign、Equal 和 Placidus。请求的几何不可用时显式失败，
支持范围见[排盘指南](chart.md)。`Body` 标识太阳、月亮至冥王星的十个物理天体。
`LunarNode` 标识采用平均定义或 Meeus 五项真交点定义的数学升降交点。
定义是标识的一部分，不是精度开关，也不是可互换的模型；同一请求可显式选择两种定义，排盘结果会记录所用的天文模型。

对象和规则序列按原顺序复制为元组，调用方随后修改列表不会改变请求。
重复对象或重复相位标识会被拒绝，不静默合并。`"sun"` 这样的枚举值字符串不是枚举实例，不作隐式转换。

<!-- /usage: configuration.objects -->

## 请求相位

`MajorAspect` 标识合相（conjunction）、六分相（sextile）、四分相（square）、三分相（trine）和对分相（opposition）。
`AspectRule` 保存调用方提供的有限、非负 `orb_degrees`，单位为度。本层只保存请求，不计算相位，
也不替调用方选择流派的容许度规则；如何计算相位，见[相位指南](aspects.md)。

```{doctest}
>>> from astrology import AspectRule, MajorAspect
>>> rules = [AspectRule(MajorAspect.CONJUNCTION, 0)]
>>> request = ChartConfig(HouseSystem.PLACIDUS, (Body.SUN, Body.MOON), rules)
>>> rules.clear()
>>> (request.aspects[0].aspect.value, request.aspects[0].orb_degrees)
('conjunction', 0.0)
>>> (request.zodiac, request.center)
('tropical', 'geocentric')
```

上例中的零容许度是为演示手动设置的，不是库的默认值或建议值。

## 选择参与相位的对象

<!-- usage: configuration.participants -->

这个请求要求排盘返回太阳和月亮的位置，但只判断太阳与上升点的相位：

```{doctest}
>>> from astrology import AspectRule, Axis, Body, ChartConfig, HouseSystem, MajorAspect
>>> with_axes = ChartConfig(
...   HouseSystem.WHOLE_SIGN,
...   objects=(Body.SUN, Body.MOON),
...   aspects=(AspectRule(MajorAspect.SEXTILE, 3),),
...   aspect_objects=(Body.SUN, Axis.ASCENDANT),
... )
>>> [value.value for value in with_axes.aspect_participants()]
['sun', 'ascendant']
>>> [value.value for value in with_axes.objects]
['sun', 'moon']
```

`objects` 选择天文输出，只接纳 `Body` 和 `LunarNode`。`aspect_objects` 从这些天体或交点中
选择相位参与者，也可显式加入四轴；月亮在上例中仍有位置，但不参与相位。不写 `aspect_objects`
时，所有请求的天体和交点都参与，不加入四轴。

天体和交点保留原请求顺序，所选四轴按上升、中天、下降、天底（ASC/MC/DSC/IC）顺序追加，不随选择参数的顺序改变。
相位参与者也可只选四轴，但 `objects` 仍须至少含一个天体或交点。
几何与配对政策见{ref}`显式选择四轴 <axis-aspects-zh-cn>`。

<!-- /usage: configuration.participants -->

## 给对象单独的容许度

<!-- usage: configuration.orbs -->

用 `ObjectOrb` 为某个对象单独设置容许度；其他对象使用规则的 `orb_degrees`。
只要有规则使用了 `ObjectOrb`，就必须指定 `orb_combination`，说明两个对象的容许度如何合成一个上限；
没有规则使用时，就不能指定。只能为参与相位的身份单独设置容许度，包括所选四轴。

```{doctest}
>>> from astrology import LunarNode, ObjectOrb, OrbCombination
>>> rules = [AspectRule(MajorAspect.TRINE, 3, [ObjectOrb(Body.MOON, 13)])]
>>> objects = (Body.SUN, Body.MOON, LunarNode.MEAN_ASCENDING)
>>> request = ChartConfig(
...   HouseSystem.PLACIDUS, objects, rules,
...   aspect_objects=[Body.SUN, Body.MOON],
...   orb_combination=OrbCombination.EITHER_WITHIN_OWN_ORB,
... )
>>> [value.value for value in request.aspect_objects]
['sun', 'moon']
>>> request.orb_combination.value
'either_within_own_orb'
>>> ChartConfig(HouseSystem.PLACIDUS, objects, rules)
Traceback (most recent call last):
...
ValueError: orb_combination is required when aspect rules have object orbs
```

NaN、无穷、负容许度、布尔值、不支持的模式及不一致的选择，在普通 Python 和 `python -O` 下都会报错。

<!-- /usage: configuration.orbs -->

定义枚举和 API 合同见从实际定义生成的[参考页](reference.md)。实际天文模型、版本、时标和生效设置
见[排盘结果](records.md)；不排盘的查询见[知识指南](knowledge.md)。
