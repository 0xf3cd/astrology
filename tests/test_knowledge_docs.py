"""Discriminating catalog/search artifact checks. 目录及搜索产物检查的区分力。"""

import html
import json
from dataclasses import fields, is_dataclass, replace
from pathlib import Path

import pytest

from astrology.knowledge import Entry, LocalizedText, Source, load_catalog
from astrology.knowledge.records import Language
from tools.catalog_docs import catalog_anchor, check_catalog_data, localized_texts, render_catalog
from tools.check import check_catalog_html
from tools.docs_search import JS_SPLITTER, BilingualSearch, check_search_html, read_search_index


def test_all_localized_fields_and_configuration_coverage() -> None:
  catalog = load_catalog()
  check_catalog_data(catalog)
  assert any("excerpt" in path for path, _ in localized_texts(catalog))
  with pytest.raises(ValueError, match="configuration identity"):
    check_catalog_data(replace(catalog, concepts=catalog.concepts[1:], variants=(), entries=()))


@pytest.mark.parametrize("stale", [False, True])
@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_translation_gap_is_visible_and_not_complete(stale: bool, language: Language) -> None:
  catalog = load_catalog()
  name = replace(catalog.concepts[0].name, revision=2) if stale else LocalizedText("Sun")
  concept = replace(catalog.concepts[0], name=name)
  changed = replace(catalog, concepts=(concept, *catalog.concepts[1:]))
  with pytest.raises(ValueError, match="Required translation"):
    check_catalog_data(changed)
  rendered = render_catalog(changed, language, "0.0.0")
  names = next(line for line in rendered.splitlines() if line.startswith("Chinese names"))
  assert ("[stale] 太阳" if stale else "[missing]") in names


def test_anchor_normalization_collision_is_rejected() -> None:
  catalog = load_catalog()
  first = replace(catalog.concepts[0], identifier="test.one", en_aliases=(), zh_aliases=())
  second = replace(first, identifier="test-one")
  with pytest.raises(ValueError, match="anchor normalization"):
    render_catalog(replace(catalog, concepts=(first, second), variants=(), entries=()), "en", "0")


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_generation_covers_every_record(language: Language) -> None:
  catalog = load_catalog()
  rendered = render_catalog(catalog, language, "code-test")
  assert "code=code-test" in rendered and f"corpus={catalog.version}" in rendered
  for group in (catalog.concepts, catalog.variants, catalog.sources, catalog.entries):
    for record in group:
      assert f"({catalog_anchor(record.identifier, language)})=" in rendered
  assert "astrology.config.Body.SUN" in rendered
  assert "source_verification=verified" in rendered
  assert "chart=not_assessed" in rendered
  assert "Original excerpt (English)" in rendered
  assert "project Chinese translation of Ashmand's English" in rendered
  assert "No prerequisites recorded / 未记录前提" in rendered


def _strings(value: object, language: Language) -> list[str]:
  if isinstance(value, LocalizedText):
    return [value.text(language) or "", value.translation_credit or "", value.en]
  if isinstance(value, str):
    return [value]
  if isinstance(value, (list, tuple)):
    return [text for item in value for text in _strings(item, language)]
  if is_dataclass(value) and not isinstance(value, type):
    return [
      text for field in fields(value) for text in _strings(getattr(value, field.name), language)
    ]
  return []


@pytest.fixture
def catalog_html(tmp_path: Path) -> Path:
  catalog = load_catalog()
  languages: tuple[Language, ...] = ("en", "zh-CN")
  for language in languages:
    other = "zh-CN" if language == "en" else "en"
    blocks = []
    for group in (catalog.concepts, catalog.variants, catalog.sources, catalog.entries):
      for record in group:
        content = _strings(record, language)
        if (configuration := getattr(record, "configuration", None)) is not None:
          content.append(f"astrology.config.{type(configuration).__name__}.{configuration.name}")
        if hasattr(record, "kind"):
          content.append(f"kind={record.kind}")
        if isinstance(record, Source):
          content.extend(
            (f"source_verification={record.verification}", f"language={record.language}")
          )
        if isinstance(record, Entry):
          content.extend(
            (
              f"prerequisites={record.prerequisite_status}",
              f"output={record.output_eligibility}",
              f"chart={record.chart_applicability}",
            )
          )
        source_link = (
          f'<a href="{html.escape(record.url)}"><code>{html.escape(record.url)}</code></a>'
          if isinstance(record, Source)
          else ""
        )
        blocks.append(
          f'<section id="{catalog_anchor(record.identifier, language)}">'
          + html.escape("\n".join(content))
          + source_link
          + "</section>"
        )
    directory = tmp_path / "docs" / language
    directory.mkdir(parents=True)
    (directory / "catalog.html").write_text(
      f'<html lang="{language}"><a href="../{other}/catalog.html">Other</a>'
      f"<p>code=0.0.0 corpus={catalog.version}</p>" + "".join(blocks) + "</html>",
      encoding="utf-8",
    )
  return tmp_path


def test_complete_catalog_html(catalog_html: Path) -> None:
  check_catalog_html(catalog_html)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize(
  "defect",
  [
    "anchor",
    "description",
    "alias",
    "locator",
    "condition",
    "version",
    "language",
    "navigation",
    "link",
    "source_label",
  ],
)
def test_catalog_artifact_defects(catalog_html: Path, language: Language, defect: str) -> None:
  page = catalog_html / "docs" / language / "catalog.html"
  text = page.read_text(encoding="utf-8")
  replacements = {
    "anchor": (f'id="{catalog_anchor("body.sun", language)}"', 'id="omitted"'),
    "description": (
      "Physical-body request for the Sun. The chart adapter calculates its apparent geocentric"
      " position; this catalog computes none.",
      "omitted",
    ),
    "alias": ("Sol", "omitted"),
    "locator": ("complete equinoctial-sign sentence", "omitted"),
    "condition": ("makes the day and night equal.", "omitted"),
    "version": ("corpus=", "omitted="),
    "language": (f'lang="{language}"', 'lang="fr"'),
    "navigation": ("/catalog.html", "/other.html"),
    "link": ("</html>", '<a href="#catalog-lost">lost</a></html>'),
    "source_label": (
      "<code>https://commons.wikimedia.org/w/index.php?title=File:Ptolemy%27s",
      "<code>https://commons.wikimedia.org/w/index.php?title=File:Ptolemy's",
    ),
  }
  old, new = replacements[defect]
  # Chinese fixtures retain English originals too; removing the selected description must target Chinese.
  if language == "zh-CN" and defect == "description":
    old = "太阳的物理天体请求。排盘适配层计算它的地心视位置；本目录不计算位置。"
  page.write_text(text.replace(old, new), encoding="utf-8")
  with pytest.raises(ValueError):
    check_catalog_html(catalog_html)


@pytest.mark.parametrize(
  "text,tokens",
  [
    ("太阳位于白羊座 houses", ["太阳", "阳位", "位于", "于白", "白羊", "羊座", "houses"]),
    ("日 / 月", ["日", "月"]),
    ("合相位", ["合相", "相位"]),
    ("\U00020000\U00020001", ["\U00020000\U00020001"]),
    ("Placidus Body.SUN", ["Placidus", "Body", "SUN"]),
  ],
)
def test_splitter_known_tokens(text: str, tokens: list[str]) -> None:
  assert BilingualSearch({}).split(text) == tokens
  assert BilingualSearch({}).stem("houses") == "hous"


@pytest.fixture
def search_html(tmp_path: Path) -> Path:
  language = BilingualSearch({})
  words = "太阳 日轮 日 月 牡羊座 合相位 平均北交点 普拉西度制 conjunctions houses"
  terms = {language.stem(word): [0, 1] for word in language.split(words)}
  index = {"docnames": ["docs/zh-CN/catalog", "docs/en/catalog"], "terms": terms, "titleterms": {}}
  (tmp_path / "searchindex.js").write_text(
    "Search.setIndex(" + json.dumps(index) + ")", encoding="utf-8"
  )
  static = tmp_path / "_static"
  static.mkdir()
  (static / "language_data.js").write_text(
    JS_SPLITTER + "\nwindow.Stemmer = EnglishStemmer;", encoding="utf-8"
  )
  return tmp_path


def test_generated_search_contract(search_html: Path) -> None:
  check_search_html(search_html)


@pytest.mark.parametrize(
  "defect", ["wrapper", "term", "documents", "splitter", "stemmer", "negative"]
)
def test_search_artifact_defects(search_html: Path, defect: str) -> None:
  page = search_html / "searchindex.js"
  index = read_search_index(page)
  if defect == "wrapper":
    page.write_text("{}", encoding="utf-8")
  elif defect in ("splitter", "stemmer"):
    script = search_html / "_static/language_data.js"
    value = script.read_text(encoding="utf-8")
    script.write_text(
      value.replace("splitQuery", "lost")
      if defect == "splitter"
      else value.replace("EnglishStemmer", "OtherStemmer"),
      encoding="utf-8",
    )
  else:
    if defect == "term":
      index["terms"] = {}
    elif defect == "documents":
      index["docnames"] = ["other", "another"]
    else:
      terms = index["terms"]
      assert isinstance(terms, dict)
      terms.update({"龘靐": [0], "靐齉": [0]})
    page.write_text("Search.setIndex(" + json.dumps(index) + ")", encoding="utf-8")
  with pytest.raises(ValueError):
    check_search_html(search_html)


@pytest.mark.parametrize("index", [-1, 2, True, "0", None])
def test_invalid_search_document_index(search_html: Path, index: object) -> None:
  page = search_html / "searchindex.js"
  data = read_search_index(page)
  data["terms"] = {"太阳": [index]}
  page.write_text("Search.setIndex(" + json.dumps(data) + ")", encoding="utf-8")
  with pytest.raises(ValueError, match="Invalid generated search document index"):
    check_search_html(search_html)


@pytest.mark.parametrize("artifact", ["catalog", "search"])
def test_missing_knowledge_artifact(catalog_html: Path, search_html: Path, artifact: str) -> None:
  if artifact == "catalog":
    (catalog_html / "docs/en/catalog.html").unlink()
    with pytest.raises(FileNotFoundError):
      check_catalog_html(catalog_html)
  else:
    (search_html / "searchindex.js").unlink()
    with pytest.raises(FileNotFoundError):
      check_search_html(search_html)


def test_node_definition_relation_comes_from_configuration() -> None:
  from astrology.config import LunarNode

  catalog = load_catalog()
  node = catalog.concept("node.mean_ascending")
  assert node.configuration is LunarNode.MEAN_ASCENDING
  assert catalog.concept(node.related[0]).configuration is node.configuration.definition
  changed = replace(node, related=("node_definition.meeus_five_term_true",))
  values = tuple(changed if c.identifier == node.identifier else c for c in catalog.concepts)
  with pytest.raises(ValueError, match="owning node-definition relation"):
    check_catalog_data(replace(catalog, concepts=values))


@pytest.mark.parametrize("defect", ["missing", "duplicate", "extra", "wrong"])
def test_rule_configuration_coverage_is_independent_of_concepts(defect: str) -> None:
  from astrology import Body, HouseSystem

  catalog = load_catalog()
  first = catalog.variant("rule.house.whole_sign")
  variants = list(catalog.variants)
  if defect == "missing":
    variants.remove(first)
  elif defect == "duplicate":
    variants.append(replace(first, identifier="rule.synthetic.duplicate"))
  elif defect == "extra":
    variants.append(
      replace(
        first, identifier="rule.synthetic.body", concept_ids=("body.sun",), configuration=Body.SUN
      )
    )
  else:
    variants[0] = replace(first, concept_ids=("house.equal",), configuration=HouseSystem.EQUAL)
  changed = replace(catalog, variants=variants, entries=())
  with pytest.raises(ValueError, match="rule-bearing configuration"):
    check_catalog_data(changed)


def test_generated_aspect_angles_come_from_executable_rules() -> None:
  for language in ("en", "zh-CN"):
    rendered = render_catalog(load_catalog(), language, "0")
    for angle in (0, 60, 90, 120, 180):
      assert f"Exact angle / 精确角度：{angle}°" in rendered
