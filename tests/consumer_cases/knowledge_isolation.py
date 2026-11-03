"""Observe explicit uncached resource loading. 观察显式且不缓存的资源加载。"""

import importlib.resources
import sys
from typing import Any

original = importlib.resources.files
calls: list[tuple[Any, ...]] = []


def observed(*args: Any, **kwargs: Any) -> Any:
  calls.append(args)
  return original(*args, **kwargs)


importlib.resources.files = observed

# The first import must be observed before any corpus resource read.
# 首次导入必须在读取任何语料资源之前被观察。
from astrology.knowledge import load_catalog  # noqa: E402

if calls:
  raise RuntimeError("import read a corpus resource")
first = load_catalog()
second = load_catalog()
if first != second or first is second or len(calls) != 2:
  raise RuntimeError("unexpected catalog cache or nondeterminism")
first.lookup("日轮")
first.citations("entry.equinoctial_example")
from astrology import AshmandSignGroup, Sign, ashmand_sign_group  # noqa: E402

if {ashmand_sign_group(sign) for sign in Sign} != set(AshmandSignGroup):
  raise RuntimeError("historical lookup lost a group")
first.citations("entry.ashmand_sign_groups")
overlay = first.entry("entry.cross_house_overlays")
if overlay.chart_applicability != "not_assessed":
  raise RuntimeError("overlay retrieval claimed chart applicability")
first.citations(overlay.identifier)
first.list_variants(concept_id="axis.ascendant")
if any(name.startswith(("celestial", "tzdata", "zoneinfo", "ctypes")) for name in sys.modules):
  raise RuntimeError("knowledge initialized time or native machinery")
