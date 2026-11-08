"""Moment input, calculation, source-time and consumer contracts. 时刻盘输入、计算、来源时刻及消费合同。"""

import importlib
import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, cast

import pytest

from astrology import (
  AspectRule,
  Body,
  ChartConfig,
  ChartDomainError,
  Dispositors,
  HistoricalTimeError,
  HouseRulers,
  HouseSystem,
  Location,
  MajorAspect,
  MomentChart,
  MomentInput,
  NatalChart,
  TransitDirection,
  TransitHit,
  chart_sign_distribution,
  cross_chart_aspects,
  cross_chart_house_overlays,
  format_chart,
  load_catalog,
  moment_chart,
  natal_lunar_phase,
  transit_hits,
)

NOW = datetime(2024, 1, 1, tzinfo=UTC)
SITE = Location(0, 0)
CONFIG = ChartConfig(HouseSystem.WHOLE_SIGN, tuple(Body), ())


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_supplied_moment_consumers_remain_native_and_time_data_free(mode: tuple[str, ...]) -> None:
  program = Path("tests/consumer_cases/moments_isolation.py").read_text(encoding="utf-8")
  subprocess.run((sys.executable, *mode, "-c", program), check=True, capture_output=True, text=True)


def _hit(jde_tt: float) -> TransitHit:
  return TransitHit(
    Body.MERCURY,
    Body.SUN,
    MajorAspect.CONJUNCTION,
    0,
    10,
    jde_tt,
    10,
    1,
    TransitDirection.INCREASING,
  )


class ChangingOffset(tzinfo):
  offset = timedelta(hours=2)

  def utcoffset(self, dt: datetime | None) -> timedelta:
    return self.offset

  def dst(self, dt: datetime | None) -> timedelta:
    return timedelta(0)

  def tzname(self, dt: datetime | None) -> str:
    return "synthetic"


def test_datetime_input_is_canonical_isolated_and_has_no_birth_fields() -> None:
  zone = ChangingOffset()
  chart = moment_chart(datetime(2024, 1, 1, 2, tzinfo=zone, fold=1), SITE, CONFIG)
  zone.offset = timedelta(hours=4)
  assert chart.moment == MomentInput(NOW, SITE)
  assert chart.moment.utc.tzinfo is UTC and chart.moment.utc.fold == 0
  assert chart.moment.source_jde_tt is None
  assert "resolved" not in {f.name for f in fields(chart)}
  assert {f.name for f in fields(chart.moment)} == {"utc", "location", "source_jde_tt"}
  assert hash(chart) == hash(replace(chart))
  with pytest.raises(FrozenInstanceError):
    chart.moment = chart.moment  # type: ignore[misc]


def test_real_moment_matches_natal_snapshot_without_constructing_a_birth_record(
  recorded_chart: NatalChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  import astrology.birth as birth

  def forbidden(*args: object, **kwargs: object) -> Any:
    pytest.fail("Moment calculation must not construct a birth record")

  monkeypatch.setattr(birth.BirthRecord, "__init__", forbidden)
  chart = moment_chart(
    recorded_chart.resolved.utc,
    cast(Location, recorded_chart.resolved.record.location),
    recorded_chart.requested,
  )
  assert type(chart) is MomentChart
  for name in (
    "requested",
    "effective",
    "provenance",
    "times",
    "positions",
    "houses",
    "placements",
    "aspects",
  ):
    assert getattr(chart, name) == getattr(recorded_chart, name)


@pytest.mark.parametrize(
  "instant,error",
  [
    (None, TypeError),
    ("2024-01-01", TypeError),
    (datetime(2024, 1, 1), ValueError),
    (datetime(1972, 1, 1, tzinfo=timezone(timedelta(hours=1))), HistoricalTimeError),
    (datetime.max.replace(tzinfo=timezone(-timedelta(hours=1))), ValueError),
  ],
)
def test_bad_instant_is_rejected_before_adapter(
  instant: Any, error: type[Exception], monkeypatch: pytest.MonkeyPatch
) -> None:
  adapter = importlib.import_module("astrology.celestial")

  def forbidden(*args: object, **kwargs: object) -> Any:
    pytest.fail("Bad datetime reached the adapter")

  monkeypatch.setattr(adapter, "snapshot", forbidden)
  with pytest.raises(error):
    moment_chart(instant, SITE, CONFIG)


def test_datetime_subclasses_location_and_configuration_are_rejected() -> None:
  class Derived(datetime):
    pass

  with pytest.raises(TypeError):
    moment_chart(Derived(2024, 1, 1, tzinfo=UTC), SITE, CONFIG)
  with pytest.raises(TypeError):
    moment_chart(NOW, cast(Any, None), CONFIG)
  with pytest.raises(TypeError):
    moment_chart(NOW, SITE, cast(Any, None))
  with pytest.raises(TypeError):
    MomentInput(NOW, cast(Any, None))


@pytest.mark.parametrize(
  "value,error",
  [(True, TypeError), ("1", TypeError), (math.inf, ValueError), (math.nan, ValueError)],
)
def test_source_tt_is_a_finite_number(value: Any, error: type[Exception]) -> None:
  with pytest.raises(error):
    MomentInput(NOW, SITE, value)


def test_retained_hit_uses_datetime_fields_and_keeps_distinct_source_tt() -> None:
  import celestial_calendar as celestial

  source = celestial.utc_to_jde(celestial.CivilDateTime(1972, 7, 1, 0))
  chart = moment_chart(_hit(source), SITE, CONFIG)
  assert chart.moment.source_jde_tt == source
  assert chart.moment.utc == datetime(1972, 7, 1, 0, 0, 0, 999994, tzinfo=UTC)
  direct = moment_chart(chart.moment.utc, SITE, CONFIG)
  assert chart.times == direct.times and chart.positions == direct.positions
  assert (chart.times.jde_tt - source) * 86400 == pytest.approx(1, abs=1e-4)
  assert direct.moment.source_jde_tt is None
  assert chart != direct


def test_ordinary_hit_and_converted_modern_floor_are_checked() -> None:
  source = 2460392.2373059206
  chart = moment_chart(_hit(source), SITE, CONFIG)
  assert chart.moment.source_jde_tt == source
  assert chart.times == moment_chart(chart.moment.utc, SITE, CONFIG).times
  with pytest.raises(HistoricalTimeError):
    moment_chart(_hit(2441317.5004882407), SITE, CONFIG)


def test_midnight_rounding_uses_the_rounded_year_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
  import celestial_calendar as celestial

  monkeypatch.setattr(
    celestial, "jde_to_utc", lambda value: celestial.CivilDateTime(2099, 12, 31, 1 - 1e-12)
  )
  with pytest.raises(ChartDomainError, match="Civil year 2100") as caught:
    moment_chart(_hit(2460392), SITE, CONFIG)
  assert caught.value.house_system is CONFIG.house_system


@pytest.mark.parametrize("failure", [ValueError("conversion rejected"), OverflowError("too large")])
def test_conversion_failures_keep_cause_and_requested_geometry(
  failure: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
  import celestial_calendar as celestial

  def reject(value: float) -> Any:
    raise failure

  monkeypatch.setattr(celestial, "jde_to_utc", reject)
  with pytest.raises(ChartDomainError) as caught:
    moment_chart(_hit(2460392), SITE, CONFIG)
  assert caught.value.__cause__ is failure
  assert caught.value.house_system is CONFIG.house_system
  assert caught.value.upstream_message == str(failure)
  assert caught.value.operation == "jde_to_utc"


def test_conversion_native_error_retains_structured_diagnostics(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  import celestial_calendar as celestial

  failure = celestial.CelestialError("jde_to_utc", "synthetic conversion failure", recorded=True)

  def reject(value: float) -> Any:
    raise failure

  monkeypatch.setattr(celestial, "jde_to_utc", reject)
  with pytest.raises(ChartDomainError) as caught:
    moment_chart(_hit(2460392), SITE, CONFIG)
  assert caught.value.__cause__ is failure
  assert caught.value.operation == failure.operation
  assert caught.value.recorded is failure.recorded
  assert caught.value.house_system is CONFIG.house_system
  assert caught.value.upstream_message == str(failure)


@pytest.mark.parametrize("system", list(HouseSystem))
def test_moment_house_requests_share_natal_geometry_without_substitution(
  recorded_chart: NatalChart, system: HouseSystem
) -> None:
  from astrology import natal_chart

  config = replace(recorded_chart.requested, house_system=system)
  natal = natal_chart(recorded_chart.resolved, config)
  moving = moment_chart(natal.resolved.utc, cast(Location, natal.resolved.record.location), config)
  assert moving.houses == natal.houses
  assert moving.requested.house_system is moving.effective.house_system is system


def test_hit_domain_does_not_promise_snapshot_admission() -> None:
  import celestial_calendar as celestial

  source = celestial.utc_to_jde(celestial.CivilDateTime(2200, 1, 1, 0))
  with pytest.raises(ChartDomainError, match="Civil year 2200"):
    moment_chart(_hit(source), SITE, CONFIG)


def test_poles_and_out_of_snapshot_domain_are_not_silently_substituted() -> None:
  with pytest.raises(ChartDomainError):
    moment_chart(NOW, Location(90, 0), CONFIG)
  with pytest.raises(ChartDomainError):
    moment_chart(datetime(2200, 1, 1, tzinfo=UTC), SITE, CONFIG)


def test_moment_constructor_isolates_sequences_and_checks_derived_values() -> None:
  chart = moment_chart(NOW, SITE, CONFIG)
  positions = list(chart.positions)
  placements = list(chart.placements)
  supplied = replace(chart, positions=positions, placements=placements, aspects=[])  # type: ignore[arg-type]
  positions.clear()
  placements.clear()
  assert supplied == chart and type(supplied.positions) is tuple
  for name, value in [("moment", None), ("positions", [None]), ("houses", None)]:
    with pytest.raises(TypeError):
      replace(chart, **{name: cast(Any, value)})
  with pytest.raises(ValueError):
    replace(chart, positions=tuple(reversed(chart.positions)))
  with pytest.raises(ValueError):
    replace(chart, placements=chart.placements[:-1])


def test_existing_consumers_accept_the_genuine_moment_result(recorded_chart: NatalChart) -> None:
  chart = moment_chart(NOW, SITE, CONFIG)
  rules = (AspectRule(MajorAspect.CONJUNCTION, 180),)
  for first, second in ((chart, recorded_chart), (recorded_chart, chart), (chart, chart)):
    assert cross_chart_aspects(first, second, rules).chart_left is first
    assert cross_chart_house_overlays(first, second).chart_right is second
  assert len(HouseRulers(chart).houses) == 12
  assert Dispositors(chart, (Body.SUN,)).chart is chart
  assert chart_sign_distribution(chart, objects=(Body.SUN,)).total == 1
  with pytest.raises(TypeError):
    natal_lunar_phase(cast(Any, chart))
  result = transit_hits(
    chart,
    start_utc=NOW,
    end_utc=NOW + timedelta(days=1),
    moving_objects=(Body.SUN,),
    natal_objects=(Body.SUN,),
    aspects=(MajorAspect.CONJUNCTION,),
  )
  assert result.chart is chart
  assert result.epoch_policy == "fixed_natal_degree_against_moving_of_date_longitude"


@pytest.mark.parametrize(
  "language,title,excluded",
  [
    ("en", "moment chart", ("Recorded clock", "tzdata package", "fold")),
    ("zh-CN", "时刻盘", ("原始钟点", "tzdata 包", "fold")),
  ],
)
def test_moment_text_does_not_fabricate_birth_or_timezone_provenance(
  language: Any, title: str, excluded: tuple[str, ...]
) -> None:
  chart = moment_chart(_hit(2460392.2373059206), SITE, CONFIG)
  text = format_chart(chart, load_catalog(), language=language)
  assert title in text
  assert chart.moment.utc.isoformat() in text
  assert str(chart.moment.source_jde_tt) in text
  assert all(word not in text for word in excluded)
