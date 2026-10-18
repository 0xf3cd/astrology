"""Documentation build settings. 文档构建配置。"""

from importlib import metadata

project = "astrology"
release = metadata.version("astrology")
extensions = ["myst_parser", "sphinx.ext.doctest"]
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
