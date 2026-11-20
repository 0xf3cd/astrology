"""Planetary returns to stored natal longitudes. 针对已存本命黄经的行星返照。"""

from dataclasses import replace
from datetime import datetime

from astrology.chart import NatalChart
from astrology.config import MajorAspect
from astrology.objects import Body
from astrology.transits import TransitHit, TransitHits, transit_hits


def _post_natal_hits(natal: NatalChart, hits: tuple[TransitHit, ...]) -> tuple[TransitHit, ...]:
  """Keep hits strictly after natal TT. 仅保留严格晚于本命 TT 的命中。"""
  return tuple(hit for hit in hits if hit.jde_tt > natal.times.jde_tt)


def _require_return_result(result: TransitHits) -> None:
  """Require a post-natal single-body conjunction result. 要求本命后的单星体合相结果。"""
  if (
    type(result.chart) is not NatalChart
    or len(result.moving_objects) != 1
    or type(result.moving_objects[0]) is not Body
    or result.moving_objects != result.natal_objects
    or result.aspects != (MajorAspect.CONJUNCTION,)
    or result.hits != _post_natal_hits(result.chart, result.hits)
  ):
    raise ValueError("result must be a post-natal same-body conjunction return on a NatalChart")


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
  not count. Distinct events are never merged by a time tolerance. When the
  interval includes the birth instant, the provider's numerical search may return
  a distinct hit just after natal TT, which passes the strictly-later filter.
  To omit such near-natal hits, choose an interval around the
  later return of interest. An empty hits tuple is valid. Pass a retained hit to
  moment_chart with an explicit location and configuration to build its chart.
  See entry.solar_lunar_returns.

  Wrong natal/body types raise TypeError; a missing natal body raises ValueError.

  查找 [start_utc, end_utc) 内所选 Body 在本命时刻后的全部返照，返回 TransitHits。
  body 须已存在于 NatalChart。同星体合相搜索使用 transit_hits，沿用其转换后 TT 区间、
  有效域及失败合同。只保留严格晚于本命 TT 的命中，本命时刻的精确命中不计入。
  不按时间容差合并不同的事件。区间包含出生时刻时，事件来源的数值搜索可能返回另一个
  稍晚于本命 TT 的命中，它会通过严格晚于本命 TT 的过滤。要排除这种命中，
  请选择之后所关心的返照附近区间。hits 可以为空。将保留的命中连同显式地点和配置交给 moment_chart，
  即可建立返照时刻的盘。
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
  return replace(result, hits=_post_natal_hits(natal, result.hits))
