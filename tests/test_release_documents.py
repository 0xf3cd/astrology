"""Publication-neutral installation and snapshot text. 不依赖发布状态的安装及快照说明。"""

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
  "This candidate has not been published on PyPI.",
  "These are source-install instructions, not a claim that the candidate can be\ninstalled from the package index.",
  "当前源码准备版本 `0.1.0`，尚未发布到 PyPI；",
  "此候选尚未发布到 PyPI；",
  "这些命令从源码安装，不表示候选包已可从包索引安装。",
  "is labeled as development documentation.",
  "并明确标为开发文档。",
)


def _contract(root: Path) -> None:
  project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
  for unit in UNITS:
    text = " ".join((root / unit).read_text(encoding="utf-8").split())
    assert not any(" ".join(sentence.split()) in text for sentence in OLD_SENTENCES), unit
    assert "not yet published" not in text and "has not been published" not in text, unit
    assert "尚未发布" not in text, unit
  command = f'pip install "{project["name"]}=={project["version"]}"'
  for name in ("README.md", "README.zh-CN.md"):
    text = (root / name).read_text(encoding="utf-8")
    assert f".venv/bin/python -m {command}" in text
    assert f".venv\\Scripts\\python.exe -m {command}" in text
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
def test_readme_install_mutation_tracks_fixture_version(
  documents: Path, unit: str, next_version: bool
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
      pinned = f"{project['name']}=={current}"
      assert pinned in text
      path.write_text(text.replace(pinned, f"{project['name']}=={future}"), encoding="utf-8")
  _contract(documents)
  project = tomllib.loads(project_path.read_text(encoding="utf-8"))["project"]
  command = f'pip install "{project["name"]}=={project["version"]}"'
  path = documents / unit
  text = path.read_text(encoding="utf-8")
  assert command in text
  changed = text.replace(command, 'pip install "astrology"')
  assert changed != text and command not in changed
  path.write_text(changed, encoding="utf-8")
  with pytest.raises(AssertionError):
    _contract(documents)
