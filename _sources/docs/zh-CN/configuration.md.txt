# 排盘请求配置

[English](../en/configuration.md) · [文档](index.md) · [API 参考](reference.md)

`ChartConfig` 用来指定排盘时的宫制、要返回的天体或交点，以及相位规则，构造后不能修改。
它只保存请求，不计算命盘；天文模型等实际计算信息保存在[排盘结果](records.md)中。
目前只支持热带黄道（`tropical`）和地心位置（`geocentric`）。
宫制、对象和相位规则都要明确传入：对象不能为空，不计算相位时传 `aspects=()`。
本库不提供默认宫制或默认容许度。

## 选择宫制与输出对象

<!-- usage: configuration.objects -->

例如，要用整宫制计算太阳、月亮和平均升交点的位置，可以这样配置。
`house_system` 指定宫制，`objects` 指定要返回哪些天体或交点，`aspects=()` 表示不计算相位：

```{doctest}
>>> from astrology import Body, ChartConfig, HouseSystem, LunarNode
>>> objects = [Body.SUN, Body.MOON, LunarNode.MEAN_ASCENDING]
>>> request = ChartConfig(
...   house_system=HouseSystem.WHOLE_SIGN,
...   objects=objects,
...   aspects=(),
... )
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

`HouseSystem` 可选 Whole Sign（整宫制）、Equal（等宫制）和 Placidus。所选宫制在给定时刻或地点
无法计算时，排盘会报错，不会换成另一种宫制；支持范围见[排盘指南](chart.md)。
`Body` 包括太阳、月亮及水星至冥王星，共十个物理天体。月交点不是物理天体，用 `LunarNode` 选择。
它提供平均交点和 Meeus 五项真交点两种定义，每种都区分升交点和降交点。
选择哪种定义决定了计算哪个交点，不是切换精度；两种定义不能互相替代，也可以在同一请求中同时选择。
排盘结果会记录实际使用的天文模型。

对象和规则序列按原顺序复制为元组，调用方随后修改列表不会改变请求。
重复对象或重复相位标识会被拒绝，不静默合并。`"sun"` 这样的枚举值字符串不是枚举实例，不作隐式转换。

<!-- /usage: configuration.objects -->

## 请求相位

`MajorAspect` 标识合相（conjunction）、六分相（sextile）、四分相（square）、三分相（trine）和对分相（opposition）。
用 `AspectRule` 为一种相位指定容许度 `orb_degrees`，单位为度，须为有限的非负数。
配置本身不计算相位，也不替你选择某个流派的容许度；计算方法见[相位指南](aspects.md)。

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
没有规则使用时，就不能指定。只能为参与相位的天体、交点或四轴单独设置容许度。

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

可用的枚举成员及参数、返回值说明见 [API 参考](reference.md)。实际天文模型、版本、时标和生效设置
见[排盘结果](records.md)；不排盘的查询见[知识指南](knowledge.md)。
