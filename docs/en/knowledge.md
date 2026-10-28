# Knowledge organization and bilingual documentation

[简体中文](../zh-CN/knowledge.md) · [Project](../../README.md) · [Architecture](architecture.md)

The knowledge catalog lets you look up English and Chinese names and aliases,
read rule definitions, and find the cited books or code. For example, look up the
Sun as "Sol" or find Aries' group in Ashmand's 1822 edition. These queries need no
birth data or chart. Browse the [complete catalog](catalog.md), or use the Python
queries below. See the [API](reference.md) for interfaces and the [chart guide](chart.md)
for calculation.

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
>>> [rule.identifier for rule in catalog.list_variants(concept_id="body.sun")]
['rule.lilly1647.essential_dignities']
>>> catalog.filter_entries(concept_id="body.sun")[0].identifier
'entry.body_requests'
>>> len(catalog.filter_sources(verification=SourceVerification.VERIFIED))
10
>>> bool(catalog.version)
True
```

Several names can identify one concept: `Sun`, `Sol` and `日轮` all refer to
`body.sun`. A rule variant records a particular definition, such as a house
system or lunar-node algorithm. Body names and ascending/descending node directions
do not get identity-only rules. The Sun links to the sourced dignity rule,
which carries assignments rather than repeating its name. See [rule-ID changes](#pre-release-rule-id-changes)
for the old identifiers.

You can also look up the rules for [cross-chart aspect comparison](cross_aspects.md).
`entry.cross_aspect_evaluation` is the explanatory entry;
`rule.project.cross_aspect_evaluation` is its linked rule. Retrieving the entry
returns the explanation rather than running a comparison:

```{doctest}
>>> comparison = catalog.entry("entry.cross_aspect_evaluation")
>>> comparison.prerequisite_status.value, comparison.output_eligibility.value, comparison.chart_applicability
('complete', 'reference_only', 'not_assessed')
```

Here, `complete` means the entry has stated its prerequisites, `reference_only`
means it is for reference, and `not_assessed` means no chart has been checked
against those prerequisites. These answer different questions; see [status meanings](#status-has-several-dimensions).

For [house overlays](cross_aspects.md#find-houses-in-the-other-chart), retrieve the
separate composition rule and its fixed implementation source:

```{doctest}
>>> overlay = catalog.entry("entry.cross_house_overlays")
>>> overlay.rule_ids
('rule.project.cross_house_overlays', 'rule.project.cusp_ownership')
>>> citation, source = catalog.citations(overlay.identifier)[0]
>>> source.identifier
'source.astrology.house_overlays.f269d14'
>>> overlay.prerequisite_status.value, overlay.output_eligibility.value, overlay.chart_applicability
('complete', 'reference_only', 'not_assessed')
```

`rule.project.cross_house_overlays` uses the shared `rule.project.cusp_ownership`
interval rule. The composition keeps the object owner distinct from the receiving house owner,
with independent selections and retained source house systems. Its code citation
documents the implementation, not astronomical authentication or relationship
interpretation. Looking it up does not calculate placements or assess a chart.

### Return values and errors

Each `load_catalog()` reads the packaged JSON file without network access or a
cache. Record constructors copy input sequences into immutable tuples. Invalid
record types, duplicate IDs, links to missing records and conflicting aliases
raise `TypeError` or `ValueError`; these checks also run under `python -O`.

`lookup()` normalizes NFC, trims and case-folds, then matches exact names/aliases.
It returns an immutable tuple: `()` for no match, several distinct concepts for
ambiguous names. Select `language="en"` or `language="zh-CN"` to restrict
lookup; omission searches both. Unknown well-formed IDs in getters/filters raise
`KeyError`; malformed strings raise `ValueError`, non-string IDs `TypeError`.
Entry filters combine all selected criteria; they never evaluate prerequisites.

(knowledge-source-definitions-en)=
## Follow a source to a definition

The catalog currently includes:

- Available bodies, axes, house systems, lunar-node definitions and aspects, with their
  English and Chinese names.
- How this project divides the zodiac into twelve signs, places objects in houses
  (including cross-chart overlays), and calculates single-chart and cross-chart aspects.
- The four sign groups in Ashmand's 1822 edition, with bibliographic records,
  excerpts and Chinese translations.
- [Traditional sign rulers and four statuses](dignities.md) from William Lilly's
  *Christian Astrology* (1647), with short primary-scan excerpts and a generated
  sign table.

Configuration entries link to the enum members the program uses; rule descriptions
link to their implementations. House systems, node definitions and aspect angles
have separate explanations of the chosen definitions and their limits. Reference
pages take exact aspect angles directly from the calculation code and check the
angles in explanatory text against it. The catalog supplies no default orbs or
interpretation rules. Dignity assignments belong to `astrology.dignities`.

For example, inspect the equinoctial-sign entry's source, excerpt, translation
and status:

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
source explains the name using equal day and night; retaining that historical
explanation does not guarantee observed daylight duration. The source has been
checked (`verified`), but the entry's prerequisites for chart interpretation remain
unclear (`unresolved`). The entry is marked `reference_only`, for consultation
rather than chart conclusions. The entry's statements,
definitions and limits are project explanations, separate from the quotation.

Source records give the edition, scan hash, transcription changes and reproduction
terms. The package includes limited definition excerpts, not scan images,
watermarks or modern website prose. Mirrors and bibliographic records can help
confirm an edition; they are not independent evidence for its rules. Code
citations identify the package version and symbols at a fixed commit. A definition
bearing an author's name does not mean the formulas in that author's book have
been checked.

Implementation source records stay pinned to the inspected commits instead of
following the package version. The chart source record locates the node-comparison
test in `tests/test_reference.py` at that same commit. The test calculates reference
node longitudes from the formulas recorded there and compares them with upstream
results. This does not verify Meeus's printed text, establish an error bound or show
equivalence to an osculating node.

The hand-written data below illustrates knowing only some of the conditions:
the first is true, while the second remains unknown. The catalog does not read
this dictionary or change the entry's chart-applicability status:

```{doctest}
>>> partial_evidence = {"condition_a": True, "condition_b": None}
>>> partial_evidence["condition_a"], partial_evidence["condition_b"]
(True, None)
>>> catalog.entry(entry.identifier).chart_applicability
'not_assessed'
```

All built-in entries are for reference. The package does not check whether a chart
satisfies an entry or store chart evidence for that judgment.

## Explicit axis vocabulary

`axis.ascendant`, `axis.midheaven`, `axis.descendant` and `axis.imum_coeli` are
separate concepts bound to `Axis`, not bodies, nodes or cusp aliases. The
reference-only `entry.axis_aspects` states the project's explicit-selection,
pairing and missing-rate policies and cites their fixed implementation revision.
The earlier body/node sources keep their original revisions; they are not
retroactively evidence for the axis extension.

```{doctest}
>>> from astrology import Axis
>>> catalog.concept("axis.ascendant").configuration is Axis.ASCENDANT
True
>>> axes = catalog.entry("entry.axis_aspects")
>>> axes.prerequisite_status.value, axes.output_eligibility.value, axes.chart_applicability
('complete', 'reference_only', 'not_assessed')
```

These queries need no chart or native astronomy. To calculate the geometry, see
[explicit natal selection](aspects.md#select-axes-explicitly) and
[independent cross-side selection](cross_aspects.md#select-axes-on-each-side).

## Ashmand 1822 sign groups

These groups come from Ashmand's 1822 *Ptolemy's Tetrabiblos, or Quadripartite*.
New in 0.2.0, `ashmand_sign_group` takes a `Sign` and returns its group:

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
explicitly. The result is a group label, not a score or interpretation. Here,
`complete` means the membership lookup has all its required input: a `Sign`.
The earlier equinoctial entry remains `unresolved` because prerequisites for
chart interpretation are a separate question.

The four labels are **tropical**, **equinoctial**, **fixed** and **bicorporeal**.
Tropical here means the two solstitial signs, not all twelve signs of the tropical
zodiac. The source directly names the tropical and equinoctial pairs. In zodiac
order, fixed signs immediately follow those signs, and bicorporeal signs
immediately follow fixed signs. The
{ref}`twelve-sign table <catalog-en-rule-ptolemy-ashmand-sign-groups>` is
project-derived, not a verbatim source list.

The definitions appear in Book I, chapter XIV, printed pp. 34–35 (PDF pp. 72–73),
recorded as `source.ptolemy.ashmand1822`. The catalog labels English excerpts,
credited Chinese translations and project explanations separately, with the
extent of each excerpt recorded in its citation. This classification follows
Ashmand's edition; it does not establish agreement across traditions or predict
actual weather or daylight.

## Elements, modalities and lunation types

These output concepts have their own kinds and stable IDs: `element.*`,
`modality.*`, `lunation_type.rudhyar1950.*`, without request-configuration links.
See the [queries, statistics and lunar phase guide](summaries.md). The inspected
sources are an Astrodienst webpage snapshot and Rudhyar's online transcription;
Rudhyar's magazine original was not inspected. Classifications carry no personality interpretation;
generated tables read the owning executable definitions.

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
concept. Their removal did not prohibit later substantive rules: the seven
classical bodies now link to the dignity and debility rules recorded in Lilly's
*Christian Astrology* (1647). Use `concept()`,
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

Finding a source does not establish a rule's prerequisites for use in a chart;
stating those prerequisites does not establish that a particular chart meets
them. The catalog records these questions separately:

| Question | Field and values | Meaning |
|---|---|---|
| Has the source been checked? | `source.verification`: `verified` / `unverified` | Whether the cited source was inspected, not whether its historical claim is true. |
| Are the prerequisites clear? | `entry.prerequisite_status`: `complete` / `unresolved` | Whether the prerequisites are understood and fully stated, or something remains unclear. |
| Can the entry appear in default output? | `entry.output_eligibility`: `eligible` / `reference_only` | An editorial decision; `eligible` does not mean a chart meets the prerequisites. |
| Does a chart meet the conditions? | `entry.chart_applicability`: `not_assessed` | Catalog lookup does not make this judgment, regardless of the other three fields. |

Any future chart-condition evaluator must distinguish satisfied, not satisfied,
and unknown.
Matching part of a condition must remain partial evidence. For example, a
calculated aspect alone cannot establish a statement that also requires sect and
dignity when those conditions have not been evaluated.

Related design: [bazi](https://github.com/0xf3cd/bazi).

## Bilingual surfaces

- `README.md` and `README.zh-CN.md` provide equivalent project entry points.
- Guides and explanations use matching paths in `docs/en/` and `docs/zh-CN/`, with
  links to their language counterpart. Both cover the same supported behavior.
- Public API documentation exposes Chinese and English descriptions, constraints,
  and examples. Signatures, units, defaults, identifiers and error behavior are
  defined once. Public docstring summaries and usage requirements are bilingual;
  both language views share signatures and parameter tables.
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
