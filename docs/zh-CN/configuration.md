# 排盘请求配置

[English](../en/configuration.md) · [文档](index.md) · [API 参考](reference.md)

`ChartConfig` 是不可变请求，不是已计算的命盘或已解析的天文元数据。
仅接纳 `tropical` 和 `geocentric`。宫制、对象选择及相位规则均须显式提供。
空相位序列表示未请求相位规则；对象选择不能为空。不提供宫制或容许度默认值。

## 保留所选标识

`HouseSystem` 接纳 Whole Sign、Equal 和 Placidus。本层保留该选择，不计算宫位几何，也不替换宫制。
未来排盘适配器必须显式报告请求的几何不可用。

`Body` 标识太阳、月亮至冥王星的十个物理天体。`LunarNode` 标识采用平均定义或
Meeus 五项真交点定义的数学升降交点。定义是各交点标识的一部分，不是精度开关，也不是可互换的模型。
同一请求可显式选择两种定义。

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

对象和规则序列按原顺序复制为元组，调用方随后修改列表不会改变请求。
重复对象或重复相位标识会被拒绝，不静默合并。显示字符串不是枚举实例，不作隐式转换。

## 提供相位规则，但不执行判断

`MajorAspect` 标识合相、六合、刑相、三合和冲相。`AspectRule` 保存调用方提供的
有限、非负 `orb_degrees`，单位为度。本层只保存请求，不计算相位，不选择流派的容许度政策，
也不判断入相／出相运动。

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

上例的零容许度是显式的合成请求值，不是库默认值或建议。
NaN、无穷、负容许度、布尔值、不支持的模式及不一致的选择，在普通 Python 和 `python -O` 下都会报错。

定义枚举和 API 合同见从实际定义生成的[参考页](reference.md)。实际天文模型、版本、时标和生效计算设置
归未来适配器的结果，本层不为凑齐元数据而虚构它们。目前尚无知识查询或命盘计算。
