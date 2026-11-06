"""Construct supplied transit values without astronomy or time-data initialization.

不初始化天文或时区数据，构造给定行运值。
"""

import builtins
import importlib.metadata as metadata
import sys
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, NoReturn

original_import = builtins.__import__


def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
  raise RuntimeError("Supplied transit values crossed an effectful boundary")


def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
  if name == "astrology.celestial" or name.startswith(("celestial_calendar", "tzdata", "zoneinfo")):
    forbidden()
  return original_import(name, *args, **kwargs)


builtins.__import__ = guarded
metadata.version = metadata.distribution = forbidden

import astrology as a  # noqa: E402
from tools.installed_check import _cross_source  # noqa: E402

chart = _cross_source(2000, "supplied-transit", ((a.Body.SUN, 10),))
source = a.TransitSource(
  a.Body.MERCURY,
  "position_source",
  3,
  "synthetic model",
  2400000,
  2500000,
  3660,
  "synthetic event window",
)
hit = a.TransitHit(
  a.Body.MERCURY,
  a.Body.SUN,
  a.MajorAspect.CONJUNCTION,
  0,
  10,
  2460311,
  370.000000001,
  -1e-12,
  a.TransitDirection.TANGENT,
)
result = a.TransitHits(
  chart,
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
if result.chart is not chart or result.hits != (hit,):
  raise RuntimeError("Supplied transit source or hit changed")
try:
  replace(result, hits=(replace(hit, jde_tt=result.end_jde_tt),))
except ValueError:
  pass
else:
  raise RuntimeError("Optimized mode lost half-open interval checks")
if a.load_catalog().entry("entry.transit_hits").chart_applicability != "not_assessed":
  raise RuntimeError("Knowledge retrieval acquired a chart-matching claim")
if any(
  name.startswith(("celestial_calendar", "astrology.celestial", "tzdata", "zoneinfo"))
  for name in sys.modules
):
  raise RuntimeError("Supplied transit values initialized machinery")
