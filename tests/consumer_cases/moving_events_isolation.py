"""Construct and render empty moving queries without native initialization.

不初始化原生库，构造及显示空移动查询。
"""

import builtins
import importlib.metadata as metadata
import sys
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, NoReturn

original_import = builtins.__import__


def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
  raise RuntimeError("Supplied moving-event values crossed an initialization boundary")


def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
  if name == "astrology.celestial" or name.startswith(("celestial_calendar", "tzdata", "zoneinfo")):
    forbidden()
  return original_import(name, *args, **kwargs)


builtins.__import__ = guarded
metadata.version = metadata.distribution = forbidden

import astrology as a  # noqa: E402

pair = [a.Body.MOON, a.Body.SUN]
pairs = [pair]
sources = [
  a.TransitSource(body, "position_source", index, "synthetic", 2400000, 2500000, 3660, "window")
  for body, index in ((a.Body.MOON, 2), (a.Body.SUN, 1))
]
result = a.MovingAspectEvents(
  datetime(2024, 1, 1, tzinfo=UTC),
  datetime(2024, 2, 1, tzinfo=UTC),
  2460310.5,
  2460341.5,
  pairs,  # type: ignore[arg-type]
  [a.MajorAspect.CONJUNCTION],  # type: ignore[arg-type]
  sources,  # type: ignore[arg-type]
  [],  # type: ignore[arg-type]
  "synthetic",
  "synthetic",
)
pair.clear()
pairs.clear()
sources.clear()
if result.pairs != ((a.Body.MOON, a.Body.SUN),):
  raise RuntimeError("Nested moving pair aliases caller data")
for language in ("en", "zh-CN"):
  text = a.format_moving_events(result, a.load_catalog(), language=language)
  pair_line = (
    "Requested moving pairs (first, second): (Moon [moon], Sun [sun])"
    if language == "en"
    else "请求移动对象对（第一侧，第二侧）: (月亮 [moon], 太阳 [sun])"
  )
  legend = (
    "Relative direction and rate describe second minus first longitude."
    if language == "en"
    else "相对方向与速率按第二侧黄经减第一侧黄经定义。"
  )
  if pair_line not in text.splitlines():
    raise RuntimeError("Empty result lost its requested ordered-pair line")
  if legend not in text.splitlines():
    raise RuntimeError("Empty result lost its relative-motion legend")
for changed in ({"pairs": ((a.Body.SUN, a.Body.SUN),)}, {"sources": ()}):
  try:
    replace(result, **changed)
  except (TypeError, ValueError):
    pass
  else:
    raise RuntimeError("Moving-event validation disappeared under optimization")
try:
  a.moving_hit_utc(None)  # type: ignore[arg-type]
except TypeError:
  pass
else:
  raise RuntimeError("Moving hit reader accepted a non-hit")
if any(name.startswith(("celestial_calendar", "astrology.celestial")) for name in sys.modules):
  raise RuntimeError("Supplied moving-event values initialized native astronomy")
