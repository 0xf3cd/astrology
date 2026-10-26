"""Equal-count sign statistics and lunar-phase composition from supplied chart values.

从给定命盘值组合等权星座统计与月相，不重新计算天文。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from astrology.chart import NatalChart, Placement
from astrology.config import Body, LunarNode
from astrology.lunar_phase import LunarPhaseResult, lunar_phase
from astrology.zodiac import Element, Modality, element_of, modality_of


@dataclass(frozen=True, slots=True)
class SignDistribution:
  """An immutable, nonempty Placement snapshot; each distinct object contributes one count.

  Input sequences are copied to tuples; counts include zero for every category,
  and proportions are count/total. Objects and total derive from the snapshot.
  Invalid containers/members raise TypeError, empty or duplicate populations
  ValueError. The caller is responsible for common provenance of low-level
  placements; this record does not authenticate a chart or assign object weights.

  不可变且非空的 Placement 快照，每个不同对象计一次。输入序列复制成元组，计数包含各类的
  零值，比例为计数除以总数；对象及总数从快照推导。容器或成员类型非法抛出 TypeError，空集合或
  重复对象抛出 ValueError。调用方负责保证低层落点的共同来源；本记录不核实命盘来源或设置对象权重。
  """

  placements: tuple[Placement, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.placements, Sequence) or isinstance(self.placements, (str, bytes)):
      raise TypeError("placements must be a sequence")
    snapshot = tuple(self.placements)
    if any(type(p) is not Placement for p in snapshot):
      raise TypeError("placements must contain Placement values")
    if not snapshot:
      raise ValueError("placements must not be empty")
    if len({p.identity for p in snapshot}) != len(snapshot):
      raise ValueError("placements must not contain duplicate identities")
    object.__setattr__(self, "placements", snapshot)

  @property
  def objects(self) -> tuple[Body | LunarNode, ...]:
    """Return the counted identities in snapshot order. 返回按快照顺序排列的计数对象。"""
    return tuple(p.identity for p in self.placements)

  @property
  def total(self) -> int:
    """Return the common nonzero denominator. 返回共同的非零分母。"""
    return len(self.placements)

  @property
  def element_counts(self) -> Mapping[Element, int]:
    """Return all four element counts, including zero. 返回四元素计数，包含零。"""
    return MappingProxyType(
      {e: sum(element_of(p.sign) is e for p in self.placements) for e in Element}
    )

  @property
  def modality_counts(self) -> Mapping[Modality, int]:
    """Return all three modality counts, including zero. 返回三模式计数，包含零。"""
    return MappingProxyType(
      {m: sum(modality_of(p.sign) is m for p in self.placements) for m in Modality}
    )

  @property
  def element_proportions(self) -> Mapping[Element, float]:
    """Return each element count divided by total. 返回各元素计数除以总数的比例。"""
    return MappingProxyType({e: n / self.total for e, n in self.element_counts.items()})

  @property
  def modality_proportions(self) -> Mapping[Modality, float]:
    """Return each modality count divided by total. 返回各模式计数除以总数的比例。"""
    return MappingProxyType({m: n / self.total for m, n in self.modality_counts.items()})


def sign_distribution(placements: Sequence[Placement]) -> SignDistribution:
  """Count an explicit nonempty population, preserving its order; see SignDistribution's checks.

  统计显式提供的非空落点集合，保留输入顺序；校验规则见 SignDistribution。
  """
  # Validate before conversion so None, strings and iterators do not become an implicit population.
  # 在转换前校验，避免把 None、字符串或迭代器当作落点集合。
  if not isinstance(placements, Sequence) or isinstance(placements, (str, bytes)):
    raise TypeError("placements must be a sequence")
  return SignDistribution(tuple(placements))


def chart_sign_distribution(
  chart: NatalChart, *, objects: Sequence[Body | LunarNode]
) -> SignDistribution:
  """Count explicitly selected existing placements in source-chart order, without astronomy.

  No default population is inferred. None, strings, wrong enums or invalid chart
  types raise TypeError; empty/duplicate selections or unavailable objects raise
  ValueError. The source chart is unchanged, and no missing object is calculated.

  按源盘顺序统计显式选择的已有落点，不调用天文库。不推断默认统计对象。None、字符串、其他枚举
  或错误的命盘类型抛出 TypeError；空选择、重复选择或缺失对象抛出 ValueError。源盘不变，不补算缺失对象。
  """
  if type(chart) is not NatalChart:
    raise TypeError("chart must be a NatalChart")
  if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
    raise TypeError("objects must be a sequence")
  selected = tuple(objects)
  if any(type(identity) not in (Body, LunarNode) for identity in selected):
    raise TypeError("objects must contain Body or LunarNode values")
  if not selected or len(set(selected)) != len(selected):
    raise ValueError("objects must be nonempty and contain no duplicate identities")
  available = {p.identity for p in chart.placements}
  missing = [identity.value for identity in selected if identity not in available]
  if missing:
    raise ValueError(f"Objects unavailable in chart: {', '.join(missing)}")
  return sign_distribution([p for p in chart.placements if p.identity in selected])


def natal_lunar_phase(chart: NatalChart) -> LunarPhaseResult:
  """Compose lunar phase from this chart's Sun/Moon in its shared frame, without astronomy.

  Wrong chart types raise TypeError; a missing Sun or Moon raises ValueError
  naming the absent objects. Nothing is recalculated or added to the source chart.

  用此盘共同坐标约定下的日月位置组合月相，不调用天文库。命盘类型错误抛出 TypeError；
  缺太阳或月亮时抛出 ValueError 并列出缺失对象。不重新计算，也不向源盘添加内容。
  """
  if type(chart) is not NatalChart:
    raise TypeError("chart must be a NatalChart")
  positions = {p.identity: p.longitude_deg for p in chart.positions}
  missing = [body.value for body in (Body.SUN, Body.MOON) if body not in positions]
  if missing:
    raise ValueError(f"Objects unavailable in chart: {', '.join(missing)}")
  return lunar_phase(positions[Body.SUN], positions[Body.MOON])
