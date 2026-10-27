# Traditional sign rulers and four statuses

[简体中文](../zh-CN/dignities.md) · [API](reference.md) · [Knowledge](knowledge.md)

These source-checkout APIs are planned for 0.3.0 and are not in the published
0.2.0 package. They use the rules recorded in William Lilly's *Christian
Astrology* (London, 1647), for Sun, Moon, Mercury, Venus, Mars, Jupiter and Saturn,
the seven classical planets in traditional astrology.

The assessments belong to traditional essential dignities and debilities. This
API assesses only four sign-level statuses: domicile, exaltation, detriment and
fall.

`rule.lilly1647.essential_dignities` identifies this fixed rule set in the
implementation, `HouseRulers.rule_id` and the knowledge catalog. It does not load
or select rules dynamically.

## Query a sign without a chart

```{doctest}
>>> from astrology import Body, Sign, DignityStatus, sign_ruler, essential_dignities
>>> sign_ruler(Sign.SCORPIO) is Body.MARS
True
>>> essential_dignities(Body.MERCURY, Sign.VIRGO)
(<DignityStatus.DOMICILE: 'domicile'>, <DignityStatus.EXALTATION: 'exaltation'>)
>>> essential_dignities(Body.MERCURY, Sign.PISCES)
(<DignityStatus.DETRIMENT: 'detriment'>, <DignityStatus.FALL: 'fall'>)
>>> essential_dignities(Body.SUN, Sign.TAURUS)
()
```

Every match is returned, in domicile, exaltation, detriment, fall order. Domicile
means a planet occupies one of its own zodiacal houses (its ruled signs), not a
numbered chart house. Exaltation applies throughout the assigned sign. Detriment
is opposite a domicile; fall is opposite exaltation. See the
{ref}`generated twelve-sign table <catalog-en-rule-lilly1647-essential-dignities>`.

An empty tuple means **none of these four**. It does not establish peregrine
status, since other dignities are not assessed. Strings, nodes and unrelated enums
raise `TypeError`; use exact `Body` and `Sign` members. Valid outer-planet bodies
(`URANUS`, `NEPTUNE`, `PLUTO`) raise `ValueError` naming the unsupported body,
rather than returning an empty assessment. Scorpio uses Mars, Aquarius Saturn
and Pisces Jupiter; there is no modern co-ruler substitution.

## Follow the rulers in an existing chart

Calculate this synthetic example once, then read its existing cusps and placements:

```{doctest}
>>> from datetime import date, time, timedelta
>>> from astrology import (BirthRecord, FixedOffset, Location, ChartConfig, HouseSystem,
...     natal_chart, prepare_natal_input, HouseRulers, format_house_rulers, load_catalog)
>>> chart = natal_chart(prepare_natal_input(BirthRecord(date(2000, 1, 1), time(12),
...     FixedOffset(timedelta(0)), Location(0, 0))),
...     ChartConfig(HouseSystem.WHOLE_SIGN, (Body.SUN, Body.MERCURY), ()))
>>> result = HouseRulers(chart)
>>> result.chart is chart, len(result.houses), result.rule_id
(True, 12, 'rule.lilly1647.essential_dignities')
>>> first = result.houses[0]
>>> first.house, first.cusp_sign.value, first.ruler.value, first.placement, first.statuses
(1, 'aries', 'mars', None, None)
>>> third = result.houses[2]
>>> third.ruler.value, third.placement is chart.placements[1], third.statuses
('mercury', True, ())
>>> catalog = load_catalog()
>>> text = format_house_rulers(result, catalog)
>>> print("\n".join(text.splitlines()[:5]))
House rulers (Lilly 1647)
House system: Whole Sign
Rule: rule.lilly1647.essential_dignities
House | Cusp sign | Ruler | Ruler placement | Statuses
1 | Aries | Mars | Not calculated | Not calculated
>>> text.splitlines()[6].endswith("None of these four")
True
```

`HouseRulers` retains only the supplied `NatalChart`. Each `houses` access builds
twelve new records in house order; repeated accesses return equal tuples.
It uses **actual cusp longitudes**, not ASC or MC as replacements for the first
or tenth cusp. Repeated cusp signs remain separate
records. The requested house system and raw astronomy are unchanged. No ruler is
recalculated or added to the chart; present placements are the original objects.

`placement=None` and `statuses=None` mean that the ruler was not calculated.
An available placement with `statuses=()` was assessed and matched none of the
four. The formatter distinguishes these states and prints every simultaneous
status. It displays the ruler's sign, unrounded degree within sign and numbered
house. Status assessment uses the sign alone, not the displayed degree.

### Construct an individual record

```{doctest}
>>> from astrology import HouseRuler, Placement
>>> placement = Placement(Body.MERCURY, Sign.VIRGO, 0, 6)
>>> record = HouseRuler(house=3, cusp_sign=Sign.GEMINI, placement=placement)
>>> record.ruler is Body.MERCURY, record.statuses == essential_dignities(Body.MERCURY, Sign.VIRGO)
(True, True)
>>> record.placement is placement
True
```

`HouseRuler` is immutable. Its `ruler` and `statuses` derive from its fields and
cannot be supplied separately. A wrong field type raises `TypeError`, including
a boolean house number. A house outside 1–12 or a placement identifying a different
ruler raises `ValueError`. A low-level record does not authenticate chart origin
or bind a cusp sign to a house number; `HouseRulers(chart)` performs that composition.
It rejects a non-`NatalChart` with `TypeError` and accepts no separate tuple of house records.
Runtime checks also run under `python -O`.

`format_house_rulers` requires a supplied `Catalog` and current names in `en` or
`zh-CN`. Invalid result/catalog types raise `TypeError`, invalid languages and
missing/stale names `ValueError`. Missing sign/status IDs raise `KeyError`.
If the catalog has no unique concept for a ruler or house system, formatting raises
`ValueError`. Table delimiters and nonprinting characters in names are escaped.
Formatting performs no resource I/O;
pure queries and chart composition do not initialize native astronomy.

## Source and limits

The {ref}`source record <catalog-en-source-lilly-christian-astrology-1647>` locates
the inspected Wellcome scan, its 1647 imprint, image hashes and Public Domain Mark
statement. Book I, chapters VIII–XIV provide the planet assignments; chapter XVIII,
printed pp.102 and 104–105 explain sign-wide exaltation and the opposite-sign
relations. Six detriments are explicit in the planet chapters; Saturn's is derived
from its domiciles and the stated relation. The generated table is a project
expansion of those assignments, not a transcription of every printed table cell.

Three short English excerpts are distinguished from credited Chinese translations
and project explanations. Their locators state the fragment boundaries; long-s,
line breaks and astrological glyphs have the recorded normalization. A second
scan corroborates readings of the same historical witness, not an independent
tradition. Lilly calls his table Ptolemaic; Ptolemy's original was not inspected.

This API does not assess exact exaltation degrees, sect, node dignities, triplicity,
bounds/terms, faces, reception, aggregate scores or interpretation. Day/night
domicile labels are not extra conditions on the four sign queries. Source
verification records what the edition states, not empirical validity.

Catalog status concepts have IDs `dignity_status.<value>` and no request-configuration
link. `entry.essential_dignities` has complete query prerequisites but remains
`reference_only` and `not_assessed`. Catalog retrieval does not evaluate a chart.
