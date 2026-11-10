"""Import returns and reject invalid queries before native initialization.

导入返照入口，并在初始化原生天文前拒绝无效查询。
"""

import builtins
import importlib.metadata as metadata
import sys
from datetime import UTC, datetime
from typing import Any, NoReturn, cast

original_import = builtins.__import__


def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
  raise RuntimeError("Return validation crossed an effectful calculation boundary")


def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
  if name == "astrology.celestial" or name.startswith(("celestial_calendar", "tzdata", "zoneinfo")):
    forbidden()
  return original_import(name, *args, **kwargs)


builtins.__import__ = guarded
metadata.version = metadata.distribution = forbidden

import astrology as a  # noqa: E402
from tools.installed_check import _cross_source  # noqa: E402

entry = a.load_catalog().entry("entry.solar_lunar_returns")
if entry.statement.text("en") is None or entry.statement.text("zh-CN") is None:
  raise RuntimeError("Return definitions are not available in both languages")

natal = _cross_source(2000, "synthetic", ((a.Body.SUN, 10),))
moving = a.MomentChart(
  a.MomentInput(datetime(2000, 1, 1, tzinfo=UTC), a.Location(0, 0)),
  natal.requested,
  natal.effective,
  natal.provenance,
  natal.times,
  natal.positions,
  natal.houses,
  natal.placements,
  natal.aspects,
)
start, end = datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 2, 1, tzinfo=UTC)
cases: tuple[tuple[object, object, type[Exception]], ...] = (
  (moving, a.Body.SUN, TypeError),
  (None, a.Body.SUN, TypeError),
  (natal, "sun", TypeError),
  (natal, True, TypeError),
  (natal, a.LunarNode.MEAN_ASCENDING, TypeError),
  (natal, a.Body.MARS, ValueError),
  (natal, a.Body.MOON, ValueError),
)
for source, body, expected in cases:
  try:
    a.return_hits(cast(a.NatalChart, source), cast(a.Body, body), start_utc=start, end_utc=end)
  except expected:
    pass
  else:
    raise RuntimeError("An invalid return source/body was accepted")
if any(name.startswith(("celestial_calendar", "astrology.celestial")) for name in sys.modules):
  raise RuntimeError("Return import or validation initialized native astronomy")
