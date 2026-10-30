# celestial-astrology

[English](https://0xf3cd.github.io/astrology/README.html) | [简体中文](https://0xf3cd.github.io/astrology/README.zh-CN.html)

A Python library for reproducible Western astrology charts and knowledge queries. It uses
[celestial-calendar](https://github.com/0xf3cd/celestial-calendar) for astronomy and
keeps astrological rules, their sources, and their variants in this repository.

Calculate a tropical, geocentric natal chart from a known birth time and location,
or query the knowledge catalog without a chart. Start with the examples below;
the [guides](https://0xf3cd.github.io/astrology/docs/en/index.html) and
[API reference](https://0xf3cd.github.io/astrology/docs/en/reference.html) cover the full contracts.

The current source also adds [element/modality distributions and natal lunar
phase](https://0xf3cd.github.io/astrology/docs/en/summaries.html),
[traditional sign rulers and four statuses](https://0xf3cd.github.io/astrology/docs/en/dignities.html),
[explicit axis aspects for natal and static cross-chart queries](https://0xf3cd.github.io/astrology/docs/en/aspects.html#select-axes-explicitly),
[cross-chart house overlays and bilingual comparison text](https://0xf3cd.github.io/astrology/docs/en/cross_aspects.html),
and [SVG natal wheels and aspect matrices](https://0xf3cd.github.io/astrology/docs/en/svg.html).
These additions are planned for 0.3.0. Axes participate only when selected;
requests without selected axes keep their behavior.

New in 0.2.0 (in development):

- [Static cross-chart aspects](https://0xf3cd.github.io/astrology/docs/en/cross_aspects.html)
  between two natal charts, retaining both source charts and distinct left/right
  objects, without applying/separating labels.
- `ashmand_sign_group(Sign.ARIES)` queries the twelve signs' four groups in
  Ashmand's 1822 edition. See [the source and lookup example](https://0xf3cd.github.io/astrology/docs/en/knowledge.html#ashmand-1822-sign-groups).

## Install a release

Installation follows the astronomy dependency: celestial-calendar 0.8.0 publishes
wheels for Linux x86_64 and aarch64, macOS 14+ arm64 and Windows amd64, and no source
distribution. On any other platform this package cannot be installed, and
knowledge browsing is not available either.

`celestial-astrology` is the distribution name; the Python import is `astrology`.
Do not install the unrelated PyPI project named `astrology`.

Use **Python 3.11–3.14** on one of the platforms listed above.

This checkout prepares 0.2.0. To try the candidate now,
[install from source](https://0xf3cd.github.io/astrology/README.html#install-from-source).
After 0.2.0 is published on PyPI, use the commands below.
The examples show output from 0.2.0.

Linux/macOS (replace `python3.14` with your supported Python version):

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install "celestial-astrology==0.2.0"
```

Windows PowerShell:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install "celestial-astrology==0.2.0"
```

Runtime dependencies remain exactly pinned to `celestial-calendar==0.8.0` and
`tzdata==2026.5`. This can conflict with applications requiring another version.
See the [release notes](https://0xf3cd.github.io/astrology/docs/en/releases.html).

## Install from source

For the exact source
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

These commands install your source checkout. Development checks use `uv sync --locked` as
described in the contribution guide.

## First chart

Save this Python script as `first_chart.py`.
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
0.2.0
2000-01-01T12:00:00+00:00
sun: capricorn
moon: scorpio
```

Unknown time or missing location is rejected, not replaced with noon or an inferred
place. Undefined requested house geometry raises `ChartDomainError` without a
fallback. See the [chart guide](https://0xf3cd.github.io/astrology/docs/en/chart.html)
for admitted domains, and the [result guide](https://0xf3cd.github.io/astrology/docs/en/records.html)
for structured results and bilingual text tables.

The output lists the resolved UTC instant and each selected object's sign.
Change `ChartConfig.objects` to request other bodies or nodes; use
`aspect_objects` and explicit orb rules to choose who participates in aspects.

| Next task | Guide |
|---|---|
| Resolve a local clock or select a repeated time | [Birth inputs](https://0xf3cd.github.io/astrology/docs/en/birth.html) |
| Select objects, participants and orbs | [Configuration](https://0xf3cd.github.io/astrology/docs/en/configuration.html) |
| Compare two charts | [Cross-chart aspects and house overlays](https://0xf3cd.github.io/astrology/docs/en/cross_aspects.html) |
| Draw the result (source-checkout API) | [SVG wheels and matrices](https://0xf3cd.github.io/astrology/docs/en/svg.html) |

## First knowledge lookup

Save this separate script as `first_knowledge.py` and run it with the same
virtual-environment Python. This example finds the Sun by name and alias:

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

The [knowledge guide](https://0xf3cd.github.io/astrology/docs/en/knowledge.html)
explains lookup, citations and editorial status. Browse the
[complete catalog](https://0xf3cd.github.io/astrology/docs/en/catalog.html) for definitions and sources.

## Supported chart

The chart supports Whole Sign, Equal and Placidus houses, the Sun, Moon and eight
planets, and explicitly selected lunar-node definitions. House placement uses
longitude only, without object latitude. The five major aspects use caller-supplied
orbs; applying/separating describes local motion, not a future-event prediction.
Immutable results retain the original input, resolved time scales, configuration,
unrounded astronomy and named models. Chart persistence is removed in the current source; see the
[release notes](https://0xf3cd.github.io/astrology/docs/en/releases.html) for the
difference from the published v0.1.0 API.

## Design boundaries

- [Repository structure and calculation boundaries](https://0xf3cd.github.io/astrology/docs/en/architecture.html)
- [Knowledge organization and bilingual documentation](https://0xf3cd.github.io/astrology/docs/en/knowledge.html)
- [Development and review conventions](https://0xf3cd.github.io/astrology/docs/en/contributing.html)

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
