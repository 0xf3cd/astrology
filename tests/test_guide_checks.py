"""Required guide blocks survive editing but cannot disappear. 必需说明块可改写，不可丢失。"""

from pathlib import Path

import pytest

from tools.guide_checks import check_examples, check_guide_content, example_documents

TOPICS = frozenset({"cross.orbs"})
EXAMPLE = "```{doctest}\n>>> 1 + 1\n2\n```\n"
BLOCK = (
  "<!-- usage: cross.orbs -->\n\nChoose the pair's orb limit.\n\n"
  + EXAMPLE
  + "\n<!-- /usage: cross.orbs -->\n"
)


@pytest.fixture
def guides(tmp_path: Path) -> Path:
  for language in ("en", "zh-CN"):
    page = tmp_path / "docs" / language / "cross.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Cross chart\n\n" + BLOCK, encoding="utf-8")
  return tmp_path


def test_valid_required_blocks(guides: Path) -> None:
  check_guide_content(guides, TOPICS)


def test_repository_required_topics() -> None:
  check_guide_content(Path(__file__).resolve().parents[1])


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize(
  ("replacement", "message"),
  [
    ("", "Missing required"),
    (BLOCK.replace("Choose the pair's orb limit.", ""), "needs prose"),
    (BLOCK.replace("Choose the pair's orb limit.", "## Only a heading"), "needs prose"),
    (BLOCK.replace("Choose the pair's orb limit.", "12345!?"), "needs prose"),
    (BLOCK.replace("Choose the pair's orb limit.", "`choose_the_orb_limit`"), "needs prose"),
    (BLOCK.replace(EXAMPLE, ""), "needs prose"),
    (BLOCK.replace(EXAMPLE, "```{doctest}\n2\n```\n"), "needs prose"),
    (BLOCK.replace(EXAMPLE, EXAMPLE * 2), "needs prose"),
    (BLOCK * 2, "Duplicate"),
    (BLOCK.replace("cross.orbs", "unknown"), "Unknown"),
    (BLOCK.replace("<!-- /usage: cross.orbs -->", ""), "Unclosed"),
    (BLOCK.replace("<!-- /usage: cross.orbs -->", "<!-- /usage: another -->"), "Unmatched"),
    ("<!-- /usage: cross.orbs -->\n" + BLOCK, "Unmatched"),
    (BLOCK.replace(EXAMPLE, "<!-- usage: cross.orbs -->\n" + EXAMPLE), "Nested"),
    (BLOCK.replace("usage: cross.orbs", "usage: cross orbs"), "Invalid"),
  ],
)
def test_missing_and_malformed_content_rejected(
  guides: Path, language: str, replacement: str, message: str
) -> None:
  page = guides / "docs" / language / "cross.md"
  page.write_text("# Cross chart\n\n" + replacement, encoding="utf-8")
  with pytest.raises(ValueError, match=message):
    check_guide_content(guides, TOPICS)


def test_missing_language_rejected(guides: Path) -> None:
  (guides / "docs/zh-CN/cross.md").unlink()
  with pytest.raises(ValueError, match=r"Missing required.*zh-CN"):
    check_guide_content(guides, TOPICS)


def test_empty_requirements_rejected(guides: Path) -> None:
  with pytest.raises(ValueError, match="must not be empty"):
    check_guide_content(guides, frozenset())


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_translation_heading_and_cross_page_relocation_are_valid(
  guides: Path, language: str
) -> None:
  page = guides / "docs" / language / "cross.md"
  page.write_text("# A different heading\n", encoding="utf-8")
  moved = page.parent / "advanced/orbs.md"
  moved.parent.mkdir()
  moved.write_text(
    "## 移动后的标题\n\n"
    + BLOCK.replace("Choose the pair's orb limit.", "用两个对象的容许度计算配对上限。"),
    encoding="utf-8",
  )
  check_guide_content(guides, TOPICS)
  assert (f"docs/{language}/advanced/orbs", 1) in example_documents(guides)


def test_other_page_example_cannot_replace_a_topic_example(guides: Path) -> None:
  page = guides / "docs/en/cross.md"
  page.write_text(BLOCK.replace(EXAMPLE, "") + "\n" + EXAMPLE, encoding="utf-8")
  with pytest.raises(ValueError, match="needs prose"):
    check_guide_content(guides, TOPICS)


def test_markers_in_code_are_not_content(guides: Path) -> None:
  page = guides / "docs/en/cross.md"
  page.write_text("````text\n" + BLOCK + "````\n", encoding="utf-8")
  with pytest.raises(ValueError, match="Missing required"):
    check_guide_content(guides, TOPICS)


@pytest.mark.parametrize("count", [None, 0, 2])
@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_report_must_execute_every_source_example(
  guides: Path, language: str, count: int | None
) -> None:
  sections = {lang: f"Document: docs/{lang}/cross\n1 test in 1 item.\n" for lang in ("en", "zh-CN")}
  sections[language] = (
    "" if count is None else sections[language].replace("1 test", f"{count} tests")
  )
  with pytest.raises(ValueError, match=f"docs/{language}/cross"):
    check_examples("".join(sections.values()), guides)


@pytest.mark.parametrize("word", ["item", "items"])
def test_report_group_names_do_not_split_documents(guides: Path, word: str) -> None:
  report = "".join(
    f"Document: docs/{language}/cross\n"
    f"1 item passed all tests:\n   1 tests in Document: group\n1 test in 1 {word}.\n"
    for language in ("en", "zh-CN")
  )
  check_examples(report, guides)


def test_no_source_examples_rejected(tmp_path: Path) -> None:
  with pytest.raises(ValueError, match="No executable"):
    check_examples("", tmp_path)
