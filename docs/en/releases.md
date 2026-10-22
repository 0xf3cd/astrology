# Release notes

[简体中文](../zh-CN/releases.md) · [Documentation](index.md) · [Release procedure](releasing.md)

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

The [chart](chart.md), [aspect](aspects.md), [record](records.md) and
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
version or model mismatch raises `ChartReplayError`. See [record compatibility](records.md).

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
