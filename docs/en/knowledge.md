# Knowledge organization and bilingual documentation

[简体中文](../zh-CN/knowledge.md) · [Project](../../README.md) · [Architecture](architecture.md)

The development package provides a chart-independent knowledge catalog. List
concepts and variants, find bilingual names/aliases, filter entries and sources,
and inspect citations without birth data or native astronomy. Chart calculation
is not implemented. See the generated [catalog](catalog.md) and [API](reference.md).

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
>>> catalog.list_variants(concept_id="body.sun")[0].configuration.name
'SUN'
>>> catalog.filter_entries(concept_id="body.sun")[0].identifier
'entry.body_requests'
>>> len(catalog.filter_sources(verification=SourceVerification.VERIFIED))
2
>>> bool(catalog.version)
True
```

Each `load_catalog()` explicitly reads the packaged JSON, without a cache or
network. Constructors copy sequences into tuples. Invalid record types, duplicate
IDs, dangling links and conflicting aliases raise `TypeError` or `ValueError`,
including under `python -O`.

`lookup()` normalizes NFC, trims and case-folds, then matches exact names/aliases.
It returns an immutable tuple: `()` for no match, several distinct identities for
ambiguous display names. Select `language="en"` or `language="zh-CN"` to restrict
lookup; omission searches both. Unknown IDs in getters/filters raise `KeyError`.
Entry filters combine all selected criteria; they never evaluate prerequisites.

## Follow a source to a definition

The corpus contains project configuration contracts and one single-source
historical grouping. It names every admitted configuration identity and twelve
sign concepts. It provides no sign boundaries, house geometry, node formula,
aspect angles, default orbs, dignity or interpretation rules. Request variants
reference actual config enum members, not implemented astronomical algorithms.

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
of Ashmand's translation through the paraphrase attributed to Proclus. The
{ref}`catalog example <catalog-en-entry-equinoctial-example>` preserves the complete
English sentence and a separately credited project Chinese translation. The
historical equal-day/night rationale is retained, not endorsed as an observed
daylight guarantee. Statements, definitions and limitations are project
explanations, not additional quotations.

The source records the edition, scan hash, transcription normalization and bounded
reproduction status. Only a short transcription is included, not scan images,
watermarks or modern website prose. Mirrors/catalogs corroborate the edition,
not independent rule authorship. Config citations identify package version and
symbols at a fixed commit; they do not verify an author's book formula merely
because a project definition bears that author's name.

The following is synthetic partial evidence, not a traditional claim or matching
API. The catalog does not consume it or promote the entry to applicable:

```{doctest}
>>> partial_evidence = {"condition_a": True, "condition_b": None}
>>> partial_evidence["condition_a"], partial_evidence["condition_b"]
(True, None)
>>> catalog.entry(entry.identifier).chart_applicability
'not_assessed'
```

All built-in entries are reference-only. Even `eligible` would mean editorial
output eligibility, not a satisfied chart. This package has no matcher or
chart-evidence store; future matching must retain unknown and partial evidence.

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

Documentation search keeps English stemming and splits Han runs into overlapping
adjacent-character pairs. Python indexing and emitted JavaScript queries use this
same character-bigram algorithm, not dictionary segmentation, exact phrase search
or semantic alias expansion. Acceptance cases include `太阳`, `日轮`, `牡羊座`,
`平均北交点` and `普拉西度制`. Single-character queries only find indexed singleton
blocks; explicit aliases `日` and `月` have those blocks. Arbitrary single-character
substring matching is not supported. Use `Catalog.lookup()` for exact identity lookup.

## Add a sourced variant

1. Inspect a retrievable edition and reproduction terms. Record work, author or
   translator, edition, language, locator, lineage, supported claim and limits.
   Mark unverified material honestly; two mirrors are not two sources.
2. Add stable records to `src/astrology/knowledge/catalog.json`. Reference an
   owning enum class/member instead of copying its value or inventing an algorithm.
   The loader derives `rule.<concept-id>` request variants from those same links.
   Source-only variants have no config reference; entries link variant IDs and citations.
3. Keep excerpts, translations and authored statements distinct. `text_defaults`
   supplies initial revision 1 and project translation credit; each text can
   override them. Increment a changed text's `revision`; retain its old `zh_revision`
   until translation review, then update revision and credit together.
4. State prerequisites, exceptions and limits. Select source verification,
   prerequisite completeness and output eligibility independently. Retrieval must
   leave chart applicability `not_assessed` even when one condition is computable.
5. Add boundary/source tests, run the [complete checks](contributing.md) and inspect
   both generated language pages. Checks cover current translations, complete
   config/catalog/API references and installed resources. Semantic review still
   verifies translation meaning and source fidelity.

## Records and ownership

Use stable, language-independent identifiers for concepts, rule variants, sources,
and knowledge entries. These are record roles, not a requirement for one class or
file per role. Define the first schema against a small real corpus.

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

The knowledge design in [bazi](https://github.com/0xf3cd/bazi) already separates
these questions in `knowledge.py` and `context_matching.py`:

1. Has the stated source been checked?
2. Are the entry's prerequisites understood and represented?
3. Is the entry eligible for the default output?
4. Does a particular chart satisfy the represented prerequisites?

Astrology should retain this separation rather than copying bazi's exact enum
values or default-output rule. Source verification alone does not establish
applicability. Finding a related statement does not establish that it applies to
a chart.

An eventual matcher must distinguish satisfied, not satisfied, and unknown.
Matching part of a condition must remain partial evidence. For example, a
calculated aspect alone cannot establish a statement that also requires sect and
dignity when those conditions have not been evaluated.

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

Language labels must not change calculation. Distinct definitions must not be
collapsed merely because a translation gives them the same display name. Search
should support both languages and aliases while returning stable identities.

## First useful slice

The catalog starts with concepts and definitions requested by the natal chart: its bodies,
zodiac signs, house systems, node definitions, and major aspects. Add enough
verified sources to explain those definitions; leave unsupported interpretations
out of the default corpus.

The catalog supports listing concepts and variants, finding names/aliases,
filtering entries and sources, and inspecting citations without calculating a
chart. Ship a small worked example with source text, a labeled translation, a
rule reference, and a conditional or unresolved entry that is not automatically
presented as applicable.

The schema may later grow to hold interpretations and premise matching. A graph
database or general rule engine requires an actual query need, not just a large
list of possible future techniques.

## Documentation checks

Generate API and catalog reference pages from their owning definitions. Handwrite
guides that answer reader tasks: calculate a chart, compare configurations, browse
knowledge, inspect sources, and add a sourced variant.

The first documentation implementation must check counterpart-page coverage,
stable entry links, required translation coverage, unknown references, duplicate
identifiers, and executable examples in both languages. Inspect generated HTML as
well as build success: missing members or descriptions can still produce a green
build. A semantic review checks that translations preserve conditions and limits;
an identifier comparison cannot prove that.

Published documentation must identify its code/corpus version and distinguish
development pages from released pages. Deployment is a later explicit action;
the current Markdown documents remain the readable entry points.
