"""Input checks shared by the owning domains. 各领域共用的输入检查。"""

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


def nonempty_text(value: str, name: str) -> None:
  """Require a nonblank built-in string. 要求非空白的内建字符串。"""
  if type(value) is not str or not value.strip():
    raise ValueError(f"{name} must be a nonempty plain string")
