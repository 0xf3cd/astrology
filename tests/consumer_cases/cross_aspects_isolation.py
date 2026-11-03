"""Guard imports and metadata before comparison. 比较前保护导入与元数据边界。"""

import builtins
import importlib.metadata as metadata
import sys
from typing import Any, NoReturn

original_import = builtins.__import__


def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
  raise RuntimeError("Pure cross comparison reached an effectful boundary")


def guarded(name: str, *args: Any, **kwargs: Any) -> Any:
  if name == "astrology.celestial" or name.startswith(("celestial_calendar", "tzdata", "zoneinfo")):
    forbidden()
  return original_import(name, *args, **kwargs)


builtins.__import__ = guarded
metadata.version = metadata.distribution = forbidden

# Import the tested modules only after installing the guards.
# 必须先安装守卫，再导入被测模块。
import astrology  # noqa: E402
import astrology.birth as birth  # noqa: E402

birth.resolve_birth_time = birth.prepare_natal_input = forbidden
astrology.natal_chart = forbidden
from tools.installed_check import acceptance_cross_aspects  # noqa: E402

result = acceptance_cross_aspects()
if len(result.hits) != 5 or any(hasattr(hit, "motion") for hit in result.hits):
  raise RuntimeError("Static result changed")
try:
  astrology.cross_chart_aspects(
    chart_left=result.chart_left,
    chart_right=result.chart_right,
    rules=[result.rules[0], result.rules[0]],
  )
except ValueError:
  pass
else:
  raise RuntimeError("Duplicate rule validation disappeared")
if any(
  name.startswith(("celestial_calendar", "astrology.celestial", "tzdata", "zoneinfo"))
  for name in sys.modules
):
  raise RuntimeError("Pure comparison initialized machinery")
