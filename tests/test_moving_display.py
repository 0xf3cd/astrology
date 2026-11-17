"""Moving-event display and conversion boundaries. 移动事件显示及转换边界。"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, NoReturn

import celestial_calendar as native
import pytest

from astrology import (
  Body,
  EventDisplayError,
  MajorAspect,
  MovingAspectEvents,
  MovingAspectHit,
  RelativeDirection,
  TransitSource,
  format_moving_events,
  format_return_hits,
  format_transit_hits,
  load_catalog,
  moving_hit_utc,
)


def _hit(jde_tt: float = 2460392.2373059206) -> MovingAspectHit:
  return MovingAspectHit(
    Body.MOON,
    Body.SUN,
    MajorAspect.CONJUNCTION,
    0,
    jde_tt,
    10,
    10,
    1,
    2,
    0,
    RelativeDirection.INCREASING,
  )


def _result() -> MovingAspectEvents:
  return MovingAspectEvents(
    datetime(2024, 3, 1, tzinfo=UTC),
    datetime(2024, 6, 1, tzinfo=UTC),
    2460370.5,
    2460462.5,
    ((Body.MOON, Body.SUN),),
    (MajorAspect.CONJUNCTION,),
    tuple(
      TransitSource(body, "position_source", index, "synthetic", 2400000, 2500000, 3660, "window")
      for body, index in ((Body.MOON, 2), (Body.SUN, 1))
    ),
    (_hit(),),
    "synthetic-native",
    "synthetic-astrology",
  )


@pytest.mark.parametrize("language", ("en", "zh-CN"))
def test_populated_and_empty_tables_keep_both_roles_relative_direction_and_tt(
  language: Any,
) -> None:
  result = _result()
  text = format_moving_events(result, load_catalog(), language=language)
  pair_line = (
    "Requested moving pairs (first, second): (Moon [moon], Sun [sun])"
    if language == "en"
    else "请求移动对象对（第一侧，第二侧）: (月亮 [moon], 太阳 [sun])"
  )
  legend = (
    "Relative direction and rate describe second minus first longitude."
    if language == "en"
    else "相对方向与速率按第二侧黄经减第一侧黄经定义。"
  )
  assert pair_line in text.splitlines() and legend in text.splitlines()
  assert "[moon]" in text and "[sun]" in text
  assert "position_source/2" in text and "position_source/1" in text
  assert "2460392.2373059206" in text and "2024-03-22T17:40:34+00:00" in text
  assert "synthetic-astrology / synthetic-native" in text
  row = text.splitlines()[-1].split(" | ")
  assert row[1].endswith("[moon]") and row[2].endswith("[sun]")
  assert row[-1] == repr(result.hits[0].jde_tt)
  assert ("separation increasing" if language == "en" else "角距增大") in text
  assert (
    "First moving object | Second moving object"
    if language == "en"
    else "第一侧移动对象 | 第二侧移动对象"
  ) in text
  assert "黄经增大" not in text and "Fixed source" not in text
  empty = format_moving_events(replace(result, hits=()), load_catalog(), language=language)
  assert pair_line in empty.splitlines() and legend in empty.splitlines()
  assert ("No exact moving-pair events" if language == "en" else "没有精确移动对象对事件") in empty
  assert "[moon]" in empty and "[sun]" in empty and "2460370.5" in empty


def test_explicitly_synthetic_public_major_aspect_tangent_preserves_nonzero_relative_rate() -> None:
  result = _result()
  hit = replace(result.hits[0], direction=RelativeDirection.TANGENT)
  assert hit.relative_rate_deg_per_tt_day == 1
  text = format_moving_events(replace(result, hits=(hit,)), load_catalog())
  assert "separation tangent | 1.0 |" in text


def test_populated_table_converts_only_retained_times(monkeypatch: pytest.MonkeyPatch) -> None:
  def forbidden(*args: object, **kwargs: object) -> NoReturn:
    pytest.fail("Displaying a moving event performed astronomy")

  for name in (
    "longitude_difference_events",
    "longitude_events",
    "positions",
    "chart_snapshot",
    "house_query",
  ):
    monkeypatch.setattr(native, name, forbidden)
  original = native.jde_to_utc
  calls = []

  def convert(value: float) -> native.CivilDateTime:
    calls.append(value)
    return original(value)

  monkeypatch.setattr(native, "jde_to_utc", convert)
  result = _result()
  assert format_moving_events(result, load_catalog())
  assert calls == [result.hits[0].jde_tt]
  calls.clear()
  assert format_moving_events(replace(result, hits=()), load_catalog())
  assert calls == []


@pytest.mark.parametrize(
  "jde_tt,expected",
  [
    (2460392.2373059206, datetime(2024, 3, 22, 17, 40, 34, 47537, tzinfo=UTC)),
    (2457754.5007891664, datetime(2016, 12, 31, 23, 59, 59, 999979, tzinfo=UTC)),
    (2457754.500789167, datetime(2017, 1, 1, 0, 0, 0, 20, tzinfo=UTC)),
    (2457754.5007997686, datetime(2017, 1, 1, 0, 0, 0, 916007, tzinfo=UTC)),
    (2457754.500800926, datetime(2017, 1, 1, 0, 0, 0, 15987, tzinfo=UTC)),
  ],
)
def test_conversion_ordinary_and_real_leap_boundary(jde_tt: float, expected: datetime) -> None:
  hit = _hit(jde_tt)
  assert moving_hit_utc(hit) == expected
  assert hit.jde_tt == jde_tt


@pytest.mark.parametrize("value", (2441000.0, 1867521.5, 13689325.5, 5373485.0))
def test_display_errors_keep_raw_time_and_do_not_discard_hit(value: float) -> None:
  hit = _hit(value)
  with pytest.raises(EventDisplayError) as raised:
    moving_hit_utc(hit)
  assert raised.value.jde_tt == hit.jde_tt == value
  assert raised.value.operation == "jde_to_utc"


def test_display_1972_seam_and_rounding_carry(monkeypatch: pytest.MonkeyPatch) -> None:
  import math

  floor = native.utc_to_jde(native.CivilDateTime(1972, 1, 1, 0))
  with pytest.raises(EventDisplayError):
    moving_hit_utc(_hit(floor))
  assert moving_hit_utc(_hit(math.nextafter(floor, math.inf))) == datetime(
    1972, 1, 1, 0, 0, 0, 40, tzinfo=UTC
  )
  monkeypatch.setattr(
    native, "jde_to_utc", lambda value: native.CivilDateTime(2099, 12, 31, 1 - 1e-12)
  )
  assert moving_hit_utc(_hit()) == datetime(2100, 1, 1, tzinfo=UTC)
  assert (
    format_moving_events(_result(), load_catalog())
    .splitlines()[-1]
    .startswith("2100-01-01T00:00:00+00:00")
  )


def test_conversion_failure_keeps_native_exception_identity(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  error = native.CelestialError("jde_to_utc", "synthetic computation failure", recorded=True)

  def fail(value: float) -> NoReturn:
    raise error

  monkeypatch.setattr(native, "jde_to_utc", fail)
  with pytest.raises(native.CelestialError) as raised:
    moving_hit_utc(_hit())
  assert raised.value is error


def test_populated_formatter_propagates_display_failure_without_losing_tt() -> None:
  floor = native.utc_to_jde(native.CivilDateTime(1972, 1, 1, 0))
  hit = _hit(floor)
  result = replace(
    _result(),
    start_utc=datetime(1972, 1, 1, tzinfo=UTC),
    end_utc=datetime(1972, 1, 2, tzinfo=UTC),
    start_jde_tt=floor,
    end_jde_tt=floor + 1,
    hits=(hit,),
  )
  with pytest.raises(EventDisplayError) as raised:
    format_moving_events(result, load_catalog())
  assert raised.value.jde_tt == hit.jde_tt == floor
  assert raised.value.operation == "jde_to_utc"


def test_transit_formatters_still_reject_a_moving_result() -> None:
  for formatter in (format_transit_hits, format_return_hits):
    with pytest.raises(TypeError, match="TransitHits"):
      formatter(_result(), load_catalog())  # type: ignore[arg-type]


@pytest.mark.parametrize("value", (None, True, "event", 2460392))
def test_reader_rejects_non_hits(value: Any) -> None:
  with pytest.raises(TypeError):
    moving_hit_utc(value)


@pytest.mark.parametrize(
  "overrides", ({"result": None}, {"catalog": None}, {"language": "zh"}, {"language": True})
)
def test_formatter_checks_supplied_inputs(overrides: dict[str, Any]) -> None:
  arguments: dict[str, Any] = {"result": _result(), "catalog": load_catalog()}
  arguments.update(overrides)
  with pytest.raises((ValueError, TypeError)):
    format_moving_events(**arguments)
