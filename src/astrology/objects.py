"""Object identities and the families admitted by their consumers, without astronomy.

对象身份及各使用方接纳的对象类别，不调用天文库。
"""

from enum import StrEnum
from typing import TypeAlias, TypeGuard


class Body(StrEnum):
  """Physical natal bodies, distinct from mathematical nodes. 本命盘物理天体，与数学交点区分。"""

  SUN = "sun"
  MOON = "moon"
  MERCURY = "mercury"
  VENUS = "venus"
  MARS = "mars"
  JUPITER = "jupiter"
  SATURN = "saturn"
  URANUS = "uranus"
  NEPTUNE = "neptune"
  PLUTO = "pluto"


class NodeDefinition(StrEnum):
  """Named lunar-node definitions, not accuracy settings. 具名月交点定义，不是精度档位。"""

  MEAN = "mean"
  MEEUS_FIVE_TERM_TRUE = "meeus_five_term_true"


class LunarNode(StrEnum):
  """Mathematical nodes whose identity includes their definition and direction.

  数学月交点，其标识同时包含定义与升降方向。
  """

  MEAN_ASCENDING = "mean_ascending_node"
  MEAN_DESCENDING = "mean_descending_node"
  MEEUS_FIVE_TERM_TRUE_ASCENDING = "meeus_five_term_true_ascending_node"
  MEEUS_FIVE_TERM_TRUE_DESCENDING = "meeus_five_term_true_descending_node"

  @property
  def definition(self) -> NodeDefinition:
    """Return the identity's named definition. 返回该标识对应的具名定义。"""
    return {
      LunarNode.MEAN_ASCENDING: NodeDefinition.MEAN,
      LunarNode.MEAN_DESCENDING: NodeDefinition.MEAN,
      LunarNode.MEEUS_FIVE_TERM_TRUE_ASCENDING: NodeDefinition.MEEUS_FIVE_TERM_TRUE,
      LunarNode.MEEUS_FIVE_TERM_TRUE_DESCENDING: NodeDefinition.MEEUS_FIVE_TERM_TRUE,
    }[self]


class Axis(StrEnum):
  """Stored chart axes, distinct from bodies, nodes and house cusps.

  Iteration defines the ASC/MC/DSC/IC append order for selected aspect axes.

  命盘保存的四轴身份，与天体、交点及宫头区分。
  枚举迭代顺序决定所选相位轴按上升、中天、下降、天底顺序追加。
  """

  ASCENDANT = "ascendant"
  MIDHEAVEN = "midheaven"
  DESCENDANT = "descendant"
  IMUM_COELI = "imum_coeli"


#: Native-output identities, also used by placements and statistics. 天文输出、落点及统计所用的身份。
AstronomicalObject: TypeAlias = Body | LunarNode
#: Aspect identities, including explicitly selected stored axes. 相位所用的身份，含显式选择的已存四轴。
ChartObject: TypeAlias = AstronomicalObject | Axis


def _is_astronomical_object(value: object) -> TypeGuard[AstronomicalObject]:
  return isinstance(value, AstronomicalObject)


def _is_chart_object(value: object) -> TypeGuard[ChartObject]:
  return isinstance(value, ChartObject)
