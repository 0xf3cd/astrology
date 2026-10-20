# Knowledge organization and bilingual documentation

[简体中文](../zh-CN/knowledge.md) · [Project](../../README.md) · [Architecture](architecture.md)

The development package provides a chart-independent knowledge catalog. List
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
>>> catalog.list_variants(concept_id="body.sun")[0].configuration.name
'SUN'
>>> catalog.filter_entries(concept_id="body.sun")[0].identifier
'entry.body_requests'
>>> len(catalog.filter_sources(verification=SourceVerification.VERIFIED))
3
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
lookup; omission searches both. Unknown well-formed IDs in getters/filters raise
`KeyError`; malformed strings raise `ValueError`, non-string IDs `TypeError`.
Entry filters combine all selected criteria; they never evaluate prerequisites.

## Follow a source to a definition

The corpus contains project configuration contracts, the project conventions for
sign sectors and house placement, and one single-source historical grouping. It
names every admitted configuration identity and twelve sign concepts, and points
at the executable rules in the chart implementation instead of restating them.
It states the project's own aspect evaluation, but provides no default orbs, dignity or interpretation rules.
Request variants reference actual config enum members and the implementation
that owns them.

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

All built-in entries are reference-only. This package has no matcher or
chart-evidence store.

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
   The loader derives `rule.<concept-id>` request variants from those same links.
   Lunar-node definition links are derived from `LunarNode.definition`.
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
- The generated [catalog](catalog.md) identifies its code and corpus versions and
  is labeled as development documentation. Checks and semantic review are described
  in [contributing](contributing.md).

Language labels must not change calculation. Distinct definitions must not be
collapsed merely because a translation gives them the same display name. Search
should support both languages and aliases while returning stable identities.
