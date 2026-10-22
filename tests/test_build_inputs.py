"""Check workflow and documentation inputs. 检查工作流和文档构建输入。"""

import re
import shutil
from io import StringIO
from pathlib import Path
from runpy import run_path

import pytest
from jinja2 import DictLoader, Environment
from sphinx.application import Sphinx
from sphinx.project import Project

from tools.check import ROOT


def test_every_ci_job_selects_its_reviewed_uv_archive_digest() -> None:
  workflow = (ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8")
  entries = re.findall(
    r'(?m)^          - os: (\S+)\n            python: "([^"]+)"\n'
    r"            uv-artifact: (\S+)\n            uv-checksum: ([0-9a-f]{64})$",
    workflow,
  )
  linux = (
    "uv-x86_64-unknown-linux-gnu.tar.gz",
    "68a509da24b06b4223a1c0175fb5eb5bc79342b76cbeff0cfe51ac3f5b17b6b2",
  )
  assert entries == [
    ("ubuntu-latest", "3.11", *linux),
    ("ubuntu-latest", "3.14", *linux),
    (
      "macos-latest",
      "3.14",
      "uv-aarch64-apple-darwin.tar.gz",
      "5bb0e5fe008a773c3dbcb97ff79cd89e1241464fe9d2f986d52ad8f1b037bd62",
    ),
    (
      "windows-latest",
      "3.14",
      "uv-x86_64-pc-windows-msvc.zip",
      "4c4d49d8738847d9b71ba319e49a5688c93eac0fe6204b1df24e98528dddf39a",
    ),
  ]
  setup = workflow.partition(
    "      - uses: astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78"
  )[2].partition("      - run:")[0]
  assert re.search(r"(?m)^          checksum: \$\{\{ matrix.uv-checksum \}\}$", setup)
  assert '          version: "0.12.5"\n' in setup
  assert "          enable-cache: false\n" in setup
  assert (
    "          RUNNER_TOOL_CACHE: ${{ runner.temp }}/astrology-uv-${{ github.run_id }}"
    "-${{ github.run_attempt }}\n"
  ) in setup


def test_document_discovery_keeps_all_project_pages_and_ignores_other_environments(
  tmp_path: Path,
) -> None:
  source = tmp_path / "source"
  shutil.copytree(ROOT / "docs", source / "docs", ignore=shutil.ignore_patterns("__pycache__"))
  for filename in ("README.md", "README.zh-CN.md", "pyproject.toml"):
    shutil.copy2(ROOT / filename, source / filename)
  stray = source / "another-environment/share/doc/unrelated.rst"
  stray.parent.mkdir(parents=True)
  stray.write_text(".. unknown-directive::\n", encoding="utf-8")
  app = Sphinx(
    srcdir=source,
    confdir=source / "docs",
    outdir=tmp_path / "html",
    doctreedir=tmp_path / "doctrees",
    buildername="html",
    freshenv=True,
    status=StringIO(),
    warning=StringIO(),
    warningiserror=True,
  )
  config = app.config
  project = Project(source, config.source_suffix)
  found = project.discover(config.exclude_patterns, config.include_patterns)
  expected = {"README", "README.zh-CN"} | {
    path.relative_to(ROOT).with_suffix("").as_posix() for path in (ROOT / "docs").rglob("*.md")
  }
  assert found == expected
  assert config.root_doc in found


@pytest.mark.parametrize(
  "revision", ["a" * 39, "a" * 41, "A" * 40, "g" * 40, "a" * 40 + "\n", "main", "$(command)"]
)
def test_documentation_rejects_invalid_source_revision(
  monkeypatch: pytest.MonkeyPatch, revision: str
) -> None:
  monkeypatch.setenv("ASTROLOGY_DOCS_SOURCE_SHA", revision)
  with pytest.raises(ValueError, match="full lowercase Git commit SHA"):
    run_path(str(ROOT / "docs/conf.py"))


@pytest.mark.parametrize("revision", ["", "a" * 40])
def test_snapshot_template_uses_metadata_urls_and_explicit_environment_interpreters(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, revision: str
) -> None:
  docs = tmp_path / "docs"
  docs.mkdir()
  shutil.copyfile(ROOT / "docs/conf.py", docs / "conf.py")
  (tmp_path / "pyproject.toml").write_text(
    '[project.urls]\nDocumentation = "https://example.org/docs/"\n'
    'Repository = "https://example.org/project"\n',
    encoding="utf-8",
  )
  monkeypatch.setenv("ASTROLOGY_DOCS_SOURCE_SHA", revision)
  config = run_path(str(docs / "conf.py"))
  assert config["html_baseurl"] == "https://example.org/docs/"
  context = config["html_context"]
  archive = f"https://example.org/project/archive/{revision}.zip" if revision else ""
  tree = f"https://example.org/project/tree/{revision}" if revision else ""
  assert context["source_archive_url"] == archive
  assert context["source_tree_url"] == tree
  template = (ROOT / "docs/_templates/site_index.html").read_text(encoding="utf-8")
  environment = Environment(
    loader=DictLoader(
      {
        "layout.html": "<title>{{ title }}</title>{% block body %}{% endblock %}",
        "site_index.html": template,
      }
    )
  )
  page = environment.get_template("site_index.html").render(
    project="celestial-astrology", release="0.1.0", pathto=lambda name: name + ".html", **context
  )
  assert "<title>Documentation / 文档</title>" in page
  commands = re.findall(r"<pre>(.*?)</pre>", page, flags=re.DOTALL)
  if revision:
    assert commands == [
      f'.venv/bin/python -m pip install "{archive}"',
      f'.venv\\Scripts\\python.exe -m pip install "{archive}"',
    ]
    assert f'href="{tree}"' in page
    chinese = re.findall(r'<p lang="zh-CN">(.*?)</p>', page, flags=re.DOTALL)
    assert any('href="README.zh-CN.html"' in paragraph for paragraph in chinese)
  else:
    assert not commands
    assert "This local build has no fixed source revision" in page
