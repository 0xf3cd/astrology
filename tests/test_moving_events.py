"""Moving-pair contracts and independent crossing references.

移动对象对合同及独立穿越参考。
"""

import hashlib
import json
import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

import celestial_calendar as native
import pytest

import astrology.celestial as adapter
from astrology import (
  Axis,
  Body,
  ChartConfig,
  ChartDomainError,
  HistoricalTimeError,
  HouseSystem,
  Location,
  LunarNode,
  MajorAspect,
  MovingAspectEvents,
  MovingAspectHit,
  MovingEventDomainError,
  RelativeDirection,
  aspect_angle,
  moment_chart,
  moving_aspect_events,
  moving_hit_utc,
)
from astrology.aspects import _signed
from tools.calibrate_moving_reference import time_tolerance_seconds

START, END = datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 2, 2, tzinfo=UTC)
REFERENCE = Path(__file__).parent / "reference/moving_pair_reference.json"


def _search(**overrides: Any) -> MovingAspectEvents:
  arguments: dict[str, Any] = {
    "pairs": ((Body.MOON, Body.SUN),),
    "aspects": (MajorAspect.CONJUNCTION,),
    "start_utc": START,
    "end_utc": END,
  }
  arguments.update(overrides)
  return moving_aspect_events(**arguments)


@pytest.fixture
def controlled(monkeypatch: pytest.MonkeyPatch) -> list[tuple[native.Target, native.Target, float]]:
  calls = []

  def events(
    first: native.Target,
    second: native.Target,
    level: float,
    start: float,
    end: float,
  ) -> tuple[native.LongitudeDifferenceEvent, ...]:
    calls.append((first, second, level))
    return tuple(
      native.LongitudeDifferenceEvent(
        instant,
        level,
        0,
        1.0000000001,
        1.0,
        level,
        direction,
      )
      for instant, direction in (
        (start + 1, native.EventDirection.TANGENT),
        (start + 1 + 2**-20, native.EventDirection.INCREASING),
      )
    )

  monkeypatch.setattr(native, "longitude_difference_events", events)
  return calls


def test_all_branches_roles_coincidences_and_close_contacts_are_preserved(
  controlled: list[tuple[native.Target, native.Target, float]],
) -> None:
  pairs = ((Body.MOON, Body.SUN), (Body.SUN, Body.MOON), (Body.MOON, LunarNode.MEAN_ASCENDING))
  result = _search(pairs=pairs, aspects=tuple(reversed(tuple(MajorAspect))))
  assert [call[2] for call in controlled] == [0, 60, -60, 90, -90, 120, -120, 180] * 3
  assert result.pairs == pairs
  assert type(result.hits[0]) is MovingAspectHit
  assert result.aspects == tuple(MajorAspect)
  assert len(result.hits) == 48
  assert [hit.branch_deg for hit in result.hits[:8]] == [0, -60, 60, -90, 90, -120, 120, 180]
  assert all(hit.direction is RelativeDirection.TANGENT for hit in result.hits[:24])
  assert all(hit.direction is RelativeDirection.DECREASING for hit in result.hits[24:])
  assert {hit.jde_tt for hit in result.hits} == {
    result.start_jde_tt + 1,
    result.start_jde_tt + 1 + 2**-20,
  }
  assert result.hits[0].relative_rate_deg_per_tt_day != 0
  assert result.hits[4].separation_deg == 90
  assert result.hits[7].separation_deg == 180
  assert all(hit.deviation_deg == 0 for hit in result.hits)
  assert tuple(source.moving_object for source in result.sources) == (
    Body.MOON,
    Body.SUN,
    LunarNode.MEAN_ASCENDING,
  )


@pytest.mark.parametrize(
  "overrides,exception",
  [
    ({"pairs": ()}, ValueError),
    ({"pairs": "sun"}, TypeError),
    ({"pairs": ((Body.SUN,),)}, TypeError),
    ({"pairs": ((Body.SUN, "moon"),)}, TypeError),
    ({"pairs": ((Axis.ASCENDANT, Body.SUN),)}, TypeError),
    ({"pairs": ((Body.SUN, Body.SUN),)}, ValueError),
    ({"pairs": ((Body.SUN, Body.MOON),) * 2}, ValueError),
    ({"aspects": ()}, ValueError),
    ({"aspects": ("conjunction",)}, TypeError),
    ({"aspects": (MajorAspect.SQUARE,) * 2}, ValueError),
    ({"start_utc": datetime(2024, 1, 1)}, ValueError),
    ({"start_utc": datetime(1971, 1, 1, tzinfo=UTC)}, HistoricalTimeError),
    ({"end_utc": START}, ValueError),
    ({"start_utc": None}, TypeError),
  ],
)
def test_invalid_inputs_never_reach_astronomy(
  monkeypatch: pytest.MonkeyPatch,
  overrides: dict[str, Any],
  exception: type[Exception],
) -> None:
  def forbidden(*args: object) -> NoReturn:
    pytest.fail("Invalid moving query reached astronomy")

  monkeypatch.setattr(adapter, "moving_interval", forbidden)
  with pytest.raises(exception):
    _search(**overrides)


def test_nested_inputs_and_results_are_isolated(
  controlled: list[tuple[native.Target, native.Target, float]],
) -> None:
  pair = [Body.MOON, Body.SUN]
  pairs, aspects = [pair], [MajorAspect.CONJUNCTION]
  result = _search(pairs=pairs, aspects=aspects)
  pair.clear()
  pairs.clear()
  aspects.clear()
  sources, hits = list(result.sources), list(result.hits)
  copied = replace(result, sources=sources, hits=hits)  # type: ignore[arg-type]
  sources.clear()
  hits.clear()
  assert copied == result
  assert copied.pairs == ((Body.MOON, Body.SUN),)
  with pytest.raises(FrozenInstanceError):
    copied.hits = ()  # type: ignore[misc]


@pytest.mark.parametrize(
  "field,value",
  [
    ("pairs", ()),
    ("sources", ()),
    ("sources", "invalid"),
    ("hits", (None,)),
    ("aspects", ()),
    ("start_jde_tt", math.nan),
    ("end_jde_tt", 0),
    ("end_utc", START),
    ("celestial_version", ""),
    ("astrology_version", True),
  ],
)
def test_result_rejects_inconsistent_supplied_values(
  controlled: list[tuple[native.Target, native.Target, float]],
  field: str,
  value: Any,
) -> None:
  with pytest.raises((ValueError, TypeError)):
    replace(_search(), **{field: value})


def test_both_retained_domains_spans_membership_and_order(
  controlled: list[tuple[native.Target, native.Target, float]],
) -> None:
  result = _search()
  for index in (0, 1):
    for change in (
      {"domain_start_jde_tt": result.start_jde_tt + 1},
      {"domain_end_jde_tt": result.end_jde_tt - 1},
      {"maximum_span_tt_days": 1},
    ):
      sources = list(result.sources)
      sources[index] = replace(sources[index], **change)
      with pytest.raises(ValueError, match=r"domain|span"):
        replace(result, sources=tuple(sources), hits=())
  with pytest.raises(ValueError, match="sources"):
    replace(result, sources=tuple(reversed(result.sources)))
  with pytest.raises(ValueError, match="order"):
    replace(result, hits=tuple(reversed(result.hits)))
  with pytest.raises(ValueError, match="half-open"):
    replace(result, hits=(replace(result.hits[0], jde_tt=result.end_jde_tt),))
  with pytest.raises(ValueError, match="selections"):
    replace(result, hits=(replace(result.hits[0], first_object=Body.MARS),))
  assert replace(result, hits=()).hits == ()
  assert replace(result, hits=(replace(result.hits[0], jde_tt=result.start_jde_tt),)).hits


@pytest.mark.parametrize(
  "field,value",
  [
    ("first_object", Axis.ASCENDANT),
    ("second_object", Body.MOON),
    ("branch_deg", 180),
    ("jde_tt", math.inf),
    ("first_longitude_deg", math.nan),
    ("second_rate_deg_per_tt_day", True),
    ("signed_difference_deg", 360),
    ("signed_difference_deg", 1),
    ("direction", "tangent"),
    ("aspect", "conjunction"),
  ],
)
def test_hit_rejects_malformed_values(
  controlled: list[tuple[native.Target, native.Target, float]],
  field: str,
  value: Any,
) -> None:
  with pytest.raises((TypeError, ValueError)):
    replace(_search().hits[0], **{field: value})


@pytest.mark.parametrize("recorded", (False, True))
def test_late_native_failure_keeps_exception_identity_and_aborts(
  monkeypatch: pytest.MonkeyPatch,
  recorded: bool,
) -> None:
  error = native.CelestialError(
    "longitude_difference_events", "candidate budget exhausted", recorded=recorded
  )
  calls = []

  def events(
    first: native.Target, second: native.Target, level: float, start: float, end: float
  ) -> tuple[native.LongitudeDifferenceEvent, ...]:
    calls.append(level)
    if len(calls) == 2:
      raise error
    return (
      native.LongitudeDifferenceEvent(
        start + 1, level, 0, 1, 2, level, native.EventDirection.INCREASING
      ),
    )

  monkeypatch.setattr(native, "longitude_difference_events", events)
  with pytest.raises(native.CelestialError) as raised:
    _search(aspects=(MajorAspect.SEXTILE,))
  assert raised.value is error and raised.value.recorded is recorded
  assert calls == [60, -60]


def test_domain_error_has_both_roles_verbatim_text_and_cause() -> None:
  with pytest.raises(MovingEventDomainError) as raised:
    _search(
      pairs=((Body.MOON, Body.PLUTO),),
      start_utc=datetime(2200, 1, 1, tzinfo=UTC),
      end_utc=datetime(2200, 2, 1, tzinfo=UTC),
    )
  error = raised.value
  assert error.first_object is Body.MOON and error.second_object is Body.PLUTO
  assert error.operation == "longitude_difference_events"
  assert error.upstream_message == str(error.__cause__)
  assert error.start_jde_tt is not None and error.end_jde_tt is not None
  assert not hasattr(error, "natal_object")
  with pytest.raises(MovingEventDomainError, match="3660"):
    _search(end_utc=START + timedelta(days=3661))


def test_conversion_rejection_does_not_invent_pair_roles(monkeypatch: pytest.MonkeyPatch) -> None:
  original = ValueError("synthetic UTC rejection")

  def fail(*args: object) -> NoReturn:
    raise original

  monkeypatch.setattr(native, "utc_to_jde", fail)
  with pytest.raises(MovingEventDomainError) as raised:
    _search()
  assert raised.value.__cause__ is original
  assert raised.value.operation == "utc_to_jde"
  assert raised.value.first_object is raised.value.second_object is None


def test_real_node_pairs_constant_mismatch_and_continuous_relation() -> None:
  for node in LunarNode:
    result = _search(pairs=((Body.MOON, node),))
    assert result.hits and result.sources[1].moving_object is node
  assert _search(pairs=((LunarNode.MEAN_ASCENDING, LunarNode.MEAN_DESCENDING),)).hits == ()
  with pytest.raises(MovingEventDomainError):
    _search(
      pairs=((LunarNode.MEAN_ASCENDING, LunarNode.MEAN_DESCENDING),),
      aspects=(MajorAspect.OPPOSITION,),
    )


@pytest.mark.parametrize("aspect", tuple(MajorAspect))
def test_real_reversal_and_half_open_ownership(aspect: MajorAspect) -> None:
  forward = _search(aspects=(aspect,))
  reverse = _search(pairs=((Body.SUN, Body.MOON),), aspects=(aspect,))
  assert len(forward.hits) == len(reverse.hits) > 0
  for first, second in zip(forward.hits, reverse.hits, strict=True):
    assert first.jde_tt == second.jde_tt
    assert second.branch_deg == _signed(-first.branch_deg)
    assert first.first_longitude_deg == second.second_longitude_deg
    assert first.first_rate_deg_per_tt_day == second.second_rate_deg_per_tt_day
    assert first.relative_rate_deg_per_tt_day == -second.relative_rate_deg_per_tt_day
    assert first.direction is not second.direction
  event = forward.hits[0]
  estimate = moving_hit_utc(event)
  for offset in range(-100, 101):
    split = estimate + timedelta(microseconds=offset)
    if adapter.moving_interval(split, END)[0] == event.jde_tt:
      break
  else:
    pytest.fail("Canonical event has no tested datetime representation")
  assert _search(aspects=(aspect,), end_utc=split).hits == ()
  assert _search(aspects=(aspect,), start_utc=split).hits[0] == event


def test_real_adapter_canonical_tangent_and_raw_subtraction_regression() -> None:
  # celestial-calendar v1.1.1, ACanonicalRelativeStationConstructsARepeatablePairTangent.
  instant = 2460742.5711974148
  first, second = native.positions((native.Target.MERCURY, native.Target.SUN), instant)
  level = _signed(_signed(first.longitude_deg) - _signed(second.longitude_deg))
  (event,) = adapter.moving_events(Body.MERCURY, Body.SUN, level, instant - 0.5, instant + 0.5)
  assert event.jde_tt == instant and event.direction is RelativeDirection.TANGENT
  assert event.first_rate_deg_per_tt_day != event.second_rate_deg_per_tt_day
  normalized = _signed(_signed(event.first_longitude_deg) - _signed(event.second_longitude_deg))
  assert normalized == event.signed_difference_deg == level
  raw = _signed(event.first_longitude_deg - event.second_longitude_deg)
  assert raw != level
  for rejected in (raw, math.nextafter(level, -math.inf), math.nextafter(level, math.inf)):
    with pytest.raises(native.CelestialError):
      adapter.moving_events(Body.MERCURY, Body.SUN, rejected, instant - 0.5, instant + 0.5)
  (reverse,) = adapter.moving_events(Body.SUN, Body.MERCURY, -level, instant - 0.5, instant + 0.5)
  assert reverse.jde_tt == instant and reverse.direction is RelativeDirection.TANGENT
  nearby = adapter.moving_events(Body.MERCURY, Body.SUN, level - 1e-5, instant - 0.1, instant + 0.1)
  assert len(nearby) == 2
  assert {hit.direction for hit in nearby} == {
    RelativeDirection.INCREASING,
    RelativeDirection.DECREASING,
  }
  assert adapter.moving_events(Body.MERCURY, Body.SUN, level, instant - 0.5, instant) == ()
  assert adapter.moving_events(Body.MERCURY, Body.SUN, level, instant, instant + 0.5) == (event,)


def _cases() -> list[dict[str, Any]]:
  return list(json.loads(REFERENCE.read_text(encoding="utf-8"))["cases"])


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_independent_moving_pair_reference(case: dict[str, Any]) -> None:
  aspect = next(value for value in MajorAspect if aspect_angle(value) == case["aspect_deg"])
  result = _search(
    pairs=((Body(case["first"]), Body(case["second"])),),
    aspects=(aspect,),
    start_utc=datetime.fromisoformat(case["start_utc"]),
    end_utc=datetime.fromisoformat(case["end_utc"]),
  )
  assert len(result.hits) == len(case["hits"])
  fixture = json.loads(REFERENCE.read_text(encoding="utf-8"))
  bounds = fixture["calibration"]["angular_tolerance_deg"]
  for actual, expected in zip(result.hits, case["hits"], strict=True):
    assert abs(actual.jde_tt - expected["jde_tt"]) * 86400 <= expected["time_tolerance_seconds"]
    assert (
      actual.branch_deg == expected["branch_deg"]
      and actual.direction.value == expected["direction"]
    )
    assert abs(actual.deviation_deg) < 1e-6
    first, second = native.positions(
      (adapter._target(actual.first_object), adapter._target(actual.second_object)),
      expected["jde_tt"],
    )
    assert (
      abs(_signed(first.longitude_deg - expected["first_longitude_deg"])) <= bounds[case["first"]]
    )
    assert (
      abs(_signed(second.longitude_deg - expected["second_longitude_deg"]))
      <= bounds[case["second"]]
    )


def test_reference_recipes_and_bilateral_calibration_are_pinned() -> None:
  fixture = json.loads(REFERENCE.read_text(encoding="utf-8"))
  assert fixture["source"]["requested_flags"] == fixture["source"]["verified_returned_flags"] == 260
  assert fixture["source"]["library_version"] == "2.10.03"
  assert fixture["calibration"]["sample_count"] == 696
  assert len(fixture["cases"]) == 8 and sum(len(case["hits"]) for case in fixture["cases"]) == 18
  for block, filename in (
    ("source", "fetch_moving_reference.py"),
    ("calibration", "calibrate_moving_reference.py"),
  ):
    assert (
      hashlib.sha256((Path(__file__).parents[1] / "tools" / filename).read_bytes()).hexdigest()
      == fixture[block]["recipe_sha256"]
    )
  assert fixture["calibration"]["native_version"] == "1.1.1"


def test_bilateral_time_budget_uses_both_bounds_and_enforces_reference_limits() -> None:
  assert time_tolerance_seconds(0.0001, 0.0002, 1) == pytest.approx(51.84, abs=1e-12)
  assert time_tolerance_seconds(0.0001, 0.0002, -1) == pytest.approx(51.84, abs=1e-12)
  assert time_tolerance_seconds(1e-8, 1e-8, 1) == 2
  with pytest.raises(ValueError, match="rate"):
    time_tolerance_seconds(0.0001, 0.0002, 0.01)
  with pytest.raises(ValueError, match="300"):
    time_tolerance_seconds(0.1, 0.2, 1)


def test_stored_reference_time_budgets_match_both_body_bounds() -> None:
  fixture = json.loads(REFERENCE.read_text(encoding="utf-8"))
  bounds = fixture["calibration"]["angular_tolerance_deg"]
  for case in fixture["cases"]:
    for hit in case["hits"]:
      assert hit["time_tolerance_seconds"] == time_tolerance_seconds(
        bounds[case["first"]], bounds[case["second"]], hit["relative_rate_deg_per_tt_day"]
      )


def test_stored_reference_extrema_stay_outside_the_angular_budget() -> None:
  fixture = json.loads(REFERENCE.read_text(encoding="utf-8"))
  bounds = fixture["calibration"]["angular_tolerance_deg"]
  checked = 0
  for case in fixture["cases"]:
    for extremum in case["relative_extrema"]:
      assert extremum["distance_from_requested_branch_deg"] > (
        bounds[case["first"]] + bounds[case["second"]]
      )
      checked += 1
  assert checked > 0


def test_shared_event_records_preserve_legacy_import_identity() -> None:
  import astrology
  import astrology.event_records as owner
  import astrology.transits as legacy

  assert astrology.TransitSource is legacy.TransitSource is owner.TransitSource
  assert astrology.EventDisplayError is legacy.EventDisplayError is owner.EventDisplayError


def test_retained_moving_event_builds_real_moment_chart_and_keeps_source_time() -> None:
  hit = _search().hits[0]
  config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ())
  chart = moment_chart(hit, Location(0, 0), config)
  assert chart.moment.source_jde_tt == hit.jde_tt
  assert chart.moment.utc == moving_hit_utc(hit)
  assert len(chart.positions) == 2 and len(chart.houses.cusps_deg) == 12
  assert abs(_signed(chart.positions[0].longitude_deg - hit.second_longitude_deg)) < 1e-7
  with pytest.raises(ChartDomainError):
    moment_chart(hit, Location(90, 0), config)
  assert hit.jde_tt == _search().hits[0].jde_tt


@pytest.mark.parametrize("mode", ((), ("-O",)))
def test_native_free_construction_and_validation(mode: tuple[str, ...]) -> None:
  program = (Path(__file__).parent / "consumer_cases/moving_events_isolation.py").read_text(
    encoding="utf-8"
  )
  completed = subprocess.run([sys.executable, *mode, "-c", program], capture_output=True, text=True)
  assert completed.returncode == 0, completed.stdout + completed.stderr
