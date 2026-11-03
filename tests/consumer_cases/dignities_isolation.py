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
checks: tuple[tuple[Callable[[], object], type[Exception]], ...] = (
  (lambda: sign_ruler("aries"), TypeError),  # type: ignore[arg-type]
  (lambda: essential_dignities(LunarNode.MEAN_ASCENDING, Sign.ARIES), TypeError),  # type: ignore[arg-type]
  (lambda: essential_dignities(Body.PLUTO, Sign.ARIES), ValueError),
  (lambda: HouseRuler(True, Sign.ARIES, None), TypeError),
  (lambda: HouseRuler(0, Sign.ARIES, None), ValueError),
  (lambda: HouseRuler(1, Sign.ARIES, Placement(Body.SUN, Sign.LEO, 0, 1)), ValueError),
  (lambda: HouseRulers(None), TypeError),  # type: ignore[arg-type]
)
for call, error in checks:
  try:
    call()
  except error:
    pass
  else:
    raise RuntimeError("missing public check")
