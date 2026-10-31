"""Reader-path checks and their rejection cases. 读者路径检查及拒绝用例。"""

import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.check import (
  PACKAGE_FILES,
  check_readme_examples,
  check_site_html,
  check_wheel,
  readme_examples,
  readme_links,
)

BASE = "https://example.org/astrology/"
REPOSITORY = "https://github.com/example/astrology"
REVISION = "a" * 40


@pytest.mark.parametrize(
  "source",
  [
    "[Docs](lost.md)",
    "![image](/image.png)",
    '<a href="other.html">Page</a>',
    '<div><img src="image.png"></div>',
    "[x][ref]\n\n[ref]: #local",
    "[x](//example.org/path)",
    "[x](mailto:a@example.org)",
    '<a href="javascript:alert">x</a>',
  ],
)
def test_readme_rejects_context_dependent_targets(source: str) -> None:
  with pytest.raises(ValueError, match="absolute HTTP"):
    readme_links(source)


@pytest.mark.parametrize(
  "source", ["[x](https://user:secret@example.org/)", '<a href="https://user@example.org/">x</a>']
)
def test_readme_rejects_url_credentials(source: str) -> None:
  with pytest.raises(ValueError, match="credentials"):
    readme_links(source)


def test_readme_links_parse_markdown_and_raw_html_but_not_code() -> None:
  source = """[Docs](https://example.org/docs)
<a href="https://example.org/a?x=1&amp;y=2">x</a>

<div><img src="https://example.org/image.png" /></div>

`<img src="absent.png">` `[x](absent.md)`

```html
<a href="absent.html">code</a>
```
"""
  assert set(readme_links(source)) == {
    "https://example.org/docs",
    "https://example.org/a?x=1&y=2",
    "https://example.org/image.png",
  }
  with pytest.raises(ValueError, match="must link"):
    readme_links("No links")


@pytest.fixture
def site(tmp_path: Path) -> tuple[Path, Path]:
  root, output = tmp_path / "source", tmp_path / "html"
  root.mkdir()
  output.mkdir()
  (root / "pyproject.toml").write_text(
    '[project]\nname = "celestial-astrology"\nversion = "0.1.0"\n'
    f'[project.urls]\nDocumentation = "{BASE}"\nRepository = "{REPOSITORY}"\n',
    encoding="utf-8",
  )
  (root / "LICENSE").touch()
  (output / "index.html").write_text(
    f"<h1>celestial-astrology 0.1.0</h1><p>Source documentation snapshot / 源码文档快照</p>"
    '<a href="docs/en/index.html">English</a><a href="docs/zh-CN/index.html">中文</a>'
    f'<a href="{REPOSITORY}/tree/{REVISION}">{REVISION}</a>'
    f"<pre>{REPOSITORY}/archive/{REVISION}.zip</pre><p>安装这一源码快照</p>",
    encoding="utf-8",
  )
  for name, language, headings in (
    ("README.md", "en", ("Install from source", "First chart", "First knowledge lookup")),
    ("README.zh-CN.md", "zh-CN", ("从源码安装", "第一张命盘", "第一次查询知识")),
  ):
    text = "\n".join("## " + heading for heading in headings)
    targets = [
      "",
      "README.html",
      "README.zh-CN.html",
      f"docs/{language}/reference.html",
      f"docs/{language}/catalog.html",
      f"docs/{language}/catalog.html#catalog",
    ]
    text += "\n" + "\n".join(f"[link]({BASE}{target})" for target in targets)
    text += f"\n[License]({REPOSITORY}/blob/main/LICENSE)\n"
    (root / name).write_text(text, encoding="utf-8")
    for relative in targets[1:]:
      path = output / relative.partition("#")[0]
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text('<p id="catalog">content</p>', encoding="utf-8")
  for name in ("README.html", "README.zh-CN.html"):
    (output / name).write_text(
      '<a href="https://pypi.org/project/celestial-astrology/0.1.0/">Index</a>'
      '<pre>.venv/bin/python -m pip install "celestial-astrology==0.1.0"</pre>'
      '<pre>.venv\\Scripts\\python.exe -m pip install "celestial-astrology==0.1.0"</pre>',
      encoding="utf-8",
    )
  (output / "_images").mkdir()
  for language in ("en", "zh-CN"):
    (output / f"_images/svg-wheel-{language}.svg").write_text(
      '<svg><g data-role="label"><text>Delta-T model / astrology / celestial-calendar: '
      "algo5 / 0.1.0 / 0.8.0</text></g></svg>",
      encoding="utf-8",
    )
  return root, output


@pytest.mark.parametrize("name", ["README.html", "README.zh-CN.html"])
@pytest.mark.parametrize("defect", ["candidate", "pin", "index"])
def test_rendered_release_text_rejects_defects(
  site: tuple[Path, Path], name: str, defect: str
) -> None:
  root, output = site
  page = output / name
  text = page.read_text(encoding="utf-8")
  if defect == "candidate":
    text += "<p>New in 0.1.0 (in development) / 0.1.0（开发中）</p>"
  elif defect == "pin":
    text = text.replace("==0.1.0", "==0.0.0")
  else:
    text = text.replace("pypi.org/project/", "example.org/project/")
  page.write_text(text, encoding="utf-8")
  with pytest.raises(ValueError, match=r"candidate claim|installation|index page"):
    check_site_html(output, root=root)


def test_valid_bilingual_site_and_snapshot(site: tuple[Path, Path]) -> None:
  root, output = site
  check_site_html(output, root=root)
  check_site_html(output, root=root, source_revision=REVISION)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_non_readme_rendered_claims_are_rejected(site: tuple[Path, Path], language: str) -> None:
  root, output = site
  page = output / f"docs/{language}/catalog.html"
  page.write_text(page.read_text(encoding="utf-8") + "<p>0.1.0（开发中）</p>", encoding="utf-8")
  with pytest.raises(ValueError, match="candidate claim") as caught:
    check_site_html(output, root=root)
  assert f"docs/{language}/catalog.html" in str(caught.value)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_rendered_svg_versions_are_checked(site: tuple[Path, Path], language: str) -> None:
  root, output = site
  page = output / f"_images/svg-wheel-{language}.svg"
  page.write_text(page.read_text(encoding="utf-8").replace("0.1.0", "0.0.0"), encoding="utf-8")
  with pytest.raises(ValueError, match="SVG sample version"):
    check_site_html(output, root=root)


def test_rendered_svg_samples_cannot_all_be_missing(site: tuple[Path, Path]) -> None:
  root, output = site
  for page in (output / "_images").glob("*.svg"):
    page.unlink()
  with pytest.raises(ValueError, match="SVG samples are missing"):
    check_site_html(output, root=root)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_extra_unquoted_rendered_pin_is_rejected(site: tuple[Path, Path], language: str) -> None:
  root, output = site
  page = output / ("README.html" if language == "en" else "README.zh-CN.html")
  page.write_text(
    page.read_text(encoding="utf-8")
    + "<pre>.venv/bin/python -m pip install celestial-astrology==0.0.0</pre>",
    encoding="utf-8",
  )
  with pytest.raises(ValueError, match="inconsistent"):
    check_site_html(output, root=root)


@pytest.mark.parametrize(
  "old,new,message",
  [
    ("celestial-astrology 0.1.0", "celestial-astrology 0.0.0", "version"),
    ("源码文档快照", "", "source snapshot"),
    ("Source documentation snapshot", "", "source snapshot"),
    ("docs/zh-CN/index.html", "lost.html", "both languages"),
    (f"/tree/{REVISION}", "/tree/main", "fixed source"),
    (f"/archive/{REVISION}.zip", "/archive/main.zip", "fixed source"),
    ("安装这一源码快照", "", "fixed source"),
  ],
)
def test_site_root_contracts(site: tuple[Path, Path], old: str, new: str, message: str) -> None:
  root, output = site
  page = output / "index.html"
  page.write_text(page.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
  with pytest.raises(ValueError, match=message):
    check_site_html(output, root=root, source_revision=REVISION)


def test_site_requires_a_root_page(site: tuple[Path, Path]) -> None:
  root, output = site
  (output / "index.html").unlink()
  with pytest.raises(ValueError, match="site-root"):
    check_site_html(output, root=root)


@pytest.mark.parametrize("language,name", [("en", "README.md"), ("zh-CN", "README.zh-CN.md")])
@pytest.mark.parametrize(
  "defect,message",
  [
    ("section", "first-use sections"),
    ("counterpart", "counterpart navigation"),
    ("page", "absent built page"),
    ("anchor", "absent built anchor"),
    ("escape", "absent built page"),
    ("repository", "absent repository file"),
  ],
)
def test_both_reader_paths_reject_defects(
  site: tuple[Path, Path], language: str, name: str, defect: str, message: str
) -> None:
  root, output = site
  page = root / name
  text = page.read_text(encoding="utf-8")
  if defect == "section":
    text = text.replace("## ", "", 1)
  elif defect == "counterpart":
    text = text.replace(f"[link]({BASE}README.zh-CN.html)", "")
  elif defect == "page":
    (output / f"docs/{language}/reference.html").unlink()
  elif defect == "anchor":
    text = text.replace("#catalog", "#missing")
  elif defect == "escape":
    text += f"\n[escape]({BASE}%2e%2e/source/LICENSE)"
  elif defect == "repository":
    text = text.replace("/blob/main/LICENSE", "/blob/main/lost.txt")
  page.write_text(text, encoding="utf-8")
  with pytest.raises(ValueError, match=message):
    check_site_html(output, root=root)


@pytest.mark.parametrize(
  "body",
  [
    "[Docs](README.md)",
    '<a href="relative.html">API</a>',
    "[Docs](https://example.org/)\n0.1.0（开发中）",
  ],
)
def test_wheel_checks_actual_long_description(tmp_path: Path, body: str) -> None:
  wheel = tmp_path / "package.whl"
  for content_type, description in (
    ("text/markdown", "[Docs](https://example.org/)"),
    ("text/plain", body),
    ("text/markdown", body),
  ):
    with ZipFile(wheel, "w") as archive:
      for name in (*PACKAGE_FILES, "a.dist-info/licenses/LICENSE"):
        archive.writestr(name, "")
      archive.writestr(
        "a.dist-info/METADATA",
        f"Name: celestial-astrology\nVersion: 0.1.0\nDescription-Content-Type: {content_type}\n\n{description}\n",
      )
    if description == "[Docs](https://example.org/)":
      check_wheel(wheel, "0.1.0")
    else:
      with pytest.raises(ValueError, match=r"Markdown content|absolute HTTP|candidate claim"):
        check_wheel(wheel, "0.1.0")


def _scripts(code: str = "print('太阳')", expected: str = "太阳") -> str:
  return f"```python\n{code}\n```\n\nOutput:\n```text\n{expected}\n```\n" * 2


@pytest.mark.parametrize(
  "text", ["", "```python\npass\n```", _scripts()[: _scripts().find("Output:")]]
)
def test_readme_scripts_require_two_scripts_and_outputs(text: str) -> None:
  with pytest.raises(ValueError, match="README"):
    readme_examples(text)


@pytest.mark.parametrize("mode", [(), ("-O",)])
@pytest.mark.parametrize("failure", ["none", "output", "stderr", "exit"])
def test_readme_execution_compares_output_and_propagates_failure(
  tmp_path: Path, mode: tuple[str, ...], failure: str
) -> None:
  root, consumer = tmp_path / "source", tmp_path / "consumer"
  root.mkdir()
  consumer.mkdir()
  for name in ("README.md", "README.zh-CN.md"):
    code = "import sys\nprint('太阳')\nif not sys.flags.isolated:\n  raise SystemExit(13)"
    expected = "太阳"
    if name == "README.zh-CN.md":
      if failure == "output":
        expected = "Sun"
      elif failure == "stderr":
        code += "\nprint('warning', file=sys.stderr)"
      elif failure == "exit":
        code += "\nraise SystemExit(7)"
    (root / name).write_text(_scripts(code, expected), encoding="utf-8")
  if failure == "exit":
    with pytest.raises(subprocess.CalledProcessError) as error:
      check_readme_examples(root, Path(sys.executable), consumer, mode)
    assert error.value.returncode == 7
  elif failure == "none":
    check_readme_examples(root, Path(sys.executable), consumer, mode)
  else:
    with pytest.raises(ValueError, match=r"README\.zh-CN\.md"):
      check_readme_examples(root, Path(sys.executable), consumer, mode)
