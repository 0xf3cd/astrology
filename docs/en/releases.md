# Release notes

[简体中文](../zh-CN/releases.md) · [Documentation](index.md) · [Release procedure](releasing.md)

## 0.4.0

This version adds dispositor chains and exact transit-to-natal hits, upgrades
celestial-calendar to 1.1.1 and removes the independent catalog version.
Package index: [PyPI](https://pypi.org/project/celestial-astrology/0.4.0/).

### Exact transit hits and UTC input

[`transit_hits`](transits.md) searches an explicit modern UTC interval for exact
moving-to-fixed-natal major aspects. `TransitHits` retains the source chart,
selections, TT interval, effective models and every native hit's rate/direction,
including retrograde repetitions and tangent contacts. No moving-side birth
record or place is required. Fixed-instant transit charts, orb windows and
returns remain outside this operation.

Runtime dependencies are exactly `celestial-calendar==1.1.1` and `tzdata==2026.5`.
The astronomy dependency provides the UTC conversion API used by transit searches.
The macOS arm64 minimum rises from 14 to **15**; other platform minimums and
Python 3.11–3.14 support are unchanged. Existing natal calculations and text
formats are unchanged. The chart guide's current calculation now reports upstream 1.1.1.

### Dispositor chains and rulership ownership

[`chart_dispositors(chart, objects=...)`](dignities.md#follow-dispositor-chains)
returns immutable `Dispositors`: ruler edges, paths from selected roots, reached
cycles and final dispositors, and missing successor rulers. It uses Lilly's
unchanged traditional sign rulers. The traversal is a project rule, with no
scoring or interpretation.

`HouseRuler` and `HouseRulers` move from `astrology.summaries` to
`astrology.dignities`. Update direct module imports; the old module has no aliases.
Imports from the package root (`from astrology import HouseRulers`) remain valid.
This is a 0.x source-path compatibility change. Chart calculations, dignity
assignments and existing text output are unchanged.

The knowledge catalog records inspected Meeus node terms, external definitions
of aspects and house systems, corrected Lilly scan locators, and retention or
access limits. Source inspection does not change chart applicability or default
output eligibility; model choices, orbs and numerical algorithms are unchanged.

### Breaking change: catalog version removed

The source API removes `Catalog.version` and its constructor argument. Custom
catalogs now use `Catalog(concepts, variants, sources, entries)`, omitting the
former first version argument. The catalog JSON's `version` key and release
manifest's `corpus_version` key are also removed, with no separate catalog version
to replace them. For the installed package version, use
`version("celestial-astrology")` from `importlib.metadata`. This is a 0.x
compatibility change; source revisions, bibliographic editions and chart
provenance remain.

## 0.3.0

This version adds natal analysis, axis aspect selection and cross-chart house overlays.
Package index: [PyPI](https://pypi.org/project/celestial-astrology/0.3.0/).

- [Element and modality distributions](summaries.md) count explicitly selected
  objects equally and retain zero-count categories, counts and proportions.
- [Natal lunar phase](summaries.md) classifies the Sun-to-Moon longitude angle
  using the named Rudhyar rule and the project's documented interval boundaries.
- [Traditional rulership and dignities](dignities.md) provide sign rulers, house
  rulers and domicile, exaltation, detriment and fall under Lilly's fixed rule.
- [Axis aspects](aspects.md#select-axes-explicitly) admit explicitly selected
  Ascendant, Midheaven, Descendant and Imum Coeli in natal and static cross-chart
  queries. Missing axis rates remain missing, not zero.
- [Cross-chart house overlays and bilingual comparison text](cross_aspects.md)
  retain both source charts and distinguish left/right objects and host houses.

SVG rendering from earlier source snapshots has been removed. Chart calculation,
structured results and bilingual text output remain available.

The guides now organize first use, focused API examples and verification details
separately. Release checks inspect package descriptions and rendered bilingual
pages as well as source text. The [release procedure](releasing.md) distinguishes
automatic protection from maintainer acceptance and describes partial-publication
recovery without replacing published files.

The astronomy models, Python/platform support and runtime dependency pins remain
unchanged from 0.2.0. This version does not add transits, returns, constructed
relationship charts or an interactive chart UI.

## 0.2.0

### Static cross-chart aspects

`cross_chart_aspects` compares two in-memory natal results with explicit rules.
`CrossAspectHit` records static geometry with distinct left/right endpoints;
`CrossChartAspects` retains both complete sources and the comparison request.
Same-named objects and cross-chart node pairs are allowed. There is no motion
field or common-epoch conversion. See the [cross-chart guide](cross_aspects.md).

### Ashmand 1822 sign groups

`ashmand_sign_group` maps an existing `Sign` to an `AshmandSignGroup`: tropical,
equinoctial, fixed or bicorporeal. The [knowledge guide](knowledge.md#ashmand-1822-sign-groups)
links the complete twelve-sign table, explains the historical names, and provides
source excerpts and Chinese translations.

### Breaking change: chart persistence removed

This release removed `dumps_chart`, `loads_chart`, `recompute_chart`, `ChartRecordError`,
`ChartReplayError` and the `astrology.serialization` module. The chart storage
schema and historical-record compatibility policy are withdrawn, with no
replacement format or compatibility wrapper. The package no longer reads saved
chart JSON. If an application needs the old API, keep the published v0.1.0
environment; its tag and artifacts are unchanged.

Calculate with `natal_chart`, use its immutable in-memory `NatalChart` and format
it with `format_chart`. Original/resolved birth input, requested/effective
configuration, astronomical values, domain validation and calculation provenance
remain. This removal does not change the astronomy, timezone policy or dependency
pins.

## 0.1.0

The first release provides modern tropical, geocentric natal charts and an
independently browsable English/Chinese knowledge catalog. Install the distribution
`celestial-astrology`; Python imports remain `astrology`.

### Delivered API

- Immutable original birth records, explicit timezone interpretation, and resolved
  calculation instants. Unknown time or location is preserved as missing; natal
  preparation rejects incomplete inputs rather than supplying noon or a location.
- Solar, lunar and planetary positions, named lunar-node definitions, axes and
  Whole Sign, Equal or Placidus houses. An undefined requested geometry raises
  `ChartDomainError` without selecting another house system.
- Tropical signs, longitude-only house placement, and five major aspects with
  explicit orb rules and local applying/separating status. This status describes
  motion at the calculation instant, not a forecast of a later exact aspect.
- Versioned chart records, restoration, explicit recomputation, and English/Chinese
  text output. Astronomy values, requested/effective settings and provenance remain
  separate in the stored result.
- Knowledge concepts, named rule variants, aliases and citations without calculating
  a chart or initializing native astronomy. Source verification, prerequisite status,
  output eligibility and chart applicability remain distinct. Quotations,
  translations and project-authored explanations retain their own attribution.

The [chart](chart.md), [aspect](aspects.md),
[v0.1.0 record](https://github.com/0xf3cd/astrology/blob/6b3293fae94b2f61e89a1d95778464f307c0d373/docs/en/records.md) and
[knowledge](knowledge.md) guides define the admitted conventions and corpus.

### Installation and compatibility

Python 3.11–3.14 is supported. Runtime dependencies are exactly
`celestial-calendar==0.8.0` and `tzdata==2026.5`. Exact pins preserve the selected
models and timezone data, but can prevent installation beside a consumer that
requires another version. This release does not upgrade to celestial 0.9 or widen
the dependency ranges.

Installation requires a compatible upstream astronomy wheel: Linux x86_64 or
aarch64 with the corresponding manylinux support, macOS 14+ arm64, or Windows
amd64. The astronomy dependency has no sdist. The astrology wheel's `any` platform
tag does not remove that restriction; knowledge-only use needs the same install.

Schema v1 restoration preserves stored values and their original provenance,
including historical `0.0.0` records, without loading astronomy. Recomputation
requires exact installed astrology/celestial versions and the recorded model.
Restoring a historical record does not make it recomputable under `0.1.0`; a
version or model mismatch raises `ChartReplayError`. See the
[v0.1.0 record guide](https://github.com/0xf3cd/astrology/blob/6b3293fae94b2f61e89a1d95778464f307c0d373/docs/en/records.md).

### Verification and limits

The full quality workflow runs on Linux Python 3.11/3.14 and macOS/Windows 3.14.
Release installation consumers use the same retained wheel on Linux x86_64
3.11/3.12/3.13/3.14, Linux ARM64 3.14, macOS ARM64 3.14 and Windows amd64 3.14.
The latter seven jobs check installation and consumers; they are not full quality
runs on every supported Python/platform pair. Run-specific results and artifact
digests belong to the release record, not a prewritten claim that those jobs passed.

Independent JPL Horizons and Swiss reference cases use named conventions and
documented tolerances. Their scope and shared-model limits are in the
[correctness guide](contributing.md#correctness). Restoration round trips and
same-runner source/install comparisons check preservation; they do not replace
those external references or promise cross-platform bitwise floating-point equality.

The adapter evaluates a fixed joint fourteen-object snapshot, even when a request
selects fewer objects. Its admitted domain is the intersection of that snapshot's
ephemeris/time limits and the requested house geometry. Astronomy civil-year
support alone does not establish the narrower chart domain. See [chart limits](chart.md#limits).
Historical input research, sidereal charts, transits/returns, relationship charts,
additional objects, interpretation and a chart-wheel UI are outside this release.
