"""Solar and lunar returns to stored natal longitudes. 日月返回已存本命黄经的返照。"""

from datetime import datetime

from astrology.chart import NatalChart
from astrology.config import MajorAspect
from astrology.objects import Body
from astrology.transits import TransitHits, transit_hits


def return_hits(
  natal: NatalChart,
  body: Body,
  *,
  start_utc: datetime,
  end_utc: datetime,
) -> TransitHits:
  """Find every solar or lunar return in [start_utc, end_utc), as TransitHits.

  body must be SUN or MOON and present on the NatalChart. The same-body conjunction
  search uses transit_hits, including its UTC, domain and failure contracts. An
  empty hits tuple is valid. Pass a retained hit to moment_chart with an explicit
  location and configuration to build its chart. See entry.solar_lunar_returns.
  Wrong natal/body types raise TypeError; unsupported bodies or a missing natal
  luminary raise ValueError.

  查找 [start_utc, end_utc) 内全部日返照或月返照，返回 TransitHits。body 须为本命盘中
  已有的 SUN 或 MOON；同星体合相搜索使用 transit_hits，沿用其 UTC、有效域及失败合同。
  hits 可以为空。将保留的命中连同显式地点和配置交给 moment_chart，即可建立返照时刻的盘。
  定义见 entry.solar_lunar_returns。
  natal 或 body 类型不符时抛 TypeError；星体不受支持或本命盘缺少所选日月时抛 ValueError。
  """
  if type(natal) is not NatalChart:
    raise TypeError("natal must be a NatalChart")
  if type(body) is not Body:
    raise TypeError("body must be a Body")
  if body not in (Body.SUN, Body.MOON):
    raise ValueError("body must be SUN or MOON for a return search")
  return transit_hits(
    natal,
    start_utc=start_utc,
    end_utc=end_utc,
    moving_objects=(body,),
    natal_objects=(body,),
    aspects=(MajorAspect.CONJUNCTION,),
  )
