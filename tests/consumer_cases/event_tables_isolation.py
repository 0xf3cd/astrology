"""Format empty event results without initializing native astronomy.

不初始化原生天文，格式化空事件结果。
"""

import builtins
import importlib.metadata as metadata
import sys
from datetime import UTC, datetime
from typing import Any, NoReturn

original_import = builtins.__import__


def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
  raise RuntimeError("Empty event formatting crossed an effectful boundary")


def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
  if name == "astrology.celestial" or name.startswith(("celestial_calendar", "tzdata", "zoneinfo")):
    forbidden()
  return original_import(name, *args, **kwargs)


builtins.__import__ = guarded
metadata.version = metadata.distribution = forbidden

import astrology as a  # noqa: E402
from tools.installed_check import _cross_source  # noqa: E402

chart = _cross_source(2000, "empty-event-table", ((a.Body.SUN, 10),))
source = a.TransitSource(
  a.Body.SUN,
  "position_source",
  3,
  "synthetic model",
  2400000,
  2500000,
  3660,
  "synthetic event window",
)
result = a.TransitHits(
  chart,
  datetime(2024, 1, 1, tzinfo=UTC),
  datetime(2024, 2, 1, tzinfo=UTC),
  2460310.5,
  2460341.5,
  (a.Body.SUN,),
  (a.Body.SUN,),
  (a.MajorAspect.CONJUNCTION,),
  (source,),
  (),
  "synthetic",
  "synthetic",
)
for language in ("en", "zh-CN"):
  transit = a.format_transit_hits(result, a.load_catalog(), language=language)
  returns = a.format_return_hits(result, a.load_catalog(), language=language)
  if not transit or not returns:
    raise RuntimeError("An empty event table lost its context")
if any(name.startswith(("celestial_calendar", "astrology.celestial")) for name in sys.modules):
  raise RuntimeError("Empty event formatting initialized native astronomy")
