# 相位

[English](../en/aspects.md) · [文档](index.md) · [API 参考](reference.md)

相位用两个对象黄经之间的夹角把它们联系起来。`find_aspects` 根据黄经和黄经速率，在同一时刻判断
五种主要相位。每条结果保留它所对照的精确角度、相对该角度的带符号偏差、用到的限度和局部运动状态。
容许度全部由调用方给出，没有默认值。[`natal_chart`](chart.md) 对请求里的相位调用同一个函数。

## 用普通数值判断相位

`find_aspects` 不需要命盘，也不需要天文计算。传入带黄经（度）和速率（度每日）的对象，再传入
要用的规则就行。

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
它在 3 度的容许度之内，限度本身也算在内。

## 分支与偏差

合相和对分相只有一个精确角度，分别是 0 度和 180 度。六分相、四分相、三分相有两个，即相位角的
负值和正值，因为第二个对象可能在第一个之前，也可能在它之后。每条命中用 `branch_deg` 记下它
对照的是哪一个；`deviation_deg` 是间距减去该分支，取值大于 -180、到 180 为止，包含 180。

交换配对后，相位不变，方向翻转：偏差变号，有两个分支的相位，分支也变号；状态不变。偏差恰为
180 时，它是自己的镜像。

```{doctest}
>>> hit = find_aspects([mars, sun], [sextile])[0]
>>> (hit.branch_deg, hit.deviation_deg, hit.motion.value)
(-60.0, 2.0, 'applying')
```

容许度较宽时，一对对象可能同时命中几种相位，或同一相位的两个分支。所有命中都会返回，顺序固定：
先按对象的顺序，再按相位角，同一相位里负分支在正分支之前。不会为了取更近的一个而丢掉别的。

## 入相、离相和其他状态

偏差不为 180 度时，它以第二个对象的速率减去第一个的速率变化。这个相对速率与偏差异号时，相位在入相；
同号时，在离相。逆行时同样成立。

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

各状态按确切的数值比较，没有容差。`stationary` 指没有相对运动，不是某颗行星自己的留。状态只
描述这一时刻，不说明相位会不会在之后的留之前变得精确。

偏差恰为 180 度时，回绕后的绝对偏差在这里有尖点；若存在相对运动，就没有双侧导数，
所以两种对象顺序都报告 `indeterminate`。速率相等时仍为 `stationary`。
只有容许度至少为 180 度，这个边界才可能命中。

## 对象各有容许度时怎样合成

相位规则给所有对象同一个容许度。要给某个对象单独的容许度，就在规则里加 `ObjectOrb`，并选定
一对对象的两个容许度怎样合成：

| `OrbCombination` | 一对对象的偏差在下面的范围内时成立 |
|---|---|
| `EITHER_WITHIN_OWN_ORB` | 至少一个对象自己的容许度之内，即较大的容许度 |
| `BOTH_WITHIN_OWN_ORB` | 两个对象各自的容许度之内，即较小的容许度 |
| `MEAN_OF_ORBS` | 两个容许度的平均值之内 |

规则带按对象的容许度时，必须给出合成规则。排盘请求里，不带时不能给；`find_aspects` 本身接受它，
也不会因此改变结果。每条命中都报告它用的限度。

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

## 选择参与的对象

两个月交点之间不构成相位。四个交点标识只是同一对交点的两种定义和两个方向，所以升交点和降交点
永远正好相对。月交点可以与天体构成相位。

```{doctest}
>>> nodes = [
...   AspectObject(LunarNode.MEAN_ASCENDING, 10.0, -0.05),
...   AspectObject(LunarNode.MEAN_DESCENDING, 190.0, -0.05),
... ]
>>> find_aspects(nodes, [AspectRule(MajorAspect.OPPOSITION, 3)])
()
```

请求里的 `aspect_objects` 指定参与相位的对象，必须是所请求对象的子集；不写时，所有请求的对象
都参与。被请求但不在 `aspect_objects` 里的交点仍有位置，只是不参与任何相位。轴线不是请求里的
对象，没有相位。

## 本命盘里的相位

`natal_chart` 在参与的对象之间判断请求的规则，用的是同一次计算得出的位置和速率，结果放在
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

## 检查结果

手算的案例覆盖 0 度与 360 度处的回绕、两个分支、容许度端点、精确相位、速率相等和逆行。状态
由黄经速率决定，所以速率也与报告出的黄经对照：取一小时的差商，与每个速率相差约 1e-6 度每日。

参考测试还用公布的 Hellenistic 容许度配置本库，把它求出的相位与另一份列表比较。那份列表由
两个参考时刻的 JPL Horizons 黄经，按无向间距推出。该风格页公布的是参数，不是某张盘的相位表，
所以这不是与另一个程序的输出比对。检查要求没有任何一对对象离容许度限度不足 0.4 度，而且偏离
该惯例的五种做法，每一种都至少在其中一个时刻改变结果。这两个时刻里有合相、四分相和三分相，没有
六分相和对分相，所以 60 度与 180 度这两个角度靠手算案例核对，不靠这次比较。各项参考能检出和检不出
什么，见[参与开发](contributing.md#正确性)。

## 限度

- 只用黄经。黄纬、赤纬、次要相位、整宫相位及与轴线的相位都不判断。
- 状态是局部的。它不说明相位会不会在之后的留之前变得精确，也不是解释或强度。
- 本库不提供默认容许度。语料把这套判断写成项目定义，不对任何流派的容许度作断言。
- 结果尚未序列化，也没有文本输出。
