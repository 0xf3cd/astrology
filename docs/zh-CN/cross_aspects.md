# 双盘相位与落宫

[English](../en/cross_aspects.md) · [文档](index.md) · [API](reference.md)

用 `cross_chart_aspects` 比较两张已有 `NatalChart` 的静态主要相位，或用
`cross_chart_house_overlays` 查询各侧对象落入另一张盘的哪一宫。
左盘太阳与右盘太阳仍是不同端点，不必重命名对象或合并命盘。

静态双盘相位自 0.2.0 起提供。双盘落宫和比较文本是仍在开发中的 0.3.0 新增功能，
目前可按[源码安装说明](../../README.zh-CN.md#从源码安装)使用。

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

## 查询对象落入另一张盘的哪一宫

每条落宫同时标出对象所属盘和宫位所属盘。以下两颗太阳即使恰好都落在接收盘第一宫，
也保留各自角色，不合并为一条记录。

```{doctest}
>>> from astrology import cross_chart_house_overlays
>>> overlays = cross_chart_house_overlays(chart_left, chart_right)
>>> [(p.object_owner, p.identity.value, p.house_owner, p.house) for p in overlays.placements]
[('left', 'sun', 'right', 1), ('right', 'sun', 'left', 1)]
>>> overlays.chart_left is chart_left, overlays.chart_right is chart_right
(True, True)
>>> one_way = cross_chart_house_overlays(chart_left, chart_right,
...   left_objects=(Body.SUN,), right_objects=())
>>> [(p.object_owner, p.house_owner) for p in one_way.placements]
[('left', 'right')]
```

两侧分别选择要贡献哪些对象。空选择只取消该方向，盘上的宫头仍可接收另一侧对象。
`None` 选该侧天体和交点，不加入四轴；显式选择可含任一已存 `Axis`，与
{ref}`下方的四轴示例 <cross-axis-aspects-zh-cn>`相同。天体和交点按源顺序排列，再接上升、中天、下降、天底；
结果先列左对象入右宫，再列反方向。重复或源盘没有的对象抛出 `ValueError`；非对象值或非序列请求
抛出 `TypeError`，即使另一侧选择为空也一样。

用对象所属盘的已存黄经与宫位所属盘的实际宫头比较。宫位使用半开区间 `[宫头, 下一宫头)`，
跨 0/360 度回绕；恰在宫头的黄经归入从该宫头开始的宫。保留各自宫制，不改动源盘。
换边后角色相应交换，也允许同一张盘占两侧。`CrossChartHouseOverlays` 构造时重算全部落宫，
拒绝缺项、改值或乱序的记录。

## 选择配对与容许度

`left_objects` 与 `right_objects` 分别选择两侧对象。`None` 选该侧全部天体和交点，不加入四轴，即使其本命相位只用了
较小的子集。参与者按源盘的位置顺序排列，不按选择参数的顺序排列。
每个所选左对象都与每个所选右对象配对，包括同名对象，以及左侧每个所选交点标识与右侧每个所选交点标识的配对。
也允许同一张盘占两个角色。这些是项目的几何选择，不是传统解读。
[单盘交点排除规则](aspects.md#选择参与的对象)保持不变。

对象容许度覆盖以 `Body`、`LunarNode` 或 `Axis` 标识作用于两侧。太阳覆盖同时作用于两颗太阳，不提供
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

(cross-axis-aspects-zh-cn)=
## 分别选择两侧四轴

显式的 `left_objects`／`right_objects` 可含该源盘任一已存轴，不继承其本命参与者。
天体和交点保留源盘顺序，所选四轴按上升、中天、下降、天底顺序追加。
各侧使用自己的实际轴字段，不使用宫头或另一张盘的轴。允许轴间、同名轴及对轴配对，不折叠身份或丢弃命中。
与天体覆盖一样，轴容许度覆盖按身份作用于两侧。

```{doctest}
>>> from astrology import Axis
>>> axes = cross_chart_aspects(chart_left, chart_left, rules,
...   left_objects=(Axis.ASCENDANT,), right_objects=(Axis.ASCENDANT,))
>>> [(h.left_object.value, h.right_object.value, h.deviation_deg) for h in axes.hits]
[('ascendant', 'ascendant', 0.0)]
>>> hasattr(axes.hits[0], 'motion')
False
```

比较不执行原生天文计算，也不为四轴增加距离或运动字段。另见{ref}`本命选四轴 <axis-aspects-zh-cn>`。

## 输出比较文本

显式加载目录后交给相应格式化函数。`language="zh-CN"` 输出中文，默认输出英文。

```{doctest}
>>> from astrology import format_house_overlays, format_cross_aspects, load_catalog
>>> catalog = load_catalog()
>>> print(format_house_overlays(overlays, catalog, language="zh-CN"))  # doctest: +ELLIPSIS
双盘落宫
...
对象所属盘 | 对象 | 宫位所属盘 | 宫号
左盘 | 太阳 [sun] | 右盘 | 1
右盘 | 太阳 [sun] | 左盘 | 1
>>> print(format_cross_aspects(result, catalog, language="zh-CN"))  # doctest: +ELLIPSIS
静态双盘相位
...
左盘对象 | 右盘对象 | 相位 | 分支 | 偏差 | 容许度上限
太阳 [sun] | 太阳 [sun] | 合相 | 0°00'00" | ... | 3°00'00"
...
相位规则 / 基础容许度 / 对象单独设置: 合相 / 3°00'00" / 无
...
```

两种表格均显示各源盘的宫制、坐标约定、时标值、模型和版本标签，以及实际所选对象。
静态相位文本保留全部匹配分支，包括同一配对的多个命中；另列显式的基础容许度、对象单独设置、
合成方式及每条命中的实际上限（包含等号），不添加运动标签。空结果也显示其选择和规则。
角度沿用[整角秒显示规则](records.md#显示不改分类)，截断不改变落宫或丢弃记录。
传入目录中的所需名称及译文须齐备且为当前版本；缺失、过期或对应关系不唯一时抛出 `ValueError`，
不回退到另一种语言。表格会转义非打印字符和表格分隔符，不是无损命盘记录。

## 读取静态几何

每条命中包含 `left_object`、`right_object`、`aspect`、`branch_deg`、`deviation_deg` 与
`orb_limit_deg`。[分支与偏差的定义](aspects.md#分支与偏差)不变，单位为度。
返回所有匹配分支，按左位置、右位置、相位角升序及负分支在前排序。宽容许度可能让同一配对符合多个相位
或两个分支；不会只留最近的一个，也不按显示精度舍入后再判断。

不设运动字段，也不标入相／离相。两次出生时刻的速率不能描述共同的时间演化。
偏差为零仍表示静态几何恰好精确，不预测之后的事件。

## 源盘兼容与计算边界

两种比较都要求源盘使用相同的黄道、中心及位置坐标约定，不一致时抛出 `ValueError`。当前公开构造器只接纳一种约定：
热带地心位置，以各盘自身日期的真黄道和
真春分点为基准。因此，不同日期的春分点基准不同：命中比较的是存储的黄经值，不是两个位置在同一时刻的夹角。
不转换共同历元。
不同日期、地点、宫制、模型及软件标签均保留，不因此自动拒绝。
构造时按来源、选择和规则重算全部命中，拒绝任何差异，不认证所提供天文值或来源标签是否真实。

双盘落宫同样把各对象自身日期的已存黄经与接收盘宫头比较，不转换共同历元，也不计算三维落宫。
两种操作在输出为空时仍校验请求；不执行天文计算、时区解析、版本查询或资源 I/O。
文本使用调用方提供的目录。

Composite／Davison、行运搜索及解读不属于这些操作。
