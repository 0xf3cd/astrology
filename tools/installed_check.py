"""Verify the installed package in isolation. 隔离验证已安装的包。"""

import sys
from importlib.metadata import distribution
from pathlib import Path

import astrology


def main(expected_version: str) -> None:
  """Check identity, import origin and native isolation. 检查身份、导入路径及原生库隔离。"""
  metadata = distribution("astrology")
  origin = Path(str(astrology.__file__)).resolve()
  if not origin.is_relative_to(Path(sys.prefix).resolve()):
    raise ValueError("Imported astrology from outside the consumer environment")
  if metadata.version != expected_version:
    raise ValueError("Installed version differs from the built version")
  if not origin.with_name("py.typed").is_file():
    raise ValueError("Installed package is missing py.typed")
  if any(name == "celestial" or name.startswith("celestial.") for name in sys.modules):
    raise ValueError("Import initialized the astronomy adapter")
  print(f"Installed astrology {metadata.version}; optimized={sys.flags.optimize}")


if __name__ == "__main__":
  main(sys.argv[1])
