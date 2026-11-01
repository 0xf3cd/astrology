# 相位

[English](../en/aspects.md) · [文档](index.md) · [API 参考](reference.md)

`find_aspects` 根据两个对象在同一时刻的黄经和速率，判断它们是否构成五种主要相位。
每条结果给出用来对照的精确角度、带符号的角度偏差、容许度上限和当前的运动状态。
容许度全部由调用方给出，没有默认值。[`natal_chart`](chart.md) 对请求里的相位调用同一个函数。

比较两张给定命盘时，使用[静态交叉相位](cross_aspects.md)，保留左右归属，不设运动字段。

## 用普通数值判断相位

<!-- usage: aspects.longitudes -->

`find_aspects` 不需要命盘，也不调用天文库。传入带黄经（度）和速率（度/日）的对象，再传入
要用的规则就行。
所有对象须采用同一时刻和坐标约定，速率采用同一种日作为时间单位，例如 TT 日。
裸数值无法核实这些前提。

`AspectObject` 接受任何有限黄经，包括负值、超过 360° 的值及最大的有限浮点值。
传入值转为浮点数保存，不取模。相位计算先约去各黄经中的整圈再相减，极大的有限输入也不会溢出。
布尔值和非数值输入抛出 `TypeError`；NaN 和无穷抛出 `ValueError`。

```{doctest}
>>> from astrology import (
...   AspectObject, AspectRule, Body, LunarNode, MajorAspect, ObjectOrb,
...   OrbCombination, find_aspects,
... )
>>> sun = AspectObject(Body.SUN, 10.0, 1.0)
>>> mars = AspectObject(Body.MARS, 68.0, 3.0)
>>> sextile = AspectRule(MajorAspect.SEXTILE, 3)
>>> hit = find_aspects([sun, mars], [sextile])[0]
>>> (hit.aspect.value, hit.branch_deg, hit.deviation_deg, hit.motion.value)
('sextile', 60.0, -2.0, 'applying')
```

间距从第一个对象指向第二个：68 减 10 得 58 度。六分相是 60 度，所以偏差是 58 减 60，即 -2。
偏差的绝对值小于 3 度，所以符合规则。等于容许度上限也算符合。

<!-- /usage: aspects.longitudes -->

## 分支与偏差

合相和对分相只有一个精确角度，分别是 0 度和 180 度。六分相、四分相、三分相有两个，即相位角的
负值和正值，因为第二个对象可能在第一个之前，也可能在它之后。`branch_deg` 记录用的是哪个角度；
`deviation_deg` 是间距减去该分支，取值范围是 (-180, 180]，不含 -180，包含 180。

交换两个对象的顺序后，相位和运动状态不变。偏差变号，但 180 仍记为 180；
有两个分支的相位，分支也变号。

```{doctest}
>>> hit = find_aspects([mars, sun], [sextile])[0]
>>> (hit.branch_deg, hit.deviation_deg, hit.motion.value)
(-60.0, 2.0, 'applying')
```

容许度较宽时，一对对象可能同时命中几种相位，或同一相位的两个分支。所有命中都会返回，顺序固定：
先按对象的顺序，再按相位角，同一相位里负分支在正分支之前。不会只保留偏差最小的一个。

## 入相、离相和其他状态

相对速率是第二个对象的黄经速率减去第一个的速率。偏差不为 180 度时，
相对速率与偏差异号表示入相，同号表示离相。逆行时也用这个规则。

| 状态 | 条件 |
|---|---|
| `applying` | 偏差的绝对值在变小。 |
| `separating` | 偏差的绝对值在变大。 |
| `exact` | 偏差恰为零，不论速率如何。 |
| `stationary` | 相对速率恰为零，偏差不为零。 |
| `indeterminate` | 缺少速率，或偏差恰为 180 度且存在相对运动。 |

```{doctest}
>>> exact = AspectObject(Body.MARS, 70.0, 1.0)
>>> find_aspects([sun, exact], [sextile])[0].motion.value
'exact'
>>> same_speed = AspectObject(Body.MARS, 68.0, 1.0)
>>> find_aspects([sun, same_speed], [sextile])[0].motion.value
'stationary'
>>> no_rate = AspectObject(Body.MARS, 68.0, None)
>>> find_aspects([sun, no_rate], [sextile])[0].motion.value
'indeterminate'
```

判断时直接比较浮点数，不使用容差。`stationary` 只表示两个对象没有相对运动，
不表示某颗行星的黄经速率为零（占星术语中的“留”）。状态只描述当前时刻，
不预测相位之后会不会变得精确；行星可能在达到精确相位前改变运动方向。

偏差恰为 180 度时，回绕后的绝对偏差在这里有尖点；若存在相对运动，就没有双侧导数，
所以两种对象顺序都报告 `indeterminate`。速率相等时仍为 `stationary`。
只有容许度至少为 180 度，这个边界才可能命中。

## 对象各有容许度时怎样合成

<!-- usage: aspects.orbs -->

相位规则给所有对象同一个容许度。要给某个对象单独的容许度，就在规则里加 `ObjectOrb`，并选定
一对对象的两个容许度怎样合成：

| `OrbCombination` | 一对对象的偏差在下面的范围内时成立 |
|---|---|
| `EITHER_WITHIN_OWN_ORB` | 至少一个对象自己的容许度之内，即较大的容许度 |
| `BOTH_WITHIN_OWN_ORB` | 两个对象各自的容许度之内，即较小的容许度 |
| `MEAN_OF_ORBS` | 两个容许度的平均值之内 |

规则给对象单独设置了容许度时，必须指定合成规则。排盘请求里，如果没有单独设置的容许度，
就不能指定合成规则；直接调用 `find_aspects` 时则可以传入，但不会改变结果。每条结果都记录所用的上限。

```{doctest}
>>> moon = AspectObject(Body.MOON, 7.0, 13.0)
>>> sun = AspectObject(Body.SUN, 0.0, 1.0)
>>> wide_moon = AspectRule(MajorAspect.CONJUNCTION, 3, [ObjectOrb(Body.MOON, 13)])
>>> for combination in OrbCombination:
...   hits = find_aspects([sun, moon], [wide_moon], combination)
...   print(combination.value, [hit.orb_limit_deg for hit in hits])
either_within_own_orb [13.0]
both_within_own_orb []
mean_of_orbs [8.0]
```

<!-- /usage: aspects.orbs -->

## 选择参与的对象

在此单盘判断中，两个月交点之间不构成相位。四个交点标识只是同一对交点的两种定义和两个方向，所以升交点和降交点
永远正好相对。月交点可以与天体构成相位。

```{doctest}
>>> nodes = [
...   AspectObject(LunarNode.MEAN_ASCENDING, 10.0, -0.05),
...   AspectObject(LunarNode.MEAN_DESCENDING, 190.0, -0.05),
... ]
>>> find_aspects(nodes, [AspectRule(MajorAspect.OPPOSITION, 3)])
()
```

请求里的 `aspect_objects` 从所请求的天体或交点中选择参与者，也可显式加入四轴；不写时，所有请求的
天体和交点都参与，不加入四轴。被请求但不在 `aspect_objects` 里的交点仍有位置，只是不参与任何相位。
所选轴可与天体、交点或另一轴配对。

## 本命盘里的相位

`natal_chart` 按请求的规则，在参与的对象之间计算相位。位置和速率来自同一次计算，结果放在
`chart.aspects` 里。`chart.effective` 记录哪些对象参与、用了哪种合成规则。下面例子里的容许度
取自 Astrodienst 公布的 “Hellenistic” 绘图风格：月亮 13 度，太阳和行星 3 度，月交点不画相位。

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (
...   BirthRecord, ChartConfig, FixedOffset, HouseSystem, Location, TimePrecision,
...   natal_chart, prepare_natal_input,
... )
>>> record = BirthRecord(
...   date(2003, 7, 17), time(5, 37, 13), FixedOffset(timedelta(0)),
...   Location(64.15, -21.94), TimePrecision.SECOND, {"record": "synthetic"},
... )
>>> planets = (
...   Body.SUN, Body.MOON, Body.MERCURY, Body.VENUS, Body.MARS, Body.JUPITER, Body.SATURN,
... )
>>> rules = [AspectRule(aspect, 3, [ObjectOrb(Body.MOON, 13)]) for aspect in MajorAspect]
>>> request = ChartConfig(
...   HouseSystem.WHOLE_SIGN, (*planets, LunarNode.MEAN_ASCENDING), rules,
...   aspect_objects=planets,
...   orb_combination=OrbCombination.EITHER_WITHIN_OWN_ORB,
... )
>>> chart = natal_chart(prepare_natal_input(record), request)
>>> for hit in chart.aspects:
...   print(hit.first.value, hit.second.value, hit.aspect.value,
...         round(hit.deviation_deg, 2), hit.motion.value)
moon venus trine 7.42 applying
moon mars conjunction 1.28 applying
moon saturn trine -2.34 separating
>>> len(chart.positions), [value.value for value in chart.effective.aspect_objects][:2]
(8, ['sun', 'moon'])
```

(axis-aspects-zh-cn)=
## 显式选择四轴

`Axis.ASCENDANT`、`MIDHEAVEN`、`DESCENDANT` 和 `IMUM_COELI` 分别表示上升点、中天、下降点和天底。
排盘时直接读取 `ChartHouses` 中各轴的黄经，不用宫头代替，也不从另一轴推算相对的轴。
在整宫制中，上升点与中天不必是第一、第十宫头。

```{doctest}
>>> from astrology import Axis
>>> axis_request = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,),
...   (AspectRule(MajorAspect.SEXTILE, 3), AspectRule(MajorAspect.TRINE, 3)),
...   aspect_objects=(Axis.IMUM_COELI, Body.SUN, Axis.MIDHEAVEN))
>>> axis_chart = natal_chart(prepare_natal_input(record), axis_request)
>>> [value.value for value in axis_chart.effective.aspect_objects]
['sun', 'midheaven', 'imum_coeli']
>>> [(h.second.value, h.aspect.value, round(h.deviation_deg, 2), h.motion.value)
...  for h in axis_chart.aspects]
[('midheaven', 'trine', 2.47, 'indeterminate'), ('imum_coeli', 'sextile', 2.47, 'indeterminate')]
>>> [p.identity.value for p in axis_chart.positions]
['sun']
```

排盘结果没有轴的黄经速率，以 `None` 表示。因此，涉及轴的相位只要偏差不为零，运动状态就是
`indeterminate`；偏差恰为零时仍为 `exact`。判断时直接比较浮点数，几乎相对的轴值也可能有微小的非零偏差。
缺少的速率不会补成零，也不会用行星速率代替。
低层 `AspectObject` 允许调用方给出有限轴速率，但须与其他对象采用相同的日作为时间单位，例如 TT 日。
四轴没有物理距离，不列入 `chart.positions`，也不参与星座分布统计。

显式所选的四轴可互相配对，包括上升点与下降点、中天与天底。相对的两轴仍分别保留，全部匹配相位及分支都返回。
这是本项目采用的配对规则，不代表各传统都采用相同的容许度或解读。`ObjectOrb` 及三种合成规则同样适用于所选轴。
{ref}`双盘 API <cross-axis-aspects-zh-cn>`分别选择两侧参与者。

## 检查结果

我们用手算结果测试相位角度和容许度边界，也用 JPL Horizons 的黄经数据算出相位，与本库结果对照。
具体测试方法见[参与开发](contributing.md#正确性)。

## 适用范围

- 只用黄经。不判断黄纬、赤纬、次要相位或整宫相位；四轴须显式选择才参与。
- 运动状态只描述当前时刻，不预测之后会不会达到精确相位，也不表示相位的含义或强度。
- 本库不提供默认容许度。知识目录记录的是本项目的规则，不代表任何流派的容许度选择。

结构化结果与文本输出见[结果指南](records.md)。
