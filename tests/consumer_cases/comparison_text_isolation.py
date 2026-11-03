"""Block effects after preparing supplied inputs. 准备给定输入后阻止副作用。"""

import builtins
import importlib.metadata as metadata
import io
from typing import Any, NoReturn

import astrology
import astrology._distribution as distribution
import astrology.birth as birth
import astrology.chart as chart
import astrology.knowledge.catalog as catalog_module
from tools.installed_check import acceptance_cross_aspects, acceptance_house_overlays

overlays = acceptance_house_overlays()
aspects = acceptance_cross_aspects()
catalog = astrology.load_catalog()
original_import = builtins.__import__


def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
  raise RuntimeError("Supplied comparison crossed an effectful boundary")


def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
  if name == "astrology.celestial" or name.startswith(("celestial_calendar", "tzdata", "zoneinfo")):
    forbidden()
  return original_import(name, *args, **kwargs)


builtins.__import__ = guarded
builtins.open = io.open = forbidden
metadata.version = metadata.distribution = distribution.version = forbidden  # type: ignore[attr-defined]
astrology.load_catalog = catalog_module.load_catalog = catalog_module.files = forbidden  # type: ignore[attr-defined]
astrology.natal_chart = chart.natal_chart = forbidden
astrology.prepare_natal_input = birth.prepare_natal_input = birth.resolve_birth_time = forbidden
again = astrology.cross_chart_house_overlays(
  overlays.chart_left,
  overlays.chart_right,
  left_objects=overlays.left_objects,
  right_objects=overlays.right_objects,
)
if again != overlays:
  raise RuntimeError("Supplied geometry changed")
for language in ("en", "zh-CN"):
  if not astrology.format_house_overlays(again, catalog, language=language):
    raise RuntimeError("Empty overlay output")
  if not astrology.format_cross_aspects(aspects, catalog, language=language):
    raise RuntimeError("Empty aspect output")
try:
  astrology.HouseOverlay("left", "right", astrology.Body.SUN, True)
except TypeError:
  pass
else:
  raise RuntimeError("Optimized mode lost house validation")
