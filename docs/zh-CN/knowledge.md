# 知识组织与双语文档

[English](../en/knowledge.md) · [项目入口](../../README.zh-CN.md) · [结构设计](architecture.md)

知识目录可以查中英文名称和别名、查看规则定义，并找到引用的书籍或代码。
例如，可以用“日轮”查到太阳，也可以查白羊座在 Ashmand 1822 年版中属于哪一组。
这些查询不需要出生资料或先排盘。直接浏览见[完整目录](catalog.md)，下面介绍 Python 查询方法；
接口说明见 [API](reference.md)，排盘见[排盘指南](chart.md)。

## 不排盘，先查知识

```{doctest}
>>> from astrology.knowledge import ConceptKind, SourceVerification, load_catalog
>>> catalog = load_catalog()
>>> catalog.lookup("Sol")[0].identifier
'body.sun'
>>> catalog.lookup("日轮")[0] is catalog.lookup("Sun")[0]
True
>>> len(catalog.list_concepts(kind=ConceptKind.SIGN))
12
>>> catalog.concept("body.sun").configuration.name
'SUN'
>>> [rule.identifier for rule in catalog.list_variants(concept_id="body.sun")]
['rule.lilly1647.essential_dignities']
>>> catalog.filter_entries(concept_id="body.sun")[0].identifier
'entry.body_requests'
>>> len(catalog.filter_sources(verification=SourceVerification.VERIFIED))
10
>>> bool(catalog.version)
True
```

同一个概念可以有多个名称，但只有一个标识。例如，`Sun`、`Sol` 和“日轮”都指向 `body.sun`。
规则变体则记录某套具体定义，例如采用哪种宫制或月交点算法。天体名称和升降交点方向本身不另建规则。
太阳链接有来源依据的尊贵规则，其中含具体归属，不是重复太阳名称。
旧标识的处理见[规则标识变更](#首发前的规则标识变更)。

也可以查询[双盘相位比较](cross_aspects.md)采用的规则。
`entry.cross_aspect_evaluation` 是相关说明条目，`rule.project.cross_aspect_evaluation` 是它链接的规则。
查到条目只会返回说明，不会运行双盘比较：

```{doctest}
>>> comparison = catalog.entry("entry.cross_aspect_evaluation")
>>> comparison.prerequisite_status.value, comparison.output_eligibility.value, comparison.chart_applicability
('complete', 'reference_only', 'not_assessed')
```

这里的 `complete` 表示条目已经写清所需前提；`reference_only` 表示它仅供参考，
`not_assessed` 表示没有判断某张命盘是否满足这些前提。三者回答不同的问题，详见[状态说明](#状态需要分开表达)。

查询[双盘落宫](cross_aspects.md)时，使用独立的组合规则及其固定实现来源：

```{doctest}
>>> overlay = catalog.entry("entry.cross_house_overlays")
>>> overlay.rule_ids
('rule.project.cross_house_overlays', 'rule.project.cusp_ownership')
>>> citation, source = catalog.citations(overlay.identifier)[0]
>>> source.identifier
'source.astrology.house_overlays.f269d14'
>>> overlay.prerequisite_status.value, overlay.output_eligibility.value, overlay.chart_applicability
('complete', 'reference_only', 'not_assessed')
```

此项目规则区分对象所属盘与接收它的宫位所属盘，两侧独立选择对象，保留各自源盘的宫制。
代码引用记录的是实现，不认证天文来源，也不提供关系解读。检索不会计算落宫或判断某张命盘。

### 返回值与错误

`load_catalog()` 每次都从包内 JSON 文件读取目录，不访问网络，也不使用缓存。
构造记录时会把传入的序列复制为不可变元组。记录类型错误、标识重复、链接指向不存在的记录或别名冲突时，
会抛出 `TypeError` 或 `ValueError`；这些检查在 `python -O` 下仍然执行。

`lookup()` 先做 NFC 规范化、去首尾空白及大小写折叠，再精确匹配名称与别名。
结果为不可变元组：无匹配时返回 `()`，名称有歧义时返回多个不同的概念。
可用 `language="en"` 或 `language="zh-CN"` 限定语言，不选则查两种语言。
获取及筛选遇到格式正确但未知的标识时抛出 `KeyError`；格式不合法的字符串抛出 `ValueError`，
非字符串标识抛出 `TypeError`。条目筛选同时应用全部所选条件，从不判断前提。

(knowledge-source-definitions-zh-cn)=
## 从来源查到定义

目录目前包括：

- 排盘时可选的天体、四轴、宫制、月交点定义和相位，以及它们的中英文名称。
- 本项目如何划分十二星座、判断落宫（包括双盘落宫），以及计算单盘和双盘相位。
- Ashmand 1822 年版中的四组星座分类，以及相关书目、摘录和中文译文。
- [传统星座守护与四种状态](dignities.md)：依据 William Lilly（威廉·利利）的
  《Christian Astrology》（1647），含原扫描本短引文及生成的星座表。

配置项链接到程序实际使用的枚举成员；规则说明链接到对应的实现。
宫制、月交点定义和相位角各有说明，写明采用哪种定义及其限制。
参考页中的精确相位角直接取自计算代码，并核对说明文字中的角度。
目录不提供默认容许度或解读规则；尊贵归属由 `astrology.dignities` 定义。

例如，下面查看分点星座条目的出处、原文和译文，以及条目的状态：

```{doctest}
>>> entry = catalog.entry("entry.equinoctial_example")
>>> citation, source = catalog.citations(entry.identifier)[0]
>>> source.edition
'Davis and Dickson, London, 1822'
>>> citation.excerpt.en.startswith("There are also two equinoctial signs:")
True
>>> citation.excerpt.zh is not None
True
>>> source.verification.value, entry.prerequisite_status.value
('verified', 'unresolved')
>>> entry.output_eligibility.value, entry.chart_applicability
('reference_only', 'not_assessed')
>>> catalog.variant(entry.rule_ids[0]).configuration is None
True
```

引文定位至 Ashmand 对被归于 Proclus 的转述本所作英文译文：《第一卷》第 XIV 章，印刷页 34–35
（PDF 第 72–73 页）。{ref}`目录例子 <catalog-zh-cn-entry-equinoctial-example>`保留完整英文句子及单独署名的项目中文译文。
原文用昼夜等长解释这种命名；保留这段历史说明不表示程序保证实际日照时长。
来源已经核实（`verified`），但条目用于命盘解读时需要哪些条件仍未明确（`unresolved`）。
该条目标为 `reference_only`，供查阅，不作为命盘结论。
条目的陈述、定义和限制是项目撰写的说明，与引文分开。

来源记录给出版本、扫描文件哈希、转录时的文字处理和转载条件。包内只收录有限的定义摘录，
不附扫描图、水印或现代网站说明。同一本书的镜像和书目可以帮助确认版本，但不能当作多份独立依据。
代码引用给出包版本及固定提交中的符号；程序中的定义用了某位作者的名字，不表示已经核对过其原书公式。

项目实现来源记录保留已查核的提交，不跟随包版本改写。排盘来源记录还定位到同一提交中
`tests/test_reference.py` 的交点对拍测试。测试按其中记录的公式计算交点参考黄经，再与上游
结果比较。这不等于核验 Meeus 印刷原文、确立误差界或证明与密切轨道交点等价。

下面用手工构造的数据表示“只知道部分条件”的情况：第一个条件为真，第二个仍未知。
目录不会读取这个字典，也不会因此改变条目的命盘适用状态：

```{doctest}
>>> partial_evidence = {"condition_a": True, "condition_b": None}
>>> partial_evidence["condition_a"], partial_evidence["condition_b"]
(True, None)
>>> catalog.entry(entry.identifier).chart_applicability
'not_assessed'
```

内置条目均仅供参考。当前包不判断某张命盘是否符合条目，也不存储这种判断所需的命盘证据。

## 四轴的独立词汇

`axis.ascendant`、`axis.midheaven`、`axis.descendant` 和 `axis.imum_coeli` 是绑定到 `Axis`
的不同概念，不是天体、交点或宫头的别名。仅供参考的 `entry.axis_aspects` 说明项目的显式选择、
配对及缺速率政策，并引用固定修订的实现。原天体和交点来源仍保留原修订，不倒记为四轴扩展的证据。

```{doctest}
>>> from astrology import Axis
>>> catalog.concept("axis.ascendant").configuration is Axis.ASCENDANT
True
>>> axes = catalog.entry("entry.axis_aspects")
>>> axes.prerequisite_status.value, axes.output_eligibility.value, axes.chart_applicability
('complete', 'reference_only', 'not_assessed')
```

这些查询不需要命盘或原生天文库。计算几何时，见{ref}`本命显式选择 <axis-aspects-zh-cn>`及
{ref}`双盘各侧独立选择 <cross-axis-aspects-zh-cn>`。

(ashmand-sign-groups-zh-cn)=
## Ashmand 1822 年版星座分组

这四组出自 Ashmand 的 1822 年英译本 *Ptolemy's Tetrabiblos, or Quadripartite*。
0.2.0 新增 `ashmand_sign_group`，输入一个 `Sign`，即可查到它所属的组别：

```{doctest}
>>> from astrology import AshmandSignGroup, Sign, ashmand_sign_group
>>> from astrology.knowledge import load_catalog
>>> catalog = load_catalog()
>>> ashmand_sign_group(Sign.ARIES) is AshmandSignGroup.EQUINOCTIAL
True
>>> group = ashmand_sign_group(Sign.CANCER)
>>> group.value
'tropical'
>>> catalog.concept(f"sign_group.ashmand1822.{group.value}").name.text("zh-CN")
'至点星座'
>>> historical = catalog.entry("entry.ashmand_sign_groups")
>>> historical.prerequisite_status.value, historical.output_eligibility.value, historical.chart_applicability
('complete', 'reference_only', 'not_assessed')
```

字符串或其他枚举会抛出 `TypeError`；用户输入须显式转为 `Sign`。返回的是组别，不是评分或解读。
这里的 `complete` 只表示成员查询所需的条件已齐备：提供一个 `Sign` 即可。
前面分点星座条目的 `unresolved` 仍然保留，因为那是关于命盘解读条件的另一个问题。

四组中文名为**至点星座、分点星座、固定星座、双体星座**，对应 tropical、equinoctial、fixed、bicorporeal。
这里的 tropical 只指两个至点星座，不是热带黄道的全部十二星座。原文直接点名至点与分点两对星座。
在黄道次序中，固定星座分别紧接这些星座，双体星座分别紧接固定星座。因此
{ref}`十二星座表 <catalog-zh-cn-rule-ptolemy-ashmand-sign-groups>`是项目推导，不是原文逐项列举。

原文见第一卷第 XIV 章、印刷页 34–35（PDF 第 72–73 页），记录在 `source.ptolemy.ashmand1822` 中。
目录中的英文摘录、署名中文译文和项目说明分别标明，引用也注明了摘录范围。
这里依据的是 Ashmand 的这一版本，不能据此认为各流派都采用相同分类，也不能用组名预测实际天气或日照。

## 元素、模式与月相类型

这些输出概念有各自的类别及稳定标识：`element.*`、`modality.*`、
`lunation_type.rudhyar1950.*`，不链接请求配置。用法见[查询、统计及月相指南](summaries.md)。
已核的来源是 Astrodienst 网页快照和 Rudhyar 在线转录，未核 Rudhyar 的杂志原件。分类不作性格解读；
生成表读取各领域的可执行定义。

## 译文修订与搜索

当前文本格式以英文为原文或基准，中文译文单独署名。缺译是 `None`；旧译保留其修订号，
不用英文回退冒充中文：

```{doctest}
>>> from astrology.knowledge import LocalizedText
>>> LocalizedText("Original").status("zh-CN").value
'missing'
>>> old = LocalizedText("Revised", "旧译", revision=2, zh_revision=1, translation_credit="example translator")
>>> old.status("zh-CN").value, old.text("zh-CN")
('stale', '旧译')
```

必需翻译检查拒绝内置语料中的缺译或旧译；构造及参考页渲染仍能显式表达这些状态。

文档搜索使用英文词干及相邻汉字双字切分，不做词典分词、精确短语搜索或语义别名扩展。
单字查询只命中索引中的单字条目，例如显式别名 `日`、`月`；不支持任意单字子串查询。
精确从别名查身份请用 `Catalog.lookup()`。

## 增加有来源的变体

1. 查可取得的版本及转载条件，记录作品、作者或译者、版本、语言、定位、谱系、所支持的陈述及限度。
   未核材料如实标注，两个镜像不算两份来源。
2. 在 `src/astrology/knowledge/catalog.json` 添加稳定记录。引用所属枚举类与成员，
   不抄其值，也不虚构算法。只有承载规则时才另加显式变体，写明其定义与限制；配置链接本身
   不会生成变体。月交点的定义关联从 `LunarNode.definition` 派生，加载器还检查内置语料中
   十二个 Sign 与概念的身份对应。
   纯来源变体没有配置引用；条目关联变体标识及引用。
3. 区分引文、译文及原作陈述。`text_defaults` 提供初始修订 1 及项目译者署名，各文本可覆盖它们。
   文本改动时递增 `revision`；译文未经复核前保留原 `zh_revision`，复核后再更新修订及署名。
4. 写清前提、例外及限度；独立选择来源查核、前提完整性与输出资格。
   即使一个条件可算，检索仍须将命盘适用性留为 `not_assessed`。
   缺乏依据的解释不进入默认语料。
5. 补充边界与来源测试，运行[完整检查](contributing.md)，核双语生成页。
   检查覆盖当前译文、完整配置／目录／API 及安装资源；语义审阅仍须核译意与来源保真。

## 首发前的规则标识变更

语料 `2026.10.21.1` 移除十四条仅重复请求身份的自动变体，保留其概念、别名、配置链接和条目。
`entry.body_requests` 与 `entry.node_directions` 的 `rule_ids` 现为空；条目原本就允许这种形状。
移除的标识如下：

```text
rule.body.sun
rule.body.moon
rule.body.mercury
rule.body.venus
rule.body.mars
rule.body.jupiter
rule.body.saturn
rule.body.uranus
rule.body.neptune
rule.body.pluto
rule.node.mean_ascending
rule.node.mean_descending
rule.node.meeus_five_term_true_ascending
rule.node.meeus_five_term_true_descending
```

`variant()` 遇到这些标识会抛出 `KeyError`，不提供别名或隐式转换为概念。
移除纯身份规则不限制后续增加有实质内容的规则：太阳、月亮及水星至土星现在关联到
Lilly《Christian Astrology》（1647）所载的尊贵与弱势规则。保留的身份信息可用 `concept()`、`lookup()`
或 `filter_entries()` 查询。三条 `rule.house.*`、两条 `rule.node_definition.*`、五条
`rule.aspect.*` 以及原有九条显式规则标识均保留，相对顺序不变：十条带配置链接的规则在前，
原有九条显式规则在后。该修订当时含 19 条变体，概念、来源和条目数量仍为 36、3 和 8。
来源状态、前提完整性、输出资格和命盘适用性仍各自独立。

新增双盘判断后，已有规则标识保持不变，参与者规则限定用于单盘判断，运动规则限定用于同一时刻的速率。

## 记录与归属

概念、规则变体、来源与知识条目使用稳定、与语言无关的标识。这些是记录职责，
不要求每种职责都独占一个类或文件。

| 记录 | 保存什么 |
|---|---|
| 概念 | 身份、种类、中英文名称与别名、相关概念 |
| 规则变体 | 定义、流派、适用范围；可执行时链接实现 |
| 来源 | 书名／作者、版本、定位、原文语言、来源谱系、支持的论断与限度 |
| 知识条目 | 陈述、关联概念／规则／来源、前提、例外、限度及整理状态 |

可执行常量与规则表归领域实现。知识条目链接规则标识，生成的参考表读取可执行定义。
解释文字说明原因与范围，不再维护第二份计算规则表。

原文引述、译文、仓内原作说明是不同文本层。译文标明对应原文；同一来源的多个译本
不构成独立证据。保留原文措辞与定位，并记录收录材料的转载权限。

## 状态需要分开表达

查到出处，不等于已经知道一条规则用于命盘时需要什么条件；写清条件，也不等于某张命盘已经满足它。
所以条目分别记录以下状态：

| 问题 | 字段及取值 | 怎样理解 |
|---|---|---|
| 出处核实了吗？ | `source.verification`：`verified`／`unverified` | 表示是否查核过所列来源，不是认定历史主张为真。 |
| 所需前提写清了吗？ | `entry.prerequisite_status`：`complete`／`unresolved` | 表示前提已理解并表达完整，或仍有未明确之处。 |
| 条目可以进入默认输出吗？ | `entry.output_eligibility`：`eligible`／`reference_only` | 是条目的整理决定；`eligible` 也不表示某张命盘满足前提。 |
| 某张命盘符合条件吗？ | `entry.chart_applicability`：`not_assessed` | 查询目录没有做这种判断，不论上面三个状态如何。 |

将来若增加命盘条件判断，需要区分满足、不满足和未知。只验证部分条件时，只能返回部分证据。
例如，一条陈述同时要求相位、昼夜派与尊贵状态，程序只算出相位，不能声称整条前提成立。

相关设计：[bazi](https://github.com/0xf3cd/bazi)。

## 双语入口

- `README.md` 与 `README.zh-CN.md` 提供内容对应的项目入口。
- 指南与解释采用 `docs/en/`、`docs/zh-CN/` 下的对应路径，互链另一语言页面，覆盖同一支持范围。
- 公开 API 文档提供中英文说明、约束与例子。签名、单位、默认值、标识和异常行为只定义一次。
  公开 docstring 的概述和使用约定保留双语；两种语言共用签名与参数表。
- 每个概念／条目只有一个语义身份，附带各语言文本。记录译文对应的语义修订；
  缺译或过期须可见，不能静默换成另一语言并当作翻译完成。
- 原文保留原语言，读者选择译文后仍能找到原文。
- 生成的[目录](catalog.md)标明代码与语料版本。
  检查及语义审阅见[参与开发](contributing.md)。

显示语言不能改变计算。不同定义不能因为中文译名相同就合成一个对象。
检索支持两种语言及别名，返回稳定身份。
