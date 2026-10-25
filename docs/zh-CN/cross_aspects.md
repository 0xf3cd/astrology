# 静态双盘交叉相位

[English](../en/cross_aspects.md) · [文档](index.md) · [API](reference.md)

`cross_chart_aspects` 比较两张已有的内存 `NatalChart` 结果。左盘太阳与右盘太阳仍是不同端点，
不必重命名对象或合并命盘。比较给定结果不执行天文计算、时区解析、版本查询或 I/O。

此 API 属于当前源码，不在已发布的 v0.1.0 中。安装见[源码安装说明](../../README.zh-CN.md#从源码安装)。

## 比较两份合成出生记录

先计算源盘。它们的本命相位规则可以为空；比较时显式给出另一组规则。

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (AspectRule, BirthRecord, Body, ChartConfig, FixedOffset,
...   HouseSystem, Location, MajorAspect, ObjectOrb, OrbCombination,
...   cross_chart_aspects, natal_chart, prepare_natal_input)
>>> config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ())
>>> def source_chart(year):
...   record = BirthRecord(date(year, 7, 17), time(6), FixedOffset(timedelta(0)),
...     Location(0, 0), source={"record": "synthetic", "year": str(year)})
...   return natal_chart(prepare_natal_input(record), config)
>>> chart_left, chart_right = source_chart(2003), source_chart(2004)
>>> rules = [AspectRule(MajorAspect.CONJUNCTION, 3)]
>>> result = cross_chart_aspects(chart_left=chart_left, chart_right=chart_right, rules=rules)
>>> [(h.left_object.value, h.right_object.value, h.aspect.value) for h in result.hits]
[('sun', 'sun', 'conjunction')]
>>> result.chart_left is chart_left, result.chart_right is chart_right
(True, True)
>>> result.chart_left.resolved.utc.year, result.chart_right.resolved.utc.year
(2003, 2004)
>>> hit = result.hits[0]
>>> abs(hit.deviation_deg) <= hit.orb_limit_deg == 3
True
```

`result.chart_left` 与 `result.chart_right` 保留两张完整源盘，包括原始／已解析出生输入、位置、
请求／实际配置及来源。`rules` 和 `combination` 保存本次比较请求；不继承任一盘的本命规则或参与对象。

## 选择配对与容许度

`left_objects` 与 `right_objects` 分别选择两侧对象。`None` 选该侧全部位置，即使其本命相位只用了
较小的子集。参与者按源盘的位置顺序排列，不按选择参数的顺序排列。
每个所选左对象都与每个所选右对象配对，包括同名对象，以及左侧每个所选交点标识与右侧每个所选交点标识的配对。
也允许同一张盘占两个角色。这些是项目的几何选择，不是传统解读。
[单盘交点排除规则](aspects.md#选择参与的对象)保持不变。

对象容许度覆盖仍以 `Body` 或 `LunarNode` 标识作用于两侧。太阳覆盖同时作用于两颗太阳，不提供
左太阳／右太阳分别设值的机制。覆盖必须指向至少一侧的所选对象。
只要某条规则有覆盖，就必须选择 `OrbCombination`；没有覆盖时，`combination` 须为 `None`。
[三种合成方式](aspects.md#对象各有容许度时怎样合成)和包含等号的上限，沿用本命配对的算术。

```{doctest}
>>> own_sun = [AspectRule(MajorAspect.CONJUNCTION, 1, [ObjectOrb(Body.SUN, 5)])]
>>> adjusted = cross_chart_aspects(chart_left, chart_right, own_sun,
...   combination=OrbCombination.MEAN_OF_ORBS)
>>> adjusted.hits[0].orb_limit_deg
5.0
>>> cross_chart_aspects(chart_left, chart_right, rules, left_objects=[]).hits
()
>>> cross_chart_aspects(chart_left, chart_right, ()).rules
()
```

空选择、空规则和没有匹配都会得到空命中，可从结果里的选择与规则区分。
以下请求即使没有配对也会抛出 `ValueError`：同一侧选择里重复的参与对象、源盘没有的对象、重复相位标识、
指向未选对象的覆盖、无覆盖却给合成方式，以及有覆盖却未给合成方式。
调用方序列会复制为不可变元组。

## 读取静态几何

每条命中包含 `left_object`、`right_object`、`aspect`、`branch_deg`、`deviation_deg` 与
`orb_limit_deg`。[分支与偏差的定义](aspects.md#分支与偏差)不变，单位为度。
返回所有匹配分支，按左位置、右位置、相位角升序及负分支在前排序。宽容许度可能让同一配对符合多个相位
或两个分支；不会只留最近的一个，也不按显示精度舍入后再判断。

不设运动字段，也不标入相／离相。两次出生时刻的速率不能描述共同的时间演化。
偏差为零仍表示静态几何恰好精确，不预测之后的事件。

源盘须使用相同的黄道、中心及位置坐标约定，不一致时抛出 `ValueError`。当前公开构造器只接纳一种约定：
热带地心位置，以各盘自身日期的真黄道和
真春分点为基准。因此，不同日期的春分点基准不同：命中比较的是存储的黄经值，不是两个位置在同一时刻的夹角。
不转换共同历元。
不同日期、地点、宫制、模型及软件标签均保留，不因此自动拒绝。
构造时按来源、选择和规则重算全部命中，拒绝任何差异，不认证所提供天文值或来源标签是否真实。

Composite／Davison、宫位叠加、行运搜索及解读不属于此 API；不提供独立文本格式化入口。
