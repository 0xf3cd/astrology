"""Documentation build settings. 文档构建配置。"""

from importlib import metadata

from sphinx.application import Sphinx

from astrology.knowledge import load_catalog
from astrology.knowledge.records import Language
from tools.catalog_docs import render_catalog
from tools.docs_search import BilingualSearch

project = "astrology"
release = metadata.version("astrology")
extensions = ["myst_parser", "sphinx.ext.doctest", "sphinx.ext.autodoc", "sphinx.ext.intersphinx"]
intersphinx_mapping = {"python": ("https://docs.python.org/3.11", None)}
autodoc_typehints = "description"
root_doc = "docs/index"
exclude_patterns = [
  ".venv/**",
  ".review/**",
  ".git/**",
  ".pytest_cache/**",
  ".mypy_cache/**",
  ".ruff_cache/**",
  "build/**",
  "dist/**",
  "AGENTS.md",
]
myst_heading_anchors = 6
nitpicky = True
html_theme = "alabaster"
html_title = f"astrology {release} (development / 开发版)"
html_search_language = "en-zh-bigrams"


def _page_language(
  _app: Sphinx,
  pagename: str,
  _template: str,
  context: dict[str, object],
  _doctree: object,
) -> None:
  """Label each page's content language. 标记各页面的内容语言。"""
  chinese = pagename == "README.zh-CN" or pagename.startswith("docs/zh-CN/")
  context["language"] = "zh-CN" if chinese else "en"


def setup(app: Sphinx) -> None:
  """Apply language labels when rendering HTML. 渲染 HTML 时应用语言标签。"""
  app.connect("html-page-context", _page_language)
  app.add_search_language(BilingualSearch)
  app.connect("source-read", _catalog_content)


def _catalog_content(_app: Sphinx, docname: str, source: list[str]) -> None:
  """Generate only the paired catalog pages. 仅生成双语目录页面。"""
  if docname in ("docs/en/catalog", "docs/zh-CN/catalog"):
    language: Language = "zh-CN" if docname.startswith("docs/zh-CN/") else "en"
    source[0] += "\n" + render_catalog(load_catalog(), language, release)
