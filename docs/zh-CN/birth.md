# 出生记录与现代时刻解析

[English](../en/birth.md) · [文档](index.md) · [API 参考](reference.md)

民用记录与解析后的时刻分开保存。下例均为合成数据；这些 API 准备输入，不计算命盘。

## 保留已知信息

`BirthRecord` 保存延伸公历 `datetime.date`、可缺省的无时区 `datetime.time`、时区输入、地点、
所声明的钟点精度及来源元数据。仅接纳 `calendar="gregorian"`，不执行历法转换，包括儒略历转换。
未知钟点或地点保持为 `None`。

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import BirthRecord, MissingBirthDataError, prepare_natal_input
>>> unknown = BirthRecord(date(2000, 1, 1))
>>> (unknown.birth_time, unknown.location, unknown.precision)
(None, None, None)
>>> try:
...   prepare_natal_input(unknown)
... except MissingBirthDataError as exc:
...   print(type(exc).__name__)
MissingBirthDataError
```

不代填正午或地点。`TimePrecision` 记录小时、分钟、秒或微秒精度，比所声明单位更小的钟点字段须为零。
`None` 表示精度未声明，不代表不确定区间。未知钟点不能声明钟点精度。
时区和 fold 另行传入：记录中的钟点若携带 `tzinfo` 或 `fold=1` 会被拒绝，不能成为第二种隐式输入渠道。

`Location` 使用有限的角度：纬度 `[-90, 90]`、经度 `[-180, 180]`，北纬和东经为正。
不对越界值取模。两极及经度两端都是有效的记录值，但不保证对应宫位几何可用。

## 选择有歧义的时刻

`IanaTimezone` 要求普通字符串，各非空段仅含 ASCII 字母、数字、`_`、`+` 或 `-`，以斜线分隔。
形状无效时，构造函数抛出 `ValueError`。解析时按包内时区标识列表检查精确匹配和大小写；
未知标识抛出 `ValueError`。
IANA 数据通过 `ZoneInfo.from_file` 显式读取自已安装的钉版 `tzdata`，结果不由系统时区数据库或标识缓存决定。

```{doctest}
>>> from astrology import (
...   AmbiguousBirthTimeError, IanaTimezone, Location, TimePrecision,
...   resolve_birth_time,
... )
>>> source = {"record": "synthetic"}
>>> record = BirthRecord(
...   date(2026, 4, 5), time(1, 45), IanaTimezone("Australia/Lord_Howe"),
...   Location(0, 0), TimePrecision.MINUTE, source,
... )
>>> source["record"] = "edited by caller"
>>> record.source["record"]
'synthetic'
>>> try:
...   resolve_birth_time(record)
... except AmbiguousBirthTimeError as exc:
...   print(type(exc).__name__)
AmbiguousBirthTimeError
>>> earlier = prepare_natal_input(record, fold=0)
>>> later = prepare_natal_input(record, fold=1)
>>> (earlier.utc.isoformat(), later.utc.isoformat())
('2026-04-04T14:45:00+00:00', '2026-04-04T15:15:00+00:00')
>>> (later.record.birth_time.isoformat(), later.fold, later.timezone_identity)
('01:45:00', 1, 'Australia/Lord_Howe')
```

解析器将两种 fold 候选往返转换到 UTC，按 UTC 时刻去重。空缺没有有效候选，抛出
`NonexistentBirthTimeError`；重叠须显式选择 `fold=0`（较早）或 `fold=1`（较晚）。
时钟调整不一定是一小时。唯一钟点或固定偏移不接受 fold 选择。
浮点数、布尔值，以及整数 0、1 以外的值，均不是有效的 fold 选择。

`ResolvedBirth` 保留原始记录，另存 UTC、实际偏移、fold 选择、IANA 标识、发行包版本和 IANA 版本。
其构造函数检查形状及原始钟点是否保留为 UTC 加偏移，不加载时区规则核实手动提供的偏移、fold 或版本。
需要校验实际候选并读取其数据版本时，使用 `resolve_birth_time`。

```{doctest}
>>> from importlib import import_module
>>> from importlib.metadata import version
>>> later.timezone_source
'tzdata'
>>> later.tzdata_version == version("tzdata")
True
>>> later.iana_version == import_module("tzdata").IANA_VERSION
True
```

发行包版本和 IANA 版本是不同标识，分别来自 `tzdata.__version__` 和 `tzdata.IANA_VERSION`。
导入 `astrology` 不读取时区资源，也不初始化原生天文库。

## 解析显式偏移

`FixedOffset` 接受严格介于 -24 和 +24 小时之间的 `datetime.timedelta`，可含秒或微秒。
它不查询 IANA 数据库，也不声明相关数据版本。时刻解析本身不要求地点；
`prepare_natal_input` 额外要求已知地点。

```{doctest}
>>> from astrology import FixedOffset
>>> fixed = BirthRecord(
...   date(2026, 4, 5), time(0, 15), FixedOffset(timedelta(minutes=345)),
... )
>>> resolved = resolve_birth_time(fixed)
>>> (resolved.utc.isoformat(), resolved.timezone_identity, resolved.timezone_source)
('2026-04-04T18:30:00+00:00', 'UTC+05:45', 'fixed_offset')
>>> (resolved.tzdata_version, resolved.iana_version)
(None, None)
```

## 时刻支持范围与失败行为

现代解析接纳不早于 `1972-01-01T00:00:00Z`、且在 Python datetime 可表示范围内的 UTC。
下限针对解析后的时刻，不是当地年份：1972 年的当地日期可能落到不支持的 1971 年 UTC；
1971 年末的当地钟点也可能表示首个受支持的 UTC 时刻。早于下限一天以上的钟点，不加载 IANA 数据便报错；
其余钟点若两个探测得到的 UTC 时刻均早于下限，则在 fold/gap 分类前报错。
不能删除不受支持的候选，把有歧义的钟点伪装成唯一时刻。选中的时刻必须满足下限。

较早的公历记录仍可保存。解析较早时刻需要未来显式的历史时间合同（含 UT1）；本 API 不外推 UTC，
不转换时标，也不接纳闰秒标签。UTC 换算超出 datetime 上限时显式抛出 `ValueError`。
天文模型的有效域归未来适配器，不归本记录类型。

| 错误 | 含义 |
|---|---|
| `TypeError` | 运行时类型错误，不静默转换字符串或布尔值 |
| `ValueError` | 范围、形状、精度、历法或元数据无效，标识未知，TZif 不可用，结果不一致，UTC 越界，或给出了无关的 fold |
| `MissingBirthDataError` | 缺少必需钟点／时区，或完整输入所需的地点 |
| `AmbiguousBirthTimeError` | 需要显式选择 fold |
| `NonexistentBirthTimeError` | 记录的本地钟点处于空缺中 |
| `HistoricalTimeError` | 时刻早于现代 UTC 合同的下限 |

四种具名错误都是 `ValueError` 的子类。校验在 `python -O` 下仍然有效。
输入来源元数据复制为只读的普通字符串映射，带可变属性的字符串子类会被拒绝；输入和结果值均被冻结。

环境故障另行处理：`tzdata` 包缺失时抛出导入错误，版本元数据缺失或无效时抛出 `RuntimeError`，
资源权限故障保留为 `OSError` 的子类。这些故障不属于出生信息缺失或无效。

算法遵循 [Python zoneinfo 数据来源合同](https://docs.python.org/3.11/library/zoneinfo.html#data-sources)
和 [PEP 495 的 fold 与 gap 语义](https://peps.python.org/pep-0495/)。
