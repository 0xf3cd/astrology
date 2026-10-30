# celestial-astrology

[English](https://0xf3cd.github.io/astrology/README.html) | [简体中文](https://0xf3cd.github.io/astrology/README.zh-CN.html)

用于可复现西方占星排盘与知识查询的 Python 库。天文计算由
[celestial-calendar](https://github.com/0xf3cd/celestial-calendar) 提供；本仓记录占星规则、
出处和流派变体，并组织可复现的星盘结果。

可以从已知出生时刻和地点计算热带地心本命盘，也可以不排盘，直接查询知识目录。
先运行下面的示例；完整约定见[使用指南](https://0xf3cd.github.io/astrology/docs/zh-CN/index.html)和
[API 参考](https://0xf3cd.github.io/astrology/docs/zh-CN/reference.html)。

当前源码另增[元素／模式分布与出生月相](https://0xf3cd.github.io/astrology/docs/zh-CN/summaries.html)、
[传统星座守护与四种状态](https://0xf3cd.github.io/astrology/docs/zh-CN/dignities.html)，
本命及静态双盘查询的[显式选四轴参与相位](https://0xf3cd.github.io/astrology/docs/zh-CN/aspects.html#axis-aspects-zh-cn)，
[双盘落宫和双语比较文本](https://0xf3cd.github.io/astrology/docs/zh-CN/cross_aspects.html)，
以及 [SVG 本命轮和相位矩阵](https://0xf3cd.github.io/astrology/docs/zh-CN/svg.html)，
计划随 0.3.0 交付。四轴（上升点、中天、下降点、天底）只有被显式选择后才参与相位。

0.2.0（开发中）新增：

- 两张本命盘之间的[静态交叉相位](https://0xf3cd.github.io/astrology/docs/zh-CN/cross_aspects.html)，保留两张源盘并区分左右对象，不标入相／离相。
- 用 `ashmand_sign_group(Sign.ARIES)` 查询十二星座在 Ashmand 1822 年版中的四组归属。见[来源及查询示例](https://0xf3cd.github.io/astrology/docs/zh-CN/knowledge.html#ashmand-sign-groups-zh-cn)。

## 安装发行版

安装随天文依赖而定：celestial-calendar 0.8.0 只发布 Linux x86_64 与 aarch64、
macOS 14+ arm64、Windows amd64 的轮子，没有源码分发包。其他平台无法安装本包，
连知识浏览也不可用。

分发包名是 `celestial-astrology`，Python 导入名仍是 `astrology`。
请勿安装 PyPI 上另一个无关的 `astrology` 项目。

请在上述支持的平台使用 **Python 3.11–3.14**。

当前源码准备 0.2.0。试用候选版请[从源码安装](https://0xf3cd.github.io/astrology/README.zh-CN.html#install-from-source-zh-cn)。
0.2.0 发布到 PyPI 后，再使用下面的命令。示例输出对应 0.2.0。

Linux/macOS（可把 `python3.14` 换成其他受支持的 Python 版本）：

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install "celestial-astrology==0.2.0"
```

Windows PowerShell：

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install "celestial-astrology==0.2.0"
```

运行依赖仍精确固定为 `celestial-calendar==0.8.0` 和 `tzdata==2026.5`，
可能与要求其他版本的应用发生依赖冲突。详见[发行说明](https://0xf3cd.github.io/astrology/docs/zh-CN/releases.html)。

<a id="install-from-source-zh-cn"></a>

## 从源码安装

若要安装文档对应的固定源码版本，使用[文档首页](https://0xf3cd.github.io/astrology/)标明提交号的快照安装命令。
若已下载或克隆所需源码，则在其根目录运行以下命令。安装需要联网下载构建依赖和精确钉版的运行依赖。

Linux/macOS（可把 `python3.14` 换成其他受支持的 Python 版本）：

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install .
```

Windows PowerShell：

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install .
```

这些命令安装本地源码。
开发检查使用 `uv sync --locked`，详见参与开发指南。

## 第一张命盘

把下面的 Python 脚本保存为 `first_chart.py`。
Linux/macOS 运行 `.venv/bin/python first_chart.py`，PowerShell 运行
`.venv\Scripts\python.exe first_chart.py`。
输入明确使用 UTC 偏移和合成坐标；本例不请求相位。

```python
from datetime import date, time, timedelta
from astrology import (
  BirthRecord,
  Body,
  ChartConfig,
  FixedOffset,
  HouseSystem,
  Location,
  TimePrecision,
  natal_chart,
  prepare_natal_input,
)

record = BirthRecord(
  date(2000, 1, 1),
  time(12, 0),
  FixedOffset(timedelta(0)),
  Location(0, 0),
  TimePrecision.MINUTE,
  {"example": "synthetic"},
)
config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ())
chart = natal_chart(prepare_natal_input(record), config)
print(chart.provenance.astrology_version)
print(chart.resolved.utc.isoformat())
for placement in chart.placements:
  print(f"{placement.identity.value}: {placement.sign.value}")
```

输出：

```text
0.2.0
2000-01-01T12:00:00+00:00
sun: capricorn
moon: scorpio
```

时间未知或缺少地点时会明确拒绝，不补正午或推测地点；请求的宫几何无定义时抛出
`ChartDomainError`，不改用另一宫制。
[排盘指南](https://0xf3cd.github.io/astrology/docs/zh-CN/chart.html)说明支持范围，
[结果指南](https://0xf3cd.github.io/astrology/docs/zh-CN/records.html)说明结构化结果与双语文本表格。

输出列出解析后的 UTC 时刻及每个所选对象的星座。修改 `ChartConfig.objects` 可以请求其他天体或交点；
用 `aspect_objects` 和显式容许度规则选择谁参与相位。

| 接下来要做什么 | 指南 |
|---|---|
| 解析当地钟点，或选择重复时刻 | [出生输入](https://0xf3cd.github.io/astrology/docs/zh-CN/birth.html) |
| 选择对象、相位参与者和容许度 | [配置](https://0xf3cd.github.io/astrology/docs/zh-CN/configuration.html) |
| 比较两张命盘 | [双盘相位与落宫](https://0xf3cd.github.io/astrology/docs/zh-CN/cross_aspects.html) |
| 绘制结果（源码接口） | [SVG 轮盘与矩阵](https://0xf3cd.github.io/astrology/docs/zh-CN/svg.html) |

## 第一次查询知识

把这份独立脚本保存为 `first_knowledge.py`，用同一个虚拟环境的 Python 运行。
下面按名称和别名查找太阳：

```python
from astrology import load_catalog

catalog = load_catalog()
print(catalog.concept("body.sun").name.text("zh-CN"))
print(catalog.lookup("日轮")[0].identifier)
```

输出：

```text
太阳
body.sun
```

[知识指南](https://0xf3cd.github.io/astrology/docs/zh-CN/knowledge.html)说明查询、引用和整理状态。
定义与出处可直接浏览[完整知识目录](https://0xf3cd.github.io/astrology/docs/zh-CN/catalog.html)。

## 支持的命盘

支持 Whole Sign（整宫制）、Equal（等宫制）和 Placidus，计算太阳、月亮、八颗行星及显式选择的月交点定义。
落宫只用黄经，不用对象黄纬。五大相位使用调用方提供的容许度；入相／离相描述局部运动，不预测未来事件。
结果把四轴与十二宫头分别保存。
不可变结果保留原始输入、解析后的时标、配置、未舍入天文值和具名模型。当前源码已撤回命盘持久化；
与已发布 v0.1.0 API 的差异见[发行说明](https://0xf3cd.github.io/astrology/docs/zh-CN/releases.html)。

## 设计边界

- [仓库结构与计算边界](https://0xf3cd.github.io/astrology/docs/zh-CN/architecture.html)
- [知识组织与双语文档](https://0xf3cd.github.io/astrology/docs/zh-CN/knowledge.html)
- [开发与审阅约定](https://0xf3cd.github.io/astrology/docs/zh-CN/contributing.html)

## 后续方向

- [技术与展示](https://github.com/0xf3cd/astrology/milestone/2)：行运与返照、关系盘、
  流派规则、更多对象，以及星盘视图。
- [进阶技术与历史研究](https://github.com/0xf3cd/astrology/milestone/3)：主限、推运、
  不确定出生时间、历史输入、空间落宫与有来源的解释知识。

这些 milestone 记录方向，不设发布日期。每种技术在实现前须明确其定义、出处与参考案例。

## 许可证

项目代码、译文及本项目撰写的说明采用 [MIT](https://github.com/0xf3cd/astrology/blob/main/LICENSE)。历史引文保留其
[来源记录](https://0xf3cd.github.io/astrology/docs/zh-CN/knowledge.html#knowledge-source-definitions-zh-cn)注明的转载状态。
