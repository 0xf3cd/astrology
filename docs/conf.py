"""Documentation build settings. 文档构建配置。"""

from importlib import metadata

from sphinx.application import Sphinx

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
