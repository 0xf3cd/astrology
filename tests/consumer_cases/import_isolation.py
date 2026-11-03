"""Observe import purity before explicit calculation. 显式计算前观察导入纯度。"""

import sys

import astrology  # noqa: F401 -- Observe package import before calculation imports.

loaded = [
  name
  for name in sys.modules
  if name in ("celestial_calendar", "astrology.celestial")
  or name.startswith(("celestial_calendar.", "ctypes"))
]
if loaded:
  raise RuntimeError(f"package import initialized native machinery: {loaded}")

from datetime import date, time, timedelta  # noqa: E402

from astrology import (  # noqa: E402
  BirthRecord,
  Body,
  ChartConfig,
  FixedOffset,
  HouseSystem,
  Location,
  TimePrecision,
  natal_chart,
  prepare_natal_input,
)

record = BirthRecord(
  date(2003, 7, 17),
  time(12, 0),
  FixedOffset(timedelta(0)),
  Location(40.0, 0.0),
  TimePrecision.SECOND,
  {"record": "synthetic"},
)
resolved = prepare_natal_input(record)
natal_chart(resolved, ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ()))
if "astrology.celestial" not in sys.modules:
  raise RuntimeError("chart calculation did not load the astronomy adapter")
