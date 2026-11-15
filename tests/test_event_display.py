"""UTC readout and bilingual exact-event tables. UTC 读取与双语精确事件表。"""

import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn, cast

import celestial_calendar as native
import pytest

from astrology import (
  Body,
  ChartDomainError,
  EventDisplayError,
  LunarNode,
  MajorAspect,
  MomentChart,
  MomentInput,
  NatalChart,
  TransitDirection,
  TransitDomainError,
  TransitHit,
  TransitHits,
  TransitSource,
  format_return_hits,
  format_transit_hits,
  load_catalog,
  transit_hit_utc,
)
from tools.installed_check import _cross_source

CATALOG = load_catalog()
ORDINARY_JDE = 2460392.2373059206


def _chart() -> NatalChart:
  return _cross_source(2000, "event-display", ((Body.SUN, 10),))


def _source(body: Body) -> TransitSource:
  return TransitSource(
    body, "position_source", 3, "synthetic model", 2400000, 2500000, 3660, "window"
  )


def _hit(jde_tt: float = ORDINARY_JDE, body: Body = Body.SUN) -> TransitHit:
  return TransitHit(
    body,
    Body.SUN,
    MajorAspect.CONJUNCTION,
    0,
    10,
    jde_tt,
    10.000000001,
    1.2,
    TransitDirection.INCREASING,
  )


def _result(
  *,
  moving: Body = Body.SUN,
  jde_tt: float = ORDINARY_JDE,
  chart: NatalChart | MomentChart | None = None,
) -> TransitHits:
  source_chart = _chart() if chart is None else chart
  return TransitHits(
    source_chart,
    datetime(2024, 3, 1, tzinfo=UTC),
    datetime(2024, 6, 1, tzinfo=UTC),
    2460370.5,
    2460462.5,
    (moving,),
    (Body.SUN,),
    (MajorAspect.CONJUNCTION,),
    (_source(moving),),
    (_hit(jde_tt, moving),),
    "synthetic-celestial",
    "synthetic-astrology",
  )


def _empty(result: TransitHits) -> TransitHits:
  return replace(result, hits=())


@pytest.mark.parametrize("mode", [(), ("-O",)])
@pytest.mark.parametrize("external_cwd", [False, True])
def test_empty_tables_and_imports_stay_native_free(
  mode: tuple[str, ...], external_cwd: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
  if external_cwd:
    monkeypatch.chdir(tmp_path)
  program = (Path(__file__).parent / "consumer_cases" / "event_tables_isolation.py").read_text(
    encoding="utf-8"
  )
  subprocess.run(
    (sys.executable, *mode, "-c", program),
    check=True,
    capture_output=True,
    text=True,
    cwd=Path(__file__).parents[1],
  )


def test_ordinary_hit_utc_needs_no_location_or_chart() -> None:
  hit = _hit()
  converted = transit_hit_utc(hit)
  assert converted == datetime(2024, 3, 22, 17, 40, 34, 47537, tzinfo=UTC)
  assert hit.jde_tt == ORDINARY_JDE


@pytest.mark.parametrize("value", [None, True, "hit", 2460392.0])
def test_hit_utc_rejects_wrong_types(value: object) -> None:
  with pytest.raises(TypeError, match="TransitHit"):
    transit_hit_utc(cast(TransitHit, value))


def test_hit_type_validation_works_under_optimized_python() -> None:
  program = (
    "from astrology import transit_hit_utc\n"
    "try:\n"
    "  transit_hit_utc(None)\n"
    "except TypeError:\n"
    "  pass\n"
    "else:\n"
    "  raise RuntimeError('optimized type check missing')\n"
  )
  subprocess.run(
    (sys.executable, "-O", "-c", program),
    check=True,
    capture_output=True,
    text=True,
    cwd=Path(__file__).parents[1],
  )


def test_pre_1972_ut1_substitute_is_not_labeled_ordinary_utc() -> None:
  floor = native.utc_to_jde(native.CivilDateTime(1972, 1, 1, 0))
  for value in (floor, floor - 1 / 86400, 2441000.0):
    with pytest.raises(EventDisplayError) as raised:
      transit_hit_utc(_hit(value))
    assert type(raised.value) is EventDisplayError
    assert not isinstance(raised.value, (ChartDomainError, TransitDomainError))
    assert raised.value.jde_tt == value


def test_1972_floor_plus_one_ulp_is_modern_utc() -> None:
  floor = native.utc_to_jde(native.CivilDateTime(1972, 1, 1, 0))
  import math

  assert transit_hit_utc(_hit(math.nextafter(floor, math.inf))) == datetime(
    1972, 1, 1, 0, 0, 0, 40, tzinfo=UTC
  )
  assert transit_hit_utc(_hit(native.utc_to_jde(native.CivilDateTime(1972, 7, 1, 0)))) == datetime(
    1972, 7, 1, 0, 0, 0, 999994, tzinfo=UTC
  )


@pytest.mark.parametrize("value", [1867521.5, 13689325.5, 5373485.0])
def test_display_range_errors_have_display_specific_type_and_cause(value: float) -> None:
  with pytest.raises(EventDisplayError) as raised:
    transit_hit_utc(_hit(value))
  assert type(raised.value) is EventDisplayError
  assert raised.value.operation == "jde_to_utc"
  assert raised.value.upstream_message
  assert raised.value.__cause__ is not None


def test_native_conversion_failure_propagates_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
  failure = native.CelestialError("jde_to_utc", "synthetic conversion failure", recorded=True)

  def reject(value: float) -> NoReturn:
    raise failure

  monkeypatch.setattr(native, "jde_to_utc", reject)
  with pytest.raises(native.CelestialError) as raised:
    transit_hit_utc(_hit())
  assert raised.value is failure


def test_hit_conversion_uses_the_celestial_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
  import astrology.celestial as adapter

  calls: list[float] = []
  original = adapter._civil_from_tt

  def observed(jde_tt: float) -> native.CivilDateTime:
    calls.append(jde_tt)
    return original(jde_tt)

  monkeypatch.setattr(adapter, "_civil_from_tt", observed)
  hit = _hit()
  assert transit_hit_utc(hit) == datetime(2024, 3, 22, 17, 40, 34, 47537, tzinfo=UTC)
  assert calls == [hit.jde_tt]


def test_leap_interior_display_can_enter_next_year_and_reverse() -> None:
  first = _hit(2457754.5007916666)
  second = _hit(2457754.5007997686)
  third = _hit(2457754.500800926)
  assert transit_hit_utc(first) == datetime(2017, 1, 1, 0, 0, 0, 215991, tzinfo=UTC)
  assert transit_hit_utc(second) == datetime(2017, 1, 1, 0, 0, 0, 916007, tzinfo=UTC)
  assert transit_hit_utc(third) == datetime(2017, 1, 1, 0, 0, 0, 15987, tzinfo=UTC)
  assert first.jde_tt < second.jde_tt < third.jde_tt
  assert transit_hit_utc(second) > transit_hit_utc(third)
  assert transit_hit_utc(second).isoformat(timespec="seconds") == transit_hit_utc(third).isoformat(
    timespec="seconds"
  )


def test_leap_start_two_binary64_sides_are_not_called_a_midpoint() -> None:
  before = transit_hit_utc(_hit(2457754.5007891664))
  after = transit_hit_utc(_hit(2457754.500789167))
  assert before == datetime(2016, 12, 31, 23, 59, 59, 999979, tzinfo=UTC)
  assert after == datetime(2017, 1, 1, 0, 0, 0, 20, tzinfo=UTC)


def test_microsecond_rounding_carries_year_but_seconds_display_truncates(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(
    native,
    "jde_to_utc",
    lambda value: native.CivilDateTime(2099, 12, 31, 1 - 1e-12),
  )
  converted = transit_hit_utc(_hit())
  assert converted == datetime(2100, 1, 1, tzinfo=UTC)
  assert converted.isoformat(timespec="seconds") == "2100-01-01T00:00:00+00:00"
  monkeypatch.setattr(
    native,
    "jde_to_utc",
    lambda value: native.CivilDateTime(2024, 1, 1, 0.999999 / 86400),
  )
  truncated = transit_hit_utc(_hit())
  assert truncated.microsecond == 999999
  assert truncated.isoformat(timespec="seconds") == "2024-01-01T00:00:00+00:00"
  for formatter in (format_transit_hits, format_return_hits):
    row = formatter(_result(), CATALOG).splitlines()[-1]
    assert row.startswith("2024-01-01T00:00:00+00:00 |")


def test_populated_transit_table_has_context_roles_direction_and_raw_tt() -> None:
  result = _result(moving=Body.MERCURY)
  text = format_transit_hits(result, CATALOG)
  assert text.startswith("Exact transit hits\nSupplied UTC interval [start, end):")
  assert "Converted TT interval [start, end): [2460370.5, 2460462.5)" in text
  assert "Event models: Mercury [mercury]: position_source/3" in text
  assert (
    "astrology / celestial-calendar versions: synthetic-astrology / synthetic-celestial" in text
  )
  assert "UTC | Moving object | Fixed source | Aspect | Branch | Direction | JDE(TT)" in text
  assert "2024-03-22T17:40:34+00:00" in text
  assert (
    "Mercury [mercury] | Sun [sun] | Conjunction | 0°00'00\" | increasing | 2460392.2373059206"
    in text
  )


def test_populated_return_table_has_chinese_vocabulary_and_returning_body() -> None:
  text = format_return_hits(_result(), CATALOG, language="zh-CN")
  assert text.startswith("行星返照\n给定 UTC 区间")
  assert "转换后 TT 区间" in text
  assert "事件模型: 太阳 [sun]: position_source/3" in text
  assert "UTC | 返照星体 | 方向 | JDE(TT)" in text
  assert "太阳 [sun] | 黄经增大 | 2460392.2373059206" in text


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_empty_tables_are_meaningful_and_do_not_convert(
  language: str, monkeypatch: pytest.MonkeyPatch
) -> None:
  result = _empty(_result())

  def forbidden(value: float) -> NoReturn:
    raise AssertionError("An empty table performed UTC conversion")

  monkeypatch.setattr(native, "jde_to_utc", forbidden)
  transit = format_transit_hits(result, CATALOG, language=cast(Any, language))
  returns = format_return_hits(result, CATALOG, language=cast(Any, language))
  expected = "No exact transit hits" if language == "en" else "没有精确行运命中"
  assert expected in transit
  assert ("No returns" if language == "en" else "没有返照") in returns


def test_populated_formatting_calls_only_tt_to_civil_conversion(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[float] = []
  original = native.jde_to_utc

  def spy(value: float) -> Any:
    calls.append(value)
    return original(value)

  def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
    pytest.fail("Event formatting crossed a search/chart boundary")

  monkeypatch.setattr(native, "jde_to_utc", spy)
  monkeypatch.setattr(native, "utc_to_jde", forbidden)
  import astrology.celestial as adapter

  for name in ("snapshot", "transit_events", "transit_interval", "moment_utc"):
    monkeypatch.setattr(adapter, name, forbidden)
  format_transit_hits(_result(moving=Body.MERCURY), CATALOG)
  format_return_hits(_result(), CATALOG)
  assert calls == [ORDINARY_JDE, ORDINARY_JDE]


def test_transit_table_uses_fixed_source_for_moment_chart() -> None:
  natal = _chart()
  assert natal.resolved.record.location is not None
  moving = MomentChart(
    MomentInput(datetime(2000, 1, 1, tzinfo=UTC), natal.resolved.record.location),
    natal.requested,
    natal.effective,
    natal.provenance,
    natal.times,
    natal.positions,
    natal.houses,
    natal.placements,
    natal.aspects,
  )
  text = format_transit_hits(_result(chart=moving), CATALOG)
  assert "Fixed source" in text
  assert "Natal object" not in text


@pytest.mark.parametrize("language", ["fr", "", None, 1])
def test_formatters_reject_bad_language(language: object) -> None:
  with pytest.raises(ValueError, match="language"):
    format_transit_hits(_result(), CATALOG, language=cast(Any, language))
  with pytest.raises(ValueError, match="language"):
    format_return_hits(_result(), CATALOG, language=cast(Any, language))


@pytest.mark.parametrize("value", [None, "result", 1])
def test_formatters_reject_wrong_result_and_catalog_types(value: object) -> None:
  with pytest.raises(TypeError):
    format_transit_hits(cast(TransitHits, value), CATALOG)
  with pytest.raises(TypeError):
    format_return_hits(cast(TransitHits, value), CATALOG)
  with pytest.raises(TypeError):
    format_transit_hits(_result(), cast(Any, value))
  with pytest.raises(TypeError):
    format_return_hits(_result(), cast(Any, value))


def test_return_formatter_rejects_non_return_transit_result() -> None:
  with pytest.raises(ValueError, match="post-natal same-body"):
    format_return_hits(_result(moving=Body.MERCURY), CATALOG)


def test_return_formatter_does_not_define_node_returns() -> None:
  node = LunarNode.MEAN_ASCENDING
  result = replace(
    _result(),
    chart=_cross_source(2000, "node-display", ((node, 10),)),
    moving_objects=(node,),
    natal_objects=(node,),
    sources=(replace(_source(Body.SUN), moving_object=node),),
    hits=(),
  )
  with pytest.raises(ValueError, match="same-body"):
    format_return_hits(result, CATALOG)


def test_return_formatter_rejects_moment_source_and_multi_selections() -> None:
  natal = _chart()
  assert natal.resolved.record.location is not None
  moving = MomentChart(
    MomentInput(datetime(2000, 1, 1, tzinfo=UTC), natal.resolved.record.location),
    natal.requested,
    natal.effective,
    natal.provenance,
    natal.times,
    natal.positions,
    natal.houses,
    natal.placements,
    natal.aspects,
  )
  with pytest.raises(ValueError, match="NatalChart"):
    format_return_hits(_result(chart=moving), CATALOG)
  result = _result()
  multi_moving = replace(
    result,
    moving_objects=(Body.SUN, Body.MOON),
    sources=(_source(Body.SUN), _source(Body.MOON)),
    hits=(),
  )
  with pytest.raises(ValueError, match="same-body"):
    format_return_hits(multi_moving, CATALOG)
  multi_aspect = replace(result, aspects=(MajorAspect.CONJUNCTION, MajorAspect.OPPOSITION), hits=())
  with pytest.raises(ValueError, match="same-body"):
    format_return_hits(multi_aspect, CATALOG)


def test_return_formatter_rejects_natal_or_pre_natal_hits() -> None:
  result = _result()
  chart = result.chart
  assert isinstance(chart, NatalChart)
  natal_hit = replace(result.hits[0], jde_tt=chart.times.jde_tt)
  start_tt = chart.times.jde_tt - 1
  end_tt = chart.times.jde_tt + 1
  start_utc = chart.resolved.utc - timedelta(days=1)
  end_utc = chart.resolved.utc + timedelta(days=1)
  invalid = replace(
    result,
    start_utc=start_utc,
    end_utc=end_utc,
    start_jde_tt=start_tt,
    end_jde_tt=end_tt,
    hits=(natal_hit,),
  )
  with pytest.raises(ValueError, match="post-natal"):
    format_return_hits(invalid, CATALOG)
