# Knowledge organization and bilingual documentation

[简体中文](../zh-CN/knowledge.md) · [Project](../../README.md) · [Architecture](architecture.md)

The repository serves two tasks: compute a chart, and study the concepts and
rules behind it. Knowledge queries must work without a chart, birth data, or a
loaded celestial native library.

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

Start with concepts and definitions actually used by the natal chart: its bodies,
zodiac signs, house systems, node definitions, and major aspects. Add enough
verified sources to explain those definitions; leave unsupported interpretations
out of the default corpus.

The first catalog supports listing concepts and variants, finding names/aliases,
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
