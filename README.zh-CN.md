# celestial-astrology

[English](https://0xf3cd.github.io/astrology/README.html) | [简体中文](https://0xf3cd.github.io/astrology/README.zh-CN.html)

用于可复现西方占星排盘与知识查询的 Python 库。天文计算由
[celestial-calendar](https://github.com/0xf3cd/celestial-calendar) 提供；本仓记录占星规则、
出处和流派变体，并组织可复现的星盘结果。

本包提供不可变的[出生记录与现代时刻解析](https://0xf3cd.github.io/astrology/docs/zh-CN/birth.html)、
[排盘请求配置](https://0xf3cd.github.io/astrology/docs/zh-CN/configuration.html)、[热带本命盘计算](https://0xf3cd.github.io/astrology/docs/zh-CN/chart.html)、
[命盘结果与文本输出](https://0xf3cd.github.io/astrology/docs/zh-CN/records.html)、独立[知识目录](https://0xf3cd.github.io/astrology/docs/zh-CN/knowledge.html)、质量检查和双语 [API 文档](https://0xf3cd.github.io/astrology/docs/zh-CN/reference.html)。
天文库只在请求排盘时导入，导入本包或查询知识都不会初始化它。
运行检查见[参与开发](https://0xf3cd.github.io/astrology/docs/zh-CN/contributing.html)。

当前源码另提供两张内存本命盘之间的[静态交叉相位](https://0xf3cd.github.io/astrology/docs/zh-CN/cross_aspects.html)，
保留双侧来源及左右端点，不标运动状态。此 API 不在已发布的 v0.1.0 中。

当前源码还可用 `ashmand_sign_group(Sign.ARIES)` 不排盘查询十二星座在 Ashmand 1822 年版中的四组归属，
见[来源及查询示例](https://0xf3cd.github.io/astrology/docs/zh-CN/knowledge.html#ashmand-sign-groups-zh-cn)。
此 API 不在已发布的 v0.1.0 中。

安装随天文依赖而定：celestial-calendar 0.8.0 只发布 Linux x86_64 与 aarch64、
macOS 14+ arm64、Windows amd64 的轮子，没有源码分发包。其他平台无法安装本包，
连知识浏览也不可用。

## 安装发行版

分发包名是 `celestial-astrology`，Python 导入名仍是 `astrology`。
请勿安装 PyPI 上另一个无关的 `astrology` 项目。

请在上述支持的平台使用 **Python 3.11–3.14**。

以下命令安装已发布的 v0.1.0，其中包含命盘存取接口。当前源码为下一版撤回该接口；
下方的排盘和知识示例在两者中均可运行。

Linux/macOS（可把 `python3.14` 换成其他受支持的 Python 版本）：

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install "celestial-astrology==0.1.0"
```

Windows PowerShell：

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install "celestial-astrology==0.1.0"
```

运行依赖仍精确固定为 `celestial-calendar==0.8.0` 和 `tzdata==2026.5`，
可能与要求其他版本的应用发生依赖冲突。详见[发行说明](https://0xf3cd.github.io/astrology/docs/zh-CN/releases.html)。

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

把下面的 Python 脚本保存为 `first_chart.py`；它不是交互式终端记录。
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
0.1.0
2000-01-01T12:00:00+00:00
sun: capricorn
moon: scorpio
```

时间未知或缺少地点时会明确拒绝，不补正午或推测地点；请求的宫几何无定义时抛出
`ChartDomainError`，不改用另一宫制。
[排盘指南](https://0xf3cd.github.io/astrology/docs/zh-CN/chart.html)说明支持范围，
[结果指南](https://0xf3cd.github.io/astrology/docs/zh-CN/records.html)说明结构化结果与双语文本表格。

## 第一次查询知识

把这份独立脚本保存为 `first_knowledge.py`，用同一个虚拟环境的 Python 运行。
它读取包内目录，不排盘，也不初始化原生天文库；安装仍受上述平台限制。

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

可继续浏览[完整知识目录](https://0xf3cd.github.io/astrology/docs/zh-CN/catalog.html)或
[公开 API](https://0xf3cd.github.io/astrology/docs/zh-CN/reference.html)。
文档共用搜索索引，结果可能包含两种语言；中文采用相邻双字切分，不做语义匹配或词典分词。

## 首版目标

已知出生时刻和地点，计算现代热带黄道、地心本命盘：

- 保存出生原始记录，显式处理时区，保留最终时标与计算来源。
- 计算太阳、月亮、八颗行星及明确选择的月交点。
- 支持 Whole Sign（整宫制）、Equal（等宫制）、Placidus；请求的几何无定义时显式失败。
- 计算星座、二维黄经落宫（只用黄经，不用对象黄纬）、五大相位，以及可配置容许度和局部入相／离相状态。
- 输出不可变结构及文本表格，在内存中保留输入、配置、天文原值和模型身份。

位置、四轴、宫头、星座、落宫、相位及文本输出已实现。当前源码已撤回命盘持久化；
与已发布 v0.1.0 API 的差异见[发行说明](https://0xf3cd.github.io/astrology/docs/zh-CN/releases.html)。

交付任务与验收见 [v0.1.0 milestone](https://github.com/0xf3cd/astrology/milestone/1)。

## 设计边界

- [仓库结构与计算边界](https://0xf3cd.github.io/astrology/docs/zh-CN/architecture.html)
- [知识组织与双语文档](https://0xf3cd.github.io/astrology/docs/zh-CN/knowledge.html)
- [开发与审阅约定](https://0xf3cd.github.io/astrology/docs/zh-CN/contributing.html)

首版也要支持独立查知识：无需先排盘或加载原生天文库，就能找到概念、规则变体和出处。
来源状态、适用前提和展示资格分别记录。

项目指南与公开参考文档提供中英文。两种语言引用同一组标识、可执行规则和来源记录。
引文保留原文语言，译文单独标明。

## 后续方向

- [技术与展示](https://github.com/0xf3cd/astrology/milestone/2)：行运与返照、关系盘、
  流派规则、更多对象，以及星盘视图。
- [进阶技术与历史研究](https://github.com/0xf3cd/astrology/milestone/3)：主限、推运、
  不确定出生时间、历史输入、空间落宫与有来源的解释知识。

这些 milestone 记录方向，不设发布日期。每种技术在实现前须明确其定义、出处与参考案例。

## 许可证

项目代码、译文及本项目撰写的说明采用 [MIT](https://github.com/0xf3cd/astrology/blob/main/LICENSE)。历史引文保留其
[来源记录](https://0xf3cd.github.io/astrology/docs/zh-CN/knowledge.html#knowledge-source-definitions-zh-cn)注明的转载状态。
