"""Inspected source links and their editorial limits. 已核来源链接及其整理限度。"""

import re

import pytest

from astrology.knowledge import (
  OutputEligibility,
  PrerequisiteStatus,
  SourceVerification,
  load_catalog,
)
from tools.catalog_docs import check_catalog_data, render_catalog


@pytest.mark.parametrize(
  ("entry_id", "source_id", "status"),
  [
    (
      "entry.node_definitions",
      "source.meeus.astronomical-algorithms-1998",
      PrerequisiteStatus.UNRESOLVED,
    ),
    (
      "entry.house_requests",
      "source.astrodienst.swisseph-house-definitions",
      PrerequisiteStatus.COMPLETE,
    ),
    (
      "entry.aspect_requests",
      "source.lilly.christian-astrology-1647",
      PrerequisiteStatus.COMPLETE,
    ),
    (
      "entry.aspect_requests",
      "source.astrodienst.hellenistic-style-faq",
      PrerequisiteStatus.COMPLETE,
    ),
  ],
)
def test_external_definitions_do_not_promote_chart_conclusions(
  entry_id: str, source_id: str, status: PrerequisiteStatus
) -> None:
  catalog = load_catalog()
  entry = catalog.entry(entry_id)
  assert source_id in {citation.source_id for citation in entry.citations}
  assert catalog.source(source_id).verification is SourceVerification.VERIFIED
  assert entry.prerequisite_status is status
  assert entry.output_eligibility is OutputEligibility.REFERENCE_ONLY
  assert entry.chart_applicability == "not_assessed"


@pytest.mark.parametrize(
  "source_id",
  [
    "source.meeus.astronomical-algorithms-1998",
    "source.astrodienst.swisseph-house-definitions",
    "source.astrodienst.hellenistic-style-faq",
    "source.lilly.christian-astrology-1647",
    "source.astrodienst.elements-signs",
    "source.rudhyar.lunation-birthday",
  ],
)
def test_retained_sources_have_bilingual_receipts(source_id: str) -> None:
  source = load_catalog().source(source_id)
  for language in ("en", "zh-CN"):
    lineage = source.lineage.text(language)
    assert lineage is not None
    assert re.search(r"SHA-256(?: 为)? [a-f0-9]{64}", lineage)
    assert source.scope.text(language)


def test_scan_locators_and_unavailable_originals_remain_distinct() -> None:
  catalog = load_catalog()
  lilly = catalog.source("source.lilly.christian-astrology-1647")
  assert "137-139 for pp.103-105" in lilly.lineage.en.replace("\N{EN DASH}", "-")
  assert "p.104 table spells Ptolomy" in lilly.scope.en
  citations = catalog.entry("entry.essential_dignities").citations
  assert "p.105 / Wellcome leaf139" in citations[-2].locator
  ashmand = catalog.source("source.ptolemy.ashmand1822")
  for language in ("en", "zh-CN"):
    lineage = ashmand.lineage.text(language)
    assert lineage is not None
    assert "HTTP429" in lineage and "1896" in lineage
    assert "8ab3073b2200ba85b3dd812acc0b2edd2d2757f196cc641de42e9a46293189cb" in lineage


def test_source_addenda_keep_attribution_and_locators_bounded() -> None:
  catalog = load_catalog()
  meeus = catalog.source("source.meeus.astronomical-algorithms-1998")
  for language in ("en", "zh-CN"):
    lineage = meeus.lineage.text(language)
    assert lineage is not None
    assert "98 99 00 01 02 03 04 05 06" in lineage
    assert "9 8 7 6 5 4 3 2 1" in lineage
  faq = catalog.source("source.astrodienst.hellenistic-style-faq")
  assert "orb and node-exclusion settings" in faq.scope.en
  assert "Chris Brennan" in faq.scope.en and "Chris Brennan" in (faq.scope.zh or "")
  lilly = catalog.source("source.lilly.christian-astrology-1647")
  assert "handwritten 104" in lilly.lineage.en
  assert "PDF page146" in lilly.lineage.en
  assert "Sun-in-Aries/Mars-in-Leo" in lilly.scope.en
  assert "domicile-based mutual reception" in lilly.scope.en
  assert "基于入庙守护的互容标签" in (lilly.scope.zh or "")
  assert "太阳在白羊座、火星在狮子座" in (lilly.scope.zh or "")
  assert "reception by Houses" in lilly.scope.en
  assert "reception by Houses" in (lilly.scope.zh or "")
  assert "手写" in (lilly.lineage.zh or "")
  assert "PDF第146页" in "".join((lilly.lineage.zh or "").split())
  tradition = catalog.variant("rule.lilly1647.essential_dignities").tradition
  assert "printed p.104" not in tradition.en
  assert "印刷第104页" not in "".join((tradition.zh or "").split())
  citations = catalog.entry("entry.dispositor_chains").citations
  assert len(citations) == 3
  assert citations[0].source_id == citations[1].source_id == lilly.identifier
  assert "p.104" in citations[0].locator and "leaf138" in citations[0].locator
  assert "p.112" in citations[1].locator and "leaf146" in citations[1].locator
  assert "label only" in citations[1].locator
  assert citations[2].source_id == "source.astrology"
  assert "dignities.py: Dispositors, chart_dispositors" in citations[2].locator


def test_verified_definitions_render_in_both_catalogs() -> None:
  catalog = load_catalog()
  check_catalog_data(catalog)
  for language in ("en", "zh-CN"):
    rendered = render_catalog(catalog, language, "test")
    for identifier in (
      "source.meeus.astronomical-algorithms-1998",
      "source.astrodienst.swisseph-house-definitions",
      "source.astrodienst.hellenistic-style-faq",
    ):
      assert identifier in rendered
