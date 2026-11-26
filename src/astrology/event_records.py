"""Provider records and display errors shared by exact-event queries.

精确事件查询共用的事件模型记录及显示错误。
"""

from dataclasses import dataclass

from astrology._validation import finite_number, nonempty_text
from astrology.objects import AstronomicalObject, _is_astronomical_object


class EventDisplayError(ValueError):
  """A retained event TT cannot be represented as ordinary display UTC.

  The source-event TT and conversion operation are retained. Conversion failures also
  retain the exact upstream message and chained cause.
  Native computation failures propagate unchanged instead of becoming this error.

  保留事件的 TT 无法表示为普通显示 UTC。保留源事件 TT 和转换操作；
  转换失败时还保留上游原始错误文本及异常因果链。
  原生计算失败直接向外抛出，不改写为本错误。
  """

  def __init__(
    self,
    message: str,
    *,
    jde_tt: float,
    operation: str = "jde_to_utc",
    upstream_message: str | None = None,
  ) -> None:
    super().__init__(message)
    self.jde_tt = jde_tt
    self.operation = operation
    self.upstream_message = upstream_message


@dataclass(frozen=True, slots=True)
class TransitSource:
  """One moving object's effective model and bounded event window.

  Bounds and maximum span are in JDE(TT) and TT days. Descriptions are copied from
  the upstream; these implementation windows are not astronomical accuracy bounds.

  一个移动对象实际使用的模型及有界事件求值窗口。端点为 JDE(TT)，最长区间以 TT 日计。
  说明文字复制自上游；实现求值窗口不是天文精度界。
  """

  moving_object: AstronomicalObject
  model_kind: str
  model_identity: int
  model_description: str
  domain_start_jde_tt: float
  domain_end_jde_tt: float
  maximum_span_tt_days: float
  capability_description: str

  def __post_init__(self) -> None:
    if not _is_astronomical_object(self.moving_object):
      raise TypeError("moving_object must be a Body or LunarNode")
    if type(self.model_kind) is not str or self.model_kind != "position_source":
      raise ValueError("model_kind must be position_source")
    if type(self.model_identity) is not int or self.model_identity <= 0:
      raise ValueError("model_identity must be a positive integer")
    nonempty_text(self.model_description, "model_description")
    nonempty_text(self.capability_description, "capability_description")
    for name in ("domain_start_jde_tt", "domain_end_jde_tt", "maximum_span_tt_days"):
      object.__setattr__(self, name, finite_number(getattr(self, name), name))
    if self.domain_start_jde_tt >= self.domain_end_jde_tt or self.maximum_span_tt_days <= 0:
      raise ValueError("Event domain and maximum span must be nonempty and positive")
