# 时刻盘与固定时刻行运相位

[English](../en/moments.md) · [命盘](chart.md) · [精确行运搜索](transits.md)

用 `moment_chart` 为给定时刻与地点建盘，得到不含出生记录、也不推断地点的
`MomentChart`。用 `transit_aspects` 比较该时刻盘的移动对象与已有本命盘的固定度数。
本页示例按顺序续接。

## 按给定时刻建盘

<!-- usage: chart.moment -->

显式给出有时区的内建 `datetime`、`Location` 和 `ChartConfig`。时区偏移会归一为 UTC；
输入时刻与计算时标分别保存：

```{doctest}
>>> from datetime import UTC, date, datetime, time, timedelta
>>> from astrology import Body, ChartConfig, HouseSystem, Location, moment_chart
>>> site = Location(0, 0)
>>> config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON, Body.MERCURY), ())
>>> moving = moment_chart(datetime(2024, 3, 22, 18, tzinfo=UTC), site, config)
>>> type(moving).__name__
'MomentChart'
>>> moving.moment.utc.isoformat()
'2024-03-22T18:00:00+00:00'
>>> moving.moment.location == site and moving.moment.source_jde_tt is None
True
>>> len(moving.positions)
3
```

`moving.moment` 保存归一后的 UTC、地点及可选的来源事件 TT；`moving.times` 保存
计算所得的 JD(UT1) 与 JDE(TT)。位置、宫位、落点、盘内相位、配置及来源的作用与本命盘
相同。本例没有请求盘内相位。

<!-- /usage: chart.moment -->

仍须显式选择宫制，并遵守[联合快照有效域](chart.md#选取对象不扩大有效域)。
只选部分天体是在十四对象联合快照中筛选输出，不缩小求值域。没有时区的 datetime 会被拒绝，
归一后的 UTC 须不早于 1972-01-01。

## 比较移动对象与本命盘

<!-- usage: transits.fixed -->

用合成出生记录建立本命盘。显式给出本次固定时刻比较的规则及双侧对象，
不继承任一源盘的规则：

```{doctest}
>>> from astrology import (AspectRule, BirthRecord, FixedOffset, MajorAspect,
...     format_transit_aspects, load_catalog, natal_chart, prepare_natal_input, transit_aspects)
>>> record = BirthRecord(date(2000, 4, 10), time(12), FixedOffset(timedelta(0)), site)
>>> natal = natal_chart(prepare_natal_input(record), config)
>>> rules = (AspectRule(MajorAspect.CONJUNCTION, 3),)
>>> fixed = transit_aspects(moving, natal, rules,
...     moving_objects=(Body.MERCURY,), natal_objects=(Body.SUN,))
>>> [(hit.moving_object.value, hit.natal_object.value, hit.motion.value) for hit in fixed.hits]
[('mercury', 'sun', 'separating')]
>>> catalog = load_catalog()
>>> print(format_transit_aspects(fixed, catalog, language='zh-CN').splitlines()[0])
固定时刻的行运对本命相位
>>> print(next(line for line in format_transit_aspects(fixed, catalog, language='zh-CN').splitlines()
...     if line.startswith('水星 [mercury] |')))
水星 [mercury] | 太阳 [sun] | 合相 | 0°00'00" | -0°00'58" | 3°00'00" | 离相
```

这一行区分移动与本命对象，保留相位、有向分支、带符号偏差、包含等号的容许度上限及局部运动。
未经舍入的原值仍在 `fixed.hits` 中；显示到整角秒不改变命中或运动判断，即使非零偏差显示成零。

<!-- /usage: transits.fixed -->

选择为 `None` 时，使用该侧全部已存天体和交点，不加入四轴。显式选择可包含四个 `Axis` 成员。
空选择或空规则不产生命中，但仍校验非法输入。允许同名对象、具名交点间及轴间配对。
排序与按对象设置的容许度合成规则沿用[双盘相位](cross_aspects.md)。

移动侧须为 `MomentChart`，固定侧须为 `NatalChart`。对相同有序选择，每对原始分支、偏差和
容许度上限与 `cross_chart_aspects` 完全相同。运动状态使用移动侧速率对**零本命速率**判断，
固定本命四轴也为零，不使用本命位置记录中出生时刻的速率。移动四轴没有提供速率：非精确命中
为不确定，偏差恰为零时仍为精确。入相表示局部导数，不保证之后会有精确事件。双侧保留各自
日期的热带黄经，不转换共同历元，也不声称是同时刻的空间角。

## 从保留的精确命中建盘

<!-- usage: chart.hit_moment -->

把保留的 `TransitHit` 直接传给 `moment_chart`，无需导入上游转换器。
显式给出的地点用于新盘的宫位计算：

```{doctest}
>>> from astrology import transit_hits
>>> events = transit_hits(natal, start_utc=datetime(2024, 3, 1, tzinfo=UTC),
...     end_utc=datetime(2024, 6, 1, tzinfo=UTC), moving_objects=(Body.MERCURY,),
...     natal_objects=(Body.SUN,), aspects=(MajorAspect.CONJUNCTION,))
>>> at_hit = moment_chart(events.hits[0], site, config)
>>> at_hit.moment.source_jde_tt == events.hits[0].jde_tt
True
>>> at_hit.moment.utc.isoformat(timespec='seconds')
'2024-03-22T17:40:34+00:00'
```

`source_jde_tt` 保留来源事件的原始 JDE(TT)；`at_hit.times.jde_tt` 则来自转换后的 Python UTC
datetime 所计算的新快照。两者可能不同：上游固定闰秒表及 datetime 的微秒表示不保证精确逆变换。

<!-- /usage: chart.hit_moment -->

Python 不能表示插入的闰秒。在 1972 年首次闰秒阶跃附近，转换后的快照时刻可能比来源事件晚约
一秒。在 1972 模型边界，来源时刻可能转换为早于 1972 的 UTC，此时抛出 `HistoricalTimeError`；
准入检查针对转换后的时刻。转换还会按 datetime 精度舍入，可能进位到下一日或下一年。
所得 UTC 须满足快照有效域；处于较宽事件搜索域内的合法事件，不保证能计算完整命盘。
转换或求值域失败抛出带有所请求宫制及可用上游诊断的 `ChartDomainError`。
固定闰秒表在未来如何沿用偏移，见[行运时标限制](transits.md#限制与失败)。

## 使用已有消费者

双盘比较、落宫、宫主星、定位星、星座分布、区间行运搜索及命盘文本都接纳时刻盘。
续接上面的命盘：

```{doctest}
>>> from astrology import (Dispositors, HouseRulers, chart_sign_distribution,
...     cross_chart_aspects, cross_chart_house_overlays, format_chart)
>>> cross = cross_chart_aspects(moving, natal, rules,
...     left_objects=(Body.MERCURY,), right_objects=(Body.SUN,))
>>> cross.hits[0].deviation_deg == fixed.hits[0].deviation_deg
True
>>> cross_chart_house_overlays(natal, moving).chart_right is moving
True
>>> len(HouseRulers(moving).houses)
12
>>> Dispositors(moving, (Body.SUN,)).chart is moving
True
>>> chart_sign_distribution(moving, objects=config.objects).total
3
>>> print(format_chart(moving, catalog, language='zh-CN').splitlines()[0])
热带地心时刻盘
```

时刻盘文本显示给定 UTC 和地点，有来源事件时另列 TT，不添加出生钟点、时区身份或 tzdata/fold
来源。`natal_lunar_phase` 仍只接纳本命盘；对时刻盘使用 `lunar_phase`，传入已存日月黄经。
区间 `transit_hits` 的 `natal_objects` 命名固定参考侧的角色，即使源盘是时刻盘；保留的原
epoch-policy 值在[行运指南](transits.md)中说明。

项目定义及适用范围记录在[知识目录](catalog.md)的 `entry.moment_charts` 和 `entry.transit_aspects`。
