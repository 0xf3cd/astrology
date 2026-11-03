"""Exercise pure dignity composition and validation. 执行纯尊贵状态组合与校验。"""

import sys
from collections.abc import Callable

from astrology import (
  Body,
  DignityStatus,
  HouseRuler,
  HouseRulers,
  LunarNode,
  Placement,
  Sign,
  essential_dignities,
  format_house_rulers,
  load_catalog,
  sign_ruler,
)
from tools.installed_check import _cross_source

chart = _cross_source(2000, "pure", ((Body.MERCURY, 150), (Body.SUN, 30)))
result = HouseRulers(chart)
format_house_rulers(result, load_catalog(), language="zh-CN")
if result.chart is not chart or result.houses[5].statuses != (
  DignityStatus.DOMICILE,
  DignityStatus.EXALTATION,
):
  raise RuntimeError("lost chart or status")
if any(name.startswith(("celestial", "ctypes")) for name in sys.modules):
  raise RuntimeError("native import")
checks: tuple[tuple[str, Callable[[], object], type[Exception]], ...] = (
  ("sign-ruler type", lambda: sign_ruler("aries"), TypeError),  # type: ignore[arg-type]
  (
    "dignity body type",
    lambda: essential_dignities(LunarNode.MEAN_ASCENDING, Sign.ARIES),  # type: ignore[arg-type]
    TypeError,
  ),
  ("unsupported planet", lambda: essential_dignities(Body.PLUTO, Sign.ARIES), ValueError),
  ("boolean house", lambda: HouseRuler(True, Sign.ARIES, None), TypeError),
  ("house range", lambda: HouseRuler(0, Sign.ARIES, None), ValueError),
  (
    "ruler identity",
    lambda: HouseRuler(1, Sign.ARIES, Placement(Body.SUN, Sign.LEO, 0, 1)),
    ValueError,
  ),
  ("chart type", lambda: HouseRulers(None), TypeError),  # type: ignore[arg-type]
)
for label, call, error in checks:
  try:
    call()
  except error:
    pass
  else:
    raise RuntimeError(f"missing public check: {label}")
