"""Lilly 1647 sign rulers, four statuses and supplied-chart rulership results.

Lilly 1647 星座守护、四种尊贵状态及给定命盘的守护关系结果。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final, cast

from astrology.chart import Chart, Placement, _require_chart, _selected_placements
from astrology.config import Body
from astrology.houses import _require_house_number
from astrology.objects import AstronomicalObject
from astrology.zodiac import _SIGNS, Sign, sign_of

_RULE_ID: Final = "rule.lilly1647.essential_dignities"
_DISPOSITOR_RULE_ID: Final = "rule.project.dispositor_chains"
_DOMICILES: Final[Mapping[Body, tuple[Sign, ...]]] = MappingProxyType(
  {
    Body.SUN: (Sign.LEO,),
    Body.MOON: (Sign.CANCER,),
    Body.MERCURY: (Sign.GEMINI, Sign.VIRGO),
    Body.VENUS: (Sign.TAURUS, Sign.LIBRA),
    Body.MARS: (Sign.ARIES, Sign.SCORPIO),
    Body.JUPITER: (Sign.SAGITTARIUS, Sign.PISCES),
    Body.SATURN: (Sign.CAPRICORN, Sign.AQUARIUS),
  }
)
_EXALTATIONS: Final[Mapping[Body, Sign]] = MappingProxyType(
  {
    Body.SUN: Sign.ARIES,
    Body.MOON: Sign.TAURUS,
    Body.MERCURY: Sign.VIRGO,
    Body.VENUS: Sign.PISCES,
    Body.MARS: Sign.CAPRICORN,
    Body.JUPITER: Sign.CANCER,
    Body.SATURN: Sign.LIBRA,
  }
)
_RULERS: Final[Mapping[Sign, Body]] = MappingProxyType(
  {sign: body for body, signs in _DOMICILES.items() for sign in signs}
)


class DignityStatus(StrEnum):
  """The four assessed sign-level statuses, without scores. 所判断的四种星座级状态，不计分。"""

  DOMICILE = "domicile"
  EXALTATION = "exaltation"
  DETRIMENT = "detriment"
  FALL = "fall"


def sign_ruler(sign: Sign) -> Body:
  """Return the sign's ruler in Lilly's seven-planet set; a non-Sign raises TypeError.

  按 Lilly 的传统星座守护表返回守护星；非 Sign 输入抛出 TypeError。
  """
  if type(sign) is not Sign:
    raise TypeError("sign must be a Sign")
  return _RULERS[sign]


def essential_dignities(body: Body, sign: Sign) -> tuple[DignityStatus, ...]:
  """Return every match in domicile/exaltation/detriment/fall order, or () for none.

  Wrong enum types raise TypeError; an outer-planet Body raises ValueError.
  Assess the whole sign, not exaltation-degree proximity. See the dignity guide.

  按入庙、擢升、失势、落陷顺序返回全部命中，无命中则为 ()。枚举类型错误抛出 TypeError，
  外行星 Body 抛出 ValueError。判断整个星座，不看离擢升度数多近；详见尊贵指南。
  """
  if type(body) is not Body or type(sign) is not Sign:
    raise TypeError("body and sign must use Body and Sign")
  if body not in _DOMICILES:
    raise ValueError(f"Body outside Lilly's seven-planet rule: {body.value}")
  opposite = _SIGNS[(_SIGNS.index(sign) + 6) % len(_SIGNS)]
  return tuple(
    status
    for status, applies in (
      (DignityStatus.DOMICILE, sign in _DOMICILES[body]),
      (DignityStatus.EXALTATION, sign is _EXALTATIONS[body]),
      (DignityStatus.DETRIMENT, opposite in _DOMICILES[body]),
      (DignityStatus.FALL, opposite is _EXALTATIONS[body]),
    )
    if applies
  )


@dataclass(frozen=True, slots=True)
class HouseRuler:
  """One house's cusp sign and its traditional ruler's placement, or None if unavailable.

  Wrong types raise TypeError; a house outside 1..12 or a mismatched placement
  identity raises ValueError.

  单个宫位的宫头星座及传统宫主星落点；未计算落点时为 None。类型错误抛出 TypeError，宫号不在
  1..12 或落点身份不符时抛出 ValueError。
  """

  house: int
  cusp_sign: Sign
  placement: Placement | None

  def __post_init__(self) -> None:
    _require_house_number(self.house)
    if type(self.cusp_sign) is not Sign:
      raise TypeError("cusp_sign must be a Sign")
    if self.placement is not None:
      if type(self.placement) is not Placement:
        raise TypeError("placement must be a Placement or None")
      if self.placement.identity is not self.ruler:
        raise ValueError("placement identity must match the cusp sign's ruler")

  @property
  def ruler(self) -> Body:
    """Return the ruler derived from the cusp sign. 返回从宫头星座推出的宫主星。"""
    return sign_ruler(self.cusp_sign)

  @property
  def statuses(self) -> tuple[DignityStatus, ...] | None:
    """Return all statuses, () for no match, or None for an unavailable placement.

    返回全部状态；() 表示无命中，None 表示落点未计算。
    """
    if self.placement is None:
      return None
    return essential_dignities(self.ruler, self.placement.sign)


@dataclass(frozen=True, slots=True)
class HouseRulers:
  """Derive twelve house-ruler records from one retained natal or moment chart.

  Use actual cusps, not axes; keep repeated signs and missing ruler placements.
  Invalid chart types raise TypeError. Repeated houses accesses return new records that compare equal;
  existing placements and the source chart are retained by identity.

  从保留的本命盘或时刻盘推导十二宫主星记录。使用实际宫头，不以轴代替；保留重复
  星座及缺失的宫主星落点。命盘类型错误时抛出 TypeError。两次读取 houses 所得元组相等，
  但其中的记录不是同一批对象；已有落点及源盘保留原对象。
  """

  chart: Chart

  def __post_init__(self) -> None:
    _require_chart(self.chart)

  @property
  def houses(self) -> tuple[HouseRuler, ...]:
    """Return twelve records in cusp order, retaining available placements.

    按宫头顺序返回十二条记录，保留可用的原落点。
    """
    placements = {p.identity: p for p in self.chart.placements}
    return tuple(
      HouseRuler(house, sign_of(cusp), placements.get(sign_ruler(sign_of(cusp))))
      for house, cusp in enumerate(self.chart.houses.cusps_deg, start=1)
    )

  @property
  def rule_id(self) -> str:
    """Return the named rulership/dignity rule. 返回具名的守护及尊贵规则。"""
    return _RULE_ID


@dataclass(frozen=True, slots=True, init=False)
class Dispositors:
  """Immutable rulership paths for explicit roots in a retained chart.

  The constructor takes only chart and objects, copying the selection into
  source-chart order. Non-chart inputs, non-sequences, strings and wrong identities
  raise TypeError; empty, duplicate or unavailable roots raise ValueError.
  Available but unselected rulers can be intermediates. See entry.dispositor_chains.

  保留源盘、为显式根对象提供不可变的守护路径。构造器只接收 chart 及 objects，
  复制选择并按源盘顺序排列。非命盘、非序列、字符串或错误身份抛出 TypeError；
  空、重复或不可用的根对象抛出 ValueError。未选作根但盘中已有的守护星可作中间节点。
  见 entry.dispositor_chains。
  """

  chart: Chart
  objects: tuple[AstronomicalObject, ...]
  #: Reached object-to-ruler edges, including absent targets. 已到达对象到守护星的边，含缺失目标。
  edges: Mapping[AstronomicalObject, Body] = field(init=False, hash=False)
  #: Distinct available objects per root, before repetition or absence. 各根的可用对象路径，在重复或缺失前停止。
  chains: Mapping[AstronomicalObject, tuple[AstronomicalObject, ...]] = field(
    init=False, hash=False
  )
  #: Reached nontrivial cycles, rotated and ordered by source order. 已到达的非自环循环，按源盘顺序规范起点及排列。
  cycles: tuple[tuple[Body, ...], ...] = field(init=False, hash=False)
  #: Reached self-loop endpoints in source order. 按源盘顺序列出的已到达自环终点。
  final_dispositors: tuple[Body, ...] = field(init=False, hash=False)
  #: Each affected root's absent next ruler. 各受影响根对象缺失的下一颗守护星。
  missing_rulers: Mapping[AstronomicalObject, Body] = field(init=False, hash=False)

  def __init__(self, chart: Chart, objects: Sequence[AstronomicalObject]) -> None:
    selected = _selected_placements(chart, objects)
    placements = {placement.identity: placement for placement in chart.placements}
    roots = tuple(placement.identity for placement in selected)
    order = {identity: index for index, identity in enumerate(placements)}

    edges: dict[AstronomicalObject, Body] = {}
    chains: dict[AstronomicalObject, tuple[AstronomicalObject, ...]] = {}
    cycles: set[tuple[Body, ...]] = set()
    finals: set[Body] = set()
    absent: dict[AstronomicalObject, Body] = {}
    for root in roots:
      path: list[AstronomicalObject] = []
      visited: dict[AstronomicalObject, int] = {}
      current = root
      while True:
        visited[current] = len(path)
        path.append(current)
        ruler = sign_ruler(placements[current].sign)
        edges[current] = ruler
        if ruler not in placements:
          absent[root] = ruler
          break
        if ruler is current:
          finals.add(ruler)
          break
        if ruler in visited:
          cycle = tuple(cast(Body, identity) for identity in path[visited[ruler] :])
          start = min(range(len(cycle)), key=lambda index: order[cycle[index]])
          cycles.add(cycle[start:] + cycle[:start])
          break
        current = ruler
      chains[root] = tuple(path)

    object.__setattr__(self, "chart", chart)
    object.__setattr__(self, "objects", roots)
    object.__setattr__(
      self,
      "edges",
      MappingProxyType({identity: edges[identity] for identity in placements if identity in edges}),
    )
    object.__setattr__(self, "chains", MappingProxyType(chains))
    object.__setattr__(self, "cycles", tuple(sorted(cycles, key=lambda cycle: order[cycle[0]])))
    object.__setattr__(self, "final_dispositors", tuple(sorted(finals, key=order.__getitem__)))
    object.__setattr__(self, "missing_rulers", MappingProxyType(absent))

  @property
  def rule_id(self) -> str:
    """Return the project's chain rule identifier. 返回项目定位星链规则标识。"""
    return _DISPOSITOR_RULE_ID


def chart_dispositors(chart: Chart, *, objects: Sequence[AstronomicalObject]) -> Dispositors:
  """Follow Lilly sign rulers from selected chart placements; see Dispositors.

  从选定的命盘落点沿 Lilly 星座守护表遍历；详见 Dispositors。
  """
  return Dispositors(chart, objects)
