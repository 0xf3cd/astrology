"""Shared chart and project-version fixtures. 共用命盘及项目版本测试夹具。"""

import tomllib
from datetime import date, time
from pathlib import Path

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
def project_version() -> str:
  """Package version declared by this checkout. 当前 checkout 声明的包版本。"""
  value: str = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
  )["project"]["version"]
  return value


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
