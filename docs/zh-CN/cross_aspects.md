# 双盘相位与落宫

[English](../en/cross_aspects.md) · [文档](index.md) · [API](reference.md)

已有两张 `NatalChart` 时，可以用 `cross_chart_aspects` 查它们之间的静态主要相位，
用 `cross_chart_house_overlays` 查一张盘的对象落入另一张盘的哪一宫。
结果会区分左盘太阳和右盘太阳，不需要给对象改名，也不需要合并命盘。
比较直接使用两张盘中已存的黄经；使用前请确认它们满足[坐标要求](#源盘兼容与计算边界)。

静态双盘相位自 0.2.0 起提供。双盘落宫和比较文本是仍在开发中的 0.3.0 新增功能，
目前可按[源码安装说明](../../README.zh-CN.md#从源码安装)使用。

## 比较两张示例盘

下面用两份虚构的出生资料排盘，再查两颗太阳是否在 3 度容许度内合相。
双盘比较使用单独传入的相位规则，因此排本命盘时可以不计算相位。

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

`result.chart_left` 和 `result.chart_right` 仍是传入的两张完整命盘，可以继续读取原始出生资料、
解析后的时刻、位置、请求与实际采用的配置，以及计算来源信息。
结果的 `rules` 和 `combination` 记录本次比较使用的规则和容许度合成方式。
比较不会沿用任一盘的本命相位规则或参与对象。

## 查询对象落入另一张盘的哪一宫

`placements` 中的每条记录都写明对象来自哪张盘（`object_owner`）、使用哪张盘的宫位
（`house_owner`），以及落入的宫号（`house`）。下面第一条是左盘太阳落入右盘第一宫，
第二条是右盘太阳落入左盘第一宫；这是两个方向的结果，不会合并。

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

用 `left_objects` 选择左盘中要查落宫的对象，用 `right_objects` 选择右盘对象。
上例的 `right_objects=()` 表示不查右盘对象的落宫；右盘的宫头仍用于判断左盘太阳落在哪一宫。
两边都传空序列时，`placements` 为空。

不传选择参数或传 `None` 时，选取该盘的全部天体和交点，不包含四轴。
要查四轴的落宫，显式传入该盘已有的 `Axis`，写法见{ref}`下方示例 <cross-axis-aspects-zh-cn>`。
每张盘的天体和交点按盘中位置记录的顺序排列，所选四轴随后按上升、中天、下降、天底排列，
不按传入选择的顺序排列。`placements` 先列左盘对象在右盘的落宫，再列右盘对象在左盘的落宫。

落宫只比较对象的已存黄经与另一张盘的实际宫头，角度单位为度。
每一宫从本宫宫头开始，到下一宫宫头之前结束，即半开区间 `[宫头, 下一宫头)`；
跨过 360 度后从 0 度继续。黄经恰好等于宫头时，归入从该宫头开始的宫。
两张盘各用自己的宫制，原盘保持不变。交换参数中的左右盘后，结果中的所属盘也随之交换；
也可以把同一张盘传给两边。

同一侧重复选择对象，或选择该盘没有的对象，会抛出 `ValueError`；传入非对象值或非序列选择，
会抛出 `TypeError`。即使另一侧选择为空，这些检查仍然执行。
直接构造 `CrossChartHouseOverlays` 时，会按两张盘和所选对象重新计算完整落宫序列；
缺少记录、宫号不同或顺序不同都会被拒绝。

## 选择配对与容许度

调用 `cross_chart_aspects` 时，同样用 `left_objects` 和 `right_objects` 分别选择两张盘的对象。
`None` 表示该盘的全部天体和交点，不包含四轴，即使本命相位只使用了其中一部分。
对象按盘中位置记录的顺序排列，不按传入选择的顺序排列。
左盘的每个所选对象都会与右盘的每个所选对象配对，包括两颗太阳这样的同名对象，
以及两边各自所选的任意交点组合。也可以把同一张盘传给两边。
这些配对是本项目的几何计算约定，不是传统解读规则。
[单盘交点排除规则](aspects.md#选择参与的对象)保持不变。

用 `ObjectOrb` 为某个 `Body`、`LunarNode` 或 `Axis` 单独设置容许度时，这项设置同时作用于两边。
例如，为太阳设值会同时作用于两颗太阳，不能给左盘太阳和右盘太阳分别设值。
设置的对象必须在至少一边被选中。只要某条规则有对象单独设置，就必须选择 `OrbCombination`；
没有时，`combination` 须为 `None`。[三种合成方式](aspects.md#对象各有容许度时怎样合成)
与本命相位相同，偏差的绝对值等于容许度上限时也算命中。

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

`hits=()` 可能表示选择为空、规则为空，或没有相位匹配；查看结果中记录的对象选择和规则可以区分原因。
以下请求会抛出 `ValueError`，即使没有对象可配对也一样：

- 同一侧重复选择对象，或选择该盘没有的对象。
- 规则中重复指定同一种相位，或为两边都未选中的对象设置容许度。
- 有对象单独设置却未选合成方式，或没有对象单独设置却给了合成方式。

传入的序列会复制为不可变元组，之后修改原序列不会改变结果。

(cross-axis-aspects-zh-cn)=
## 分别选择两侧四轴

要让四轴参与比较，在 `left_objects` 或 `right_objects` 中显式选择该盘已有的轴；
本命相位选择了哪些轴，不影响本次比较。天体和交点保留盘中顺序，所选四轴随后按上升、中天、下降、天底排列。
每张盘都读取自己的实际轴字段，不用宫头代替，也不借用另一张盘的轴。
轴与轴可以配对，包括同名轴和对轴；它们仍按各自的标识保留，不会因此合并或丢掉命中。
给某个轴单独设置容许度时，与给天体设置一样，同时作用于两边的同名轴。

```{doctest}
>>> from astrology import Axis
>>> axes = cross_chart_aspects(chart_left, chart_left, rules,
...   left_objects=(Axis.ASCENDANT,), right_objects=(Axis.ASCENDANT,))
>>> [(h.left_object.value, h.right_object.value, h.deviation_deg) for h in axes.hits]
[('ascendant', 'ascendant', 0.0)]
>>> hasattr(axes.hits[0], 'motion')
False
```

比较直接读取盘中已有的轴，不重新执行原生天文计算，也不为轴增加距离或运动字段。
本命相位的选择方法见{ref}`本命选四轴 <axis-aspects-zh-cn>`。

## 输出比较文本

用 `format_house_overlays` 输出落宫表，用 `format_cross_aspects` 输出双盘相位表。
两者都需要传入 `load_catalog()` 返回的知识目录，表中的名称取自这份目录。
默认输出英文，传 `language="zh-CN"` 输出中文。

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

表格开头列出两张盘各自的宫制、坐标约定、时标值、模型和版本标签，以及本次所选对象。
落宫表随后逐条列出所属盘和宫号。相位表列出所有匹配分支，同一配对有多条命中时全部保留，
不添加入相／离相等运动标签；表中还会列出基础容许度、对象单独设置、合成方式和每条命中的实际容许度上限。
偏差的绝对值等于上限时也算命中。结果为空时，仍能从表中看到对象选择和相位规则。

分支、偏差和容许度以度、分、秒显示，沿用[整角秒截断规则](records.md#显示不改分类)。
截断只影响显示，不重新判断相位，也不删掉记录。
目录中所需的名称和译文必须齐备且为当前版本；缺失、过期或对应关系不唯一时会抛出 `ValueError`，
不会改用另一种语言。表格会转义非打印字符和表格分隔符，只适合阅读，不能用来无损恢复命盘。

## 读取静态几何

每条命中用 `left_object` 和 `right_object` 标明两边对象，用 `aspect` 标明相位。
`branch_deg`、`deviation_deg` 和 `orb_limit_deg` 分别是分支角、偏差和容许度上限，单位均为度，
定义见[分支与偏差](aspects.md#分支与偏差)。
结果按左盘对象的位置顺序、右盘对象的位置顺序、相位角升序排列，同一相位的负分支在前。
容许度较宽时，同一配对可能符合多个相位或两个分支，所有匹配都会返回；
不会只留最近的一个，也不会先按显示精度舍入再判断。

命中没有运动字段，也不标入相／离相，因为两个出生时刻的速率不能说明这组相位怎样随时间变化。
偏差为零只表示这次比较的静态几何恰好精确，不预测之后的事件。

## 源盘兼容与计算边界

两种比较都要求两张盘使用相同的黄道、中心和位置坐标约定，不一致时会抛出 `ValueError`。
当前公开构造器只接受热带地心位置，以各盘自身日期的真黄道和真春分点为基准。
日期不同，春分点基准也就不同。双盘相位直接比较存储的黄经值，不把位置转换到共同历元，
因此算出的不是两个位置在同一时刻的夹角。

两张盘可以有不同的日期、地点、宫制、模型和软件标签，这些信息会原样保留，不会仅因不同就拒绝比较。
构造双盘相位结果时，会按两张盘、所选对象和规则重算全部命中；构造双盘落宫结果时，
会按两张盘和所选对象重算全部落宫。传入记录只要与重算结果不同，就会被拒绝。
这些检查不证明所提供天文值或来源标签真实。

双盘落宫同样直接比较对象在自身日期的已存黄经与另一张盘的宫头，不转换到共同历元，
也不考虑对象纬度来计算三维落宫。
两种操作在输出为空时仍检查请求。它们不执行天文计算、时区解析、版本查询或资源 I/O；
格式化函数使用调用方传入的目录。

Composite／Davison、行运搜索及解读不属于这些操作。
