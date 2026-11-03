"""Exercise public chart checks in a fresh process. 在新进程中执行公开命盘校验。"""

from datetime import date, time, timedelta

from astrology import (
  BirthRecord,
  Body,
  ChartConfig,
  FixedOffset,
  HouseSystem,
  Location,
  TimePrecision,
  natal_chart,
  prepare_natal_input,
  resolve_birth_time,
)

config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ())
record = BirthRecord(
  date(2003, 7, 17),
  time(5, 37, 13),
  FixedOffset(timedelta(0)),
  Location(90.0, 0.0),
  TimePrecision.SECOND,
  {"record": "synthetic"},
)
try:
  natal_chart(prepare_natal_input(record), config)
except ValueError:
  pass
else:
  raise RuntimeError("optimized mode skipped the latitude domain check")
without_location = BirthRecord(
  date(2003, 7, 17),
  time(5, 37, 13),
  FixedOffset(timedelta(0)),
  None,
  TimePrecision.SECOND,
  {"record": "synthetic"},
)
try:
  natal_chart(resolve_birth_time(without_location), config)
except ValueError:
  pass
else:
  raise RuntimeError("optimized mode skipped the missing location check")
