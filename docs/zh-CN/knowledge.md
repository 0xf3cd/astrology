# 知识组织与双语文档

[English](../en/knowledge.md) · [项目入口](../../README.zh-CN.md) · [结构设计](architecture.md)

开发包已提供独立于命盘的知识目录：无需出生资料或原生天文库，即可列概念与变体、查双语名称与别名、
筛选条目及来源、查看引用。尚未实现排盘。参见生成的[目录](catalog.md)与 [API](reference.md)。

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
>>> catalog.list_variants(concept_id="body.sun")[0].configuration.name
'SUN'
>>> catalog.filter_entries(concept_id="body.sun")[0].identifier
'entry.body_requests'
>>> len(catalog.filter_sources(verification=SourceVerification.VERIFIED))
2
>>> bool(catalog.version)
True
```

每次 `load_catalog()` 均显式读取包内 JSON，不使用缓存或网络。构造时将序列复制为元组。
非法记录类型、重复标识、悬空链接和别名冲突会抛出 `TypeError` 或 `ValueError`，
即使在 `python -O` 下也如此。

`lookup()` 先做 NFC 规范化、去首尾空白及大小写折叠，再精确匹配名称与别名。
结果为不可变元组：无匹配为 `()`，歧义显示名称返回多个不同身份。
可用 `language="en"` 或 `language="zh-CN"` 限定语言，不选则查两种语言。
获取及筛选遇到未知标识时抛出 `KeyError`；条目筛选同时应用全部所选条件，从不判断前提。

## 从来源查到定义

语料收录项目配置合同及一条单源历史分组，列出全部接纳的配置身份和十二个星座概念，
不提供星座边界、宫位几何、交点公式、相位角度、默认容许度、尊贵或解释规则。
请求变体引用实际配置枚举成员，不表示天文算法已实现。

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

引文定位至 Ashmand 经署名 Proclus 的转述本所作译文：《第一卷》第 XIV 章，印刷页 34–35
（PDF 第 72–73 页）。{ref}`目录例子 <catalog-zh-cn-entry-equinoctial-example>`保留完整英文句子及单独署名的项目中文译文。
原文的昼夜等长历史理由保留，但不认可为实际日照时长保证。
条目陈述、定义及限度是项目说明，不是额外引文。

来源记录说明版次、扫描文件哈希、转录规范化及有限的转载状态；仅收录一段短文，
不附带扫描图、水印或现代网站说明。镜像及书目可旁证版本，不能算规则的独立作者。
配置引用标明包版本及固定提交中的符号；项目定义名称含作者名，不表示已核验该作者书中的公式。

下方是合成的部分证据，不是传统断言或判别 API。目录不消费它，也不将条目提升为适用：

```{doctest}
>>> partial_evidence = {"condition_a": True, "condition_b": None}
>>> partial_evidence["condition_a"], partial_evidence["condition_b"]
(True, None)
>>> catalog.entry(entry.identifier).chart_applicability
'not_assessed'
```

内置条目均仅供参考；即使标为 `eligible`，也只表示整理层面的输出资格，不表示命盘满足条件。
当前包没有判别器或命盘证据存储；未来判别须保留未知及部分证据。

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

文档搜索保留英文词干处理，将汉字连续段切成重叠的相邻双字；Python 索引及生成的 JavaScript 查询
使用同一双字算法，不做词典分词、精确短语搜索或语义别名扩展。
验收用例含 `太阳`、`日轮`、`牡羊座`、`平均北交点` 和 `普拉西度制`。
单字查询只命中索引中的单字块，显式别名 `日`、`月` 有这样的块；不支持任意单字子串查询。
精确从别名查身份请用 `Catalog.lookup()`。

## 增加有来源的变体

1. 查可取得的版本及转载条件，记录作品、作者或译者、版本、语言、定位、谱系、所支持的陈述及限度。
   未核材料如实标注，两个镜像不算两份来源。
2. 在 `src/astrology/knowledge/catalog.json` 添加稳定记录。引用所属枚举类与成员，
   不抄其值，也不虚构算法。加载器从同一链接生成 `rule.<concept-id>` 请求变体。
   纯来源变体没有配置引用；条目关联变体标识及引用。
3. 区分引文、译文及原作陈述。`text_defaults` 提供初始修订 1 及项目译者署名，各文本可覆盖它们。
   文本改动时递增 `revision`；译文未经复核前保留原 `zh_revision`，复核后再更新修订及署名。
4. 写清前提、例外及限度；独立选择来源查核、前提完整性与输出资格。
   即使一个条件可算，检索仍须将命盘适用性留为 `not_assessed`。
5. 补充边界与来源测试，运行[完整检查](contributing.md)，核双语生成页。
   检查覆盖当前译文、完整配置／目录／API 及安装资源；语义审阅仍须核译意与来源保真。

## 记录与归属

概念、规则变体、来源与知识条目使用稳定、与语言无关的标识。这些是记录职责，
不要求每种职责都独占一个类或文件；首个 schema 要用少量真实语料检验。

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

[bazi](https://github.com/0xf3cd/bazi) 的 `knowledge.py` 与 `context_matching.py`
已经将以下问题分开：

1. 所列出处核实了吗？
2. 条目的前提已理解并表达清楚了吗？
3. 条目可以进入默认输出吗？
4. 某张具体命盘满足已经表达的前提吗？

占星仓沿用这个区分，具体枚举值与默认展示规则按本领域设计，不照搬 bazi。
出处核实不能单独证明适用；检索到相关陈述，也不能证明它适用于当前盘。

将来的判别器须区分满足、不满足、未知。只验证部分条件时，只能返回部分证据。
例如，一条陈述同时要求相位、昼夜派与尊贵状态，程序只算出相位，不能声称整条前提成立。

## 双语入口

- `README.md` 与 `README.zh-CN.md` 提供内容对应的项目入口。
- 指南与解释采用 `docs/en/`、`docs/zh-CN/` 下的对应路径，互链另一语言页面，覆盖同一支持范围。
- 公开 API 文档提供中英文说明、约束与例子。签名、单位、默认值、标识与错误合同只有一份来源。
  公开 docstring 的概述／合同保留双语，语言视图不再各维护一套签名或参数表。
- 每个概念／条目只有一个语义身份，附带各语言文本。记录译文对应的语义修订；
  缺译或过期须可见，不能静默换成另一语言并当作翻译完成。
- 原文保留原语言，读者选择译文后仍能找到原文。

显示语言不能改变计算。不同定义不能因为中文译名相同就合成一个对象。
检索支持两种语言及别名，返回稳定身份。

## 首个可用范围

先整理本命盘实际使用的天体、星座、宫制、交点定义和主要相位。
为这些定义补足可核验来源；缺乏依据的解释不进入默认语料。

目录支持列概念／变体、按名称与别名查找、过滤条目与来源、独立查看引用。
交付一组有原文、明确标记的译文、规则引用及有条件／前提待定条目的完整例子，
验证这些条目不会自动变成当前命盘适用的结论。

以后再扩展解释知识与前提判别。图数据库或通用规则引擎须由实际查询需求决定，
不因未来技术清单很长而预先引入。

## 文档检查

API 和知识目录参考页从各自定义生成。手写指南按读者任务组织：排一张盘、比较配置、
查知识、看出处、增加有来源的变体。

首次文档实现检查双语页面覆盖、稳定条目链接、必需翻译覆盖、未知引用、重复标识与两种语言的可执行例子。
除了构建成功，还要核实际 HTML：成员或说明漏掉，构建仍可能全绿。
翻译语义审阅检查前提与限度是否保真，单比标识不能证明译文正确。

发布文档标明代码／语料版本，区分开发页与已发布页。部署另行执行；当前 Markdown 文档就是可读入口。
