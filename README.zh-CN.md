# astrology

[English](README.md) | [简体中文](README.zh-CN.md)

开发中的 Python 西方占星排盘与知识库。天文计算将由
[celestial-calendar](https://github.com/0xf3cd/celestial-calendar) 提供；本仓记录占星规则、
出处和流派变体，并组织可复现的星盘结果。

开发包提供不可变的[出生记录与现代时刻解析](docs/zh-CN/birth.md)、
[排盘请求配置](docs/zh-CN/configuration.md)、质量检查和双语 [API 文档](docs/zh-CN/reference.md)。
尚未实现排盘与知识查询 API；导入包不会导入或初始化天文库。
运行检查见[参与开发](docs/zh-CN/contributing.md)。

## 首版目标

已知出生时刻和地点，计算现代热带黄道、地心本命盘：

- 保存出生原始记录，显式处理时区，保留最终时标与计算来源。
- 计算太阳、月亮、八颗行星及明确选择的月交点。
- 支持 Whole Sign（整宫制）、Equal（等宫制）、Placidus；请求的几何无定义时显式失败。
- 计算星座、二维黄经落宫、五大相位，以及可配置容许度和局部入相／出相状态。
- 输出不可变结构、文本表格与带版本的序列化，保留输入、配置、天文原值和模型身份。

交付任务与验收见 [v0.1.0 milestone](https://github.com/0xf3cd/astrology/milestone/1)。

## 设计边界

- [仓库结构与计算边界](docs/zh-CN/architecture.md)
- [知识组织与双语文档](docs/zh-CN/knowledge.md)
- [开发与审阅约定](docs/zh-CN/contributing.md)

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

[MIT](LICENSE)。
