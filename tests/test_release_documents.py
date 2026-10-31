"""Release-neutral source and actual metadata checks. 发布前后均适用的源码与实际元数据检查。"""

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tools.release_documents import (
  check_description,
  check_readme_installation,
  check_release_claims,
  check_release_documents,
)

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = (
  "New in 0.2.0 (in development)",
  "This checkout prepares version `0.2.0`.",
  "After 0.3.0 is published on PyPI, use these commands.",
  "These APIs are planned for 0.3.0.",
  "House overlays and comparison text are 0.3.0 additions still in development.",
  "This candidate has not been published on PyPI.",
  "0.2.0（开发中）新增：",
  "当前源码准备 0.3.0。",
  "计划随 0.3.0 交付。",
  "双盘落宫和比较文本是仍在开发中的 0.3.0 新增功能。",
  "0.3.0 发布到 PyPI 后，再安装。",
  "此候选尚未发布到 PyPI；",
)


@pytest.fixture
def documents(tmp_path: Path) -> Path:
  for name in ("README.md", "README.zh-CN.md", "pyproject.toml"):
    shutil.copyfile(ROOT / name, tmp_path / name)
  shutil.copytree(ROOT / "docs", tmp_path / "docs", ignore=shutil.ignore_patterns("__pycache__"))
  return tmp_path


def test_real_release_documents() -> None:
  check_release_documents(ROOT)


@pytest.mark.parametrize("sentence", CLAIMS)
@pytest.mark.parametrize(
  "unit",
  ["README.md", "README.zh-CN.md", "docs/en/releases.md", "docs/zh-CN/summaries.md"],
)
def test_source_documents_reject_candidate_claims(
  documents: Path, unit: str, sentence: str
) -> None:
  path = documents / unit
  path.write_text(path.read_text(encoding="utf-8") + "\n" + sentence, encoding="utf-8")
  with pytest.raises(ValueError, match="candidate claim"):
    check_release_documents(documents)


@pytest.mark.parametrize("unit", ["README.md", "README.zh-CN.md"])
@pytest.mark.parametrize("future", [False, True])
@pytest.mark.parametrize("python", [".venv/bin/python", ".venv\\Scripts\\python.exe"])
@pytest.mark.parametrize(
  "requirement", ["astrology", "celestial-astrology", "celestial-astrology==0.0.0"]
)
def test_installation_pins_follow_project_version(
  documents: Path, unit: str, future: bool, python: str, requirement: str
) -> None:
  project_file = documents / "pyproject.toml"
  version = tomllib.loads(project_file.read_text(encoding="utf-8"))["project"]["version"]
  if future:
    next_version = f"{int(version.split('.')[0]) + 1}.0.0"
    for name in ("pyproject.toml", "README.md", "README.zh-CN.md"):
      path = documents / name
      path.write_text(
        path.read_text(encoding="utf-8").replace(version, next_version), encoding="utf-8"
      )
    version = next_version
  check_release_documents(documents)
  path = documents / unit
  command = f'{python} -m pip install "celestial-astrology=={version}"'
  text = path.read_text(encoding="utf-8")
  assert command in text
  path.write_text(
    text.replace(command, f'{python} -m pip install "{requirement}"'), encoding="utf-8"
  )
  with pytest.raises(ValueError, match="installation"):
    check_release_documents(documents)


@pytest.mark.parametrize("unit", ["README.md", "README.zh-CN.md"])
def test_source_requires_versioned_index_reference(documents: Path, unit: str) -> None:
  path = documents / unit
  text = path.read_text(encoding="utf-8")
  path.write_text(text.replace("pypi.org/project/", "example.org/project/"), encoding="utf-8")
  with pytest.raises(ValueError, match="index page"):
    check_release_documents(documents)


@pytest.mark.parametrize("unit", ["docs/index.md", "docs/_templates/site_index.html"])
def test_source_snapshot_labels_remain_required(documents: Path, unit: str) -> None:
  path = documents / unit
  path.write_text(
    path.read_text(encoding="utf-8").replace("源码文档快照", "开发版文档"), encoding="utf-8"
  )
  with pytest.raises(ValueError, match="snapshot labels"):
    check_release_documents(documents)


@pytest.mark.parametrize(
  "text",
  [
    "Source documentation snapshot / 源码文档快照。",
    "Static cross-chart aspects are available since 0.2.0.",
    "0.2.0 删除了旧接口；0.1.0 历史记录仍可查。",
    "Check the index for the documented version; otherwise install the source snapshot.",
  ],
)
def test_neutral_and_historical_text_is_allowed(text: str) -> None:
  check_release_claims(text)


def _metadata(body: str, content_type: str = "text/markdown") -> bytes:
  return f"Metadata-Version: 2.4\nDescription-Content-Type: {content_type}\n\n{body}".encode()


@pytest.mark.parametrize("newlines", ["\n", "\r\n"])
def test_description_preserves_non_ascii_and_normalizes_only_newlines(newlines: str) -> None:
  body = "# 简体中文\n\nSource documentation snapshot / 源码文档快照。\n"
  check_description(_metadata(body).replace(b"\n", newlines.encode()), body)
  with pytest.raises(ValueError, match="differs"):
    check_description(_metadata(body + " "), body)


@pytest.mark.parametrize("sentence", CLAIMS)
def test_metadata_rejects_candidate_claim_even_when_it_matches_readme(sentence: str) -> None:
  with pytest.raises(ValueError, match="candidate claim"):
    check_description(_metadata(sentence), sentence)


@pytest.mark.parametrize("defect", ["body", "content_type", "multipart", "utf8"])
def test_actual_metadata_description_defects(defect: str) -> None:
  body = "# 简体中文\n"
  content = _metadata(body)
  if defect == "body":
    content = _metadata("# stale\n")
  elif defect == "content_type":
    content = _metadata(body, "text/plain")
  elif defect == "multipart":
    content = b'Content-Type: multipart/mixed; boundary="x"\nDescription-Content-Type: text/markdown\n\n--x\n\npart\n--x--\n'
  else:
    content += b"\xff"
  with pytest.raises(ValueError):
    check_description(content, body)


@pytest.mark.parametrize("mode", [(), ("-O",)])
def test_production_rejection_does_not_depend_on_assertions(mode: tuple[str, ...]) -> None:
  code = "from tools.release_documents import check_release_claims; check_release_claims('0.3.0（开发中）')"
  result = subprocess.run(
    [sys.executable, *mode, "-c", code], cwd=ROOT, capture_output=True, text=True
  )
  assert result.returncode == 1 and "candidate claim" in result.stderr


def test_duplicate_conflicting_index_command_is_rejected() -> None:
  text = "\n".join(
    f'{p} -m pip install "celestial-astrology==0.3.0"'
    for p in (".venv/bin/python", ".venv\\Scripts\\python.exe")
  )
  check_readme_installation(text, "0.3.0")
  with pytest.raises(ValueError, match="inconsistent"):
    check_readme_installation(
      text + '\n.venv/bin/python -m pip install "celestial-astrology"', "0.3.0"
    )
