# 传统守护、尊贵状态与定位星链

[English](../en/dignities.md) · [API](reference.md) · [知识](knowledge.md)

`sign_ruler` 和 `essential_dignities` 采用 William Lilly（威廉·利利）的
《Christian Astrology》（伦敦，1647）所载规则，适用于太阳、月亮、水星、金星、火星、木星和土星。
这七颗星体在传统占星中称为 seven classical planets。

这些判断属于传统占星的本质尊贵与弱势（essential dignities and debilities）。本接口仅判断
入庙（domicile）、擢升（exaltation）、失势（detriment）、落陷（fall）四种星座级状态。

`rule.lilly1647.essential_dignities` 是这套固定规则的标识，用于对应代码实现、
`HouseRulers.rule_id` 和知识目录记录，不负责动态加载或选择规则。

## 离盘查询星座

<!-- usage: dignities.lookup -->

用 `sign_ruler` 查询一个星座的传统守护星；用 `essential_dignities` 查询某颗星体在某个星座的四种状态。
例如，天蝎座的守护星是火星，水星在处女座同时入庙、擢升，在双鱼座则同时失势、落陷：

```{doctest}
>>> from astrology import Body, Sign, DignityStatus, sign_ruler, essential_dignities
>>> sign_ruler(Sign.SCORPIO) is Body.MARS
True
>>> essential_dignities(Body.MERCURY, Sign.VIRGO)
(<DignityStatus.DOMICILE: 'domicile'>, <DignityStatus.EXALTATION: 'exaltation'>)
>>> essential_dignities(Body.MERCURY, Sign.PISCES)
(<DignityStatus.DETRIMENT: 'detriment'>, <DignityStatus.FALL: 'fall'>)
>>> essential_dignities(Body.SUN, Sign.TAURUS)
()
```

全部命中按入庙、擢升、失势、落陷的顺序返回。入庙指行星位于自己的某一守护星座；
原文在此所说的 houses 不是命盘编号宫位。擢升覆盖所定的整个星座。
失势与某一入庙星座相对，落陷与擢升星座相对。具体归属见
{ref}`生成的十二星座表 <catalog-zh-cn-rule-lilly1647-essential-dignities>`。

空元组表示**这四项均未命中**，不等于游离，因为其他尊贵尚未判断。
字符串、交点及无关枚举抛出 `TypeError`；应传入确切的 `Body` 和 `Sign` 成员。
有效的外行星枚举（`URANUS`、`NEPTUNE`、`PLUTO`）抛出点明该对象的 `ValueError`，
不会返回空状态冒充已判断。
天蝎由火星守护，水瓶由土星守护，双鱼由木星守护，不替换为现代共守护星。

<!-- /usage: dignities.lookup -->

## 跟随已有命盘的宫主星

合成示例只计算一次，随后读取已有宫头和落点：

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (BirthRecord, FixedOffset, Location, ChartConfig, HouseSystem,
...     natal_chart, prepare_natal_input, HouseRulers, format_house_rulers, load_catalog)
>>> chart = natal_chart(prepare_natal_input(BirthRecord(date(2000, 1, 1), time(12),
...     FixedOffset(timedelta(0)), Location(0, 0))),
...     ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MERCURY), ()))
>>> result = HouseRulers(chart)
>>> result.chart is chart, len(result.houses), result.rule_id
(True, 12, 'rule.lilly1647.essential_dignities')
>>> first = result.houses[0]
>>> first.house, first.cusp_sign.value, first.ruler.value, first.placement, first.statuses
(1, 'aries', 'mars', None, None)
>>> third = result.houses[2]
>>> third.ruler.value, third.placement is chart.placements[1], third.statuses
('mercury', True, ())
>>> catalog = load_catalog()
>>> text = format_house_rulers(result, catalog, language="zh-CN")
>>> print("\n".join(text.splitlines()[:5]))
宫主星（Lilly 1647）
宫制: 整宫制
规则: rule.lilly1647.essential_dignities
宫位 | 宫头星座 | 宫主星 | 宫主星落点 | 状态
1 | 白羊座 | 火星 | 未计算 | 未计算
>>> print(text.splitlines()[6])  # doctest: +ELLIPSIS
3 | 双子座 | 水星 | 摩羯座 1.889...° / 宫位 10 | 这四项均未命中
```

`HouseRulers` 只保存给定的 `NatalChart`。每次读取 `houses`，按宫号顺序生成十二条新记录；
两次读取所得的元组相等。使用**实际宫头黄经**，不借 ASC 或 MC 代替一宫头或十宫头。重复宫头星座仍保留为不同宫的记录。
请求的宫制和原始天文值不变；不重算或补入宫主星，可用落点保留源盘中的原对象。

`placement=None` 且 `statuses=None` 表示未计算宫主星位置；已有落点但 `statuses=()`
表示已判断而四项均未命中。文本明确区分两者，并显示全部同时命中的状态。
宫主星落点包括其星座、未舍入的星座内度数和编号宫位；状态只依星座判断，不依显示的度数。

### 单独构造一条记录

```{doctest}
>>> from astrology import HouseRuler, Placement
>>> placement = Placement(Body.MERCURY, Sign.VIRGO, 0, 6)
>>> record = HouseRuler(house=3, cusp_sign=Sign.GEMINI, placement=placement)
>>> record.ruler is Body.MERCURY, record.statuses == essential_dignities(Body.MERCURY, Sign.VIRGO)
(True, True)
>>> record.placement is placement
True
```

`HouseRuler` 不可变，`ruler` 和 `statuses` 从字段推导，不能单独传入。
单条记录接受宫头星座；若要从命盘的编号宫头推导这个星座，请用 `HouseRulers(chart)`。
字段校验见[守护 API 参考](reference.md#传统守护与本质尊贵)。

### 格式化与错误

`format_house_rulers` 要求传入 `Catalog` 及 `en` 或 `zh-CN` 的当前名称。
名称中的表格分隔符及不可打印字符会转义。
[命盘和比较表格](records.md#显示不改分类)把角度截断到整角秒；宫主星表的星座内度数则显示为存储的十进制浮点值。
上面的示例用 `...` 省略了部分数字，实际输出会保留完整的浮点值。状态仍只依星座判断。
格式化的错误行为见[文本 API 参考](reference.md#命盘文本)。

## 跟随定位星链

<!-- usage: dignities.dispositors -->

一个落点的定位星（dispositor）是它所在星座的传统守护星。用 `chart_dispositors`
继续查询这颗守护星的落点，直到路径到达自环、循环，或命盘中缺少的守护星。

下面的完整合成示例计算十颗天体，但只选太阳和月亮作为起点：

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (BirthRecord, Body, ChartConfig, FixedOffset, HouseSystem,
...     Location, natal_chart, prepare_natal_input, chart_dispositors)
>>> birth = prepare_natal_input(BirthRecord(date(2000, 1, 1), time(12),
...     FixedOffset(timedelta(0)), Location(0, 0)))
>>> chart = natal_chart(birth, ChartConfig(HouseSystem.WHOLE_SIGN, tuple(Body), ()))
>>> paths = chart_dispositors(chart, objects=(Body.MOON, Body.SUN))
>>> paths.chart is chart, tuple(body.value for body in paths.objects)
(True, ('sun', 'moon'))
>>> tuple(body.value for body in paths.chains[Body.SUN])
('sun', 'saturn', 'venus', 'jupiter', 'mars')
>>> paths.edges[Body.MARS] is Body.SATURN
True
>>> tuple(tuple(body.value for body in cycle) for cycle in paths.cycles)
(('venus', 'jupiter', 'mars', 'saturn'),)
>>> paths.final_dispositors, dict(paths.missing_rulers)
((), {})
```

太阳在摩羯座，指向土星，再经过金星、木星、火星。火星又指回土星：`edges`
保留这条闭环边，`chains[Body.SUN]` 则在土星重复前停止。太阳是通往四星循环的前缀，
不是循环成员。月亮也到达同一循环，因此 `cycles` 只列一次。
土星、金星、木星和火星虽未选作根，其已有落点仍可用于遍历。

<!-- /usage: dignities.dispositors -->

其他终点这样读取：

- `final_dispositors` 列出已到达且位于自身守护星座的星体。`edges` 保留其自环边；
  对于到达该星体的根，`chains[root]` 只列一次这颗星体。
- `cycles` 中的两星循环表示本规则下基于入庙守护的互容。示例这样的较长循环不称为互容。
- `missing_rulers[root]` 给出该根缺失的下一颗守护星。路径止于最后一个已有对象，
  指向缺失守护星的边仍保留。

例如，只含这颗太阳的命盘无法继续到土星：

```{doctest}
>>> sparse = natal_chart(birth, ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ()))
>>> incomplete = chart_dispositors(sparse, objects=(Body.SUN,))
>>> incomplete.chains[Body.SUN], incomplete.missing_rulers[Body.SUN]
((<Body.SUN: 'sun'>,), <Body.SATURN: 'saturn'>)
```

接口不补算缺失位置，只报告从选定根到达的部分。多个根可以有不同的最终定位星或循环。
复数 `final_dispositors` 不表示已确立唯一的全盘主星。

`Dispositors(chart, objects)` 可直接构造相同的不可变结果。选择会复制并按命盘落点顺序排列，
不沿用参数顺序。`edges` 的键、根对象及最终定位星均按源盘顺序排列。
每个循环保留边的方向，以源盘中最早的成员起头；多个循环也按各自的首成员排列。
全部映射只读，路径、循环及终点列表均为元组。

须显式传入非空序列，成员为已有落点的 `Body` 或 `LunarNode`。
外行星及具名交点可以起头，后继仍用七颗传统星体的星座守护关系。
四轴及宫头不作根。错误命盘类型、非序列、字符串或错误身份类型抛出 `TypeError`；
空、重复或不可用的根抛出 `ValueError`。不可用的根属于输入错误，与有效链中缺失后继区分。

`paths.rule_id` 为 `rule.project.dispositor_chains`。
{ref}`项目规则 <catalog-zh-cn-rule-project-dispositor-chains>`在不变的 Lilly 星座守护表之上
定义遍历及结果顺序；{ref}`知识条目 <catalog-zh-cn-entry-dispositor-chains>`记录来源边界及
入庙互容的限度。不提供评分、解读、现代共同守护星或专用格式化函数。

## 来源与限制

归属及推导方式见{ref}`规则与生成表 <catalog-zh-cn-rule-lilly1647-essential-dignities>`；
版本、扫描本、转录约定及研究限度见{ref}`来源记录 <catalog-zh-cn-source-lilly-christian-astrology-1647>`。
目录分别标明原文摘录、署名中文译文和项目说明。

四种状态查询不判断精确擢升度数、昼夜条件、交点尊贵、三分性、界、面、互容、综合评分或解读。
原文的昼夜庙标签不作为四项星座查询的额外条件。

目录状态概念使用 `dignity_status.<value>`，不链接请求配置。
`entry.essential_dignities` 的查询前提完整，但仍为 `reference_only` 和 `not_assessed`。
目录检索不执行命盘判断。
