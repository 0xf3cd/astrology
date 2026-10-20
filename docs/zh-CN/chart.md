# 本命盘

[English](../en/chart.md) · [文档](index.md) · [API 参考](reference.md)

`natal_chart` 是现代热带黄道、地心本命盘的唯一入口。它接收已解析的出生时刻与请求配置，
返回不可变结果，并把请求的选择、实际生效的选择、天文原值及其来源分开保存。请求里的相位放在
`chart.aspects`，说明见[相位指南](aspects.md)。

## 计算一张盘

先准备输入。排盘需要已知钟点、显式时区和地点；[出生指南](birth.md)说明这一步。

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (
...   Body, BirthRecord, ChartConfig, FixedOffset, HouseSystem, Location,
...   TimePrecision, natal_chart, prepare_natal_input,
... )
>>> record = BirthRecord(
...   date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)),
...   Location(64.15, -21.94), TimePrecision.SECOND, {"record": "synthetic"},
... )
>>> resolved = prepare_natal_input(record)
>>> request = ChartConfig(HouseSystem.PLACIDUS, (Body.SUN, Body.MOON), ())
>>> chart = natal_chart(resolved, request)
>>> chart.requested.house_system.value
'placidus'
>>> chart.effective.house_system.value
'placidus'
```

位置是瞬时真黄道、真春分点上的地心视黄经与黄纬。结果保留未舍入的值，
星座与落宫由这些值派生。

```{doctest}
>>> sun, moon = chart.positions
>>> round(sun.longitude_deg, 4), round(moon.longitude_deg, 4)
(114.2565, 337.8942)
>>> placements = chart.placements
>>> (placements[0].sign, placements[0].house)
(<Sign.CANCER: 'cancer'>, 12)
>>> (placements[1].sign, placements[1].house)
(<Sign.PISCES: 'pisces'>, 9)
>>> round(placements[0].sign_degree_deg, 4)
24.2565
```

## 保存模型与口径

请求配置与实际配置是两个分开的值。ΔT 模型由适配层固定，不是调用方请求项，
但结果仍会具名记录。

```{doctest}
>>> chart.effective.delta_t_model
'algo5'
>>> chart.effective.evaluation
'fixed_fourteen_object_joint_snapshot'
>>> chart.provenance.celestial_version
'0.8.0'
>>> chart.provenance.position_frame
'apparent_geocentric_true_ecliptic_of_date'
>>> chart.provenance.ut1_derivation
'delta_t_model_from_civil_utc'
```

`position_frame` 说明这些值是瞬时真黄道、真春分点上的地心视位置。
`ut1_derivation` 说明 UT1 由民用 UTC 经 ΔT 模型推得，不是观测的 DUT1。
月交点以同一真春分点为基准，因此已含黄经章动。`ChartTimes` 记录该时刻的
UT1 儒略日与 TT 儒略历书日。

```{doctest}
>>> chart.times.jde_tt > chart.times.jd_ut1
True
```

位置与地点无关，宫位几何则与地点有关。

```{doctest}
>>> elsewhere = natal_chart(
...   prepare_natal_input(BirthRecord(
...     date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)),
...     Location(-33.87, 151.21), TimePrecision.SECOND, {"record": "synthetic"},
...   )),
...   request,
... )
>>> elsewhere.positions == chart.positions
True
>>> elsewhere.houses == chart.houses
False
```

## 按宫制的本来面目读取

Whole Sign、Equal 与 Placidus 是不同的几何，不是同一结果的不同叫法。
在 Whole Sign 下，上升点不是第一宫头，中天也不是第十宫头；结果把四轴与宫头分开保存。

```{doctest}
>>> whole = natal_chart(
...   resolved, ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ())
... )
>>> whole.houses.cusps_deg[0]
120.0
>>> round(whole.houses.ascendant_deg, 4)
127.7431
>>> whole.houses.ascendant_deg != whole.houses.cusps_deg[0]
True
>>> from astrology import house_of
>>> house_of(whole.houses.ascendant_deg, whole.houses.cusps_deg)
1
```

宫位区间是半开的：恰好落在宫头上的黄经归属于从该宫头开始的宫。
`house_of` 只使用给定的宫头表，从不参考上升点。

```{doctest}
>>> from astrology import house_of
>>> house_of(120.0, whole.houses.cusps_deg)
1
>>> house_of(150.0, whole.houses.cusps_deg)
2
>>> house_of(0.0, whole.houses.cusps_deg)
9
>>> house_of(359.999999, whole.houses.cusps_deg)
8
```

## 由黄经读取星座

星座区间是半开的：恰好 30 度为金牛，恰好 0 度为白羊。座内度数不先舍入；
展示规则是截断，因此显示值不会显示成下一个星座。

```{doctest}
>>> from astrology import Sign, sign_degree, sign_of, truncate_display
>>> sign_of(0.0), sign_of(30.0)
(<Sign.ARIES: 'aries'>, <Sign.TAURUS: 'taurus'>)
>>> sign_degree(45.0)
15.0
>>> truncate_display(29.9999999)
29.99972222222222
>>> sign_of(truncate_display(29.9999999)) is sign_of(29.9999999)
True
```

## 显式失败

能预先判定的输入由适配层在调用天文库之前拒绝；上游报告的失败不做替代。
绝不返回部分结果，请求的宫制也绝不替换。

```{doctest}
>>> from astrology import ChartDomainError, MissingBirthDataError
>>> polar = BirthRecord(
...   date(2003, 7, 17), time(12, 0), FixedOffset(timedelta(0)),
...   Location(90.0, 0.0), TimePrecision.SECOND, {"record": "synthetic"},
... )
>>> try:
...   natal_chart(prepare_natal_input(polar), request)
... except ChartDomainError as error:
...   (type(error).__name__, error.house_system.value)
('ChartDomainError', 'placidus')
```

缺少地点属于信息缺失，不是计算域错误，单独报告。

```{doctest}
>>> without_location = BirthRecord(
...   date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)), None,
...   TimePrecision.SECOND, {"record": "synthetic"},
... )
>>> from astrology import resolve_birth_time
>>> try:
...   natal_chart(resolve_birth_time(without_location), request)
... except MissingBirthDataError as error:
...   type(error).__name__
'MissingBirthDataError'
```

| 情形 | 报告方式 |
|---|---|
| 记录没有地点 | `MissingBirthDataError` |
| 纬度在两极 | `ChartDomainError`，不带上游细节 |
| 民用年份 2100 及以后 | `ChartDomainError`，不带上游细节 |
| 时刻超出支持的星历范围 | `ChartDomainError`，携带上游操作 |
| 该纬度下请求的几何无定义 | `ChartDomainError`，携带请求的宫制 |

分类从不依赖解析上游消息。调用前拒绝不带上游细节；由天文库报告的失败携带操作与记录状态。

```{doctest}
>>> high = prepare_natal_input(BirthRecord(
...   date(1990, 6, 21), time(0, 0), FixedOffset(timedelta(0)),
...   Location(69.65, 0.0), TimePrecision.SECOND, {"record": "synthetic"},
... ))
>>> try:
...   natal_chart(high, ChartConfig(HouseSystem.PLACIDUS, (Body.SUN,), ()))
... except ChartDomainError as error:
...   (error.house_system.value, error.operation, error.recorded)
('placidus', 'chart_snapshot', True)
>>> natal_chart(high, ChartConfig(HouseSystem.EQUAL, (Body.SUN,), ())).houses.system.value
'equal'
```

## 选取对象不扩大有效域

天文库把十四个对象的快照与宫位几何一起求值。少选对象只是过滤输出，
不缩小求值域，结果也会如实记录这一点。

```{doctest}
>>> one = natal_chart(resolved, ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ()))
>>> len(one.positions)
1
>>> one.effective.evaluation
'fixed_fourteen_object_joint_snapshot'
```

## 与独立参考比对

`tests/reference/natal_reference.json` 中的参考案例覆盖南北半球各一个时刻，
与 JPL Horizons 比对。在同口径下，检查要求太阳与行星一致到 3 角秒以内，月亮 15 角秒，
黄纬 1 角秒（月亮 3 角秒），四轴 0.001 度。Placidus 第 2、3、11、12 宫头按 Placidus 定义、
用 Horizons 的恒星时求值，同样要求一致到 0.001 度。交点检查重实现了库也在用的
Meeus 第 47 章公式，闰秒关系 `JDE(TT) - JD(UTC)` 精确成立。各条参考能检出和检不出
哪些缺陷见[参与开发](contributing.md#正确性)。

## 限度

- 请求的相位在参与的对象之间判断；规则和限度见[相位指南](aspects.md)。
- 结果尚未序列化，也没有文本输出。
- 仓库里没有 Placidus 宫头的外部参考值。第 2、3、11、12 宫头按定义核对，而检查与库对该定义的
  理解相同；第 5、6、8、9 宫头只作为精确对冲核对。
- 天文库支持 1885 至 2099 民用年，UTC 输入起于 1972-01-01；
  星历有效域比民用年范围更窄，超出即显式失败。
- 安装需要有 celestial-calendar 轮子的平台；见
  [参与开发](contributing.md#运行检查)。
