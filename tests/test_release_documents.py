"""Candidate installation context and neutral snapshot labels. 候选安装语境与中性的快照标签。"""

import shutil
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UNITS = (
  "README.md",
  "README.zh-CN.md",
  "docs/en/contributing.md",
  "docs/zh-CN/contributing.md",
  "docs/en/knowledge.md",
  "docs/zh-CN/knowledge.md",
  "docs/index.md",
  "docs/_templates/site_index.html",
  "docs/conf.py",
  "pyproject.toml",
)
OLD_SENTENCES = (
  "This checkout prepares version `0.1.0`, which is not yet published on PyPI.",
  "当前源码准备版本 `0.1.0`，尚未发布到 PyPI；",
  "is labeled as development documentation.",
  "并明确标为开发文档。",
)


def _contract(root: Path) -> None:
  project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  for unit in UNITS:
    text = " ".join((root / unit).read_text(encoding="utf-8").split())
    assert not any(" ".join(sentence.split()) in text for sentence in OLD_SENTENCES), unit
  command = f'pip install "{project["name"]}=={project["version"]}"'
  for name, heading, guard, source_link in (
    (
      "README.md",
      "Install a release",
      f"After {project['version']} is published on PyPI",
      "https://0xf3cd.github.io/astrology/README.html#install-from-source",
    ),
    (
      "README.zh-CN.md",
      "安装发行版",
      f"{project['version']} 发布到 PyPI 后",
      "https://0xf3cd.github.io/astrology/README.zh-CN.html#install-from-source-zh-cn",
    ),
  ):
    text = (root / name).read_text(encoding="utf-8")
    assert f"\n## {heading}\n" in text, name
    installation = text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]
    assert guard in installation, name
    for python in (".venv/bin/python", ".venv\\Scripts\\python.exe"):
      index_command = f"{python} -m {command}"
      assert index_command in installation, name
      context = installation[: installation.index(index_command)]
      assert guard in context and f"]({source_link})" in context, name
    normalized = " ".join(installation.split()).casefold()
    assert not any(
      claim.casefold() in normalized
      for claim in (
        f"install the published v{project['version']}",
        f"install the published {project['version']}",
        f"以下命令安装已发布的 v{project['version']}",
        f"以下命令安装已发布的 {project['version']}",
      )
    ), name
    assert "`astrology`" in text
  for name in ("docs/index.md", "docs/_templates/site_index.html"):
    text = (root / name).read_text(encoding="utf-8")
    assert "Source documentation snapshot" in text and "源码文档快照" in text, name
    assert "开发版文档" not in text and "not a package release" not in text, name
  assert "(development / 开发版)" not in (root / "docs/conf.py").read_text(encoding="utf-8")


def test_release_installation_and_snapshot_units() -> None:
  _contract(ROOT)


@pytest.fixture
def documents(tmp_path: Path) -> Path:
  for name in UNITS:
    destination = tmp_path / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / name, destination)
  return tmp_path


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("sentence", OLD_SENTENCES)
def test_every_status_unit_rejects_actual_old_status_claims(
  documents: Path, unit: str, sentence: str
) -> None:
  _contract(documents)
  path = documents / unit
  if unit == "pyproject.toml":
    sentence = "# " + " ".join(sentence.split())
  with path.open("a", encoding="utf-8") as stream:
    stream.write("\n" + sentence + "\n")
  with pytest.raises(AssertionError):
    _contract(documents)


@pytest.mark.parametrize(
  "unit",
  [
    "docs/index.md",
    "docs/_templates/site_index.html",
    "docs/conf.py",
  ],
)
def test_neutral_labels_are_required(documents: Path, unit: str) -> None:
  path = documents / unit
  text = path.read_text(encoding="utf-8")
  if unit == "docs/conf.py":
    text += '\nhtml_title = "(development / 开发版)"\n'
  else:
    text = text.replace("源码文档快照", "开发版文档")
  path.write_text(text, encoding="utf-8")
  with pytest.raises(AssertionError):
    _contract(documents)


@pytest.mark.parametrize("unit", ["README.md", "README.zh-CN.md"])
@pytest.mark.parametrize("next_version", [False, True])
@pytest.mark.parametrize("python", [".venv/bin/python", ".venv\\Scripts\\python.exe"])
@pytest.mark.parametrize("defect", ["name", "version", "unpinned"])
def test_readme_install_mutation_tracks_fixture_version(
  documents: Path, unit: str, next_version: bool, python: str, defect: str
) -> None:
  project_path = documents / "pyproject.toml"
  project = tomllib.loads(project_path.read_text(encoding="utf-8"))["project"]
  if next_version:
    current = project["version"]
    future = f"{int(current.split('.')[0]) + 1}.0.0"
    assert current != future
    text = project_path.read_text(encoding="utf-8")
    old_version = f'version = "{current}"'
    assert old_version in text
    project_path.write_text(text.replace(old_version, f'version = "{future}"'), encoding="utf-8")
    for name in ("README.md", "README.zh-CN.md"):
      path = documents / name
      text = path.read_text(encoding="utf-8")
      assert f"{project['name']}=={current}" in text
      path.write_text(text.replace(current, future), encoding="utf-8")
  _contract(documents)
  project = tomllib.loads(project_path.read_text(encoding="utf-8"))["project"]
  command = f'{python} -m pip install "{project["name"]}=={project["version"]}"'
  path = documents / unit
  text = path.read_text(encoding="utf-8")
  assert command in text
  if defect == "name":
    replacement = f'{python} -m pip install "astrology"'
  elif defect == "version":
    replacement = f'{python} -m pip install "{project["name"]}==0.0.0"'
  else:
    replacement = f'{python} -m pip install "{project["name"]}"'
  changed = text.replace(command, replacement)
  assert changed != text and command not in changed
  path.write_text(changed, encoding="utf-8")
  with pytest.raises(AssertionError):
    _contract(documents)


@pytest.mark.parametrize("unit", ["README.md", "README.zh-CN.md"])
@pytest.mark.parametrize(
  "defect",
  [
    "missing_guard",
    "guard_after_first_command",
    "guard_after_both_commands",
    "guard_in_source_section",
    "wrong_guard_version",
    "unversioned_guard",
    "missing_source_link",
    "already_published",
  ],
)
def test_candidate_installation_context_rejects_misleading_edits(
  documents: Path, unit: str, defect: str
) -> None:
  _contract(documents)
  project = tomllib.loads((documents / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  version = project["version"]
  english = unit == "README.md"
  guard = f"After {version} is published on PyPI" if english else f"{version} 发布到 PyPI 后"
  path = documents / unit
  text = path.read_text(encoding="utf-8")
  assert text.count(guard) == 1
  if defect == "missing_guard":
    changed = text.replace(guard, "")
  elif defect in ("guard_after_first_command", "guard_after_both_commands"):
    python = (
      ".venv/bin/python" if defect == "guard_after_first_command" else ".venv\\Scripts\\python.exe"
    )
    command = f'{python} -m pip install "{project["name"]}=={version}"'
    changed = text.replace(guard, "").replace(command, command + "\n" + guard)
  elif defect == "guard_in_source_section":
    heading = "## Install from source" if english else "## 从源码安装"
    changed = text.replace(guard, "").replace(heading, heading + "\n" + guard)
  elif defect == "wrong_guard_version":
    changed = text.replace(guard, guard.replace(version, "0.0.0"))
  elif defect == "unversioned_guard":
    changed = text.replace(guard, "After publication on PyPI" if english else "发布到 PyPI 后")
  elif defect == "missing_source_link":
    link = (
      "https://0xf3cd.github.io/astrology/README.html#install-from-source"
      if english
      else "https://0xf3cd.github.io/astrology/README.zh-CN.html#install-from-source-zh-cn"
    )
    assert link in text
    changed = text.replace(link, "")
  else:
    claim = (
      f"The commands below install the published v{version}."
      if english
      else f"以下命令安装已发布的 {version}。"
    )
    changed = text.replace(guard, claim + "\n" + guard)
  assert changed != text
  path.write_text(changed, encoding="utf-8")
  with pytest.raises(AssertionError):
    _contract(documents)


@pytest.mark.parametrize("unit", ["README.md", "README.zh-CN.md"])
@pytest.mark.parametrize(
  "sentence",
  [
    "This candidate has not been published on PyPI.",
    "These are source-install instructions, not a claim that the candidate can be installed from the package index.",
    "此候选尚未发布到 PyPI；",
    "这些命令从源码安装，不表示候选包已可从包索引安装。",
  ],
)
def test_truthful_candidate_wording_is_allowed(documents: Path, unit: str, sentence: str) -> None:
  path = documents / unit
  with path.open("a", encoding="utf-8") as stream:
    stream.write("\n" + sentence + "\n")
  _contract(documents)
