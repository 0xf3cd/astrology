"""Installed distribution identity, separate from the Python import name.

已安装分发包的身份，与 Python 导入名分开。
"""

from importlib.metadata import version
from typing import Final

DISTRIBUTION_NAME: Final = "celestial-astrology"


def installed_version() -> str:
  """Read installed metadata explicitly; missing metadata raises PackageNotFoundError.

  显式读取已安装的元数据；缺失时抛出 PackageNotFoundError。
  """
  return version(DISTRIBUTION_NAME)
