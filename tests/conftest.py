"""Shared complete charts for result and rendering tests. 结果与显示测试共用的完整命盘。"""

from datetime import date, time

import pytest

from astrology import (
  AspectRule,
  BirthRecord,
  Body,
  ChartConfig,
  HouseSystem,
  IanaTimezone,
  Location,
  LunarNode,
  MajorAspect,
  NatalChart,
  ObjectOrb,
  OrbCombination,
  TimePrecision,
  natal_chart,
  prepare_natal_input,
)


@pytest.fixture
def recorded_chart() -> NatalChart:
  record = BirthRecord(
    date(2021, 11, 7),
    time(1, 30),
    IanaTimezone("America/New_York"),
    Location(40.71, -74.01),
    TimePrecision.MINUTE,
    {"record": "synthetic", "note": "双语 source"},
  )
  config = ChartConfig(
    HouseSystem.PLACIDUS,
    (*Body, *LunarNode),
    tuple(AspectRule(aspect, 6, (ObjectOrb(Body.SUN, 10),)) for aspect in MajorAspect),
    aspect_objects=(*reversed(tuple(Body)), LunarNode.MEAN_ASCENDING),
    orb_combination=OrbCombination.MEAN_OF_ORBS,
  )
  return natal_chart(prepare_natal_input(record, fold=1), config)
