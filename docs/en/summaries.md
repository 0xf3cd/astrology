# Sign distributions and natal lunar phase

[简体中文](../zh-CN/summaries.md) · [API](reference.md) · [Knowledge](knowledge.md)

These source-checkout APIs are planned for 0.3.0; they are not in the published
0.2.0 package. They classify supplied values without astronomy or source-chart
changes. Formatters take a loaded catalog and do no resource I/O.

## Query signs and count an explicit population

<!-- usage: summaries.population -->

Pass the placements you want to count to `sign_distribution`. The example counts
Sun and Moon equally and prints all element and modality categories:

```{doctest}
>>> from astrology import (Body, Element, Modality, Placement, Sign, element_of,
...     modality_of, sign_distribution, format_sign_distribution, load_catalog)
>>> element_of(Sign.ARIES) is Element.FIRE
True
>>> modality_of(Sign.CANCER) is Modality.CARDINAL
True
>>> placements = [Placement(Body.SUN, Sign.ARIES, 10, 1),
...               Placement(Body.MOON, Sign.CANCER, 10, 4)]
>>> result = sign_distribution(placements)
>>> placements.clear()
>>> result.objects, result.total
((<Body.SUN: 'sun'>, <Body.MOON: 'moon'>), 2)
>>> result.element_counts[Element.FIRE], result.element_proportions[Element.FIRE]
(1, 0.5)
>>> result.modality_counts[Modality.CARDINAL]
2
>>> catalog = load_catalog()
>>> print(format_sign_distribution(result, catalog))
Sign distribution (equal counts)
Counted objects: Sun [sun], Moon [moon]
Total / denominator: 2
Rule: rule.zodiac.elements, rule.zodiac.modalities
Category | Count / total | Proportion
Fire element | 1/2 | 50.00%
Earth element | 0/2 | 0.00%
Air element | 0/2 | 0.00%
Water element | 1/2 | 50.00%
Cardinal modality | 2/2 | 100.00%
Fixed modality | 0/2 | 0.00%
Mutable modality | 0/2 | 0.00%
```

Each distinct selected identity contributes one count, with `total` as the common
denominator. Every category is present, including zero counts. Percentage display
rounds to two decimal places alongside exact count/total. No planet weights or
dominant scores are assigned.

`sign_distribution` and `SignDistribution` copy sequences to immutable placement
tuples, preserving input order. Empty or duplicate populations raise `ValueError`;
`None`, iterators and non-`Placement` members raise `TypeError`. The caller must
ensure appropriate common provenance for low-level placements; the record cannot
authenticate it. Counts and proportions derive from the snapshot, so no inconsistent
total can be supplied separately. `element_of` and `modality_of` accept only `Sign`,
not strings or unrelated enums.

<!-- /usage: summaries.population -->

Classification sources and the distinction from historical sign groups are
described in [knowledge](knowledge.md#elements-modalities-and-lunation-types).

## Classify a supplied Sun/Moon pair

<!-- usage: summaries.lunar_phase -->

Supply Sun first and Moon second, in degrees at the same instant and with the
same coordinate convention. The result gives the oriented arc and its type:

```{doctest}
>>> from astrology import lunar_phase, format_lunar_phase
>>> phase = lunar_phase(sun_longitude_deg=350, moon_longitude_deg=10)
>>> phase.elongation_deg, phase.phase.value, phase.direction
(20.0, 'new_moon', 'waxing')
>>> print(format_lunar_phase(phase, catalog))
Lunar phase type: New Moon Type
Moon minus Sun (longitude, degrees): 20.0
Angular direction: waxing
Rule: rule.lunation.rudhyar1950
A type covers an interval, not an exact event; no illuminated fraction is calculated.
>>> lunar_phase(10, 350).direction, lunar_phase(0, 180).direction
('waning', 'turning')
```

The oriented difference is `(Moon - Sun) mod 360`, in degrees. Finite inputs may contain whole turns.
Booleans, strings and unrelated types raise `TypeError`; nonfinite values raise
`ValueError`. Bare numbers carry no instant or coordinate convention, so the
scalar function cannot detect a frame mismatch.

See the {ref}`generated intervals <catalog-en-rule-lunation-rudhyar1950>` and
[source discussion](knowledge.md#elements-modalities-and-lunation-types).
Each type spans 45°. The project uses half-open intervals: exact boundaries belong
to the following type, with 360° wrapping to 0°. Strict `(0, 180)` is `waxing`,
strict `(180, 360)` is `waning`, and 0°/180° are `turning`. Endpoints and direction
labels are project policies.

`LunarPhaseResult` is immutable. Type, direction and rule ID derive from its angle;
direct construction requires `[0, 360)`. New Moon Type at 20° is not an exact
conjunction. No illuminated fraction, 3D phase angle, exact-event search or
personality interpretation is calculated. Direction describes the arc, not a
rate-based forecast.

<!-- /usage: summaries.lunar_phase -->

## Compose from an existing natal chart

This synthetic chart is calculated once. Summary calls only read its existing
positions and placements, using one chart's shared coordinate frame:

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (BirthRecord, FixedOffset, Location, ChartConfig, HouseSystem,
...     natal_chart, prepare_natal_input, chart_sign_distribution, natal_lunar_phase)
>>> record = BirthRecord(date(2000, 1, 1), time(12), FixedOffset(timedelta(0)), Location(0, 0))
>>> chart = natal_chart(prepare_natal_input(record),
...     ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MOON), ()))
>>> summary = chart_sign_distribution(chart, objects=(Body.MOON, Body.SUN))
>>> summary.objects == chart.requested.objects
True
>>> summary.total
2
>>> natal_lunar_phase(chart) == lunar_phase(chart.positions[0].longitude_deg,
...                                       chart.positions[1].longitude_deg)
True
```

`objects` is required and nonempty. `None`, strings and wrong identity types raise
`TypeError`; duplicates or unavailable identities raise `ValueError`. Results
follow source-chart order, not selection order. To count all requested objects,
explicitly pass `objects=chart.requested.objects`. No unselected body, node or axis
is added. Axes are not placements and are rejected even when explicitly selected
for these statistics. `natal_lunar_phase` requires Sun and Moon; missing positions raise
`ValueError` naming absent identities, never a request to calculate them. Both
wrappers reject non-`NatalChart` inputs with `TypeError`. Checks work under `python -O`.

Catalog entries remain `reference_only`, with stated prerequisites `complete` and
chart applicability `not_assessed`. Verified source inspection does not make
catalog lookup a chart evaluation.

## Numerical angle and display

Inputs use the numeric validator's float conversion. Exact ratios of those binary
values avoid subtraction overflow and loss of boundary sides. The nearest float
is returned unless conversion erases the interval side; then one adjacent float
on the correct side is used. For example, `lunar_phase(5e-324, 0)` returns
`359.99999999999994`, not 360° or a false exact conjunction. This is a numerical
approximation, not an exact real angle. Equal rotations preserve the mathematical
difference, but rotating floats may already round inputs; bitwise invariance is
not promised.

The phase formatter prints the stored float without arcsecond truncation. Labels
never come from rounded text. Both formatters require current catalog names in
`en` or `zh-CN`; missing/stale names raise `ValueError`, missing IDs `KeyError`, and
invalid result/catalog types `TypeError`. Names' table delimiters and nonprinting
characters are escaped.
