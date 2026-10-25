"""Knowledge identity, isolation and editorial boundaries. 知识身份、隔离与整理边界。"""

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from astrology import OrbCombination, aspect_angle
from astrology.config import Body, HouseSystem, LunarNode, MajorAspect, NodeDefinition
from astrology.knowledge import (
  Catalog,
  Citation,
  Concept,
  ConceptKind,
  Entry,
  LocalizedText,
  OutputEligibility,
  PrerequisiteStatus,
  RuleVariant,
  Source,
  SourceVerification,
  TranslationStatus,
  load_catalog,
)


class LanguageString(str):
  pass


class LanguageEnum(StrEnum):
  EN = "en"


@pytest.fixture
def catalog() -> Catalog:
  return load_catalog()


@pytest.mark.parametrize(
  "english,chinese,identifier",
  [
    ("Sol", "日轮", "body.sun"),
    ("Luna", "太阴", "body.moon"),
    ("Aries", "牡羊座", "sign.aries"),
    ("mean north node", "平均北交点", "node.mean_ascending"),
    ("whole sign houses", "整宫", "house.whole_sign"),
    ("Conjunction", "合相位", "aspect.conjunction"),
  ],
)
def test_bilingual_aliases(catalog: Catalog, english: str, chinese: str, identifier: str) -> None:
  assert catalog.lookup(english, language="en") == catalog.lookup(chinese, language="zh-CN")
  assert catalog.lookup(english)[0] is catalog.lookup(chinese)[0]
  assert catalog.lookup(chinese)[0].identifier == identifier


def test_query_contracts(catalog: Catalog) -> None:
  assert catalog.lookup("  sOL ")[0].identifier == "body.sun"
  assert catalog.lookup("不存在") == ()
  assert catalog.lookup("太阳", language="en") == ()
  assert catalog.list_concepts() == tuple(catalog.concepts)
  assert len(catalog.list_concepts(kind=ConceptKind.BODY)) == len(Body)
  assert len(catalog.list_concepts(kind=ConceptKind.SIGN)) == 12
  sign_rules = catalog.list_variants(concept_id="sign.taurus")
  assert [rule.identifier for rule in sign_rules] == ["rule.project.tropical_sign_sectors"]
  assert catalog.list_variants(concept_id="body.sun") == ()
  assert catalog.concept("body.sun").configuration is Body.SUN
  assert len(catalog.list_variants()) == len(catalog.variants)
  assert catalog.filter_entries() == tuple(catalog.entries)
  assert len(catalog.filter_entries(concept_id="sign.aries")) == 2
  assert len(catalog.filter_entries(source_id="source.ptolemy.ashmand1822")) == 2
  assert catalog.filter_entries(output_eligibility=OutputEligibility.ELIGIBLE) == ()
  assert catalog.filter_entries(output_eligibility=OutputEligibility.REFERENCE_ONLY) == tuple(
    catalog.entries
  )
  assert {
    entry.identifier
    for entry in catalog.filter_entries(prerequisite_status=PrerequisiteStatus.COMPLETE)
  } == {
    "entry.aspect_evaluation",
    "entry.aspect_requests",
    "entry.cross_aspect_evaluation",
    "entry.body_requests",
    "entry.house_requests",
    "entry.node_directions",
    "entry.sign_vocabulary",
  }
  assert all(
    entry.prerequisite_status is PrerequisiteStatus.UNRESOLVED
    for entry in catalog.filter_entries(prerequisite_status=PrerequisiteStatus.UNRESOLVED)
  )
  assert catalog.filter_entries(concept_id="body.sun", source_id="source.ptolemy.ashmand1822") == ()
  assert catalog.filter_sources() == tuple(catalog.sources)
  assert catalog.filter_sources(verification=SourceVerification.UNVERIFIED) == ()
  assert catalog.variant("rule.house.whole_sign") in catalog.variants
  with pytest.raises(FrozenInstanceError):
    catalog.version = "mutated"  # type: ignore[misc]


def test_complete_owning_configuration_coverage(catalog: Catalog) -> None:
  expected = {
    member
    for enum in (Body, HouseSystem, LunarNode, MajorAspect, NodeDefinition)
    for member in enum
  }
  actual = [
    concept.configuration for concept in catalog.concepts if concept.configuration is not None
  ]
  assert set(actual) == expected
  assert len(actual) == len(expected)
  assert {
    variant.configuration for variant in catalog.variants if variant.configuration is not None
  } == {member for enum in (HouseSystem, MajorAspect, NodeDefinition) for member in enum}
  assert all(c.configuration is None for c in catalog.list_concepts(kind=ConceptKind.SIGN))
  assert catalog.variant("rule.ptolemy_ashmand.equinoctial_signs").configuration is None


def test_source_layers_and_four_independent_states(catalog: Catalog) -> None:
  entry = catalog.entry("entry.equinoctial_example")
  citation, source = catalog.citations(entry.identifier)[0]
  assert source.verification is SourceVerification.VERIFIED
  assert entry.prerequisite_status is PrerequisiteStatus.UNRESOLVED
  assert entry.output_eligibility is OutputEligibility.REFERENCE_ONLY
  assert entry.chart_applicability == "not_assessed"
  assert citation.excerpt is not None
  assert citation.excerpt.en.startswith("There are also two equinoctial signs:")
  assert citation.excerpt.en.endswith("makes the day and night equal.")
  assert citation.excerpt.translation_credit is not None
  assert "project Chinese translation" in citation.excerpt.translation_credit
  assert entry.statement.en != citation.excerpt.en
  assert "34\u201335" in citation.locator
  assert "1822" in source.edition and "life-plus-70" in source.rights.en
  assert "not a guarantee" in catalog.variant(entry.rule_ids[0]).limits.en


def test_partial_computation_cannot_promote_retrieval(catalog: Catalog) -> None:
  # Synthetic evidence, not a traditional claim or a bibliography.
  partial_evidence = {"condition_a": True, "condition_b": None}
  entry = catalog.entry("entry.equinoctial_example")
  assert partial_evidence["condition_a"] is True
  assert partial_evidence["condition_b"] is None
  assert entry.chart_applicability == "not_assessed"
  assert (
    replace(entry, prerequisite_status=PrerequisiteStatus.COMPLETE).chart_applicability
    == "not_assessed"
  )
  assert (
    replace(entry, output_eligibility=OutputEligibility.ELIGIBLE).chart_applicability
    == "not_assessed"
  )
  assert catalog.filter_entries(concept_id="sign.aries")[-1] is entry


def test_container_ownership(catalog: Catalog) -> None:
  aliases = ["solar alias"]
  related = ["body.moon"]
  concept = replace(catalog.concepts[0], en_aliases=aliases, related=related)
  concepts = [concept, *catalog.concepts[1:]]
  variants = list(catalog.variants)
  sources = list(catalog.sources)
  entries = list(catalog.entries)
  copy = Catalog("snapshot", concepts, variants, sources, entries)
  aliases.clear()
  related.clear()
  concepts.clear()
  variants.clear()
  sources.clear()
  entries.clear()
  assert copy.lookup("solar alias")[0] is concept
  assert concept.related == ("body.moon",)
  assert copy.sources == catalog.sources and copy.entries == catalog.entries
  refs = ["body.sun"]
  citations = list(catalog.entries[0].citations)
  prerequisites = [LocalizedText("Condition not evaluated")]
  entry = replace(
    catalog.entries[0], concept_ids=refs, citations=citations, prerequisites=prerequisites
  )
  rule = replace(catalog.variants[0], concept_ids=refs)
  refs.clear()
  citations.clear()
  prerequisites.clear()
  assert entry.concept_ids == rule.concept_ids == ("body.sun",)
  assert len(entry.citations) == len(catalog.entries[0].citations)
  assert len(entry.prerequisites) == 1


@pytest.mark.parametrize("group", ["concepts", "variants", "sources", "entries"])
def test_duplicate_ids(catalog: Catalog, group: str) -> None:
  changes: dict[str, Any] = {group: [*getattr(catalog, group), getattr(catalog, group)[0]]}
  with pytest.raises(ValueError, match="Duplicate"):
    replace(catalog, **changes)


@pytest.mark.parametrize("language", ["en", "zh"])
@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_aliases_and_equal_display_names(
  catalog: Catalog, language: str, reverse: bool
) -> None:
  first = catalog.concepts[0]
  second = replace(first, identifier="body.other", configuration=None)
  field = f"{language}_aliases"
  first_alias: dict[str, Any] = {field: ["shared"]}
  second_alias: dict[str, Any] = {field: ["SHARED"]}
  values = [replace(first, **first_alias), replace(second, **second_alias)]
  if reverse:
    values.reverse()
  with pytest.raises(ValueError, match="Conflicting"):
    Catalog("test", values, (), (), ())
  first = replace(first, en_aliases=(), zh_aliases=())
  second = replace(second, en_aliases=(), zh_aliases=())
  same_name = Catalog("test", (first, second), (), (), ())
  assert {value.identifier for value in same_name.lookup("太阳")} == {
    first.identifier,
    second.identifier,
  }
  with pytest.raises(ValueError, match="Conflicting"):
    Catalog("test", (first, replace(second, en_aliases=(first.name.en,))), (), (), ())


def test_unicode_normalization() -> None:
  first = Concept("test.one", ConceptKind.SIGN, LocalizedText("é"), LocalizedText("test"))
  assert Catalog("test", (first,), (), (), ()).lookup("e\u0301") == (first,)


@pytest.mark.parametrize(
  "field,value",
  [("related", ("absent.id",)), ("configuration", HouseSystem.EQUAL)],
)
def test_invalid_concept_links(catalog: Catalog, field: str, value: Any) -> None:
  with pytest.raises((ValueError, TypeError)):
    replace(
      catalog, concepts=(replace(catalog.concepts[0], **{field: value}), *catalog.concepts[1:])
    )


@pytest.mark.parametrize("field", ["concept_ids", "rule_ids", "citations"])
def test_dangling_entry_links(catalog: Catalog, field: str) -> None:
  value: Any = (Citation("absent.id", "locator"),) if field == "citations" else ("absent.id",)
  with pytest.raises(ValueError, match="Dangling"):
    replace(catalog, entries=(replace(catalog.entries[0], **{field: value}),))


def test_invalid_variant_links(catalog: Catalog) -> None:
  with pytest.raises(ValueError, match="Dangling"):
    replace(catalog, variants=(replace(catalog.variants[0], concept_ids=("absent.id",)),))
  with pytest.raises(ValueError, match="no linked concept"):
    replace(catalog, variants=(replace(catalog.variants[0], configuration=Body.MOON),))


@pytest.mark.parametrize(
  "kwargs,status,text",
  [
    ({}, TranslationStatus.MISSING, None),
    (
      {"zh": "译文", "zh_revision": 1, "translation_credit": "translator"},
      TranslationStatus.CURRENT,
      "译文",
    ),
    (
      {"revision": 2, "zh": "旧译", "zh_revision": 1, "translation_credit": "translator"},
      TranslationStatus.STALE,
      "旧译",
    ),
  ],
)
def test_translation_status(
  kwargs: dict[str, Any], status: TranslationStatus, text: str | None
) -> None:
  value = LocalizedText("original", **kwargs)
  assert value.status("zh-CN") is status
  assert value.text("zh-CN") == text
  assert value.status("en") is TranslationStatus.CURRENT
  assert value.text("en") == "original"


@pytest.mark.parametrize(
  "kwargs",
  [
    {"en": ""},
    {"en": 1},
    {"revision": True},
    {"revision": 0},
    {"zh": "text"},
    {"zh_revision": 1},
    {"translation_credit": "translator"},
    {"zh": "text", "zh_revision": 2, "translation_credit": "translator"},
    {"zh": "text", "zh_revision": 0, "translation_credit": "translator"},
    {"zh": "text", "zh_revision": True, "translation_credit": "translator"},
    {"zh": "text", "zh_revision": 1, "translation_credit": ""},
    {"zh": "", "zh_revision": 1, "translation_credit": "translator"},
  ],
)
def test_invalid_localized_text(kwargs: dict[str, Any]) -> None:
  with pytest.raises((ValueError, TypeError)):
    LocalizedText(**dict({"en": "original"}, **kwargs))


@pytest.mark.parametrize("identifier", ["", "中文", "Upper", "bad id", 3])
def test_invalid_identifiers(catalog: Catalog, identifier: Any) -> None:
  for record in (catalog.concepts[0], catalog.variants[0], catalog.sources[0], catalog.entries[0]):
    with pytest.raises((TypeError, ValueError)):
      replace(record, identifier=identifier)


@pytest.mark.parametrize("value", ["body", None, 1])
def test_wrong_record_types(catalog: Catalog, value: Any) -> None:
  for record, field in (
    (catalog.concepts[0], "kind"),
    (catalog.concepts[0], "name"),
    (catalog.variants[0], "definition"),
    (catalog.sources[0], "rights"),
    (catalog.sources[0], "verification"),
    (catalog.entries[0], "statement"),
    (catalog.entries[0], "prerequisite_status"),
    (catalog.entries[0], "output_eligibility"),
  ):
    with pytest.raises((TypeError, ValueError)):
      replace(record, **{field: value})
  with pytest.raises(TypeError):
    replace(catalog, concepts=(value,))


@pytest.mark.parametrize("value", ["string", {"id": "value"}, [1], None])
def test_wrong_sequences(catalog: Catalog, value: Any) -> None:
  for record, field in (
    (catalog.concepts[0], "related"),
    (catalog.concepts[0], "en_aliases"),
    (catalog.variants[0], "concept_ids"),
    (catalog.entries[0], "citations"),
    (catalog.entries[0], "prerequisites"),
  ):
    with pytest.raises((TypeError, ValueError)):
      replace(record, **{field: value})


def test_invalid_and_unknown_queries(catalog: Catalog) -> None:
  for getter in (
    catalog.concept,
    catalog.variant,
    catalog.source,
    catalog.entry,
    catalog.citations,
  ):
    with pytest.raises(KeyError):
      getter("absent.id")
    with pytest.raises(ValueError):
      getter("Body.Sun")
    with pytest.raises(TypeError):
      getter(3)  # type: ignore[arg-type]
  with pytest.raises(KeyError):
    catalog.list_variants(concept_id="absent.id")
  with pytest.raises(KeyError):
    catalog.filter_entries(source_id="absent.id")
  with pytest.raises(KeyError):
    catalog.filter_entries(concept_id="absent.id")
  for value in ("unknown", "", "en_US", 1):
    with pytest.raises(ValueError):
      catalog.lookup("Sun", language=value)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
      LocalizedText("text").text(value)  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    catalog.list_concepts(kind="body")  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    catalog.filter_sources(verification="verified")  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    catalog.filter_entries(prerequisite_status="complete")  # type: ignore[arg-type]
  with pytest.raises(TypeError):
    catalog.filter_entries(output_eligibility="eligible")  # type: ignore[arg-type]


def test_loading_is_explicit_uncached_and_import_is_pure() -> None:
  source = """
import importlib.resources
import sys
original = importlib.resources.files
calls = []
def observed(*args, **kwargs):
  calls.append(args)
  return original(*args, **kwargs)
importlib.resources.files = observed
from astrology.knowledge import load_catalog
if calls:
  raise RuntimeError('import read a corpus resource')
first = load_catalog()
second = load_catalog()
if first != second or first is second or len(calls) != 2:
  raise RuntimeError('unexpected catalog cache or nondeterminism')
first.lookup('日轮')
first.citations('entry.equinoctial_example')
if any(name.startswith(('celestial', 'tzdata', 'zoneinfo', 'ctypes')) for name in sys.modules):
  raise RuntimeError('knowledge initialized time or native machinery')
"""
  for mode in ((), ("-O",)):
    result = subprocess.run([sys.executable, *mode, "-c", source], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_resource_is_real_json() -> None:
  data = json.loads(
    files("astrology.knowledge").joinpath("catalog.json").read_text(encoding="utf-8")
  )
  assert data["version"] == load_catalog().version
  assert len(data["entries"]) == len(load_catalog().entries)


def test_record_classes_are_public() -> None:
  assert all(cls.__doc__ for cls in (Citation, Concept, RuleVariant, Source, Entry, Catalog))


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("collision", ["alias", "name", "translated_name"])
def test_cross_language_alias_conflicts(catalog: Catalog, reverse: bool, collision: str) -> None:
  first, second = catalog.concepts[:2]
  if collision == "alias":
    first = replace(first, en_aliases=("shared",))
    second = replace(second, zh_aliases=("SHARED",))
  elif collision == "name":
    second = replace(second, zh_aliases=(first.name.en,))
  else:
    second = replace(second, en_aliases=(first.name.zh or "",))
  values = (second, first) if reverse else (first, second)
  with pytest.raises(ValueError, match="Conflicting alias"):
    Catalog("test", values, (), (), ())


@pytest.mark.parametrize("name,error", [("", ValueError), ("  ", ValueError), (3, TypeError)])
def test_invalid_lookup_names(catalog: Catalog, name: Any, error: type[Exception]) -> None:
  with pytest.raises(error):
    catalog.lookup(name)


def test_required_sequences_and_record_types(catalog: Catalog) -> None:
  with pytest.raises(ValueError, match="identify its concepts"):
    replace(catalog.variants[0], concept_ids=())
  for field in ("concept_ids", "citations"):
    changes: dict[str, Any] = {field: ()}
    with pytest.raises(ValueError, match="identify concepts and cite"):
      replace(catalog.entries[0], **changes)
  with pytest.raises(TypeError, match="excerpt"):
    Citation("test.source", "locator", 1)  # type: ignore[arg-type]
  for record in (catalog.concepts[0], catalog.variants[0]):
    with pytest.raises(TypeError, match="owning config enum"):
      replace(record, configuration=5)  # type: ignore[arg-type]
  with pytest.raises(TypeError, match="iterator"):
    replace(catalog, concepts=iter(catalog.concepts))  # type: ignore[arg-type]


@pytest.mark.parametrize(
  "reference,error",
  [
    ({"enum": "Absent", "member": "SUN"}, ValueError),
    ({"enum": "Body", "member": "SIRIUS"}, KeyError),
    ({"enum": "Body"}, KeyError),
  ],
)
def test_invalid_packaged_config_reference(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reference: dict[str, str], error: type[Exception]
) -> None:
  from astrology.knowledge import catalog as module

  data = json.loads(
    files("astrology.knowledge").joinpath("catalog.json").read_text(encoding="utf-8")
  )
  data["concepts"][0]["configuration"] = reference
  (tmp_path / "catalog.json").write_text(json.dumps(data), encoding="utf-8")
  monkeypatch.setattr(module, "files", lambda package: tmp_path)
  with pytest.raises(error):
    load_catalog()


@pytest.mark.parametrize("aspect", list(MajorAspect), ids=lambda aspect: aspect.value)
def test_aspect_descriptions_state_the_angle_the_code_uses(
  catalog: Catalog, aspect: MajorAspect
) -> None:
  concept = catalog.concept(f"aspect.{aspect.value}")
  angle = aspect_angle(aspect)
  assert f"Exact angle {angle:g} degrees" in concept.description.en
  assert f"精确角度 {angle:g} 度" in (concept.description.zh or "")


def test_every_orb_combination_has_one_named_rule_variant(catalog: Catalog) -> None:
  named = {
    variant.identifier.removeprefix("rule.project.orb_")
    for variant in catalog.variants
    if variant.identifier.startswith("rule.project.orb_")
  }
  assert named == {combination.value for combination in OrbCombination}
  entry = catalog.entry("entry.aspect_evaluation")
  assert {f"rule.project.orb_{combination.value}" for combination in OrbCombination} <= set(
    entry.rule_ids
  )
  assert set(entry.concept_ids) == {f"aspect.{aspect.value}" for aspect in MajorAspect}


@pytest.mark.parametrize(
  "identifier",
  [
    "rule.body.sun",
    "rule.body.moon",
    "rule.body.mercury",
    "rule.body.venus",
    "rule.body.mars",
    "rule.body.jupiter",
    "rule.body.saturn",
    "rule.body.uranus",
    "rule.body.neptune",
    "rule.body.pluto",
    "rule.node.mean_ascending",
    "rule.node.mean_descending",
    "rule.node.meeus_five_term_true_ascending",
    "rule.node.meeus_five_term_true_descending",
  ],
)
def test_retired_identity_variants_keep_their_concepts(catalog: Catalog, identifier: str) -> None:
  concept_id = identifier.removeprefix("rule.")
  with pytest.raises(KeyError):
    catalog.variant(identifier)
  concept = catalog.concept(concept_id)
  assert concept.configuration is not None
  assert catalog.lookup(concept.name.en) == (concept,)
  assert catalog.list_variants(concept_id=concept_id) == ()
  assert catalog.filter_entries(concept_id=concept_id)[0].rule_ids == ()
  entry = catalog.filter_entries(concept_id=concept_id)[0]
  with pytest.raises(ValueError, match="Dangling"):
    replace(catalog, entries=(replace(entry, rule_ids=(identifier,)),))


def test_retained_rule_ids_and_order(catalog: Catalog) -> None:
  expected = (
    ("rule.house.whole_sign", HouseSystem.WHOLE_SIGN),
    ("rule.house.equal", HouseSystem.EQUAL),
    ("rule.house.placidus", HouseSystem.PLACIDUS),
    ("rule.node_definition.mean", NodeDefinition.MEAN),
    ("rule.node_definition.meeus_five_term_true", NodeDefinition.MEEUS_FIVE_TERM_TRUE),
    ("rule.aspect.conjunction", MajorAspect.CONJUNCTION),
    ("rule.aspect.sextile", MajorAspect.SEXTILE),
    ("rule.aspect.square", MajorAspect.SQUARE),
    ("rule.aspect.trine", MajorAspect.TRINE),
    ("rule.aspect.opposition", MajorAspect.OPPOSITION),
  )
  assert [(v.identifier, v.configuration) for v in catalog.variants[:10]] == list(expected)
  assert [v.identifier for v in catalog.variants[10:]] == [
    "rule.project.tropical_sign_sectors",
    "rule.project.cusp_ownership",
    "rule.ptolemy_ashmand.equinoctial_signs",
    "rule.project.aspect_deviation",
    "rule.project.aspect_motion",
    "rule.project.aspect_participation",
    "rule.project.orb_either_within_own_orb",
    "rule.project.orb_both_within_own_orb",
    "rule.project.orb_mean_of_orbs",
    "rule.project.cross_aspect_evaluation",
  ]
  for identifier, configuration in expected:
    variant = catalog.variant(identifier)
    concept = catalog.concept(variant.concept_ids[0])
    assert concept.configuration is configuration
    assert variant.definition != concept.description
    assert variant.configuration is configuration
    if isinstance(configuration, (HouseSystem, NodeDefinition)):
      assert "orb" not in variant.limits.en.lower()


def test_cross_policy_is_independently_retrievable_without_chart_applicability(
  catalog: Catalog,
) -> None:
  entry = catalog.entry("entry.cross_aspect_evaluation")
  assert entry.rule_ids[0] == "rule.project.cross_aspect_evaluation"
  assert "rule.project.aspect_motion" not in entry.rule_ids
  assert "rule.project.aspect_participation" not in entry.rule_ids
  assert set(entry.concept_ids) == {f"aspect.{aspect.value}" for aspect in MajorAspect}
  assert entry.prerequisite_status is PrerequisiteStatus.COMPLETE
  assert entry.output_eligibility is OutputEligibility.REFERENCE_ONLY
  assert entry.chart_applicability == "not_assessed"
  citation, source = catalog.citations(entry.identifier)[0]
  assert source.identifier == "source.astrology.cross_aspects.0d7122a"
  assert source.url.endswith("/0d7122a7f7ef86ecc5798c9ea12668c68bb4a516")
  assert "src/astrology/cross_aspects.py" in citation.locator
  assert source.verification is SourceVerification.VERIFIED
  assert citation.excerpt is None
  assert "single-chart" in catalog.variant("rule.project.aspect_participation").definition.en
  assert "单盘" in (catalog.entry("entry.aspect_evaluation").statement.zh or "")
  assert "one shared instant" in catalog.variant("rule.project.aspect_motion").definition.en


def test_fixed_implementation_source_and_node_test_locator(catalog: Catalog) -> None:
  source = catalog.source("source.astrology.chart.fc845fa")
  commit = "fc845fa1aa786f7e1eda7b4d901e70e9a505add5"
  assert source.url == f"https://github.com/0xf3cd/astrology/tree/{commit}"
  assert commit in source.edition
  citation = catalog.entry("entry.node_definitions").citations[1]
  assert citation.source_id == source.identifier
  assert "tests/test_reference.py" in citation.locator
  for symbol in (
    "_meeus_nodes",
    "_nodes_agree",
    "test_the_lunar_nodes_agree_with_the_meeus_definition",
  ):
    assert symbol in citation.locator
  assert "does not verify printed Meeus formulas" in source.scope.en
  assert (
    catalog.entry("entry.node_definitions").prerequisite_status is PrerequisiteStatus.UNRESOLVED
  )


@pytest.mark.parametrize(
  "value", [None, True, 1, [], "zh", "EN", "en-US", LanguageString("en"), LanguageEnum.EN]
)
def test_language_boundaries_preserve_value_errors(catalog: Catalog, value: Any) -> None:
  for method in (LocalizedText("text").text, LocalizedText("text").status):
    with pytest.raises(ValueError):
      method(value)
  if value is not None:
    with pytest.raises(ValueError):
      catalog.lookup("Sun", language=value)
  else:
    assert catalog.lookup("Sun", language=value) == catalog.lookup("Sun")


@pytest.mark.parametrize("defect", ["missing", "kind", "extra"])
def test_packaged_sign_relationship_is_checked(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
  from astrology.knowledge import catalog as module

  data = json.loads(
    files("astrology.knowledge").joinpath("catalog.json").read_text(encoding="utf-8")
  )
  if defect == "missing":
    # A consistent rename keeps cross-record links valid but breaks the Sign identity.
    next(row for row in data["concepts"] if row["identifier"] == "sign.leo")["identifier"] = (
      "sign.lion"
    )
    for group in ("concepts", "variants", "entries"):
      for row in data[group]:
        for field in ("concept_ids", "related"):
          if field in row:
            row[field] = ["sign.lion" if key == "sign.leo" else key for key in row[field]]
  elif defect == "kind":
    next(row for row in data["concepts"] if row["identifier"] == "sign.leo")["kind"] = "body"
  else:
    data["concepts"].append(
      {
        "identifier": "sign.extra",
        "kind": "sign",
        "name": {"en": "Extra", "zh": "额外"},
        "description": {"en": "Synthetic", "zh": "合成"},
      }
    )
  (tmp_path / "catalog.json").write_text(json.dumps(data), encoding="utf-8")
  monkeypatch.setattr(module, "files", lambda package: tmp_path)
  with pytest.raises(KeyError if defect == "missing" else ValueError):
    load_catalog()
