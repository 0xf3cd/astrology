# astrology

[English](README.md) | [简体中文](README.zh-CN.md)

A Python library in development for reproducible Western astrology charts. It uses
[celestial-calendar](https://github.com/0xf3cd/celestial-calendar) for astronomy and
keeps astrological rules, their sources, and their variants in this repository.

The development package provides immutable [birth records and modern time
resolution](docs/en/birth.md), [requested chart configuration](docs/en/configuration.md),
[tropical natal chart calculation](docs/en/chart.md), [chart records and text output](docs/en/records.md), an independent
[knowledge catalog](docs/en/knowledge.md), quality checks, and bilingual
[API documentation](docs/en/reference.md). The astronomy library is imported only
when calculation or replay is requested, so importing the package or querying knowledge never
initializes it.
See [Contributing](docs/en/contributing.md) to run the checks.

Installation follows the astronomy dependency: celestial-calendar 0.8.0 publishes
wheels for Linux x86_64 and aarch64, macOS 14+ arm64 and Windows amd64, and no source
distribution. On any other platform this package cannot be installed, and
knowledge browsing is not available either.

## First release

The first target is a modern tropical, geocentric natal chart from a known birth
time and location:

- Preserve the birth record, resolve its timezone explicitly, and retain the
  resulting time scales and calculation provenance.
- Compute the Sun, Moon, eight planets, and explicitly selected lunar nodes.
- Support Whole Sign, Equal, and Placidus houses, with explicit failures where a
  requested geometry is undefined.
- Derive signs, two-dimensional longitude house placement, and the five major
  aspects with configurable orbs and local applying/separating status.
- Return immutable structured results, a text table, and a versioned serialization
  that retains inputs, configuration, astronomical values, and model identities.

Positions, axes, cusps, signs, house placement, aspects, text output and versioned
records are implemented. Restoration preserves stored results without native
astronomy; replay explicitly checks available versions and models.

See the [v0.1.0 milestone](https://github.com/0xf3cd/astrology/milestone/1) for
delivery tasks and acceptance criteria.

## Design boundaries

- [Repository structure and calculation boundaries](docs/en/architecture.md)
- [Knowledge organization and bilingual documentation](docs/en/knowledge.md)
- [Development and review conventions](docs/en/contributing.md)

Knowledge browsing is a first-release goal in its own right: readers should be
able to find a concept, its rule variants, and its sources without creating a
chart or loading the native astronomy library. Source status, applicability, and
display eligibility are recorded separately.

Project guides and public reference documentation are provided in Chinese and
English. Both languages refer to the same identifiers, executable rules, and
source records. Quotations retain their original language; translations are
identified as translations.

## Later work

- [Techniques and presentation](https://github.com/0xf3cd/astrology/milestone/2):
  transits and returns, relationship charts, tradition-specific rules, additional
  objects, and chart views.
- [Advanced and historical research](https://github.com/0xf3cd/astrology/milestone/3):
  directions, progressions, uncertain birth times, historical inputs, spatial
  house placement, and sourced interpretation.

These milestones track directions without assigning release dates. Each technique
needs a named definition, sources, and reference cases before implementation.

## License

[MIT](LICENSE) covers project code, translations and authored explanations.
Historical excerpts retain the reproduction status recorded in their
[source records](docs/en/knowledge.md#follow-a-source-to-a-definition).
