"""Hand-worked rulership paths and supplied-chart boundaries. 手算守护路径及给定命盘边界。"""

from dataclasses import FrozenInstanceError
from enum import StrEnum
from typing import Any

import pytest

from astrology import (
  Axis,
  Body,
  Dispositors,
  HouseRuler,
  HouseRulers,
  LunarNode,
  NatalChart,
  Sign,
  chart_dispositors,
  load_catalog,
)
from astrology.objects import AstronomicalObject
from tools.installed_check import _cross_source


def _chart(*rows: tuple[AstronomicalObject, Sign]) -> NatalChart:
  return _cross_source(
    2000,
    "dispositors",
    tuple((identity, tuple(Sign).index(sign) * 30.0) for identity, sign in rows),
  )


def test_chain_to_final_dispositor_through_unselected_rulers() -> None:
  chart = _chart((Body.SUN, Sign.GEMINI), (Body.MERCURY, Sign.ARIES), (Body.MARS, Sign.ARIES))
  result = chart_dispositors(chart, objects=(Body.SUN,))
  assert result.chart is chart
  assert result.objects == (Body.SUN,)
  assert result.edges == {Body.SUN: Body.MERCURY, Body.MERCURY: Body.MARS, Body.MARS: Body.MARS}
  assert result.chains == {Body.SUN: (Body.SUN, Body.MERCURY, Body.MARS)}
  assert result.final_dispositors == (Body.MARS,)
  assert result.cycles == () and result.missing_rulers == {}
  assert result.rule_id == "rule.project.dispositor_chains"
  assert result == Dispositors(chart, (Body.SUN,))


def test_converging_roots_report_the_reached_final_dispositor_once() -> None:
  chart = _chart(
    (Body.SUN, Sign.GEMINI),
    (Body.MERCURY, Sign.ARIES),
    (Body.MARS, Sign.ARIES),
    (Body.MOON, Sign.CANCER),
  )
  result = chart_dispositors(chart, objects=(Body.MARS, Body.MERCURY, Body.SUN))
  assert result.chains == {
    Body.SUN: (Body.SUN, Body.MERCURY, Body.MARS),
    Body.MERCURY: (Body.MERCURY, Body.MARS),
    Body.MARS: (Body.MARS,),
  }
  assert result.final_dispositors == (Body.MARS,)
  assert Body.MOON not in result.edges
  assert result.cycles == () and result.missing_rulers == {}


def test_tail_and_cycle_roots_share_one_domicile_mutual_reception() -> None:
  chart = _chart(
    (Body.VENUS, Sign.AQUARIUS),
    (Body.SATURN, Sign.LEO),
    (Body.SUN, Sign.CANCER),
    (Body.MOON, Sign.LEO),
  )
  result = chart_dispositors(chart, objects=(Body.MOON, Body.VENUS))
  assert result.objects == (Body.VENUS, Body.MOON)
  assert tuple(result.chains) == result.objects
  assert result.chains == {
    Body.VENUS: (Body.VENUS, Body.SATURN, Body.SUN, Body.MOON),
    Body.MOON: (Body.MOON, Body.SUN),
  }
  assert result.cycles == ((Body.SUN, Body.MOON),)
  assert result.edges == {
    Body.VENUS: Body.SATURN,
    Body.SATURN: Body.SUN,
    Body.SUN: Body.MOON,
    Body.MOON: Body.SUN,
  }
  assert result.final_dispositors == () and result.missing_rulers == {}


def test_longer_cycle_is_canonical_and_excludes_tail_and_unvisited_domicile() -> None:
  chart = _chart(
    (Body.URANUS, Sign.VIRGO),
    (Body.MARS, Sign.GEMINI),
    (Body.MERCURY, Sign.SAGITTARIUS),
    (Body.JUPITER, Sign.ARIES),
    (Body.SUN, Sign.LEO),
  )
  result = chart_dispositors(chart, objects=(Body.URANUS, Body.JUPITER))
  assert result.chains == {
    Body.URANUS: (Body.URANUS, Body.MERCURY, Body.JUPITER, Body.MARS),
    Body.JUPITER: (Body.JUPITER, Body.MARS, Body.MERCURY),
  }
  assert result.cycles == ((Body.MARS, Body.MERCURY, Body.JUPITER),)
  assert tuple(result.edges) == (Body.URANUS, Body.MARS, Body.MERCURY, Body.JUPITER)
  assert result.edges == {
    Body.URANUS: Body.MERCURY,
    Body.MARS: Body.MERCURY,
    Body.MERCURY: Body.JUPITER,
    Body.JUPITER: Body.MARS,
  }
  assert result.final_dispositors == () and result.missing_rulers == {}


def test_missing_rulers_remain_root_specific_and_have_no_fabricated_placements() -> None:
  node = LunarNode.MEAN_ASCENDING
  chart = _chart(
    (node, Sign.SCORPIO),
    (Body.MARS, Sign.PISCES),
    (Body.SUN, Sign.AQUARIUS),
    (Body.MOON, Sign.SAGITTARIUS),
  )
  result = chart_dispositors(chart, objects=(Body.MOON, Body.SUN, node))
  assert result.chains == {node: (node, Body.MARS), Body.SUN: (Body.SUN,), Body.MOON: (Body.MOON,)}
  assert result.edges == {
    node: Body.MARS,
    Body.MARS: Body.JUPITER,
    Body.SUN: Body.SATURN,
    Body.MOON: Body.JUPITER,
  }
  assert result.missing_rulers == {
    node: Body.JUPITER,
    Body.SUN: Body.SATURN,
    Body.MOON: Body.JUPITER,
  }
  assert tuple(result.missing_rulers) == result.objects
  assert result.cycles == () and result.final_dispositors == ()
  assert Body.JUPITER not in result.edges and Body.SATURN not in result.edges
  assert result.chart is chart and len(chart.placements) == 4


def test_independent_sinks_and_cycle_do_not_imply_one_chart_wide_ruler() -> None:
  chart = _chart(
    (Body.MOON, Sign.CANCER),
    (Body.SUN, Sign.LEO),
    (Body.URANUS, Sign.AQUARIUS),
    (Body.SATURN, Sign.GEMINI),
    (Body.MERCURY, Sign.CAPRICORN),
  )
  result = chart_dispositors(chart, objects=(Body.URANUS, Body.SUN, Body.MOON))
  assert result.final_dispositors == (Body.MOON, Body.SUN)
  assert result.cycles == ((Body.SATURN, Body.MERCURY),)
  assert result.chains[Body.URANUS] == (Body.URANUS, Body.SATURN, Body.MERCURY)
  assert result.missing_rulers == {}
  assert result.objects == (Body.MOON, Body.SUN, Body.URANUS)


def test_multiple_cycles_follow_source_order_not_traversal_order() -> None:
  chart = _chart(
    (Body.MOON, Sign.LEO),
    (Body.VENUS, Sign.ARIES),
    (Body.SUN, Sign.CANCER),
    (Body.MARS, Sign.TAURUS),
    (Body.NEPTUNE, Sign.LIBRA),
  )
  result = chart_dispositors(chart, objects=(Body.NEPTUNE, Body.SUN))
  assert result.cycles == ((Body.MOON, Body.SUN), (Body.VENUS, Body.MARS))
  assert result.cycles == chart_dispositors(chart, objects=(Body.SUN, Body.NEPTUNE)).cycles
  assert tuple(result.edges) == tuple(p.identity for p in chart.placements)
  only_neptune = chart_dispositors(chart, objects=(Body.NEPTUNE,))
  assert only_neptune.cycles == ((Body.VENUS, Body.MARS),)
  assert Body.MOON not in only_neptune.edges and Body.SUN not in only_neptune.edges


@pytest.mark.parametrize("identity", [*Body, *LunarNode])
def test_each_admitted_root_family_uses_sign_rulership(identity: AstronomicalObject) -> None:
  result = chart_dispositors(_chart((identity, Sign.PISCES)), objects=(identity,))
  assert result.edges == {identity: Body.JUPITER}
  assert result.chains == {identity: (identity,)}
  assert result.cycles == ()
  if identity is Body.JUPITER:
    assert result.final_dispositors == (Body.JUPITER,) and result.missing_rulers == {}
  else:
    assert result.final_dispositors == () and result.missing_rulers == {identity: Body.JUPITER}


def test_longest_classical_cycle_terminates_with_its_closing_edge() -> None:
  chart = _chart(
    (Body.SUN, Sign.CANCER),
    (Body.MOON, Sign.GEMINI),
    (Body.MERCURY, Sign.TAURUS),
    (Body.VENUS, Sign.ARIES),
    (Body.MARS, Sign.SAGITTARIUS),
    (Body.JUPITER, Sign.CAPRICORN),
    (Body.SATURN, Sign.LEO),
  )
  order = (Body.SUN, Body.MOON, Body.MERCURY, Body.VENUS, Body.MARS, Body.JUPITER, Body.SATURN)
  result = chart_dispositors(chart, objects=(Body.SUN,))
  assert result.chains == {Body.SUN: order}
  assert result.cycles == (order,)
  assert tuple(result.edges.values()) == (*order[1:], Body.SUN)
  assert result.final_dispositors == () and result.missing_rulers == {}


def test_selection_and_all_views_are_immutable_snapshots() -> None:
  chart = _chart((Body.SUN, Sign.CANCER), (Body.MOON, Sign.LEO))
  selection: list[AstronomicalObject] = [Body.MOON, Body.SUN]
  result = Dispositors(chart, selection)
  selection.clear()
  assert result.objects == (Body.SUN, Body.MOON)
  assert result.chains[Body.SUN] == (Body.SUN, Body.MOON)
  for mapping in (result.edges, result.chains, result.missing_rulers):
    with pytest.raises(TypeError):
      mapping[Body.SUN] = Body.SATURN  # type: ignore[index]
  with pytest.raises(FrozenInstanceError):
    result.objects = ()  # type: ignore[misc]
  with pytest.raises(TypeError):
    result.cycles[0][0] = Body.SATURN  # type: ignore[index]
  with pytest.raises(TypeError):
    Dispositors(chart, (Body.SUN,), edges={})  # type: ignore[call-arg]


class Foreign(StrEnum):
  SUN = "sun"


@pytest.mark.parametrize("bad", [None, True, 1, "chart", [], {}])
def test_wrong_chart_types(bad: Any) -> None:
  with pytest.raises(TypeError, match="chart"):
    chart_dispositors(bad, objects=(Body.SUN,))


@pytest.mark.parametrize(
  "bad",
  [None, True, 1, "sun", b"sun", {Body.SUN}, {Body.SUN: 0}, iter((Body.SUN,))],
)
def test_non_sequence_selections(bad: Any) -> None:
  with pytest.raises(TypeError, match="sequence"):
    chart_dispositors(_chart((Body.SUN, Sign.LEO)), objects=bad)


@pytest.mark.parametrize("bad", [None, True, 1, "sun", Foreign.SUN, Sign.LEO, *Axis, []])
def test_wrong_root_identity_families(bad: Any) -> None:
  with pytest.raises(TypeError, match="Body or LunarNode"):
    Dispositors(_chart((Body.SUN, Sign.LEO)), (bad,))


@pytest.mark.parametrize("objects", [(), (Body.SUN, Body.SUN)])
def test_empty_or_duplicate_roots(objects: tuple[AstronomicalObject, ...]) -> None:
  with pytest.raises(ValueError, match=r"nonempty.*duplicate"):
    chart_dispositors(_chart((Body.SUN, Sign.LEO)), objects=objects)


@pytest.mark.parametrize("missing", [Body.SATURN, LunarNode.MEAN_DESCENDING])
def test_unavailable_root_is_rejected_not_returned_as_a_missing_ruler(
  missing: AstronomicalObject,
) -> None:
  with pytest.raises(ValueError, match=missing.value):
    Dispositors(_chart((Body.SUN, Sign.LEO)), (Body.SUN, missing))


def test_root_exports_follow_the_defining_domain() -> None:
  from astrology import dignities, summaries

  assert dignities.HouseRuler is HouseRuler
  assert dignities.HouseRulers is HouseRulers
  assert dignities.Dispositors is Dispositors
  assert dignities.chart_dispositors is chart_dispositors
  assert not hasattr(summaries, "HouseRulers") and not hasattr(summaries, "HouseRuler")


def test_project_rule_links_roots_without_claiming_a_chart_conclusion() -> None:
  catalog = load_catalog()
  result = chart_dispositors(_chart((Body.SUN, Sign.LEO)), objects=(Body.SUN,))
  entry = catalog.entry("entry.dispositor_chains")
  rule = catalog.variant(result.rule_id)
  roots = {f"body.{body.value}" for body in Body} | {
    "node.mean_ascending",
    "node.mean_descending",
    "node.meeus_five_term_true_ascending",
    "node.meeus_five_term_true_descending",
  }
  assert set(rule.concept_ids) == set(entry.concept_ids) == roots
  assert entry.rule_ids == (result.rule_id,)
  assert rule.configuration is None
  assert entry.prerequisite_status.value == "complete"
  assert entry.output_eligibility.value == "reference_only"
  assert entry.chart_applicability == "not_assessed"
  assert entry.citations[0].source_id == "source.lilly.christian-astrology-1647"
  assert "sign-ruler assignments only" in entry.citations[0].locator
