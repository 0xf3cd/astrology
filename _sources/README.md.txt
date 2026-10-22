# celestial-astrology

[English](https://0xf3cd.github.io/astrology/README.html) | [简体中文](https://0xf3cd.github.io/astrology/README.zh-CN.html)

A Python library in development for reproducible Western astrology charts. It uses
[celestial-calendar](https://github.com/0xf3cd/celestial-calendar) for astronomy and
keeps astrological rules, their sources, and their variants in this repository.

The development package provides immutable [birth records and modern time
resolution](https://0xf3cd.github.io/astrology/docs/en/birth.html), [requested chart configuration](https://0xf3cd.github.io/astrology/docs/en/configuration.html),
[tropical natal chart calculation](https://0xf3cd.github.io/astrology/docs/en/chart.html), [chart records and text output](https://0xf3cd.github.io/astrology/docs/en/records.html), an independent
[knowledge catalog](https://0xf3cd.github.io/astrology/docs/en/knowledge.html), quality checks, and bilingual
[API documentation](https://0xf3cd.github.io/astrology/docs/en/reference.html). The astronomy library is imported only
when calculation or replay is requested, so importing the package or querying knowledge never
initializes it.
See [Contributing](https://0xf3cd.github.io/astrology/docs/en/contributing.html) to run the checks.

Installation follows the astronomy dependency: celestial-calendar 0.8.0 publishes
wheels for Linux x86_64 and aarch64, macOS 14+ arm64 and Windows amd64, and no source
distribution. On any other platform this package cannot be installed, and
knowledge browsing is not available either.

## Install from source

`celestial-astrology` is the distribution name; the Python import is `astrology`.
This checkout prepares version `0.1.0`, which is not yet published on PyPI.
Do not install the unrelated PyPI project named `astrology`.

Use **Python 3.11–3.14** on one of the platforms listed above. For the exact source
revision used by the documentation, use the snapshot command on the
[documentation home](https://0xf3cd.github.io/astrology/). To install your downloaded
or cloned source checkout instead, run these commands from its root. Installation
needs network access for build dependencies and the pinned runtime packages.

Linux/macOS (replace `python3.14` with your supported Python version):

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install .
```

Windows PowerShell:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install .
```

These are source-install instructions, not a claim that the candidate can be
installed from the package index. Development checks use `uv sync --locked` as
described in the contribution guide.

## First chart

Save this Python script as `first_chart.py`; it is not an interactive transcript.
Run `.venv/bin/python first_chart.py` on Linux/macOS, or
`.venv\Scripts\python.exe first_chart.py` in PowerShell.
The input has an explicit UTC offset and synthetic coordinates. No aspects are requested.

```python
from datetime import date, time, timedelta
from astrology import (
  BirthRecord,
  Body,
  ChartConfig,
  FixedOffset,
  HouseSystem,
  Location,
  TimePrecision,
  natal_chart,
  prepare_natal_input,
)

record = BirthRecord(
  date(2000, 1, 1),
  time(12, 0),
  FixedOffset(timedelta(0)),
  Location(0, 0),
  TimePrecision.MINUTE,
  {"example": "synthetic"},
)
config = ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ())
chart = natal_chart(prepare_natal_input(record), config)
print(chart.provenance.astrology_version)
print(chart.resolved.utc.isoformat())
for placement in chart.placements:
  print(f"{placement.identity.value}: {placement.sign.value}")
```

Output:

```text
0.1.0
2000-01-01T12:00:00+00:00
sun: capricorn
moon: scorpio
```

Unknown time or missing location is rejected, not replaced with noon or an inferred
place. Undefined requested house geometry raises `ChartDomainError` without a
fallback. See the [chart guide](https://0xf3cd.github.io/astrology/docs/en/chart.html)
for admitted domains, and the [record guide](https://0xf3cd.github.io/astrology/docs/en/records.html)
for save/restore/recompute and bilingual text tables.

## First knowledge lookup

Save this separate script as `first_knowledge.py` and run it with the same
virtual-environment Python. It reads the packaged catalog without a chart or
native astronomy initialization; installation still has the platform limits above.

```python
from astrology import load_catalog

catalog = load_catalog()
print(catalog.concept("body.sun").name.text("en"))
print(catalog.lookup("Sol")[0].identifier)
```

Output:

```text
Sun
body.sun
```

Browse the [complete catalog](https://0xf3cd.github.io/astrology/docs/en/catalog.html)
or [public API](https://0xf3cd.github.io/astrology/docs/en/reference.html).
The shared documentation search may return either language; Chinese queries use
character pairs, not semantic matching or dictionary segmentation.

## First release

The first target is a modern tropical, geocentric natal chart from a known birth
time and location:

- Preserve the birth record, resolve its timezone explicitly, and retain the
  resulting time scales and calculation provenance.
- Compute the Sun, Moon, eight planets, and explicitly selected lunar nodes.
- Support Whole Sign, Equal, and Placidus houses, with explicit failures where a
  requested geometry is undefined.
- Derive signs, two-dimensional house placement (longitude only, without object latitude), and the five major
  aspects with configurable orbs and local applying/separating status.
- Return immutable structured results, a text table, and a versioned serialization
  that retains inputs, configuration, astronomical values, and model identities.

Positions, axes, cusps, signs, house placement, aspects, text output and versioned
records are implemented. Restoration preserves stored results without native
astronomy; replay explicitly checks available versions and models.

See the [v0.1.0 milestone](https://github.com/0xf3cd/astrology/milestone/1) for
delivery tasks and acceptance criteria.

## Design boundaries

- [Repository structure and calculation boundaries](https://0xf3cd.github.io/astrology/docs/en/architecture.html)
- [Knowledge organization and bilingual documentation](https://0xf3cd.github.io/astrology/docs/en/knowledge.html)
- [Development and review conventions](https://0xf3cd.github.io/astrology/docs/en/contributing.html)

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

[MIT](https://github.com/0xf3cd/astrology/blob/main/LICENSE) covers project code, translations and authored explanations.
Historical excerpts retain the reproduction status recorded in their
[source records](https://0xf3cd.github.io/astrology/docs/en/knowledge.html#knowledge-source-definitions-en).
