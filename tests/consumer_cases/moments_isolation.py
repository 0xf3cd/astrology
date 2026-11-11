"""Consume supplied moments without astronomy or time-data initialization.

不初始化天文或时区数据，消费给定时刻盘。
"""

import builtins
import importlib.metadata as metadata
import sys
from datetime import UTC, datetime
from typing import Any, Literal, NoReturn

original_import = builtins.__import__


def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
  raise RuntimeError("Supplied moment crossed an effectful calculation boundary")


def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
  if name == "astrology.celestial" or name.startswith(("celestial_calendar", "tzdata", "zoneinfo")):
    forbidden()
  return original_import(name, *args, **kwargs)


builtins.__import__ = guarded
metadata.version = metadata.distribution = forbidden

import astrology as a  # noqa: E402
from tools.installed_check import _cross_source  # noqa: E402

natal = _cross_source(2000, "synthetic", ((a.Body.SUN, 10),))
moving = a.MomentChart(
  a.MomentInput(datetime(2000, 1, 1, tzinfo=UTC), a.Location(0, 0), 2451544.5),
  natal.requested,
  natal.effective,
  natal.provenance,
  natal.times,
  natal.positions,
  natal.houses,
  natal.placements,
  natal.aspects,
)
catalog = a.load_catalog()
rules = (a.AspectRule(a.MajorAspect.CONJUNCTION, 3),)
fixed = a.transit_aspects(moving, natal, rules, natal_objects=(a.Body.SUN, a.Axis.ASCENDANT))
if fixed.moving_chart is not moving or fixed.natal_chart is not natal:
  raise RuntimeError("Fixed-instant source roles changed")
if fixed.hits[0].motion is not a.AspectMotion.EXACT:
  raise RuntimeError("Exact supplied geometry changed")
for first, second in ((moving, natal), (natal, moving), (moving, moving)):
  a.cross_chart_aspects(first, second, rules)
  a.cross_chart_house_overlays(first, second)
if len(a.HouseRulers(moving).houses) != 12:
  raise RuntimeError("Supplied moment lost its house rulers")
a.Dispositors(moving, (a.Body.SUN,))
a.chart_sign_distribution(moving, objects=(a.Body.SUN,))
languages: tuple[Literal["en", "zh-CN"], ...] = ("en", "zh-CN")
for language in languages:
  a.format_chart(moving, catalog, language=language)
  a.format_transit_aspects(fixed, catalog, language=language)
source = a.TransitSource(
  a.Body.MERCURY, "position_source", 3, "synthetic", 2400000, 2500000, 3660, "synthetic"
)
hit = a.TransitHit(
  a.Body.MERCURY,
  a.Body.SUN,
  a.MajorAspect.CONJUNCTION,
  0,
  10,
  2460311,
  370,
  1,
  a.TransitDirection.INCREASING,
)
stored = a.TransitHits(
  moving,
  datetime(2024, 1, 1, tzinfo=UTC),
  datetime(2024, 2, 1, tzinfo=UTC),
  2460310.5,
  2460341.5,
  (a.Body.MERCURY,),
  (a.Body.SUN,),
  (a.MajorAspect.CONJUNCTION,),
  (source,),
  (hit,),
  "synthetic",
  "synthetic",
)
if stored.chart is not moving:
  raise RuntimeError("Supplied transit discarded its moment source")
if any(
  name.startswith(("celestial_calendar", "astrology.celestial", "tzdata", "zoneinfo"))
  for name in sys.modules
):
  raise RuntimeError("Supplied moments initialized astronomy or time data")
