"""Return composition, independent event references and chart consumers.

返照组合、独立事件参考及命盘消费。
"""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, NoReturn, cast

import celestial_calendar as native
import pytest

import astrology.birth as birth_module
import astrology.returns as returns_module
from astrology import (
  AspectRule,
  BirthRecord,
  Body,
  ChartConfig,
  ChartDomainError,
  FixedOffset,
  HistoricalTimeError,
  HouseRulers,
  HouseSystem,
  Location,
  LunarNode,
  MajorAspect,
  MomentChart,
  NatalChart,
  TransitDomainError,
  TransitHits,
  chart_dispositors,
  chart_sign_distribution,
  cross_chart_aspects,
  cross_chart_house_overlays,
  format_chart,
  house_of,
  load_catalog,
  moment_chart,
  natal_chart,
  prepare_natal_input,
  return_hits,
  transit_aspects,
  transit_hits,
)
from astrology.celestial import transit_interval

REFERENCE = Path(__file__).parent / "reference" / "return_reference.json"
PLANETARY_REFERENCE = Path(__file__).parent / "reference" / "planetary_return_reference.json"
PLANETARY_OBSERVATIONS = (
  Path(__file__).parent / "reference" / "planetary_return_native_observations.json"
)
CASES: list[dict[str, Any]] = json.loads(REFERENCE.read_text())["cases"]
PLANETARY_CASES: list[dict[str, Any]] = json.loads(PLANETARY_REFERENCE.read_text())["cases"]
SITE = Location(0, 0)
CONFIG = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ())
START = datetime(2024, 1, 1, tzinfo=UTC)
END = datetime(2024, 4, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def natal() -> NatalChart:
  return natal_chart(
    prepare_natal_input(BirthRecord(date(2000, 2, 29), time(12), FixedOffset(timedelta(0)), SITE)),
    CONFIG,
  )


def _search(chart: NatalChart, body: Body = Body.MOON) -> TransitHits:
  return return_hits(chart, body, start_utc=START, end_utc=END)


@pytest.mark.parametrize("mode", [(), ("-O",)])
@pytest.mark.parametrize("external_cwd", [False, True])
def test_import_knowledge_and_rejections_do_not_initialize_native(
  mode: tuple[str, ...], external_cwd: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
  if external_cwd:
    monkeypatch.chdir(tmp_path)
  program = (Path(__file__).parent / "consumer_cases/returns_isolation.py").read_text(
    encoding="utf-8"
  )
  subprocess.run(
    (sys.executable, *mode, "-c", program),
    check=True,
    capture_output=True,
    text=True,
    cwd=Path(__file__).parents[1],
  )


@pytest.mark.parametrize("body", list(Body))
def test_same_body_conjunction_query_is_delegated_once_then_filtered_by_raw_tt(
  natal: NatalChart, body: Body, monkeypatch: pytest.MonkeyPatch
) -> None:
  chart = natal_chart(
    prepare_natal_input(
      BirthRecord(
        natal.resolved.record.birth_date,
        natal.resolved.record.birth_time,
        FixedOffset(timedelta(0)),
        SITE,
      )
    ),
    ChartConfig(HouseSystem.WHOLE_SIGN, (body,), ()),
  )
  explicit = transit_hits(
    chart,
    start_utc=START,
    end_utc=END,
    moving_objects=(body,),
    natal_objects=(body,),
    aspects=(MajorAspect.CONJUNCTION,),
  )
  expected = replace(
    explicit, hits=tuple(hit for hit in explicit.hits if hit.jde_tt > chart.times.jde_tt)
  )
  calls: list[tuple[NatalChart, dict[str, Any]]] = []

  def delegated(source: NatalChart, **kwargs: Any) -> TransitHits:
    calls.append((source, kwargs))
    return explicit

  monkeypatch.setattr(returns_module, "transit_hits", delegated)
  result = _search(chart, body)
  assert result == expected
  assert result.chart is chart
  assert calls == [
    (
      chart,
      {
        "start_utc": START,
        "end_utc": END,
        "moving_objects": (body,),
        "natal_objects": (body,),
        "aspects": (MajorAspect.CONJUNCTION,),
      },
    )
  ]


@pytest.mark.parametrize("body", [Body.SUN, Body.MOON])
def test_actual_results_equal_the_explicit_query(natal: NatalChart, body: Body) -> None:
  result = _search(natal, body)
  explicit = transit_hits(
    natal,
    start_utc=START,
    end_utc=END,
    moving_objects=(body,),
    natal_objects=(body,),
    aspects=(MajorAspect.CONJUNCTION,),
  )
  assert result == replace(
    explicit, hits=tuple(hit for hit in explicit.hits if hit.jde_tt > natal.times.jde_tt)
  )
  assert result.chart is natal and result.moving_objects == result.natal_objects == (body,)
  assert result.aspects == (MajorAspect.CONJUNCTION,)
  assert result.celestial_version == natal.provenance.celestial_version


@pytest.mark.parametrize("body", [None, True, "sun", 0, LunarNode.MEAN_ASCENDING])
def test_body_identity_is_not_coerced(natal: NatalChart, body: object) -> None:
  with pytest.raises(TypeError, match="Body"):
    _search(natal, cast(Body, body))


def test_moment_chart_is_not_a_natal_return_source(natal: NatalChart) -> None:
  moving = moment_chart(START, SITE, CONFIG)
  with pytest.raises(TypeError, match="NatalChart"):
    _search(cast(NatalChart, moving))
  with pytest.raises(TypeError, match="NatalChart"):
    _search(cast(NatalChart, natal.resolved.record))


@pytest.mark.parametrize("body", [Body.MOON, Body.MARS])
def test_selected_body_must_exist_in_the_natal_chart(body: Body) -> None:
  chart = natal_chart(
    prepare_natal_input(BirthRecord(date(2000, 2, 29), time(12), FixedOffset(timedelta(0)), SITE)),
    ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN,), ()),
  )
  with pytest.raises(ValueError, match="available") as raised:
    _search(chart, body)
  assert "natal_objects" not in str(raised.value)


@pytest.mark.parametrize(
  ("start", "end", "error"),
  [
    (START.replace(tzinfo=None), END, ValueError),
    (END, START, ValueError),
    (START, START, ValueError),
    (datetime(1971, 1, 1, tzinfo=UTC), START, HistoricalTimeError),
    (START, datetime(2036, 1, 1, tzinfo=UTC), TransitDomainError),
  ],
)
def test_existing_interval_and_domain_failures_propagate(
  natal: NatalChart, start: datetime, end: datetime, error: type[Exception]
) -> None:
  with pytest.raises(error):
    return_hits(natal, Body.MOON, start_utc=start, end_utc=end)


def test_upstream_model_domain_rejection_is_not_substituted(
  natal: NatalChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  failure = ValueError("synthetic event-domain rejection")

  def fail(*args: Any, **kwargs: Any) -> NoReturn:
    raise failure

  monkeypatch.setattr(native, "longitude_events", fail)
  with pytest.raises(TransitDomainError) as raised:
    _search(natal)
  assert raised.value.__cause__ is failure
  assert raised.value.moving_object is Body.MOON


def test_delegated_computation_failure_is_preserved(
  natal: NatalChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  failure = native.CelestialError(
    "longitude_events", "synthetic calculation failure", recorded=False
  )

  def fail(*args: Any, **kwargs: Any) -> NoReturn:
    raise failure

  monkeypatch.setattr(returns_module, "transit_hits", fail)
  with pytest.raises(native.CelestialError) as raised:
    _search(natal)
  assert raised.value is failure


def test_explicit_offsets_normalize_to_the_same_interval(natal: NatalChart) -> None:
  zone = timezone(timedelta(hours=5, minutes=30))
  result = return_hits(
    natal, Body.MOON, start_utc=START.astimezone(zone), end_utc=END.astimezone(zone)
  )
  assert result == _search(natal)
  assert result.start_utc.tzinfo is UTC and result.end_utc.tzinfo is UTC


def test_empty_return_interval_retains_search_context(natal: NatalChart) -> None:
  end = START + timedelta(seconds=1)
  result = return_hits(natal, Body.MOON, start_utc=START, end_utc=end)
  assert result.hits == ()
  assert result.chart is natal and result.start_utc == START and result.end_utc == end
  assert result.sources[0].moving_object is Body.MOON


def test_exact_natal_hit_is_excluded_but_distinct_provider_events_remain(natal: NatalChart) -> None:
  birth = natal.resolved.utc
  explicit = transit_hits(
    natal,
    start_utc=birth,
    end_utc=birth + timedelta(days=1),
    moving_objects=(Body.SUN,),
    natal_objects=(Body.SUN,),
    aspects=(MajorAspect.CONJUNCTION,),
  )
  assert any(hit.jde_tt == natal.times.jde_tt for hit in explicit.hits)
  result = return_hits(natal, Body.SUN, start_utc=birth, end_utc=birth + timedelta(days=1))
  assert result.hits == tuple(hit for hit in explicit.hits if hit.jde_tt > natal.times.jde_tt)
  assert all(hit.jde_tt > natal.times.jde_tt for hit in result.hits)


def test_birth_inclusive_pluto_root_residual_is_not_merged() -> None:
  birth = datetime(1975, 1, 9, 21, 17, 41, tzinfo=UTC)
  chart = natal_chart(
    prepare_natal_input(BirthRecord(birth.date(), birth.time(), FixedOffset(timedelta(0)), SITE)),
    ChartConfig(HouseSystem.WHOLE_SIGN, (Body.PLUTO,), ()),
  )
  result = return_hits(
    chart,
    Body.PLUTO,
    start_utc=birth - timedelta(days=1),
    end_utc=birth + timedelta(days=1),
  )
  assert len(result.hits) == 1
  assert (result.hits[0].jde_tt - chart.times.jde_tt) * 86400 == pytest.approx(0.002414, abs=1e-6)


def test_pre_natal_hits_do_not_become_returns(natal: NatalChart) -> None:
  result = return_hits(
    natal,
    Body.MOON,
    start_utc=datetime(2000, 2, 1, tzinfo=UTC),
    end_utc=datetime(2000, 2, 28, tzinfo=UTC),
  )
  assert result.hits == ()
  assert result.sources[0].moving_object is Body.MOON


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_independent_return_times_and_same_model_root_residuals(case: dict[str, Any]) -> None:
  birth = datetime.fromisoformat(case["birth_utc"])
  chart = natal_chart(
    prepare_natal_input(BirthRecord(birth.date(), birth.time(), FixedOffset(timedelta(0)), SITE)),
    CONFIG,
  )
  body = Body(case["body"])
  result = return_hits(
    chart,
    body,
    start_utc=datetime.fromisoformat(case["start_utc"]),
    end_utc=datetime.fromisoformat(case["end_utc"]),
  )
  target = native.Target.SUN if body is Body.SUN else native.Target.MOON
  natal_longitude = next(p.longitude_deg for p in chart.positions if p.identity is body)
  tolerance_seconds = 5 if body is Body.SUN else 30
  assert len(result.hits) == len(case["hits"]) > 0
  assert result.hits == tuple(sorted(result.hits, key=lambda hit: hit.jde_tt))
  for hit, independent in zip(result.hits, case["hits"], strict=True):
    assert abs(hit.jde_tt - independent["jde_tt"]) * 86400 < tolerance_seconds
    assert hit.query_longitude_deg == natal_longitude % 360
    assert result.start_jde_tt <= hit.jde_tt < result.end_jde_tt
    actual_longitude = native.positions((target,), hit.jde_tt)[0].longitude_deg
    assert abs((actual_longitude - natal_longitude + 180) % 360 - 180) < 1e-6
    assert abs((hit.longitude_deg - hit.query_longitude_deg + 180) % 360 - 180) < 1e-6
    assert hit.moving_object is hit.natal_object is body


@pytest.mark.parametrize("case", PLANETARY_CASES, ids=lambda case: case["name"])
def test_independent_planetary_return_references(case: dict[str, Any]) -> None:
  reference = json.loads(PLANETARY_REFERENCE.read_text())
  birth = datetime.fromisoformat(case["birth_utc"])
  body = Body(case["body"])
  chart = natal_chart(
    prepare_natal_input(BirthRecord(birth.date(), birth.time(), FixedOffset(timedelta(0)), SITE)),
    ChartConfig(HouseSystem.WHOLE_SIGN, (body,), ()),
  )
  result = return_hits(
    chart,
    body,
    start_utc=datetime.fromisoformat(case["start_utc"]),
    end_utc=datetime.fromisoformat(case["end_utc"]),
  )
  natal_longitude = next(p.longitude_deg for p in chart.positions if p.identity is body)
  angular_tolerance = reference["calibration"]["angular_tolerance_deg"][body.value]
  natal_model_difference = (natal_longitude - case["natal_longitude_deg"] + 180) % 360 - 180
  assert abs(natal_model_difference) < angular_tolerance
  assert len(result.hits) == len(case["hits"]) > 0
  for hit, independent in zip(result.hits, case["hits"], strict=True):
    assert hit.jde_tt > chart.times.jde_tt
    assert abs(hit.jde_tt - independent["jde_tt"]) * 86400 < independent["time_tolerance_seconds"]
    assert hit.direction.value == independent["direction"]
    assert hit.query_longitude_deg == natal_longitude % 360
    actual_longitude = native.positions((native.Target(body.value),), hit.jde_tt)[0].longitude_deg
    same_backend_residual = (actual_longitude - natal_longitude + 180) % 360 - 180
    assert abs(same_backend_residual) < 1e-6
    assert abs((hit.longitude_deg - hit.query_longitude_deg + 180) % 360 - 180) < 1e-6
    assert hit.moving_object is hit.natal_object is body


@pytest.mark.parametrize("case", PLANETARY_CASES, ids=lambda case: case["name"])
def test_every_body_return_builds_a_chart_with_comparison_content(case: dict[str, Any]) -> None:
  birth = datetime.fromisoformat(case["birth_utc"])
  body = Body(case["body"])
  config = ChartConfig(HouseSystem.WHOLE_SIGN, (body,), ())
  chart = natal_chart(
    prepare_natal_input(BirthRecord(birth.date(), birth.time(), FixedOffset(timedelta(0)), SITE)),
    config,
  )
  events = return_hits(
    chart,
    body,
    start_utc=datetime.fromisoformat(case["start_utc"]),
    end_utc=datetime.fromisoformat(case["end_utc"]),
  )
  moving = moment_chart(events.hits[0], SITE, config)
  position = next(p for p in moving.positions if p.identity is body)
  overlays = cross_chart_house_overlays(moving, chart, left_objects=(body,), right_objects=())
  assert len(overlays.placements) == 1
  placement = overlays.placements[0]
  assert placement.identity is body
  assert placement.house == house_of(position.longitude_deg, chart.houses.cusps_deg)
  rules = (AspectRule(MajorAspect.CONJUNCTION, 1),)
  comparison = cross_chart_aspects(
    moving, chart, rules, left_objects=(body,), right_objects=(body,)
  )
  assert len(comparison.hits) == 1
  assert comparison.hits[0].left_object is comparison.hits[0].right_object is body
  fixed = transit_aspects(moving, chart, rules, moving_objects=(body,), natal_objects=(body,))
  assert len(fixed.hits) == 1
  assert fixed.hits[0].moving_object is fixed.hits[0].natal_object is body


@pytest.mark.parametrize("body", [Body.SUN, Body.MOON])
def test_exact_event_endpoint_is_excluded_left_included_right(
  natal: NatalChart, body: Body
) -> None:
  whole = _search(natal, body)
  assert whole.hits
  event = whole.hits[0]
  endpoint = moment_chart(event, SITE, CONFIG).moment.utc
  converted, _ = transit_interval(endpoint, endpoint + timedelta(seconds=1))
  assert converted == event.jde_tt
  left = return_hits(natal, body, start_utc=START, end_utc=endpoint)
  right = return_hits(natal, body, start_utc=endpoint, end_utc=END)
  assert event not in left.hits and event in right.hits
  assert left.end_jde_tt == right.start_jde_tt == event.jde_tt
  assert left.hits + right.hits == whole.hits


def test_reference_provenance_counts_and_recipe_are_pinned() -> None:
  reference = json.loads(REFERENCE.read_text())
  assert (
    reference["source"]["requested_flags"]
    == reference["source"]["verified_calculation_flags"]
    == 260
  )
  assert reference["source"]["pyswisseph_version"] == "2.10.3.2"
  assert reference["source"]["library_version"] == "2.10.03"
  assert reference["source"]["time_scale"].startswith("TT")
  assert reference["calibration"]["fixture_time_tolerance_seconds"] == {"sun": 5, "moon": 30}
  recipe = Path(__file__).parents[1] / "tools" / "fetch_return_reference.py"
  assert hashlib.sha256(recipe.read_bytes()).hexdigest() == reference["source"]["recipe_sha256"]
  counts = {case["name"]: len(case["hits"]) for case in CASES}
  assert len(counts) == 9 and counts["year_end_sun_2024-01-01"] == 2
  assert counts["leap_birth_moon_2024-01-01"] == 3
  assert any(case["natal_longitude_deg"] > 359.999999 for case in CASES)
  assert any(case["natal_longitude_deg"] < 1e-6 for case in CASES)


def test_planetary_reference_provenance_counts_recipes_and_observations() -> None:
  reference = json.loads(PLANETARY_REFERENCE.read_text())
  assert reference["source"]["pyswisseph_version"] == "2.10.3.2"
  assert reference["source"]["library_version"] == "2.10.03"
  assert (
    reference["source"]["requested_flags"]
    == reference["source"]["verified_calculation_flags"]
    == 260
  )
  assert len(PLANETARY_CASES) == 11
  assert sum(len(case["hits"]) for case in PLANETARY_CASES) == 16
  assert {case["body"] for case in PLANETARY_CASES if case["name"].startswith("post_natal_")} == {
    body.value for body in Body
  }
  triple = next(case for case in PLANETARY_CASES if case["name"] == "mercury_retrograde_triple")
  assert [hit["direction"] for hit in triple["hits"]] == ["increasing", "decreasing", "increasing"]
  assert all(
    hit["jde_tt"] > case["birth_jde_tt"] for case in PLANETARY_CASES for hit in case["hits"]
  )
  fetch = Path(__file__).parents[1] / "tools" / "fetch_planetary_return_reference.py"
  calibrate = Path(__file__).parents[1] / "tools" / "calibrate_planetary_return_reference.py"
  assert hashlib.sha256(fetch.read_bytes()).hexdigest() == reference["source"]["recipe_sha256"]
  assert (
    hashlib.sha256(calibrate.read_bytes()).hexdigest()
    == reference["calibration"]["calibration_recipe_sha256"]
  )
  assert (
    hashlib.sha256(PLANETARY_OBSERVATIONS.read_bytes()).hexdigest()
    == reference["calibration"]["native_observations_sha256"]
  )
  assert reference["calibrated_utc"] > reference["generated_utc"]
  assert "adjacent double crossings" in reference["source"]["algorithm"]


def test_return_location_only_changes_local_geometry_and_consumers(
  natal: NatalChart, monkeypatch: pytest.MonkeyPatch
) -> None:
  before = repr(natal)

  def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
    pytest.fail("A return chart manufactured a birth record")

  monkeypatch.setattr(birth_module.BirthRecord, "__init__", forbidden)
  events = _search(natal)
  event = events.hits[0]
  moving = moment_chart(event, SITE, CONFIG)
  relocated = moment_chart(event, Location(40, 100), CONFIG)
  assert type(moving) is MomentChart and not hasattr(moving, "resolved")
  assert moving.moment.source_jde_tt == relocated.moment.source_jde_tt == event.jde_tt
  assert moving.moment.utc == relocated.moment.utc
  assert moving.times == relocated.times and moving.positions == relocated.positions
  assert moving.houses != relocated.houses
  assert moving.houses.ascendant_deg != relocated.houses.ascendant_deg
  assert moving.requested == relocated.requested == CONFIG
  assert moving.effective == relocated.effective and moving.provenance == relocated.provenance
  rules = (AspectRule(MajorAspect.CONJUNCTION, 1),)
  assert (
    len(
      cross_chart_aspects(
        moving, natal, rules, left_objects=(Body.MOON,), right_objects=(Body.MOON,)
      ).hits
    )
    == 1
  )
  assert (
    len(
      cross_chart_house_overlays(
        moving, natal, left_objects=(Body.MOON,), right_objects=()
      ).placements
    )
    == 1
  )
  assert (
    len(
      transit_aspects(
        moving, natal, rules, moving_objects=(Body.MOON,), natal_objects=(Body.MOON,)
      ).hits
    )
    == 1
  )
  assert len(HouseRulers(moving).houses) == 12
  assert chart_dispositors(moving, objects=(Body.MOON,)).chart is moving
  assert chart_sign_distribution(moving, objects=(Body.MOON,)).total == 1
  assert format_chart(moving, load_catalog()).startswith("Tropical geocentric moment chart")
  assert repr(natal) == before


def test_return_chart_configuration_does_not_gain_the_reference_body(natal: NatalChart) -> None:
  events = _search(natal)
  config = ChartConfig(HouseSystem.EQUAL, (Body.SUN,), ())
  moving = moment_chart(events.hits[0], SITE, config)
  assert moving.requested == config
  assert tuple(p.identity for p in moving.positions) == (Body.SUN,)
  assert moving.moment.source_jde_tt == events.hits[0].jde_tt
  assert events.natal_objects == (Body.MOON,)


def test_missing_location_and_unavailable_houses_do_not_change_the_event(natal: NatalChart) -> None:
  events = _search(natal)
  event = events.hits[0]
  with pytest.raises(TypeError, match="Location"):
    moment_chart(event, cast(Location, None), CONFIG)
  config = ChartConfig(HouseSystem.PLACIDUS, (Body.SUN, Body.MOON), ())
  with pytest.raises(ChartDomainError):
    moment_chart(event, Location(89.9, 0), config)
  assert events.hits[0] is event and events.chart is natal


def test_provider_valid_solar_return_retains_raw_tt_when_chart_is_out_of_domain(
  natal: NatalChart,
) -> None:
  events = return_hits(
    natal,
    Body.SUN,
    start_utc=datetime(2200, 1, 1, tzinfo=UTC),
    end_utc=datetime(2201, 1, 1, tzinfo=UTC),
  )
  assert len(events.hits) == 1
  event = events.hits[0]
  with pytest.raises(ChartDomainError, match="Civil year 2200"):
    moment_chart(event, SITE, CONFIG)
  assert events.hits[0] is event
  assert event.jde_tt > natal.times.jde_tt


def test_return_knowledge_preserves_sources_translations_and_editorial_states() -> None:
  catalog = load_catalog()
  entry = catalog.entry("entry.solar_lunar_returns")
  assert entry.rule_ids == (
    "rule.project.solar_lunar_returns",
    "rule.project.exact_transit_hits",
    "rule.project.moment_charts",
  )
  assert entry.prerequisite_status.value == "complete"
  assert entry.output_eligibility.value == "reference_only"
  assert entry.chart_applicability == "not_assessed"
  assert set(entry.concept_ids) == {f"body.{body.value}" for body in Body} | {"aspect.conjunction"}
  assert "ten-body project convention" in entry.statement.en
  assert "root-adjacent" in entry.limits.en
  citations = catalog.citations(entry.identifier)
  assert len(citations) == 5
  assert all(source.verification.value == "verified" for _, source in citations)
  excerpts = [citation.excerpt for citation, _ in citations if citation.excerpt is not None]
  assert len(excerpts) == 4
  assert all(text.text("en") and text.text("zh-CN") for text in excerpts)
  assert all(text.translation_credit == "astrology contributors" for text in excerpts)
  rule = catalog.variant("rule.project.solar_lunar_returns")
  assert "project conventions" in rule.tradition.en
  assert rule.tradition.zh is not None and "项目约定" in rule.tradition.zh


def test_installed_return_observations_capture_supplied_results_without_calculating(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  import astrology.celestial as adapter
  from tools.installed_check import (
    acceptance_chart,
    acceptance_moments,
    acceptance_moving_events,
    acceptance_returns,
    acceptance_transits,
    calculation_observations,
  )

  chart = acceptance_chart()
  transits = acceptance_transits(chart)
  moments = acceptance_moments(chart, transits)
  returns = acceptance_returns(chart)
  moving_case = acceptance_moving_events()

  def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
    pytest.fail("Observation serialization performed a new native calculation")

  for name in (
    "snapshot",
    "transit_events",
    "transit_source",
    "moment_utc",
    "transit_interval",
    "moving_events",
    "moving_interval",
  ):
    monkeypatch.setattr(adapter, name, forbidden)
  values = json.loads(
    calculation_observations(chart, transits, moments, returns, load_catalog(), moving_case)
  )
  assert values["moving_events"]["search"] == repr(moving_case[0])
  assert values["moving_events"]["chart"]["moment"] == repr(moving_case[1].moment)
  assert "Exact moving-pair events" in values["moving_events"]["text"]["en"]
  assert "Exact transit hits" in values["transit_table"]["en"]
  assert "精确行运命中" in values["transit_table"]["zh-CN"]
  assert len(values["returns"]) == 2
  for (events, moving), observed in zip(returns, values["returns"], strict=True):
    assert observed["search"] == repr(events)
    assert "Planetary returns" in observed["event_table"]["en"]
    assert "行星返照" in observed["event_table"]["zh-CN"]
    assert repr(events.hits[0].jde_tt) in observed["event_table"]["en"]
    assert observed["chart"]["moment"] == repr(moving.moment)
    assert observed["chart"]["requested"] == repr(moving.requested)
    assert observed["text"]["en"].startswith("Tropical geocentric moment chart")
    assert observed["text"]["zh-CN"].startswith("热带地心时刻盘")
    assert set(observed) == {
      "search",
      "event_table",
      "chart",
      "comparison",
      "overlays",
      "transits",
      "rulers",
      "dispositors",
      "distribution",
      "text",
    }
