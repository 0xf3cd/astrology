# Knowledge organization and bilingual documentation

[简体中文](../zh-CN/knowledge.md) · [Project](../../README.md) · [Architecture](architecture.md)

The package provides a chart-independent knowledge catalog. List
concepts and variants, find bilingual names/aliases, filter entries and sources,
and inspect citations without birth data or native astronomy. Chart calculation
is available through the [chart guide](chart.md) and is never needed to browse
the catalog.
See the generated [catalog](catalog.md) and [API](reference.md).

## Browse without a chart

```{doctest}
>>> from astrology.knowledge import ConceptKind, SourceVerification, load_catalog
>>> catalog = load_catalog()
>>> catalog.lookup("Sol")[0].identifier
'body.sun'
>>> catalog.lookup("日轮")[0] is catalog.lookup("Sun")[0]
True
>>> len(catalog.list_concepts(kind=ConceptKind.SIGN))
12
>>> catalog.concept("body.sun").configuration.name
'SUN'
>>> catalog.list_variants(concept_id="body.sun")
()
>>> catalog.filter_entries(concept_id="body.sun")[0].identifier
'entry.body_requests'
>>> len(catalog.filter_sources(verification=SourceVerification.VERIFIED))
5
>>> bool(catalog.version)
True
```

In the built-in catalog, body and node-direction concepts have no separate rule
variants, so the empty tuple for `body.sun` is expected. Their identity information
remains on the concepts and entries; see [rule-ID changes](#pre-release-rule-id-changes).

`entry.cross_aspect_evaluation` and `rule.project.cross_aspect_evaluation` describe
the [static cross-chart policy](cross_aspects.md), with its own fixed implementation
source. Even with complete prerequisites, this entry remains reference-only;
retrieving it does not assess a chart:

```{doctest}
>>> comparison = catalog.entry("entry.cross_aspect_evaluation")
>>> comparison.prerequisite_status.value, comparison.output_eligibility.value, comparison.chart_applicability
('complete', 'reference_only', 'not_assessed')
```

Each `load_catalog()` explicitly reads the packaged JSON, without a cache or
network. Constructors copy sequences into tuples. Invalid record types, duplicate
IDs, dangling links and conflicting aliases raise `TypeError` or `ValueError`,
including under `python -O`.

`lookup()` normalizes NFC, trims and case-folds, then matches exact names/aliases.
It returns an immutable tuple: `()` for no match, several distinct identities for
ambiguous display names. Select `language="en"` or `language="zh-CN"` to restrict
lookup; omission searches both. Unknown well-formed IDs in getters/filters raise
`KeyError`; malformed strings raise `ValueError`, non-string IDs `TypeError`.
Entry filters combine all selected criteria; they never evaluate prerequisites.

(knowledge-source-definitions-en)=
## Follow a source to a definition

The corpus contains project configuration contracts, the project conventions for
sign sectors and house placement, and one single-source historical classification
with four groups. It names every admitted configuration identity, twelve sign
concepts and four historical group concepts, and links the
executable rules in the chart implementation. Each project-defined aspect rule has
a name, a written definition and a link to its implementation. The corpus provides
no default orbs, dignity or interpretation rules.
Concepts reference actual configuration enum members. Separate variants describe
house-system bindings, named node definitions and aspect-angle rules, with limits
specific to each rule. Reference pages add an exact-angle line from the executable
definition; the angles in concept descriptions are checked against that definition.
Body and node-direction identities do not
need a second rule record.

```{doctest}
>>> entry = catalog.entry("entry.equinoctial_example")
>>> citation, source = catalog.citations(entry.identifier)[0]
>>> source.edition
'Davis and Dickson, London, 1822'
>>> citation.excerpt.en.startswith("There are also two equinoctial signs:")
True
>>> citation.excerpt.zh is not None
True
>>> source.verification.value, entry.prerequisite_status.value
('verified', 'unresolved')
>>> entry.output_eligibility.value, entry.chart_applicability
('reference_only', 'not_assessed')
>>> catalog.variant(entry.rule_ids[0]).configuration is None
True
```

The citation locates Book I, chapter XIV, printed pp. 34–35 (PDF pages 72–73)
of Ashmand's English translation of the paraphrase attributed to Proclus. The
{ref}`catalog example <catalog-en-entry-equinoctial-example>` preserves the complete
English sentence and a separately credited project Chinese translation. The
historical equal-day/night rationale is retained, not endorsed as an observed
daylight guarantee. Statements, definitions and limitations are project
explanations, not additional quotations.

The source records the edition, scan hash, transcription normalization and bounded
reproduction status. Only bounded definition excerpts are included, not scan images,
watermarks or modern website prose. Mirrors/catalogs corroborate the edition,
not independent rule authorship. Config citations identify package version and
symbols at a fixed commit; they do not verify an author's book formula merely
because a project definition bears that author's name.

Implementation source records stay pinned to the inspected commits instead of
following the package version. The chart source record locates the node-comparison
test in `tests/test_reference.py` at that same commit. The test calculates reference
node longitudes from the formulas recorded there and compares them with upstream
results. This does not verify Meeus's printed text, establish an error bound or show
equivalence to an osculating node.

The following is synthetic partial evidence, not a traditional claim or matching
API. The catalog does not consume it or promote the entry to applicable:

```{doctest}
>>> partial_evidence = {"condition_a": True, "condition_b": None}
>>> partial_evidence["condition_a"], partial_evidence["condition_b"]
(True, None)
>>> catalog.entry(entry.identifier).chart_applicability
'not_assessed'
```

All built-in entries are reference-only. This package has no matcher or
chart-evidence store.

## Ashmand 1822 sign groups

These groups come from Ashmand's 1822 *Ptolemy's Tetrabiblos, or Quadripartite*.
This lookup is in current source, not the published v0.1.0. Supply a `Sign`,
without a chart, position, birth record or native astronomy:

```{doctest}
>>> from astrology import AshmandSignGroup, Sign, ashmand_sign_group
>>> from astrology.knowledge import load_catalog
>>> catalog = load_catalog()
>>> ashmand_sign_group(Sign.ARIES) is AshmandSignGroup.EQUINOCTIAL
True
>>> group = ashmand_sign_group(Sign.CANCER)
>>> group.value
'tropical'
>>> catalog.concept(f"sign_group.ashmand1822.{group.value}").name.text("en")
'Tropical signs'
>>> historical = catalog.entry("entry.ashmand_sign_groups")
>>> historical.prerequisite_status.value, historical.output_eligibility.value, historical.chart_applicability
('complete', 'reference_only', 'not_assessed')
```

Raw strings and unrelated enums raise `TypeError`; convert user input to `Sign`
explicitly. The result is a group label, not a score or interpretation. Its
complete prerequisites describe this lookup only; the older
`entry.equinoctial_example` keeps its unresolved chart-level prerequisites.

The four labels are **tropical**, **equinoctial**, **fixed** and **bicorporeal**.
Tropical here means the two solstitial signs, not all twelve signs of the tropical
zodiac. The source directly names the tropical and equinoctial pairs. In zodiac
order, fixed signs immediately follow those signs, and bicorporeal signs
immediately follow fixed signs. The
{ref}`twelve-sign table <catalog-en-rule-ptolemy-ashmand-sign-groups>` is
project-derived, not a verbatim source list.

`source.ptolemy.ashmand1822` locates the definitions in Book I, chapter XIV,
printed pp. 34–35 (PDF pp. 72–73). The new entry includes the first complete
tropical-definition sentence and bounded fixed/bicorporeal fragments; each
locator states where its excerpt ends. The full equinoctial sentence remains in
the earlier example, rather than being copied into another entry. English
excerpts, credited project Chinese translations and authored explanations remain
separate.
This is one historical source, not a cross-tradition consensus or an observed
weather/daylight guarantee.

## Translation revisions and search

The current text schema uses English originals/canonical text and separately
credited Chinese translations. Missing text is `None`; stale text retains its
old revision, without an English fallback counted as Chinese:

```{doctest}
>>> from astrology.knowledge import LocalizedText
>>> LocalizedText("Original").status("zh-CN").value
'missing'
>>> old = LocalizedText("Revised", "旧译", revision=2, zh_revision=1, translation_credit="example translator")
>>> old.status("zh-CN").value, old.text("zh-CN")
('stale', '旧译')
```

The required-translation check rejects missing/stale text in the built-in corpus.
Constructors and reference rendering can still represent those states explicitly.

Documentation search uses English word stems and Chinese character pairs, not
dictionary segmentation, exact phrase search or semantic alias expansion.
Single-character queries only find single-character
index entries, such as the explicit aliases `日` and `月`. Arbitrary single-character
substring matching is not supported. Use `Catalog.lookup()` for exact identity lookup.

## Add a sourced variant

1. Inspect a retrievable edition and reproduction terms. Record work, author or
   translator, edition, language, locator, lineage, supported claim and limits.
   Mark unverified material honestly; two mirrors are not two sources.
2. Add stable records to `src/astrology/knowledge/catalog.json`. Reference an
   owning enum class/member instead of copying its value or inventing an algorithm.
   Add a separate explicit variant only when it carries a rule, with its own
   definition and limits; configuration links alone do not generate variants.
   Lunar-node definition links are derived from `LunarNode.definition`, and the
   loader checks all twelve Sign-to-concept identities in the built-in corpus.
   Source-only variants have no config reference; entries link variant IDs and citations.
3. Keep excerpts, translations and authored statements distinct. `text_defaults`
   supplies initial revision 1 and project translation credit; each text can
   override them. Increment a changed text's `revision`; retain its old `zh_revision`
   until translation review, then update revision and credit together.
4. State prerequisites, exceptions and limits. Select source verification,
   prerequisite completeness and output eligibility independently. Retrieval must
   leave chart applicability `not_assessed` even when one condition is computable.
   Leave unsupported interpretations out of the default corpus.
5. Add boundary/source tests, run the [complete checks](contributing.md) and inspect
   both generated language pages. Checks cover current translations, complete
   config/catalog/API references and installed resources. Semantic review still
   verifies translation meaning and source fidelity.

## Pre-release rule-ID changes

Corpus `2026.10.21.1` removes fourteen automatically generated variants that only
repeated request identities. Their concepts, aliases, configuration links and
entries remain. `entry.body_requests` and `entry.node_directions` now have empty
`rule_ids`; entries already permitted that shape. The removed IDs are:

```text
rule.body.sun
rule.body.moon
rule.body.mercury
rule.body.venus
rule.body.mars
rule.body.jupiter
rule.body.saturn
rule.body.uranus
rule.body.neptune
rule.body.pluto
rule.node.mean_ascending
rule.node.mean_descending
rule.node.meeus_five_term_true_ascending
rule.node.meeus_five_term_true_descending
```

`variant()` raises `KeyError` for these IDs; there is no alias or conversion to a
concept. `list_variants()` for their concepts returns `()`. Use `concept()`,
`lookup()` or `filter_entries()` to retrieve the preserved identity information.
The three `rule.house.*`, two `rule.node_definition.*`, five `rule.aspect.*` and
nine original authored rule IDs remain. Their relative order is unchanged:
the ten configuration-linked rules precede the original nine authored rules.
That revision had 19 variants, with 36 concepts, 3 sources and 8 entries unchanged in
count. Source status, prerequisite completeness, output eligibility and chart
applicability retain their separate meanings.

The cross-chart addition preserves existing rule identities while scoping
participation to single-chart evaluation and motion to rates at one shared instant.

## Records and ownership

Use stable, language-independent identifiers for concepts, rule variants, sources,
and knowledge entries. These are record roles, not a requirement for one class or
file per role.

| Record | Holds |
|---|---|
| Concept | Identity, kind, Chinese/English names and aliases, related concepts |
| Rule variant | Definition, tradition, applicability, implementation reference if executable |
| Source | Work/author, edition, locator, original language, source lineage, supported claims and limits |
| Knowledge entry | Statement, linked concepts/rules/sources, prerequisites, exceptions, limits, and editorial status |

Keep executable constants and tables with the domain implementation. Knowledge
entries link to the rule identifier; generated reference tables read the
executable definition. Explanations provide the reasons and scope without becoming
a second computational rule table.

Original quotations, translations, and project-authored explanations are different
text layers. A translation must identify its original; citing the same source
through several translations does not provide independent evidence. Preserve the
source's wording and locator, and document reproduction rights for included material.

## Status has several dimensions

This catalog uses `verified` / `unverified` for source inspection,
`complete` / `unresolved` for prerequisite representation, and
`eligible` / `reference_only` for editorial output eligibility. `eligible` does
not mean that a chart satisfies the prerequisites. Retrieval leaves chart
applicability `not_assessed`, regardless of the other fields. The questions are:

1. Has the stated source been checked?
2. Are the entry's prerequisites understood and represented?
3. Is the entry eligible for the default output?
4. Does a particular chart satisfy the represented prerequisites?

An eventual matcher must distinguish satisfied, not satisfied, and unknown.
Matching part of a condition must remain partial evidence. For example, a
calculated aspect alone cannot establish a statement that also requires sect and
dignity when those conditions have not been evaluated.

Related design: [bazi](https://github.com/0xf3cd/bazi).

## Bilingual surfaces

- `README.md` and `README.zh-CN.md` provide equivalent project entry points.
- Guides and explanations use matching paths in `docs/en/` and `docs/zh-CN/`, with
  links to their language counterpart. Both cover the same supported behavior.
- Public API documentation exposes Chinese and English descriptions, constraints,
  and examples. Signatures, units, defaults, identifiers, and error contracts have
  one source. Keep public docstring summaries/contracts bilingual; render language
  views without maintaining separate signature or parameter tables.
- A concept or entry has one semantic identity with localized text. Record which
  semantic revision a translation covers; absence or staleness is visible rather
  than silently replaced with text in another language.
- Original excerpts remain in their source language. A reader may choose a
  translation without losing access to that original.
- The generated [catalog](catalog.md) identifies its code and corpus versions.
  Checks and semantic review are described in [contributing](contributing.md).

Language labels must not change calculation. Distinct definitions must not be
collapsed merely because a translation gives them the same display name. Search
should support both languages and aliases while returning stable identities.
