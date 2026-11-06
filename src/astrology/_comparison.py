"""Source compatibility and stored-chart selection checks. 来源兼容性与已存命盘的对象选择检查。"""

from collections.abc import Sequence

from astrology.chart import NatalChart
from astrology.objects import Axis, ChartObject, _is_chart_object


def _require_comparable_sources(chart_left: NatalChart, chart_right: NatalChart) -> None:
  """Keep this boundary check even while public constructors admit one convention.

  即使公开构造器目前只接纳一种坐标约定，也保留比较入口处的校验。
  """
  if type(chart_left) is not NatalChart or type(chart_right) is not NatalChart:
    raise TypeError("chart_left and chart_right must be NatalChart values")
  if (
    chart_left.requested.zodiac != chart_right.requested.zodiac
    or chart_left.requested.center != chart_right.requested.center
    or chart_left.provenance.position_frame != chart_right.provenance.position_frame
  ):
    raise ValueError("Cross charts must use matching zodiac, center and position frame")


def _selection_for_chart(
  chart: NatalChart, objects: Sequence[ChartObject], name: str
) -> tuple[ChartObject, ...]:
  """Validate a chart selection and order it by stored positions, then axes.

  校验命盘中的对象选择，按已存位置及四轴的顺序排列。
  """
  if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
    raise TypeError(f"{name} must be a sequence of Body, LunarNode or Axis values")
  selected = tuple(objects)
  if any(not _is_chart_object(value) for value in selected):
    raise TypeError(f"{name} must contain Body, LunarNode or Axis values")
  if len(set(selected)) != len(selected):
    raise ValueError(f"{name} must not contain duplicate identities")
  available: tuple[ChartObject, ...] = (*[position.identity for position in chart.positions], *Axis)
  if not set(selected) <= set(available):
    raise ValueError(f"{name} must name only objects available in its source chart")
  return tuple(identity for identity in available if identity in selected)
