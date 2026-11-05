"""Transit composition contracts and independent modern event references.

行运组合合同与独立的现代事件参考。
"""

import hashlib
import json
import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, NoReturn

import celestial_calendar as native
import pytest

import astrology.celestial as adapter
from astrology import (
  Axis,
  Body,
  HistoricalTimeError,
  LunarNode,
  MajorAspect,
  NatalChart,
  TransitDirection,
  TransitDomainError,
  TransitHit,
  TransitHits,
  TransitSource,
  transit_hits,
)
from astrology.objects import AstronomicalObject
from tools.installed_check import _cross_source

START = datetime(2024, 1, 1, tzinfo=UTC)
END = datetime(2024, 2, 1, tzinfo=UTC)
REFERENCE = Path(__file__).parent / "reference" / "transit_reference.json"


def _chart(longitude: float = 10) -> NatalChart:
  return _cross_source(2000, "fixed-transit-target", ((Body.SUN, longitude),))


def _search(chart: NatalChart | None = None, **overrides: Any) -> TransitHits:
  arguments: dict[str, Any] = {
    "start_utc": START,
    "end_utc": END,
    "moving_objects": (Body.SUN,),
    "natal_objects": (Body.SUN,),
    "aspects": (MajorAspect.CONJUNCTION,),
  }
  arguments.update(overrides)
  return transit_hits(_chart() if chart is None else chart, **arguments)


@pytest.fixture
def controlled_events(monkeypatch: pytest.MonkeyPatch) -> list[tuple[AstronomicalObject, float]]:
  calls: list[tuple[AstronomicalObject, float]] = []
  identities = {adapter._target(identity): identity for identity in (*Body, *LunarNode)}

  def events(
    target: native.Target, level: float, start: float, end: float
  ) -> tuple[native.LongitudeEvent, ...]:
    calls.append((identities[target], level))
    return (
      native.LongitudeEvent(
        start + 1,
        level + 360 + 1e-10,
        math.nextafter(0.0, -math.inf),
        native.EventDirection.TANGENT,
      ),
      native.LongitudeEvent(
        start + 1 + 2**-20, level - 1e-10, -0.3141592653589793, native.EventDirection.DECREASING
      ),
    )

  monkeypatch.setattr(native, "longitude_events", events)
  return calls


def test_branches_order_identities_and_close_contacts_are_not_folded(
  controlled_events: list[tuple[AstronomicalObject, float]],
) -> None:
  chart = _cross_source(
    2000, "distinct-identities", ((Body.MOON, 10), (Body.SUN, 10)), axes=(10, 10, 10, 10)
  )
  moving = (Body.MARS, Body.MERCURY)
  natal = (Body.MOON, Body.SUN, Axis.ASCENDANT, Axis.IMUM_COELI)
  branches = (
    (MajorAspect.CONJUNCTION, 0),
    (MajorAspect.SEXTILE, -60),
    (MajorAspect.SEXTILE, 60),
    (MajorAspect.SQUARE, -90),
    (MajorAspect.SQUARE, 90),
    (MajorAspect.TRINE, -120),
    (MajorAspect.TRINE, 120),
    (MajorAspect.OPPOSITION, 180),
  )
  result = _search(
    chart,
    moving_objects=moving,
    natal_objects=tuple(reversed(natal)),
    aspects=tuple(reversed(tuple(MajorAspect))),
  )
  levels = (10, 310, 70, 280, 100, 250, 130, 190)
  assert controlled_events == [
    (identity, level) for identity in moving for _ in natal for level in levels
  ]
  assert result.natal_objects == natal
  expected = [
    (identity, endpoint, aspect, branch)
    for identity in moving
    for endpoint in natal
    for aspect, branch in branches
  ]
  assert [
    (h.moving_object, h.natal_object, h.aspect, h.branch_deg) for h in result.hits
  ] == expected * 2
  assert len(result.hits) == 128
  assert type(result.hits[0]) is TransitHit and type(result.sources[0]) is TransitSource
  assert result.hits[0].longitude_deg == 370 + 1e-10
  assert result.hits[0].longitude_rate_deg_per_tt_day.hex() == math.nextafter(0.0, -math.inf).hex()
  assert result.hits[0].direction is TransitDirection.TANGENT
  assert result.hits[64].longitude_rate_deg_per_tt_day == -0.3141592653589793
  assert result.hits[64].direction is TransitDirection.DECREASING


def test_complete_empty_success(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(adapter, "transit_events", lambda *args: ())
  result = _search()
  assert result.hits == () and len(result.sources) == 1
  assert result.celestial_version == "1.1.1" and result.chart is not None


@pytest.mark.parametrize("recorded", (False, True))
def test_computation_error_is_not_relabelled_or_returned_partially(
  monkeypatch: pytest.MonkeyPatch,
  recorded: bool,
) -> None:
  error = native.CelestialError("longitude_events", "numerical failure", recorded=recorded)
  calls = []

  def events(
    target: native.Target, level: float, start: float, end: float
  ) -> tuple[native.LongitudeEvent, ...]:
    calls.append(target)
    if target is native.Target.MERCURY:
      raise error
    return (native.LongitudeEvent(start + 1, level, 1.25, native.EventDirection.INCREASING),)

  monkeypatch.setattr(native, "longitude_events", events)
  with pytest.raises(native.CelestialError) as raised:
    _search(moving_objects=(Body.SUN, Body.MERCURY))
  assert raised.value is error and raised.value.recorded is recorded
  assert calls == [native.Target.SUN, native.Target.MERCURY]


def test_domain_errors_retain_query_and_cause(monkeypatch: pytest.MonkeyPatch) -> None:
  original = ValueError("outside the selected rate domain")

  def fail(*arguments: object) -> NoReturn:
    raise original

  monkeypatch.setattr(native, "longitude_events", fail)
  with pytest.raises(TransitDomainError) as raised:
    _search(moving_objects=(Body.PLUTO,))
  error = raised.value
  assert isinstance(error, ValueError) and error.__cause__ is original
  assert error.operation == "longitude_events" and error.moving_object is Body.PLUTO
  assert error.upstream_message == str(original)
  assert error.start_jde_tt is not None and error.end_jde_tt is not None
  assert not hasattr(error, "house_system")


def test_conversion_error_has_no_invented_provider(monkeypatch: pytest.MonkeyPatch) -> None:
  original = ValueError("UTC instant rejected")

  def fail(*arguments: object) -> NoReturn:
    raise original

  monkeypatch.setattr(native, "utc_to_jde", fail)
  with pytest.raises(TransitDomainError) as raised:
    _search()
  assert raised.value.__cause__ is original
  assert raised.value.operation == "utc_to_jde"
  assert raised.value.moving_object is None and raised.value.start_jde_tt is None


@pytest.mark.parametrize(
  "overrides,exception",
  [
    ({"start_utc": "2024-01-01"}, TypeError),
    ({"end_utc": None}, TypeError),
    ({"start_utc": datetime(2024, 1, 1)}, ValueError),
    ({"start_utc": datetime(1950, 1, 1, tzinfo=UTC)}, HistoricalTimeError),
    ({"start_utc": datetime(1972, 1, 1, tzinfo=timezone(timedelta(hours=1)))}, HistoricalTimeError),
    ({"end_utc": START}, ValueError),
    ({"end_utc": START - timedelta(days=1)}, ValueError),
    ({"end_utc": datetime.max.replace(tzinfo=timezone(-timedelta(hours=1)))}, ValueError),
    ({"moving_objects": ()}, ValueError),
    ({"moving_objects": (Body.SUN, Body.SUN)}, ValueError),
    ({"moving_objects": (Axis.ASCENDANT,)}, TypeError),
    ({"moving_objects": ("sun",)}, TypeError),
    ({"moving_objects": "sun"}, TypeError),
    ({"natal_objects": ()}, ValueError),
    ({"natal_objects": (Body.MOON,)}, ValueError),
    ({"natal_objects": (Body.SUN, Body.SUN)}, ValueError),
    ({"natal_objects": ("sun",)}, TypeError),
    ({"aspects": ()}, ValueError),
    ({"aspects": (MajorAspect.CONJUNCTION, MajorAspect.CONJUNCTION)}, ValueError),
    ({"aspects": ("conjunction",)}, TypeError),
    ({"aspects": (True,)}, TypeError),
  ],
)
def test_bad_arguments_fail_before_adapter_calls(
  monkeypatch: pytest.MonkeyPatch,
  overrides: dict[str, Any],
  exception: type[Exception],
) -> None:
  def unexpected(*arguments: object) -> NoReturn:
    pytest.fail("Invalid arguments reached astronomy")

  monkeypatch.setattr(adapter, "transit_interval", unexpected)
  with pytest.raises(exception):
    _search(**overrides)


class _ChangingOffset(tzinfo):
  def __init__(self) -> None:
    self.calls = 0

  def utcoffset(self, value: datetime | None) -> timedelta:
    self.calls += 1
    return timedelta(hours=self.calls)

  def dst(self, value: datetime | None) -> timedelta:
    return timedelta(0)

  def tzname(self, value: datetime | None) -> str:
    return "changing-offset-test"


def test_utc_is_aware_canonical_and_isolates_mutable_offset(
  controlled_events: list[tuple[AstronomicalObject, float]],
) -> None:
  zone = _ChangingOffset()
  result = _search(start_utc=datetime(2024, 1, 1, 12, tzinfo=zone, fold=1))
  assert result.start_utc == datetime(2024, 1, 1, 11, tzinfo=UTC)
  assert result.start_utc.tzinfo is UTC and result.start_utc.fold == 0
  assert zone.calls == 1
  zone.calls = 12
  assert result.start_utc.hour == 11


def test_sources_and_input_sequences_are_isolated_without_native_recomputation(
  controlled_events: list[tuple[AstronomicalObject, float]],
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  moving, natal, aspects = [Body.MERCURY], [Body.SUN], [MajorAspect.CONJUNCTION]
  chart = _chart()
  result = _search(chart, moving_objects=moving, natal_objects=natal, aspects=aspects)
  moving.clear()
  natal.clear()
  aspects.clear()
  sources, hits = list(result.sources), list(result.hits)

  def unexpected(*arguments: object) -> NoReturn:
    pytest.fail("Constructing or accessing supplied results called astronomy")

  monkeypatch.setattr(native, "longitude_events", unexpected)
  copied = replace(result, sources=sources, hits=hits)  # type: ignore[arg-type]
  sources.clear()
  hits.clear()
  assert copied == result and copied.chart is chart
  assert copied.moving_objects == (Body.MERCURY,) and copied.natal_objects == (Body.SUN,)
  assert copied.sources[0].model_identity == 3
  assert copied.sources[0].model_kind == "position_source"
  assert "VSOP87" in copied.sources[0].capability_description
  with pytest.raises(FrozenInstanceError):
    copied.hits = ()  # type: ignore[misc]


@pytest.mark.parametrize(
  "field,value",
  [
    ("hits", ()),
    ("start_jde_tt", math.nan),
    ("end_jde_tt", 0),
    ("position_frame", "mean"),
    ("time_policy", "local"),
    ("epoch_policy", "j2000"),
    ("celestial_version", ""),
    ("sources", ()),
    ("moving_objects", ()),
    ("moving_objects", (Axis.ASCENDANT,)),
    ("aspects", ()),
    ("aspects", ("conjunction",)),
  ],
)
def test_aggregate_tampering(
  controlled_events: list[tuple[AstronomicalObject, float]],
  field: str,
  value: Any,
) -> None:
  result = _search()
  if field == "hits":
    assert replace(result, hits=()).hits == ()
  else:
    with pytest.raises((ValueError, TypeError)):
      replace(result, **{field: value})


def test_interval_membership_query_geometry_and_order_are_checked(
  controlled_events: list[tuple[AstronomicalObject, float]],
) -> None:
  result = _search()
  first = result.hits[0]
  for changed in (
    replace(first, jde_tt=result.end_jde_tt),
    replace(first, query_longitude_deg=11),
    replace(first, moving_object=Body.PLUTO),
    replace(first, natal_object=Axis.ASCENDANT),
    replace(first, aspect=MajorAspect.TRINE, branch_deg=120, query_longitude_deg=130),
  ):
    with pytest.raises(ValueError):
      replace(result, hits=(changed,))
  with pytest.raises(ValueError, match="order"):
    replace(result, hits=tuple(reversed(result.hits)))
  assert (
    replace(result, hits=(replace(first, jde_tt=result.start_jde_tt),)).hits[0].jde_tt
    == result.start_jde_tt
  )


def test_source_identities_and_order_must_match_the_moving_selection(
  controlled_events: list[tuple[AstronomicalObject, float]],
) -> None:
  result = _search(moving_objects=(Body.SUN, Body.MERCURY))
  with pytest.raises(ValueError, match="sources must match"):
    replace(result, sources=tuple(reversed(result.sources)))
  with pytest.raises(ValueError, match="sources must match"):
    replace(
      result, sources=(replace(result.sources[0], moving_object=Body.MARS), result.sources[1])
    )


@pytest.mark.parametrize(
  "field,value",
  [
    ("jde_tt", math.inf),
    ("longitude_deg", math.nan),
    ("longitude_rate_deg_per_tt_day", True),
    ("branch_deg", 180),
    ("query_longitude_deg", 360),
    ("direction", "tangent"),
    ("moving_object", Axis.ASCENDANT),
    ("natal_object", "sun"),
  ],
)
def test_hit_tampering(
  controlled_events: list[tuple[AstronomicalObject, float]],
  field: str,
  value: Any,
) -> None:
  with pytest.raises((ValueError, TypeError)):
    replace(_search().hits[0], **{field: value})


def test_real_selected_domains_and_tt_span_policy() -> None:
  future: dict[str, Any] = {
    "start_utc": datetime(2200, 1, 1, tzinfo=UTC),
    "end_utc": datetime(2200, 2, 1, tzinfo=UTC),
  }
  assert len(_search(**future).hits) <= 1
  inclusive = _search(end_utc=START + timedelta(days=3660))
  assert inclusive.end_jde_tt - inclusive.start_jde_tt == inclusive.sources[0].maximum_span_tt_days
  with pytest.raises(TransitDomainError, match="domain"):
    _search(moving_objects=(Body.SUN, Body.PLUTO), **future)
  with pytest.raises(TransitDomainError, match="3660"):
    _search(end_utc=START + timedelta(days=3661))


def _cases() -> list[dict[str, Any]]:
  return list(json.loads(REFERENCE.read_text())["cases"])


def _utc_from_tt(instant: float) -> datetime:
  return (
    datetime(2000, 1, 1, tzinfo=UTC)
    + timedelta(days=instant - 2451544.5)
    - timedelta(seconds=69.184)
  )


def test_real_start_inclusion_end_exclusion_at_a_representable_reported_instant() -> None:
  start, end = datetime(2024, 3, 15, tzinfo=UTC), datetime(2024, 3, 25, tzinfo=UTC)
  chart = _chart(0)
  whole = _search(chart, start_utc=start, end_utc=end)
  event = whole.hits[0]
  estimate = _utc_from_tt(event.jde_tt)
  for offset in range(-80, 81):
    split = estimate + timedelta(microseconds=offset)
    if adapter.transit_interval(split, end)[0] == event.jde_tt:
      break
  else:
    pytest.fail("The chosen modern reporting instant has no tested datetime representation")
  assert _search(chart, start_utc=start, end_utc=split).hits == ()
  assert _search(chart, start_utc=split, end_utc=end).hits == (event,)
  assert event.longitude_deg > 359 or event.longitude_deg < 1e-6


def test_real_tangent_preserves_the_native_rate() -> None:
  start, end = datetime(2023, 8, 20, tzinfo=UTC), datetime(2023, 8, 27, tzinfo=UTC)
  left, right = adapter.transit_interval(start, end)
  station = native.longitude_stations(native.Target.MERCURY, left, right)[0]
  chart = _chart(station.longitude_deg % 360)
  result = _search(chart, start_utc=start, end_utc=end, moving_objects=(Body.MERCURY,))
  original = native.longitude_events(native.Target.MERCURY, station.longitude_deg, left, right)
  assert len(result.hits) == len(original) == 1
  assert result.hits[0].direction is TransitDirection.TANGENT
  assert (
    result.hits[0].longitude_rate_deg_per_tt_day.hex()
    == original[0].longitude_rate_deg_per_tt_day.hex()
  )


def test_tt_interval_counts_the_known_leap_step() -> None:
  start, end = datetime(2016, 12, 31, tzinfo=UTC), datetime(2017, 1, 2, tzinfo=UTC)
  result = _search(start_utc=start, end_utc=end)
  assert (result.end_jde_tt - result.start_jde_tt) * 86400 == pytest.approx(
    (end - start).total_seconds() + 1, abs=1e-4, rel=0
  )


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_independent_same_convention_references(case: dict[str, Any]) -> None:
  try:
    moving: AstronomicalObject = Body(case["moving_object"])
  except ValueError:
    moving = LunarNode(case["moving_object"])
  result = _search(
    _chart(case["query_longitude_deg"]),
    moving_objects=(moving,),
    start_utc=_utc_from_tt(case["start_jde_tt"]),
    end_utc=_utc_from_tt(case["end_jde_tt"]),
  )
  assert result.start_jde_tt == pytest.approx(case["start_jde_tt"], abs=2e-9, rel=0)
  assert result.end_jde_tt == pytest.approx(case["end_jde_tt"], abs=2e-9, rel=0)
  assert len(result.hits) == len(case["hits"])
  for actual, expected in zip(result.hits, case["hits"], strict=True):
    time_bound = max(
      2, 2 * case["angular_tolerance_deg"] / abs(expected["longitude_rate_deg_per_tt_day"]) * 86400
    )
    assert abs(actual.jde_tt - expected["jde_tt"]) * 86400 < time_bound
    assert actual.direction.value == expected["direction"]
    target = adapter._target(moving)
    at_reference = native.positions((target,), expected["jde_tt"])[0].longitude_deg
    assert (
      abs((at_reference - case["query_longitude_deg"] + 180) % 360 - 180)
      < case["angular_tolerance_deg"]
    )
    assert abs((actual.longitude_deg - actual.query_longitude_deg + 180) % 360 - 180) < 1e-6
  native_events = native.longitude_events(
    adapter._target(moving), case["query_longitude_deg"], result.start_jde_tt, result.end_jde_tt
  )
  assert [
    (h.jde_tt, h.longitude_deg, h.longitude_rate_deg_per_tt_day, h.direction.value)
    for h in result.hits
  ] == [
    (h.jde_tt, h.longitude_deg, h.longitude_rate_deg_per_tt_day, h.direction.value)
    for h in native_events
  ]


def test_reference_provenance_and_recipe_are_pinned() -> None:
  fixture = json.loads(REFERENCE.read_text())
  assert fixture["source"]["requested_flags"] == fixture["source"]["returned_flags"] == 260
  assert fixture["source"]["library_version"] == "2.10.03"
  assert fixture["calibration"]["native_version"] == "1.1.1"
  assert fixture["calibration"]["sample_count"] == 1830
  recipe = Path(__file__).parents[1] / "tools" / "fetch_transit_reference.py"
  assert hashlib.sha256(recipe.read_bytes()).hexdigest() == fixture["source"]["recipe_sha256"]
  assert len(fixture["cases"]) == 17
  node_reference = Path(__file__).with_name("test_reference.py")
  assert (
    hashlib.sha256(node_reference.read_bytes()).hexdigest()
    == fixture["source"]["node_reference_sha256"]
  )


def test_stored_node_and_axis_degrees_stay_fixed(
  controlled_events: list[tuple[AstronomicalObject, float]],
) -> None:
  chart = _cross_source(
    2000,
    "distinct-fixed-targets",
    ((Body.SUN, 10), (LunarNode.MEAN_ASCENDING, 44.5)),
    axes=(100, 110, 120, 130),
  )
  result = _search(chart, natal_objects=(Axis.ASCENDANT, LunarNode.MEAN_ASCENDING))
  assert controlled_events == [(Body.SUN, 44.5), (Body.SUN, 100)]
  assert chart.positions[1].longitude_rate_deg_per_tt_day != 0
  assert {hit.query_longitude_deg for hit in result.hits} == {44.5, 100}


def test_transit_versions_describe_the_new_calculation_not_the_natal_source(
  controlled_events: list[tuple[AstronomicalObject, float]],
) -> None:
  chart = _chart()
  chart = replace(
    chart,
    provenance=replace(
      chart.provenance, celestial_version="earlier-native", astrology_version="earlier-package"
    ),
  )
  result = _search(chart)
  assert result.chart is chart
  assert result.celestial_version == "1.1.1" != chart.provenance.celestial_version
  assert result.astrology_version != chart.provenance.astrology_version


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_supplied_transit_values_are_native_free(mode: tuple[str, ...]) -> None:
  code = (Path(__file__).parent / "consumer_cases/transits_isolation.py").read_text(
    encoding="utf-8"
  )
  completed = subprocess.run([sys.executable, *mode, "-c", code], capture_output=True, text=True)
  assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize(
  "field,value",
  [
    ("moving_object", Axis.ASCENDANT),
    ("model_kind", "delta_t"),
    ("model_identity", True),
    ("model_identity", 0),
    ("model_description", ""),
    ("domain_start_jde_tt", math.nan),
    ("domain_end_jde_tt", -1e20),
    ("maximum_span_tt_days", 0),
    ("capability_description", ""),
  ],
)
def test_source_values_reject_invalid_metadata(field: str, value: Any) -> None:
  with pytest.raises((TypeError, ValueError)):
    replace(adapter.transit_source(Body.SUN), **{field: value})


@pytest.mark.parametrize(
  "field,value",
  [
    ("chart", None),
    ("end_utc", START),
    ("natal_objects", ()),
    ("sources", "invalid"),
    ("sources", (None,)),
    ("hits", (None,)),
  ],
)
def test_aggregate_rejects_invalid_sources_and_selections(
  controlled_events: list[tuple[AstronomicalObject, float]], field: str, value: Any
) -> None:
  with pytest.raises((TypeError, ValueError)):
    replace(_search(), **{field: value})


def test_retained_source_window_and_span_are_enforced(
  controlled_events: list[tuple[AstronomicalObject, float]],
) -> None:
  result = _search()
  source = result.sources[0]
  with pytest.raises(ValueError, match="domain"):
    replace(result, sources=(replace(source, domain_start_jde_tt=result.start_jde_tt + 1),))
  with pytest.raises(ValueError, match="span"):
    replace(result, sources=(replace(source, maximum_span_tt_days=1),))


def test_invalid_source_chart_and_datetime_subclasses_never_reach_astronomy() -> None:
  class DerivedDatetime(datetime):
    pass

  with pytest.raises(TypeError, match="chart"):
    transit_hits(
      None,  # type: ignore[arg-type]
      start_utc=START,
      end_utc=END,
      moving_objects=(Body.SUN,),
      natal_objects=(Body.SUN,),
      aspects=(MajorAspect.CONJUNCTION,),
    )
  with pytest.raises(TypeError, match="built-in"):
    _search(start_utc=DerivedDatetime(2024, 1, 1, tzinfo=UTC))
  with pytest.raises(TypeError):
    _search(aspects=None)


def test_converted_tt_interval_collapse_is_a_domain_failure() -> None:
  with pytest.raises(TransitDomainError) as raised:
    _search(end_utc=START + timedelta(microseconds=1))
  assert raised.value.start_jde_tt == raised.value.end_jde_tt
  assert raised.value.__cause__ is not None


def test_bad_capability_payload_does_not_become_an_empty_success(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(native, "capabilities", lambda *args: ())
  with pytest.raises(RuntimeError, match="capability"):
    _search()


def test_transit_knowledge_states_and_scope_are_separate() -> None:
  from astrology import load_catalog
  from astrology.knowledge import OutputEligibility, PrerequisiteStatus

  catalog = load_catalog()
  entry = catalog.entry("entry.transit_hits")
  assert entry.prerequisite_status is PrerequisiteStatus.COMPLETE
  assert entry.output_eligibility is OutputEligibility.REFERENCE_ONLY
  assert entry.chart_applicability == "not_assessed"
  assert entry.rule_ids == ("rule.project.exact_transit_hits", "rule.project.aspect_deviation")
  assert set(entry.concept_ids) == {f"aspect.{aspect.value}" for aspect in MajorAspect}
  source = catalog.citations(entry.identifier)[0][1]
  assert source.identifier == "source.celestial-calendar.events.1.1.1"
  assert "not independent" in source.scope.en
  assert "own dates" in catalog.variant(entry.rule_ids[0]).limits.en
