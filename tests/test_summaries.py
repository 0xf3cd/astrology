"""Explicit populations, sourced classifications and bilingual summaries. 显式人口、来源分类和双语摘要。"""

import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from enum import StrEnum
from typing import Any

import pytest

from astrology import (
  AshmandSignGroup,
  Body,
  Element,
  LunarNode,
  Modality,
  NatalChart,
  Placement,
  Sign,
  SignDistribution,
  ashmand_sign_group,
  chart_sign_distribution,
  element_of,
  format_lunar_phase,
  format_sign_distribution,
  load_catalog,
  lunar_phase,
  modality_of,
  natal_lunar_phase,
  sign_distribution,
)
from astrology.knowledge import ConceptKind, LocalizedText
from astrology.knowledge.records import CONFIGURATION_TYPES, Language
from tools import installed_check
from tools.catalog_docs import check_catalog_data, render_catalog
from tools.installed_check import _cross_source

# Astrodienst snapshot 20251228094629, seven element/quality membership lines.
# Astrodienst 的 20251228094629 快照，七条元素和性质成员行。
_MEMBERSHIPS = (
  (Sign.ARIES, Element.FIRE, Modality.CARDINAL),
  (Sign.TAURUS, Element.EARTH, Modality.FIXED),
  (Sign.GEMINI, Element.AIR, Modality.MUTABLE),
  (Sign.CANCER, Element.WATER, Modality.CARDINAL),
  (Sign.LEO, Element.FIRE, Modality.FIXED),
  (Sign.VIRGO, Element.EARTH, Modality.MUTABLE),
  (Sign.LIBRA, Element.AIR, Modality.CARDINAL),
  (Sign.SCORPIO, Element.WATER, Modality.FIXED),
  (Sign.SAGITTARIUS, Element.FIRE, Modality.MUTABLE),
  (Sign.CAPRICORN, Element.EARTH, Modality.CARDINAL),
  (Sign.AQUARIUS, Element.AIR, Modality.FIXED),
  (Sign.PISCES, Element.WATER, Modality.MUTABLE),
)


class ForeignIdentity(StrEnum):
  ARIES = "aries"
  SUN = "sun"


@pytest.mark.parametrize("sign,element,modality", _MEMBERSHIPS)
def test_external_memberships(sign: Sign, element: Element, modality: Modality) -> None:
  assert element_of(sign) is element
  assert modality_of(sign) is modality
  assert type(ashmand_sign_group(sign)) is AshmandSignGroup


@pytest.mark.parametrize(
  "bad", ["aries", None, 0, True, Element.FIRE, AshmandSignGroup.FIXED, ForeignIdentity.ARIES]
)
def test_classification_type_boundaries(bad: Any) -> None:
  for query in (element_of, modality_of):
    with pytest.raises(TypeError):
      query(bad)


@pytest.fixture
def source_chart() -> NatalChart:
  return _cross_source(
    2000,
    "summary",
    ((Body.MOON, 100), (Body.SUN, 10), (Body.MARS, 40), (LunarNode.MEAN_ASCENDING, 65)),
  )


def test_explicit_subset_keeps_chart_order_and_does_not_mutate(source_chart: NatalChart) -> None:
  selection = [Body.SUN, Body.MOON]
  before = repr(source_chart)
  result = chart_sign_distribution(source_chart, objects=selection)
  selection.clear()
  assert result.objects == (Body.MOON, Body.SUN)
  assert result.placements == source_chart.placements[:2]
  assert (
    result.total == sum(result.element_counts.values()) == sum(result.modality_counts.values()) == 2
  )
  assert result.element_counts == {
    Element.FIRE: 1,
    Element.EARTH: 0,
    Element.AIR: 0,
    Element.WATER: 1,
  }
  assert result.modality_counts == {Modality.CARDINAL: 2, Modality.FIXED: 0, Modality.MUTABLE: 0}
  assert result.element_proportions[Element.FIRE] == 0.5
  assert result.element_proportions == {
    Element.FIRE: 0.5,
    Element.EARTH: 0.0,
    Element.AIR: 0.0,
    Element.WATER: 0.5,
  }
  assert result.modality_proportions == {
    Modality.CARDINAL: 1.0,
    Modality.FIXED: 0.0,
    Modality.MUTABLE: 0.0,
  }
  assert sum(result.modality_proportions.values()) == 1
  assert repr(source_chart) == before
  assert chart_sign_distribution(source_chart, objects=source_chart.requested.objects).total == 4


def test_all_twelve_signs_and_snapshot_isolation() -> None:
  identities = (*Body, *LunarNode)
  placements = [
    Placement(identity, sign, 1, 1) for identity, sign in zip(identities, Sign, strict=False)
  ]
  result = sign_distribution(placements)
  direct = SignDistribution(placements)  # type: ignore[arg-type]
  placements.clear()
  assert direct == result
  assert len(result.placements) == result.total == 12
  assert tuple(result.element_counts.values()) == (3, 3, 3, 3)
  assert tuple(result.modality_counts.values()) == (4, 4, 4)
  assert tuple(result.modality_proportions.values()) == (1 / 3, 1 / 3, 1 / 3)
  with pytest.raises(TypeError):
    result.element_counts[Element.FIRE] = 9  # type: ignore[index]
  with pytest.raises(TypeError):
    result.modality_proportions[Modality.FIXED] = 1  # type: ignore[index]
  with pytest.raises(FrozenInstanceError):
    result.placements = ()  # type: ignore[misc]
  assert hash(result) == hash(sign_distribution(result.placements))
  with pytest.raises(TypeError):
    SignDistribution(result.placements, total=0)  # type: ignore[call-arg]


@pytest.mark.parametrize("bad", [None, "sun", b"sun", iter(()), 1, [Body.SUN], [None]])
def test_invalid_populations(bad: Any) -> None:
  for constructor in (sign_distribution, SignDistribution):
    with pytest.raises(TypeError):
      constructor(bad)


def test_empty_and_duplicate_populations(source_chart: NatalChart) -> None:
  for constructor in (sign_distribution, SignDistribution):
    with pytest.raises(ValueError, match="empty"):
      constructor(())
    first = source_chart.placements[0]
    with pytest.raises(ValueError, match="duplicate"):
      constructor((first, replace(first, sign=Sign.LEO)))


@pytest.mark.parametrize(
  "bad", [None, "sun", b"sun", iter(()), ["sun"], [None], [Sign.ARIES], [ForeignIdentity.SUN]]
)
def test_invalid_chart_selections(source_chart: NatalChart, bad: Any) -> None:
  with pytest.raises(TypeError):
    chart_sign_distribution(source_chart, objects=bad)


@pytest.mark.parametrize(
  "selection", [[], [Body.SUN, Body.SUN], [Body.PLUTO], [LunarNode.MEAN_DESCENDING]]
)
def test_empty_duplicate_and_unavailable_selection(
  source_chart: NatalChart, selection: Any
) -> None:
  with pytest.raises(ValueError):
    chart_sign_distribution(source_chart, objects=selection)


def test_chart_composition_and_missing_positions(source_chart: NatalChart) -> None:
  assert natal_lunar_phase(source_chart) == lunar_phase(10, 100)
  assert natal_lunar_phase(source_chart).elongation_deg == 90
  for coordinates, missing in [
    (((Body.SUN, 10),), "moon"),
    (((Body.MOON, 10),), "sun"),
    (((Body.MARS, 10),), "sun, moon"),
  ]:
    chart = _cross_source(2000, "missing", coordinates)
    with pytest.raises(ValueError, match=missing):
      natal_lunar_phase(chart)
  for bad in (None, (), "chart"):
    with pytest.raises(TypeError):
      natal_lunar_phase(bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
      chart_sign_distribution(bad, objects=[Body.SUN])  # type: ignore[arg-type]


def test_names_catalog_statuses_and_generated_tables(source_chart: NatalChart) -> None:
  catalog = load_catalog()
  check_catalog_data(catalog)
  assert catalog.lookup("common")[0].identifier == "modality.mutable"
  assert catalog.lookup("固定星座")[0].identifier == "sign_group.ashmand1822.fixed"
  assert catalog.lookup("固定模式")[0].identifier == "modality.fixed"
  for kind, count in (
    (ConceptKind.ELEMENT, 4),
    (ConceptKind.MODALITY, 3),
    (ConceptKind.LUNATION_TYPE, 8),
  ):
    assert len(catalog.list_concepts(kind=kind)) == count
    assert all(c.configuration is None for c in catalog.list_concepts(kind=kind))
  request_types: tuple[type[object], ...] = CONFIGURATION_TYPES
  assert Element not in request_types and Modality not in request_types
  for identifier in ("entry.sign_elements", "entry.sign_modalities", "entry.lunation_types"):
    entry = catalog.entry(identifier)
    assert entry.prerequisite_status.value == "complete"
    assert (
      entry.output_eligibility.value == "reference_only"
      and entry.chart_applicability == "not_assessed"
    )
    assert all(c.excerpt is None for c in entry.citations)
    assert catalog.citations(identifier)[0][1].verification.value == "verified"
  for language in ("en", "zh-CN"):
    rendered = render_catalog(catalog, language, "0.2.0")
    for sign, element, modality in _MEMBERSHIPS:
      name = catalog.concept(f"sign.{sign.value}").name.text(language)
      for prefix, member in (("element", element), ("modality", modality)):
        label = catalog.concept(f"{prefix}.{member.value}").name.text(language)
        assert f"| {name} | {label} |" in rendered
    assert "| [315, 360) |" in rendered
  result = chart_sign_distribution(source_chart, objects=(Body.SUN, Body.MARS, Body.MOON))
  english = format_sign_distribution(result, catalog)
  chinese = format_sign_distribution(result, catalog, language="zh-CN")
  assert "Sun [sun]" in english and "太阳 [sun]" in chinese
  assert "1/3 | 33.33%" in english and "0/3 | 0.00%" in chinese
  near = lunar_phase(math.ulp(0.0), 45)
  text = format_lunar_phase(near, catalog)
  assert "New Moon Type" in text and "44.99999999999999" in text
  assert "新月型" in format_lunar_phase(near, catalog, language="zh-CN")


@pytest.mark.parametrize("angle", [0, 180])
@pytest.mark.parametrize(
  "language,direction_line",
  [("en", "Angular direction: turning"), ("zh-CN", "角度方向: 转折点")],
)
def test_turning_phase_text(angle: float, language: Language, direction_line: str) -> None:
  text = format_lunar_phase(lunar_phase(0, angle), load_catalog(), language=language)
  assert direction_line in text.splitlines()


@pytest.mark.parametrize(
  "language,name",
  [("en", "Mean ascending lunar node"), ("zh-CN", "平均升交点")],
)
def test_lunar_node_distribution_text(
  source_chart: NatalChart, language: Language, name: str
) -> None:
  result = chart_sign_distribution(source_chart, objects=(LunarNode.MEAN_ASCENDING,))
  text = format_sign_distribution(result, load_catalog(), language=language)
  assert result.objects == (LunarNode.MEAN_ASCENDING,)
  assert f"{name} [mean_ascending_node]" in text
  assert "1/1 | 100.00%" in text


@pytest.mark.parametrize("formatter", [format_lunar_phase, format_sign_distribution])
def test_formatter_errors_and_supplied_names(formatter: Any, source_chart: NatalChart) -> None:
  catalog = load_catalog()
  result = (
    lunar_phase(0, 45)
    if formatter is format_lunar_phase
    else sign_distribution(source_chart.placements)
  )
  with pytest.raises(TypeError):
    formatter(None, catalog)
  with pytest.raises(TypeError):
    formatter(result, None)
  with pytest.raises(ValueError):
    formatter(result, catalog, language="fr")
  identifier = (
    "lunation_type.rudhyar1950.crescent_moon" if formatter is format_lunar_phase else "element.fire"
  )
  original = catalog.concept(identifier)
  for name in (
    LocalizedText("Custom"),
    LocalizedText("Custom", "旧名", revision=2, zh_revision=1, translation_credit="test"),
  ):
    altered = replace(original, name=name)
    custom = replace(
      catalog, concepts=tuple(altered if c is original else c for c in catalog.concepts)
    )
    with pytest.raises(ValueError, match="Missing or stale"):
      formatter(result, custom, language="zh-CN")
  escaped = replace(original, name=LocalizedText("A|B\nC"))
  custom = replace(
    catalog, concepts=tuple(escaped if c is original else c for c in catalog.concepts)
  )
  assert r"A\|B\nC" in formatter(result, custom)
  # Remove the complete linked record graph so the Catalog remains internally valid.
  # 移除完整关联记录图，保持 Catalog 内部引用有效。
  custom = replace(
    catalog,
    concepts=tuple(c for c in catalog.concepts if c is not original),
    variants=(),
    entries=(),
  )
  with pytest.raises(KeyError):
    formatter(result, custom)


@pytest.mark.parametrize(
  "kind", [ConceptKind.ELEMENT, ConceptKind.MODALITY, ConceptKind.LUNATION_TYPE]
)
def test_catalog_guard_rejects_missing_output_identity_and_rule_links(kind: ConceptKind) -> None:
  catalog = load_catalog()
  omitted = catalog.list_concepts(kind=kind)[0]
  changed = replace(
    catalog,
    concepts=tuple(c for c in catalog.concepts if c is not omitted),
    variants=tuple(
      replace(v, concept_ids=tuple(i for i in v.concept_ids if i != omitted.identifier))
      for v in catalog.variants
    ),
    entries=tuple(
      replace(e, concept_ids=tuple(i for i in e.concept_ids if i != omitted.identifier))
      for e in catalog.entries
    ),
  )
  with pytest.raises(ValueError, match="identities"):
    check_catalog_data(changed)
  entry_id = {
    ConceptKind.ELEMENT: "entry.sign_elements",
    ConceptKind.MODALITY: "entry.sign_modalities",
    ConceptKind.LUNATION_TYPE: "entry.lunation_types",
  }[kind]
  original = catalog.entry(entry_id)
  broken = replace(original, rule_ids=())
  changed = replace(catalog, entries=tuple(broken if e is original else e for e in catalog.entries))
  with pytest.raises(ValueError, match="linkage"):
    check_catalog_data(changed)


@pytest.mark.parametrize("mode", [[], ["-O"]])
def test_pure_summaries_and_knowledge_do_not_import_native_astronomy(mode: list[str]) -> None:
  code = """
import sys
from astrology import *
catalog = load_catalog()
result = sign_distribution([Placement(Body.SUN, Sign.ARIES, 0, 1)])
format_sign_distribution(result, catalog)
format_lunar_phase(lunar_phase(0, 45), catalog, language="zh-CN")
if any(n.startswith(("celestial", "ctypes")) for n in sys.modules):
  raise RuntimeError("native import")
for action in (lambda: sign_distribution([]), lambda: lunar_phase(True, 0)):
  try: action()
  except (TypeError, ValueError): pass
  else: raise RuntimeError("missing runtime check")
"""
  result = subprocess.run([sys.executable, *mode, "-c", code], capture_output=True, text=True)
  assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
  "target", ["element_of", "natal_lunar_phase", "format_sign_distribution", "format_lunar_phase"]
)
def test_installed_summary_check_rejects_representative_defects(
  monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
  import astrology

  replacements: dict[str, Any] = {
    "element_of": lambda sign: Element.WATER,
    "natal_lunar_phase": lambda chart: lunar_phase(0, 10),
    "format_sign_distribution": lambda *args, **kwargs: "incomplete",
    "format_lunar_phase": lambda *args, **kwargs: "incomplete",
  }
  monkeypatch.setattr(astrology, target, replacements[target])
  with pytest.raises(ValueError, match="Installed"):
    installed_check._check_summaries()
