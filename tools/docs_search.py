"""English stemming with matching Python/JavaScript Chinese character bigrams.

保留英文词干处理，Python 与 JavaScript 均采用中文相邻双字切分。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from sphinx.search.en import SearchEnglish

_HAN_RANGE = r"\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f"
_HAN = f"[{_HAN_RANGE}]"
_BLOCKS = re.compile(f"{_HAN}+|[^{_HAN_RANGE}]+")
_JS_HAN = _HAN_RANGE.replace(r"\U00020000", r"\u{20000}").replace(r"\U0002fa1f", r"\u{2fa1f}")

JS_SPLITTER = r"""function splitQuery(query) {
  const hanRange = HAN_RANGE;
  const blocks = query.match(new RegExp("[" + hanRange + "]+|[^" + hanRange + "]+", "gu")) || [];
  const isHan = new RegExp("^[" + hanRange + "]", "u");
  const result = [];
  for (const block of blocks) {
    if (isHan.test(block)) {
      const chars = Array.from(block);
      if (chars.length === 1) result.push(block);
      else for (let i = 0; i < chars.length - 1; i++) result.push(chars[i] + chars[i + 1]);
    } else {
      result.push(...block.split(/[^\p{Letter}\p{Number}_\p{Emoji_Presentation}]+/gu).filter(Boolean));
    }
  }
  return result;
}""".replace("HAN_RANGE", json.dumps(_JS_HAN))


class BilingualSearch(SearchEnglish):
  """Use adjacent Han pairs, not dictionary/phrase segmentation; keep singleton blocks.

  使用相邻汉字双字切分，不做词典或短语分词；单字块保留。
  """

  lang = "en-zh-bigrams"
  # Sphinx 9 uses this name to select EnglishStemmer in the generated script.
  language_name = "English"
  js_splitter_code = JS_SPLITTER

  def split(self, text: str) -> list[str]:
    """Split Han runs into pairs and leave other words to English. 汉字连续段切为双字，其余沿用英文分词。"""
    result: list[str] = []
    for block in _BLOCKS.findall(text):
      if re.match(_HAN, block):
        if len(block) == 1:
          result.append(block)
        else:
          result.extend(block[index : index + 2] for index in range(len(block) - 1))
      else:
        result.extend(super().split(block))
    return result


def read_search_index(path: Path) -> dict[str, object]:
  """Read the actual generated Sphinx JSON payload, rejecting a missing wrapper.

  读取实际生成的 Sphinx JSON 载荷，缺少封装时拒绝。
  """
  text = path.read_text(encoding="utf-8").strip().removesuffix(";")
  if not text.startswith("Search.setIndex(") or not text.endswith(")"):
    raise ValueError("Invalid generated search index wrapper")
  value: object = json.loads(text[len("Search.setIndex(") : -1])
  if not isinstance(value, dict):
    raise ValueError("Generated search index is not an object")
  return value


def check_search_html(directory: Path) -> None:
  """Require generated query/index tokens, expected documents and the emitted JS handoff.

  检查生成的查询与索引词、预期文档及输出的 JavaScript 衔接。
  """
  data = read_search_index(directory / "searchindex.js")
  docnames = data["docnames"]
  terms, titleterms = data["terms"], data["titleterms"]
  if (
    not isinstance(docnames, list)
    or not isinstance(terms, dict)
    or not isinstance(titleterms, dict)
  ):
    raise ValueError("Invalid generated search document/term tables")
  language = BilingualSearch({})
  script = (directory / "_static/language_data.js").read_text(encoding="utf-8")
  if JS_SPLITTER not in script:
    raise ValueError("Missing or divergent generated JavaScript splitter")
  if "window.Stemmer" in script:
    if "window.Stemmer = EnglishStemmer;" not in script:
      raise ValueError("Generated search does not select the English stemmer")
  elif "var Stemmer = function()" not in script or "Porter Stemmer" not in script:
    raise ValueError("Missing generated English stemmer")

  def matches(query: str) -> set[str]:
    candidates: set[str] | None = None
    for word in language.split(query.lower()):
      token = language.stem(word)
      matched = set()
      for table in (terms, titleterms):
        value = table.get(token, [])
        for index in [value] if type(value) is int else value:
          matched.add(str(docnames[index]))
      candidates = matched if candidates is None else candidates & matched
    return candidates or set()

  for query, document in (
    ("太阳", "docs/zh-CN/catalog"),
    ("日轮", "docs/zh-CN/catalog"),
    ("日", "docs/zh-CN/catalog"),
    ("月", "docs/zh-CN/catalog"),
    ("牡羊座", "docs/zh-CN/catalog"),
    ("合相位", "docs/zh-CN/catalog"),
    ("平均北交点", "docs/zh-CN/catalog"),
    ("普拉西度制", "docs/zh-CN/catalog"),
    ("conjunctions", "docs/en/catalog"),
    ("houses", "docs/en/catalog"),
  ):
    if document not in matches(query):
      raise ValueError(f"Generated search misses {query!r} in {document}")
  if matches("龘靐齉"):
    raise ValueError("Generated search matches an unrelated negative query")
