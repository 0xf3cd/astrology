"""Planetary returns to stored natal longitudes. 针对已存本命黄经的行星返照。"""

from dataclasses import replace
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
  """Find every post-natal return of a Body in [start_utc, end_utc), as TransitHits.

  body must be present on the NatalChart. The same-body conjunction search uses
  transit_hits, including its converted-TT interval, domain and failure contracts.
  Only hits strictly later than the natal TT are retained; an exact natal hit does
  not count. Distinct provider events are never merged by a time tolerance, so a
  birth-inclusive interval can retain a root-adjacent event just after natal TT.
  Choose an interval away from the natal neighborhood to omit that residual. An empty
  hits tuple is valid. Pass a retained hit to moment_chart with an explicit location
  and configuration to build its chart. See entry.solar_lunar_returns.

  Wrong natal/body types raise TypeError; a missing natal body raises ValueError.

  查找 [start_utc, end_utc) 内所选 Body 在本命时刻后的全部返照，返回 TransitHits。
  body 须已存在于 NatalChart。同星体合相搜索使用 transit_hits，沿用其转换后 TT 区间、
  有效域及失败合同。只保留严格晚于本命 TT 的命中，本命时刻的精确命中不计入。
  不按时间容差合并不同的 provider 事件，因此包含本命时刻的区间可能保留紧邻本命、
  稍晚于本命 TT 的数值根；不希望保留该事件时，请选择远离本命附近的查询区间。hits 可以
  为空。将保留的命中连同显式地点和配置交给 moment_chart，即可建立返照时刻的盘。
  定义见 entry.solar_lunar_returns。natal 或 body 类型不符时抛 TypeError；
  本命盘缺少所选星体时抛 ValueError。
  """
  if type(natal) is not NatalChart:
    raise TypeError("natal must be a NatalChart")
  if type(body) is not Body:
    raise TypeError("body must be a Body")
  available = tuple(position.identity for position in natal.positions)
  if body not in available:
    names = ", ".join(identity.value for identity in available) or "none"
    raise ValueError(
      f"body must be available on the NatalChart for a return search; available: {names}"
    )
  result = transit_hits(
    natal,
    start_utc=start_utc,
    end_utc=end_utc,
    moving_objects=(body,),
    natal_objects=(body,),
    aspects=(MajorAspect.CONJUNCTION,),
  )
  return replace(result, hits=tuple(hit for hit in result.hits if hit.jde_tt > natal.times.jde_tt))
