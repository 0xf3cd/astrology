"""Rendered API checks must reject green builds with absent signatures."""

from enum import Enum
from inspect import isfunction
from pathlib import Path

import pytest

import astrology
from astrology import knowledge
from tools.check import check_api_html


@pytest.fixture
def api_html(tmp_path: Path) -> Path:
  names = set(astrology.__all__) | set(knowledge.__all__)
  for module in (astrology, knowledge):
    for name in module.__all__:
      value = getattr(module, name)
      if isinstance(value, type) and issubclass(value, Enum):
        names.update(value.__members__)
      if isinstance(value, type):
        names.update(
          name
          for name, member in vars(value).items()
          if not name.startswith("_") and (isfunction(member) or isinstance(member, property))
        )
  for language, counterpart in (("en", "zh-CN"), ("zh-CN", "en")):
    directory = tmp_path / "docs" / language
    directory.mkdir(parents=True)
    signatures = "".join(
      f'<dt class="sig"><span class="sig-name descname"><span>{name}</span></span></dt>'
      for name in sorted(names)
    )
    (directory / "reference.html").write_text(
      f'<html lang="{language}"><a href="../{counterpart}/reference.html">Other</a>'
      f"<dl>{signatures}</dl></html>",
      encoding="utf-8",
    )
  return tmp_path


def test_complete_rendered_views(api_html: Path) -> None:
  check_api_html(api_html)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize(
  "name",
  [
    "BirthRecord",
    "SUN",
    "Catalog",
    "TranslationStatus",
    "load_catalog",
    "lookup",
    "chart_applicability",
  ],
)
def test_missing_public_signature_or_enum_is_rejected(
  api_html: Path, language: str, name: str
) -> None:
  page = api_html / "docs" / language / "reference.html"
  page.write_text(
    page.read_text(encoding="utf-8").replace(f"<span>{name}</span>", "<span>omitted</span>"),
    encoding="utf-8",
  )
  with pytest.raises(ValueError, match="Missing rendered API"):
    check_api_html(api_html)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_raw_rst_with_names_is_not_rendered_api(api_html: Path, language: str) -> None:
  page = api_html / "docs" / language / "reference.html"
  page.write_text(
    "<p>.. py:class:: BirthRecord</p><p>" + " ".join(astrology.__all__) + "</p>", encoding="utf-8"
  )
  with pytest.raises(ValueError, match="Missing rendered API"):
    check_api_html(api_html)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_missing_html_page_is_rejected(api_html: Path, language: str) -> None:
  (api_html / "docs" / language / "reference.html").unlink()
  with pytest.raises(ValueError, match="Missing API HTML"):
    check_api_html(api_html)


@pytest.mark.parametrize("defect", ["language", "navigation"])
def test_language_and_navigation_are_checked(api_html: Path, defect: str) -> None:
  page = api_html / "docs/en/reference.html"
  text = page.read_text(encoding="utf-8")
  if defect == "language":
    text = text.replace('lang="en"', 'lang="fr"')
  else:
    text = text.replace("../zh-CN/reference.html", "other.html")
  page.write_text(text, encoding="utf-8")
  with pytest.raises(ValueError, match=r"language|counterpart"):
    check_api_html(api_html)
