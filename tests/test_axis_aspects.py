"""Explicit axis selection, independent geometry and family boundaries.

显式选四轴、独立几何及对象类别边界。
"""

import math
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import date, time, timedelta
from enum import StrEnum
from typing import Any, cast, get_args

import pytest

import astrology
from astrology import (
  AspectHit,
  AspectMotion,
  AspectObject,
  AspectRule,
  Axis,
  Body,
  ChartConfig,
  CrossAspectHit,
  EclipticPosition,
  EffectiveConfiguration,
  HouseSystem,
  LunarNode,
  MajorAspect,
  NatalChart,
  NodeDefinition,
  ObjectOrb,
  OrbCombination,
  Placement,
  Sign,
  chart_sign_distribution,
  cross_chart_aspects,
  find_aspects,
  format_chart,
  load_catalog,
  natal_chart,
)
from astrology.chart import _AXIS_FIELDS
from astrology.knowledge import ConceptKind
from astrology.knowledge.records import CONFIGURATION_TYPES, Language
from astrology.objects import AstronomicalObject, ChartObject
from tools.catalog_docs import check_catalog_data
from tools.installed_check import _check_axes, _cross_source

_AXES = (10.5, 100.25, 202.75, 301.125)
_OTHER_AXES = (50.25, 140.0, 230.5, 320.75)


class _ForeignAxis(StrEnum):
  ASCENDANT = "ascendant"


def _source(
  longitude: float = 68,
  axes: tuple[float, float, float, float] = _AXES,
) -> NatalChart:
  return _cross_source(2000, "axis-test", ((Body.SUN, longitude),), axes=axes)


def _selected_chart(
  source: NatalChart, config: ChartConfig, hits: tuple[AspectHit, ...]
) -> NatalChart:
  return replace(
    source,
    requested=config,
    effective=replace(
      source.effective,
      aspect_objects=config.aspect_participants(),
      orb_combination=config.orb_combination,
    ),
    aspects=hits,
  )


def _config(
  selected: tuple[ChartObject, ...],
  rules: tuple[AspectRule, ...] | None = None,
  combination: OrbCombination | None = None,
) -> ChartConfig:
  return ChartConfig(
    HouseSystem.WHOLE_SIGN,
    (Body.SUN,),
    (AspectRule(MajorAspect.SEXTILE, 3),) if rules is None else rules,
    aspect_objects=selected,
    orb_combination=combination,
  )


def test_identity_owners_preserve_old_imports_and_distinct_families() -> None:
  from astrology import config, objects

  for name in ("Body", "LunarNode", "NodeDefinition"):
    assert getattr(astrology, name) is getattr(config, name) is getattr(objects, name)
  assert LunarNode.MEAN_ASCENDING.definition is NodeDefinition.MEAN
  assert set(get_args(AstronomicalObject)) == {Body, LunarNode}
  assert set(get_args(ChartObject)) == {Body, LunarNode, Axis}
  assert set(get_args(ChartObject)) <= set(CONFIGURATION_TYPES)
  assert set(_AXIS_FIELDS) == set(Axis)
  assert tuple(Axis) == (Axis.ASCENDANT, Axis.MIDHEAVEN, Axis.DESCENDANT, Axis.IMUM_COELI)


def test_axis_selections_are_explicit_isolated_and_canonically_ordered() -> None:
  selected: list[ChartObject] = [Axis.IMUM_COELI, Body.MOON, Axis.ASCENDANT, Body.SUN]
  config = ChartConfig(
    HouseSystem.WHOLE_SIGN,
    (Body.SUN, Body.MOON),
    (AspectRule(MajorAspect.CONJUNCTION, 3),),
    aspect_objects=selected,
  )
  selected.clear()
  assert config.aspect_objects == (Axis.IMUM_COELI, Body.MOON, Axis.ASCENDANT, Body.SUN)
  assert config.aspect_participants() == (Body.SUN, Body.MOON, Axis.ASCENDANT, Axis.IMUM_COELI)
  assert replace(config, aspect_objects=None).aspect_participants() == (Body.SUN, Body.MOON)
  assert replace(config, aspect_objects=None, aspects=()).aspect_participants() == ()
  assert _config((Axis.MIDHEAVEN,)).aspect_participants() == (Axis.MIDHEAVEN,)
  with pytest.raises(ValueError, match="duplicate"):
    _config((Axis.ASCENDANT, Axis.ASCENDANT))
  with pytest.raises(ValueError, match="subset"):
    _config((Body.MOON, Axis.ASCENDANT))
  with pytest.raises(ValueError, match="requires aspect rules"):
    _config((Axis.ASCENDANT,), ())
  with pytest.raises(ValueError, match="take part"):
    ChartConfig(
      HouseSystem.WHOLE_SIGN,
      (Body.SUN,),
      (AspectRule(MajorAspect.SEXTILE, 3, (ObjectOrb(Axis.ASCENDANT, 5),)),),
      orb_combination=OrbCombination.MEAN_OF_ORBS,
    )


@pytest.mark.parametrize("axis,longitude", tuple(zip(Axis, _AXES, strict=True)))
def test_each_stored_axis_drives_natal_composition_and_reconstruction(
  axis: Axis,
  longitude: float,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  source = _source((longitude + 57.5) % 360)
  config = _config((axis, Body.SUN))
  expected = (
    AspectHit(Body.SUN, axis, MajorAspect.SEXTILE, -60, 2.5, 3, AspectMotion.INDETERMINATE),
  )
  supplied = _selected_chart(source, config, expected)
  assert supplied.aspects == expected
  assert longitude not in source.houses.cusps_deg
  assert supplied.positions == source.positions
  assert supplied.placements == source.placements
  assert supplied.effective.aspect_objects == (Body.SUN, axis)
  with pytest.raises(ValueError, match="Stored aspects"):
    replace(supplied, aspects=())
  with pytest.raises(ValueError, match="Effective aspect participants"):
    replace(supplied, effective=replace(supplied.effective, aspect_objects=(Body.SUN,)))

  from astrology import celestial

  monkeypatch.setattr(
    celestial, "snapshot", lambda *_: (source.times, source.positions, source.houses)
  )
  actual = natal_chart(source.resolved, config)
  assert actual.aspects == expected
  assert actual.positions == source.positions


def test_explicit_opposite_axes_are_distinct_exact_pairs_without_rates() -> None:
  config = _config(tuple(reversed(tuple(Axis))), (AspectRule(MajorAspect.OPPOSITION, 0),))
  source = _source(68, (10, 100, 190, 280))
  expected = tuple(
    AspectHit(first, second, MajorAspect.OPPOSITION, 180, 0, 0, AspectMotion.EXACT)
    for first, second in (
      (Axis.ASCENDANT, Axis.DESCENDANT),
      (Axis.MIDHEAVEN, Axis.IMUM_COELI),
    )
  )
  assert (
    find_aspects(
      (
        AspectObject(Axis.ASCENDANT, 10, None),
        AspectObject(Axis.MIDHEAVEN, 100, None),
        AspectObject(Axis.DESCENDANT, 190, None),
        AspectObject(Axis.IMUM_COELI, 280, None),
      ),
      config.aspects,
    )
    == expected
  )
  chart = _selected_chart(source, config, expected)
  assert chart.effective.aspect_objects == tuple(Axis)
  assert chart.aspects == expected
  assert all(hit.motion is AspectMotion.EXACT for hit in chart.aspects)


@pytest.mark.parametrize("axis,longitude", tuple(zip(Axis, _AXES, strict=True)))
def test_each_cross_axis_uses_its_own_side_and_actual_field(axis: Axis, longitude: float) -> None:
  left = _source(0)
  right = _source((longitude + 57.5) % 360, _OTHER_AXES)
  rules = (AspectRule(MajorAspect.SEXTILE, 3),)
  result = cross_chart_aspects(left, right, rules, left_objects=(axis,), right_objects=(Body.SUN,))
  expected = (CrossAspectHit(axis, Body.SUN, MajorAspect.SEXTILE, 60, -2.5, 3),)
  assert result.hits == expected
  assert result.chart_left is left and result.chart_right is right
  assert not hasattr(result.hits[0], "motion")
  reverse = cross_chart_aspects(right, left, rules, left_objects=(Body.SUN,), right_objects=(axis,))
  assert reverse.hits == (CrossAspectHit(Body.SUN, axis, MajorAspect.SEXTILE, -60, 2.5, 3),)
  with pytest.raises(ValueError, match="complete pure derivation"):
    replace(result, hits=())


def test_cross_axis_defaults_independence_aliasing_and_pair_policy() -> None:
  source = _source()
  rules = (AspectRule(MajorAspect.CONJUNCTION, 0),)
  selected = _selected_chart(source, _config((Axis.ASCENDANT,)), ())
  default = cross_chart_aspects(selected, selected, rules)
  assert default.left_objects == default.right_objects == (Body.SUN,)
  assert default.hits == (CrossAspectHit(Body.SUN, Body.SUN, MajorAspect.CONJUNCTION, 0, 0, 0),)
  selection: list[ChartObject] = [Axis.IMUM_COELI, Body.SUN, Axis.ASCENDANT]
  result = cross_chart_aspects(
    source, source, rules, left_objects=selection, right_objects=selection
  )
  selection.clear()
  assert result.left_objects == result.right_objects == (Body.SUN, Axis.ASCENDANT, Axis.IMUM_COELI)
  assert len(result.hits) == 3
  assert all(h.left_object is h.right_object for h in result.hits)
  assert cross_chart_aspects(source, source, rules, left_objects=()).hits == ()
  with pytest.raises(ValueError, match="duplicate"):
    cross_chart_aspects(source, source, rules, left_objects=(Axis.ASCENDANT, Axis.ASCENDANT))
  with pytest.raises(ValueError, match="available"):
    cross_chart_aspects(source, source, rules, right_objects=(Body.MOON, Axis.MIDHEAVEN))


_WIDE_EXPECTED = (
  (MajorAspect.CONJUNCTION, 0, 30),
  (MajorAspect.SEXTILE, -60, 90),
  (MajorAspect.SEXTILE, 60, -30),
  (MajorAspect.SQUARE, -90, 120),
  (MajorAspect.SQUARE, 90, -60),
  (MajorAspect.TRINE, -120, 150),
  (MajorAspect.TRINE, 120, -90),
  (MajorAspect.OPPOSITION, 180, -150),
)


def test_axis_pairs_retain_all_wide_orb_branches_in_natal_and_cross() -> None:
  rules = tuple(AspectRule(aspect, 180) for aspect in MajorAspect)
  source = _source(68, (0, 30, 180, 210))
  result = cross_chart_aspects(
    source, source, rules, left_objects=(Axis.ASCENDANT,), right_objects=(Axis.MIDHEAVEN,)
  )
  assert [(h.aspect, h.branch_deg, h.deviation_deg) for h in result.hits] == list(_WIDE_EXPECTED)
  assert len(result.hits) == 8
  expected = tuple(
    AspectHit(
      Axis.ASCENDANT, Axis.MIDHEAVEN, aspect, branch, deviation, 180, AspectMotion.INDETERMINATE
    )
    for aspect, branch, deviation in _WIDE_EXPECTED
  )
  chart = _selected_chart(source, _config((Axis.ASCENDANT, Axis.MIDHEAVEN), rules), expected)
  assert chart.aspects == expected


@pytest.mark.parametrize("axis", tuple(Axis))
def test_axes_pair_with_nodes_but_natal_nodes_still_do_not_pair(axis: Axis) -> None:
  nodes = (LunarNode.MEAN_ASCENDING, LunarNode.MEAN_DESCENDING)
  objects = (
    AspectObject(nodes[0], 10, None),
    AspectObject(nodes[1], 10, None),
    AspectObject(axis, 10, None),
  )
  hits = find_aspects(objects, (AspectRule(MajorAspect.CONJUNCTION, 0),))
  assert [(h.first, h.second) for h in hits] == [(nodes[0], axis), (nodes[1], axis)]


@pytest.mark.parametrize(
  "combination,limit",
  (
    (OrbCombination.EITHER_WITHIN_OWN_ORB, 4),
    (OrbCombination.BOTH_WITHIN_OWN_ORB, 2),
    (OrbCombination.MEAN_OF_ORBS, 3),
  ),
)
def test_axis_orbs_use_the_existing_combination_in_both_compositions(
  combination: OrbCombination,
  limit: float,
) -> None:
  rules = (AspectRule(MajorAspect.CONJUNCTION, 2, (ObjectOrb(Axis.ASCENDANT, 4),)),)
  source = _source(102.5, (100, 190, 280, 10))
  config = _config((Body.SUN, Axis.ASCENDANT), rules, combination)
  expected = (
    ()
    if limit < 2.5
    else (
      AspectHit(
        Body.SUN,
        Axis.ASCENDANT,
        MajorAspect.CONJUNCTION,
        0,
        -2.5,
        limit,
        AspectMotion.INDETERMINATE,
      ),
    )
  )
  assert _selected_chart(source, config, expected).aspects == expected
  result = cross_chart_aspects(
    source,
    source,
    rules,
    left_objects=(Body.SUN,),
    right_objects=(Axis.ASCENDANT,),
    combination=combination,
  )
  assert len(result.hits) == len(expected)
  if expected:
    assert result.hits[0].orb_limit_deg == limit
  with pytest.raises(ValueError, match="selected"):
    cross_chart_aspects(
      source,
      source,
      rules,
      left_objects=(Body.SUN,),
      right_objects=(Body.SUN,),
      combination=combination,
    )


@pytest.mark.parametrize(
  "first,second,branch,deviation",
  (
    (350, 48, 60, -2),
    (10, 312, -60, 2),
    (0, 63, 60, 3),
    (0, 297, -60, -3),
  ),
)
def test_axis_wrap_both_branches_and_inclusive_endpoints(
  first: float,
  second: float,
  branch: float,
  deviation: float,
) -> None:
  hits = find_aspects(
    (AspectObject(Axis.ASCENDANT, first, None), AspectObject(Axis.DESCENDANT, second, None)),
    (AspectRule(MajorAspect.SEXTILE, 3),),
  )
  assert len(hits) == 1
  assert (hits[0].branch_deg, hits[0].deviation_deg) == (branch, deviation)
  assert hits[0].motion is AspectMotion.INDETERMINATE
  assert not find_aspects(
    (
      AspectObject(Axis.ASCENDANT, 0, None),
      AspectObject(Axis.DESCENDANT, math.nextafter(63, 64), None),
    ),
    (AspectRule(MajorAspect.SEXTILE, 3),),
  )


@pytest.mark.parametrize(
  "axis_rate,motion",
  (
    (None, AspectMotion.INDETERMINATE),
    (0, AspectMotion.SEPARATING),
    (0.9537, AspectMotion.STATIONARY),
  ),
)
def test_scalar_axis_rates_are_not_confused_with_absence(
  axis_rate: float | None,
  motion: AspectMotion,
) -> None:
  hits = find_aspects(
    (AspectObject(Axis.ASCENDANT, 100, axis_rate), AspectObject(Body.SUN, 102.5, 0.9537)),
    (AspectRule(MajorAspect.CONJUNCTION, 3),),
  )
  assert hits[0].motion is motion


def test_natal_axis_missing_rate_is_not_zero_or_borrowed(monkeypatch: pytest.MonkeyPatch) -> None:
  from astrology import celestial

  source = _source(102.5, (100, 190, 280, 10))
  monkeypatch.setattr(
    celestial, "snapshot", lambda *_: (source.times, source.positions, source.houses)
  )
  chart = natal_chart(
    source.resolved, _config((Body.SUN, Axis.ASCENDANT), (AspectRule(MajorAspect.CONJUNCTION, 3),))
  )
  assert chart.aspects == (
    AspectHit(
      Body.SUN, Axis.ASCENDANT, MajorAspect.CONJUNCTION, 0, -2.5, 3, AspectMotion.INDETERMINATE
    ),
  )


@pytest.mark.parametrize("axis", tuple(Axis))
def test_axes_are_rejected_at_every_narrow_boundary(axis: Axis) -> None:
  from astrology.celestial import _target

  bad = cast(Any, axis)
  calls: tuple[Callable[[], object], ...] = (
    lambda: ChartConfig(HouseSystem.WHOLE_SIGN, (bad,), ()),
    lambda: EclipticPosition(bad, 10, 0, 1, 1),
    lambda: Placement(bad, Sign.ARIES, 10, 1),
    lambda: chart_sign_distribution(_source(), objects=(bad,)),
    lambda: _target(bad),
  )
  for call in calls:
    with pytest.raises(TypeError):
      call()


@pytest.mark.parametrize(
  "bad", ("ascendant", None, MajorAspect.CONJUNCTION, _ForeignAxis.ASCENDANT)
)
def test_foreign_values_cannot_alias_axis_identities(bad: Any) -> None:
  for call in (
    lambda: ObjectOrb(bad, 3),
    lambda: AspectObject(bad, 10, None),
    lambda: _config((bad,)),
    lambda: cross_chart_aspects(_source(), _source(), (), left_objects=(bad,)),
    lambda: EffectiveConfiguration(
      HouseSystem.WHOLE_SIGN, "model", "fixed_fourteen_object_joint_snapshot", (bad,), None
    ),
    lambda: CrossAspectHit(bad, Body.SUN, MajorAspect.CONJUNCTION, 0, 0, 3),
    lambda: AspectHit(Body.SUN, bad, MajorAspect.CONJUNCTION, 0, 0, 3, AspectMotion.EXACT),
  ):
    with pytest.raises(TypeError):
      call()


def test_all_native_bindings_have_exactly_the_supported_keys() -> None:
  from astrology.celestial import _BODY_TARGETS, _NODE_TARGETS

  assert set(_BODY_TARGETS) == set(Body)
  assert set(_NODE_TARGETS) == set(LunarNode)
  assert not set(Axis) & (set(_BODY_TARGETS) | set(_NODE_TARGETS))


@pytest.mark.parametrize("axis", tuple(Axis))
@pytest.mark.parametrize("language", ("en", "zh-CN"))
def test_axis_vocabulary_and_lazy_supplied_catalog_names(axis: Axis, language: Language) -> None:
  catalog = load_catalog()
  concept = catalog.concept(f"axis.{axis.value}")
  assert concept.kind is ConceptKind.AXIS and concept.configuration is axis
  assert catalog.lookup(concept.name.text(language) or "")[0] is concept
  stripped = replace(
    catalog,
    concepts=tuple(c for c in catalog.concepts if c is not concept),
    variants=(),
    entries=(),
  )
  with pytest.raises(ValueError, match="configuration identity"):
    check_catalog_data(stripped)
  assert format_chart(_source(), stripped, language=language)
  source = _selected_chart(_source(), _config((axis,)), ())
  with pytest.raises(ValueError, match="catalog concept"):
    format_chart(source, stripped, language=language)
  changed = replace(concept, name=replace(concept.name, en="Caller axis", zh="调用方轴名"))
  supplied = replace(
    catalog, concepts=tuple(changed if c is concept else c for c in catalog.concepts)
  )
  text = format_chart(source, supplied, language=language)
  assert ("Caller axis" if language == "en" else "调用方轴名") in text
  stale = replace(
    changed, name=replace(changed.name, en="Revised", zh="旧译", revision=2, zh_revision=1)
  )
  if language == "zh-CN":
    with pytest.raises(ValueError, match="stale"):
      format_chart(
        source,
        replace(supplied, concepts=tuple(stale if c is changed else c for c in supplied.concepts)),
        language=language,
      )


def test_axis_comparison_and_knowledge_are_native_free_in_a_fresh_process() -> None:
  code = """
import sys
from astrology import *
from tools.installed_check import _cross_source
source = _cross_source(2000, 'isolated-axes', ((Body.SUN, 10),))
result = cross_chart_aspects(source, source, (AspectRule(MajorAspect.CONJUNCTION, 0),),
                            left_objects=(Axis.ASCENDANT,), right_objects=(Axis.ASCENDANT,))
if len(result.hits) != 1 or load_catalog().concept('axis.ascendant').configuration is not Axis.ASCENDANT:
  raise RuntimeError('axis consumer failed')
if 'celestial_calendar' in sys.modules or 'astrology.celestial' in sys.modules:
  raise RuntimeError('native astronomy initialized')
"""
  result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
  assert result.returncode == 0, result.stdout + result.stderr


def test_whole_sign_axes_are_not_cusps_and_nonzero_roundoff_is_not_exact() -> None:
  record = astrology.BirthRecord(
    date(2003, 7, 17),
    time(5, 37, 13),
    astrology.FixedOffset(timedelta(0)),
    astrology.Location(64.15, -21.94),
    source={"record": "synthetic"},
  )
  chart = natal_chart(
    astrology.prepare_natal_input(record),
    _config((Body.SUN, *Axis), tuple(AspectRule(a, 3) for a in MajorAspect)),
  )
  assert chart.houses.ascendant_deg != chart.houses.cusps_deg[0]
  assert chart.houses.midheaven_deg != chart.houses.cusps_deg[9]
  sun_hits = [hit for hit in chart.aspects if hit.first is Body.SUN]
  assert [(h.second, h.aspect, h.branch_deg) for h in sun_hits] == [
    (Axis.MIDHEAVEN, MajorAspect.TRINE, -120),
    (Axis.IMUM_COELI, MajorAspect.SEXTILE, 60),
  ]
  assert all(h.deviation_deg == pytest.approx(2.4745269119, abs=1e-9) for h in sun_hits)
  assert all(h.motion is AspectMotion.INDETERMINATE for h in sun_hits)
  opposite = next(
    hit for hit in chart.aspects if hit.first is Axis.MIDHEAVEN and hit.second is Axis.IMUM_COELI
  )
  assert opposite.deviation_deg != 0
  assert opposite.motion is AspectMotion.INDETERMINATE


def test_installed_axis_checks_exercise_the_pure_consumer() -> None:
  _check_axes()


def test_axis_entry_has_a_fixed_implementation_source_and_no_chart_assessment() -> None:
  catalog = load_catalog()
  entry = catalog.entry("entry.axis_aspects")
  assert set(entry.concept_ids) == {f"axis.{axis.value}" for axis in Axis}
  assert entry.chart_applicability == "not_assessed"
  assert entry.output_eligibility.value == "reference_only"
  citation, source = catalog.citations(entry.identifier)[0]
  assert citation.source_id == "source.astrology.axis_aspects.4cb15cc"
  assert source.url is not None
  assert source.url.endswith("4cb15cc2f63a67ba804c04840f255ffff1209382")
  assert "objects.Axis" in citation.locator
