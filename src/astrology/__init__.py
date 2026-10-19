"""Birth inputs, requested configuration and independent knowledge, without native astronomy.

出生输入、请求配置与独立知识查询，不初始化原生天文库。
"""

from astrology.birth import (
  AmbiguousBirthTimeError,
  BirthRecord,
  FixedOffset,
  HistoricalTimeError,
  IanaTimezone,
  Location,
  MissingBirthDataError,
  NonexistentBirthTimeError,
  ResolvedBirth,
  TimePrecision,
  prepare_natal_input,
  resolve_birth_time,
)
from astrology.config import (
  AspectRule,
  Body,
  ChartConfig,
  HouseSystem,
  LunarNode,
  MajorAspect,
  NodeDefinition,
)
from astrology.knowledge import Catalog, load_catalog

__all__ = [
  "AmbiguousBirthTimeError",
  "AspectRule",
  "BirthRecord",
  "Body",
  "Catalog",
  "ChartConfig",
  "FixedOffset",
  "HistoricalTimeError",
  "HouseSystem",
  "IanaTimezone",
  "Location",
  "LunarNode",
  "MajorAspect",
  "MissingBirthDataError",
  "NodeDefinition",
  "NonexistentBirthTimeError",
  "ResolvedBirth",
  "TimePrecision",
  "load_catalog",
  "prepare_natal_input",
  "resolve_birth_time",
]
