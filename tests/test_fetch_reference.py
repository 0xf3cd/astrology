"""Reference fetching without author-local inputs. 不依赖作者本地文件的参考抓取。"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest

from tools import fetch_reference as fetcher

REFERENCE = Path(__file__).parent / "reference/natal_reference.json"
BODY_NAMES = {
  "10": "sun",
  "301": "moon",
  "199": "mercury",
  "299": "venus",
  "499": "mars",
  "599": "jupiter",
  "699": "saturn",
  "799": "uranus",
  "899": "neptune",
  "999": "pluto",
}


def test_fetch_help_keeps_bilingual_paragraphs_and_the_example_command() -> None:
  result = subprocess.run(
    [sys.executable, "-I", "-X", "utf8", fetcher.__file__, "--help"],
    check=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
  )
  assert "\n\n从 JPL Horizons" in result.stdout
  assert (
    "Run: python3 tools/fetch_reference.py --output /path/to/reference.json"
    in result.stdout.splitlines()
  )
  assert "QUANTITIES=31" in result.stdout and "TIME_TYPE=TT" in result.stdout
  assert not result.stderr


@pytest.fixture
def reference_queries(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
  cases: list[dict[str, Any]] = json.loads(REFERENCE.read_text(encoding="utf-8"))["cases"]
  requests: list[dict[str, str]] = []

  def query(parameters: dict[str, str]) -> tuple[str, str]:
    requests.append(parameters.copy())
    if parameters["CENTER"] == "'500@399'":
      assert parameters["TIME_TYPE"] == "'TT'" and parameters["QUANTITIES"] == "'31'"
      tt = float(parameters["TLIST"].strip("'"))
      case = next(case for case in cases if abs(case["jde_tt"] - tt) < 1e-8)
      name = BODY_NAMES[parameters["COMMAND"].strip("'")]
      body = case["bodies"][name]
      text = (
        f"Target body name: target {{source: {case['ephemeris_sources'][name]}}}\n"
        f"Center body name: Earth {{source: {case['center_source']}}}\n"
        f"$$SOE\n0,0,0,{body['longitude_deg']},{body['latitude_deg']}\n$$EOE"
      )
    else:
      assert parameters["TIME_TYPE"] == "'UT'" and parameters["QUANTITIES"] == "'7'"
      instant = parameters["TLIST"].strip("'").replace(" ", "T") + "Z"
      case = next(case for case in cases if case["utc"] == instant)
      assert parameters["SITE_COORD"] == (
        f"'{case['location']['longitude']},{case['location']['latitude']},0'"
      )
      text = f"$$SOE\n0,0,0,{case['local_apparent_sidereal_time_deg'] / 15}\n$$EOE"
    return text, fetcher.API + "?" + urlencode(parameters)

  monkeypatch.setattr(fetcher, "query", query)
  return requests


def test_fetch_matches_stored_values_and_conventions_without_local_probe_files(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reference_queries: list[dict[str, str]]
) -> None:
  monkeypatch.chdir(tmp_path)
  monkeypatch.setattr(fetcher, "__file__", str(tmp_path / "tools/fetch_reference.py"))
  private = tmp_path / ".review" / "probes"
  private.mkdir(parents=True)
  (private / "horizons_301.txt").write_text("unrelated malformed local data", encoding="utf-8")
  original = REFERENCE.read_bytes()
  target = tmp_path / "output/reference.json"
  fetcher.main(["--output", str(target)])
  result = json.loads(target.read_text(encoding="utf-8"))
  expected = json.loads(original)
  assert datetime.fromisoformat(result.pop("retrieved_utc")).tzinfo is not None
  expected.pop("retrieved_utc")
  assert result == expected
  assert len(reference_queries) == 22
  assert REFERENCE.read_bytes() == original


def test_fetch_requires_an_explicit_output_before_any_request(
  reference_queries: list[dict[str, str]],
) -> None:
  with pytest.raises(SystemExit) as caught:
    fetcher.main([])
  assert caught.value.code == 2
  assert reference_queries == []


def test_failed_fetch_does_not_change_an_existing_destination(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  target = tmp_path / "reference.json"
  target.write_text("existing data", encoding="utf-8")

  def failure(_case: fetcher._Case) -> fetcher._CaseResult:
    raise RuntimeError("network unavailable")

  monkeypatch.setattr(fetcher, "fetch_case", failure)
  with pytest.raises(RuntimeError, match="network unavailable"):
    fetcher.main(["--output", str(target)])
  assert target.read_text(encoding="utf-8") == "existing data"
