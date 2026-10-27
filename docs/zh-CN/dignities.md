# 传统星座守护与四种状态

[English](../en/dignities.md) · [API](reference.md) · [知识](knowledge.md)

这些源码接口计划随 0.3.0 交付，已发布的 0.2.0 包尚不包含。采用 William Lilly（威廉·利利）的
《Christian Astrology》（伦敦，1647）所载规则，适用于太阳、月亮、水星、金星、火星、木星和土星。
这七颗星体在传统占星中称为 seven classical planets。

这些判断属于传统占星的本质尊贵与弱势（essential dignities and debilities）。本接口仅判断
入庙（domicile）、擢升（exaltation）、失势（detriment）、落陷（fall）四种星座级状态。

`rule.lilly1647.essential_dignities` 是这套固定规则的标识，用于对应代码实现、
`HouseRulers.rule_id` 和知识目录记录，不负责动态加载或选择规则。

## 离盘查询星座

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
>>> text.splitlines()[6].endswith("这四项均未命中")
True
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
字段类型错误抛出 `TypeError`，包括把布尔值当宫号；宫号不在 1–12 或落点身份不等于所推导的
宫主星时抛出 `ValueError`。低层记录不核实命盘来源，也不把宫头星座与宫号绑定；
`HouseRulers(chart)` 完成这项组合。它拒绝非 `NatalChart` 输入，抛出 `TypeError`，
且不接受另行传入宫记录元组。运行时检查在 `python -O` 下仍执行。

`format_house_rulers` 要求传入 `Catalog` 及 `en` 或 `zh-CN` 的当前名称。
结果或目录类型错误抛出 `TypeError`；语言非法、名称缺译或过期抛出 `ValueError`；
星座或状态标识缺失抛出 `KeyError`；目录中某个宫主星或宫制没有唯一对应的概念时，格式化抛出 `ValueError`。
名称中的表格分隔符及不可打印字符会转义。
格式化不读取资源；纯查询和盘级组合不初始化原生天文库。

## 来源与限制

{ref}`来源记录 <catalog-zh-cn-source-lilly-christian-astrology-1647>`定位已核的 Wellcome 扫描本、
1647 年出版页、图像摘要及 Public Domain Mark 声明。第一卷第 VIII–XIV 章给出行星归属，
第 XVIII 章及印刷页 102、104–105 说明擢升覆盖整个星座和相对星座关系。
行星章节直接列出其中六颗星体的失势，土星失势由其入庙星座及所述关系推出。
生成表由项目按这些归属展开，不是逐格转录整张印刷表。

三段简短英文引文与署名中文译文、项目解释分别呈现。定位信息写明截取边界；
长 s 字形、换行及占星符号按记录作了规范化。另一份扫描可旁证同一历史文本的字形，
不构成独立传统。Lilly 称其表依据 Ptolemy；此处未核 Ptolemy 原文。

接口不判断精确擢升度数、昼夜条件、交点尊贵、三分性、界、面、互容、综合评分或解读。
原文的昼夜庙标签不作为四项星座查询的额外条件。来源核验只记录该版本说了什么，
不确立实证有效性。

目录状态概念使用 `dignity_status.<value>`，不链接请求配置。
`entry.essential_dignities` 的查询前提完整，但仍为 `reference_only` 和 `not_assessed`。
目录检索不执行命盘判断。
