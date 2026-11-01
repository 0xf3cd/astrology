"""Check release-facing text and archived descriptions. 检查发行说明文字与包内描述。"""

from __future__ import annotations

import re
from email.parser import Parser
from pathlib import Path

_VERSION = r"v?\d+\.\d+\.\d+"
_CANDIDATE_CLAIMS = (
  rf"\b(?:prepares|preparing|planned for)\s+(?:version\s+)?{_VERSION}",
  rf"\b(?:after|once)\s+{_VERSION}\s+is published on pypi",
  rf"{_VERSION}\s*\([^)]*(?:in development|unreleased|not yet published)[^)]*\)",
  rf"{_VERSION}\s+(?:is\s+)?not yet (?:published|available)",
  rf"{_VERSION}\s+additions still in development",
  r"this candidate (?:has not been|is not yet) published",
  rf"(?:当前源码准备|准备版本|计划随)\s*{_VERSION}",
  rf"{_VERSION}\s*[（(][^）)]*(?:开发中|未发布)[^）)]*[）)]",
  rf"{_VERSION}\s*发布到\s*pypi\s*后",
  rf"仍在开发中的\s*{_VERSION}",
  r"此候选尚未发布到\s*pypi",
)


def release_index_url() -> str:
  """Return the package's release index. 返回分发包的发行索引。"""
  return "https://pypi.org/project/celestial-astrology/"


def check_release_claims(text: str) -> None:
  """Reject known publication-dependent candidate claims, not source-snapshot labels.

  This checks representative stale wording, not arbitrary prose truth.

  拒绝已知会随发布过期的候选说法，允许源码快照标签。此检查不证明任意文字都属实。
  """
  normalized = " ".join(text.replace("`", "").split()).casefold()
  if any(re.search(pattern, normalized) for pattern in _CANDIDATE_CLAIMS):
    raise ValueError("Release text contains a publication-dependent candidate claim")


def check_readme_installation(text: str) -> None:
  """Require both platform commands to install the latest release by package name.

  要求两个平台的命令均按分发包名安装最新发行版。
  """
  normalized = " ".join(text.split())
  target_pattern = r"-m\s+pip\s+install\s+[\"']?([^\s\"'`;|&<>]+)"
  for python in (".venv/bin/python", ".venv\\Scripts\\python.exe"):
    targets = re.findall(re.escape(python) + r"\s+" + target_pattern, normalized)
    if "celestial-astrology" not in targets:
      raise ValueError("README installation command must install celestial-astrology without a pin")
  if any(
    target not in ("celestial-astrology", ".") for target in re.findall(target_pattern, normalized)
  ):
    raise ValueError("README has an inconsistent package installation command")


def check_release_documents(root: Path) -> None:
  """Check source release claims, README installation and bilingual snapshot labels.

  检查源码发行说明、README 安装命令与双语快照标签。
  """
  readmes = (root / "README.md", root / "README.zh-CN.md")
  for page in (*readmes, *sorted((root / "docs").rglob("*.md"))):
    try:
      check_release_claims(page.read_text(encoding="utf-8"))
    except ValueError as error:
      raise ValueError(f"{page.relative_to(root)}: {error}") from error
  for page in readmes:
    text = page.read_text(encoding="utf-8")
    check_readme_installation(text)
    if release_index_url() not in text:
      raise ValueError("README must link the package's index page")
    if "`astrology`" not in text:
      raise ValueError("README must distinguish the import and distribution names")
  for name in ("docs/index.md", "docs/_templates/site_index.html"):
    text = (root / name).read_text(encoding="utf-8")
    if not all(label in text for label in ("Source documentation snapshot", "源码文档快照")):
      raise ValueError("Documentation must retain bilingual source-snapshot labels")


def check_description(content: bytes, readme: str) -> None:
  """Require an actual UTF-8 Markdown metadata body to match the accepted README.

  The comparison normalizes CRLF and trailing newlines only. Decode before email
  parsing so non-ASCII text is not replaced by the byte parser's string conversion.

  要求实际元数据中的 UTF-8 Markdown 描述匹配已接受的 README。只规范 CRLF 和末尾换行；
  先解码再解析邮件格式，避免字节解析器转字符串时替换非 ASCII 文字。
  """
  metadata = Parser().parsestr(content.decode("utf-8"))
  if (metadata["Description-Content-Type"] or "").split(";", 1)[0].strip() != "text/markdown":
    raise ValueError("Archive description must declare Markdown content")
  description = metadata.get_payload()
  if not isinstance(description, str):
    raise ValueError("Archive description must be text")
  check_release_claims(description)
  if description.replace("\r\n", "\n").rstrip("\n") != readme.replace("\r\n", "\n").rstrip("\n"):
    raise ValueError("Archive description differs from the accepted README")
