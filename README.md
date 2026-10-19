# astrology

[English](README.md) | [简体中文](README.zh-CN.md)

A Python library in development for reproducible Western astrology charts. It will use
[celestial-calendar](https://github.com/0xf3cd/celestial-calendar) for astronomy and
keeps astrological rules, their sources, and their variants in this repository.

The development package provides immutable [birth records and modern time
resolution](docs/en/birth.md), [requested chart configuration](docs/en/configuration.md),
an independent [knowledge catalog](docs/en/knowledge.md), quality checks, and bilingual
[API documentation](docs/en/reference.md). Chart calculation is not yet implemented.
Astronomy is not imported or
initialized by the package. See [Contributing](docs/en/contributing.md) to run the checks.

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
