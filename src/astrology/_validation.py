"""Numeric input checks shared by the owning domains. 各领域共用的数值输入检查。"""

from math import isfinite
from typing import cast


def finite_number(value: object, name: str) -> float:
  if type(value) not in (int, float):
    raise TypeError(f"{name} must be a number, not bool or a converted string")
  try:
    number = float(cast("int | float", value))
  except OverflowError as exc:
    raise ValueError(f"{name} must be finite") from exc
  if not isfinite(number):
    raise ValueError(f"{name} must be finite")
  return number
