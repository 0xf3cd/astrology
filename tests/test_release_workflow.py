"""Release workflow policy and executed byte-guard controls. 发行工作流政策及实际字节检查反例。"""

import copy
import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow() -> dict[str, Any]:
  result: dict[str, Any] = yaml.load(
    (ROOT / ".github/workflows/release.yml").read_text(), Loader=yaml.BaseLoader
  )
  return result


def _contract(workflow: dict[str, Any]) -> None:
  assert set(workflow["on"]) == {"pull_request", "workflow_dispatch"}
  assert workflow["permissions"] == {}
  assert workflow["env"]["RELEASE_SHA"] == "${{ inputs.sha || github.sha }}"
  jobs = workflow["jobs"]
  assert set(jobs) == {"build", "consume", "publish-pypi"}
  build, consume, publish = (jobs[key] for key in ("build", "consume", "publish-pypi"))
  assert build["steps"][0]["with"]["ref"] == "${{ github.sha }}"
  assert consume["steps"][0]["with"]["ref"] == "${{ needs.build.outputs.source_sha }}"
  for job in (build, consume):
    assert job["permissions"] == {"contents": "read"}
    assert "environment" not in job
  assert consume["needs"] == "build"
  assert consume["strategy"]["fail-fast"] == "false"
  assert {(row["os"], row["python"]) for row in consume["strategy"]["matrix"]["include"]} == {
    ("ubuntu-latest", "3.11"),
    ("ubuntu-latest", "3.12"),
    ("ubuntu-latest", "3.13"),
    ("ubuntu-latest", "3.14"),
    ("ubuntu-24.04-arm", "3.14"),
    ("macos-latest", "3.14"),
    ("windows-latest", "3.14"),
  }
  assert len(consume["strategy"]["matrix"]["include"]) == 7
  assert publish["needs"] == ["build", "consume"]
  assert (
    publish["if"] == "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'"
  )
  assert publish["permissions"] == {"id-token": "write"}
  assert publish["environment"] == "pypi"
  assert publish["runs-on"] == "ubuntu-latest"
  assert "container" not in publish
  for job in jobs.values():
    assert "continue-on-error" not in job
    for step in job["steps"]:
      assert "continue-on-error" not in step
      if "uses" not in step:
        continue
      assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", step["uses"])
      if step["uses"].startswith("astral-sh/setup-uv@"):
        assert step["with"]["version"] == "0.12.5"
        assert step["with"]["enable-cache"] == "false"
        assert "runner.temp" in step["env"]["RUNNER_TOOL_CACHE"]
        assert "github.run_attempt" in step["env"]["RUNNER_TOOL_CACHE"]
        assert (
          re.fullmatch(r"[0-9a-f]{64}", step["with"]["checksum"])
          or step["with"]["checksum"] == "${{ matrix.uv-checksum }}"
        )
      if step["uses"].startswith("actions/checkout@"):
        assert step["with"]["persist-credentials"] == "false"
      if step["uses"].startswith("actions/download-artifact@"):
        assert step["with"]["artifact-ids"] == "${{ needs.build.outputs.artifact_id }}"
        assert step["with"]["digest-mismatch"] == "error"
        assert not {"name", "github-token", "repository", "run-id"}.intersection(step["with"])
  commands = [step["run"] for step in build["steps"] if "run" in step]
  assert commands == [
    "uv sync --locked --python 3.14",
    "uv run --locked python tools/release.py validate",
    "uv run --locked python tools/check.py --artifacts-dir dist/packages",
    "uv run --locked python tools/release.py prepare",
  ]
  assert consume["steps"][-1]["run"] == "uv run --locked python tools/release.py consume"
  upload = build["steps"][-1]
  assert upload["id"] == "upload"
  assert upload["with"]["overwrite"] == "false"
  assert upload["with"]["if-no-files-found"] == "error"
  assert build["outputs"]["artifact_id"] == "${{ steps.upload.outputs.artifact-id }}"
  assert len(publish["steps"]) == 3
  assert publish["steps"][0]["uses"].startswith("actions/download-artifact@")
  assert "| sha256sum -c -\n" in publish["steps"][1]["run"]
  publisher = publish["steps"][-1]
  assert publisher["uses"] == "pypa/gh-action-pypi-publish@7245906fb61fa33a13554f9d5fb856fe61758086"
  assert publisher["with"] == {
    "repository-url": "https://upload.pypi.org/legacy/",
    "packages-dir": "dist/packages",
    "attestations": "true",
    "skip-existing": "false",
  }


def test_release_workflow_has_the_restricted_artifact_chain() -> None:
  _contract(_workflow())


def test_checkout_policy_preserves_linux_archive_text_bytes() -> None:
  assert (ROOT / ".gitattributes").read_text(encoding="utf-8") == "* text=auto eol=lf\n"


@pytest.mark.parametrize(
  "defect",
  [
    "event",
    "needs",
    "build-token",
    "if",
    "floating",
    "by-name",
    "cross-run",
    "cache",
    "rebuild",
    "overwrite",
    "matrix",
    "skip-existing",
    "attestations",
    "tolerate-failure",
    "implicit-stdin",
    "build-ref",
    "consume-ref",
    "release-sha",
    "missing-files",
    "persist-credentials",
  ],
)
def test_workflow_contract_rejects_representative_defects(defect: str) -> None:
  workflow = copy.deepcopy(_workflow())
  build, consume, publish = (
    workflow["jobs"][name] for name in ("build", "consume", "publish-pypi")
  )
  if defect == "event":
    workflow["on"]["pull_request_target"] = workflow["on"].pop("pull_request")
  elif defect == "needs":
    publish["needs"] = ["build"]
  elif defect == "build-token":
    build["permissions"]["id-token"] = "write"
  elif defect == "if":
    publish["if"] = "always()"
  elif defect == "floating":
    publish["steps"][-1]["uses"] = "pypa/gh-action-pypi-publish@release/v1"
  elif defect == "by-name":
    publish["steps"][0]["with"]["name"] = "latest"
  elif defect == "cross-run":
    publish["steps"][0]["with"]["run-id"] = "123"
  elif defect == "cache":
    next(step for step in build["steps"] if step.get("uses", "").startswith("astral-sh/setup-uv@"))[
      "env"
    ] = {}
  elif defect == "rebuild":
    consume["steps"][-1]["run"] = "uv run --locked python tools/check.py"
  elif defect == "overwrite":
    build["steps"][-1]["with"]["overwrite"] = "true"
  elif defect == "matrix":
    consume["strategy"]["matrix"]["include"].pop()
  elif defect in ("skip-existing", "attestations"):
    publish["steps"][-1]["with"][defect] = "true" if defect == "skip-existing" else "false"
  elif defect == "implicit-stdin":
    publish["steps"][1]["run"] = publish["steps"][1]["run"].replace(
      "sha256sum -c -", "sha256sum -c"
    )
  elif defect == "build-ref":
    build["steps"][0]["with"]["ref"] = "main"
  elif defect == "consume-ref":
    consume["steps"][0]["with"]["ref"] = "main"
  elif defect == "release-sha":
    workflow["env"]["RELEASE_SHA"] = "${{ github.sha }}"
  elif defect == "missing-files":
    build["steps"][-1]["with"]["if-no-files-found"] = "warn"
  elif defect == "persist-credentials":
    consume["steps"][0]["with"]["persist-credentials"] = "true"
  else:
    consume["continue-on-error"] = "true"
  with pytest.raises((AssertionError, KeyError)):
    _contract(workflow)


@pytest.mark.parametrize(
  "defect",
  [
    "none",
    "digest",
    "digest-shape",
    "digest-uppercase",
    "bytes",
    "extra",
    "filename",
    "filename-newline",
    "version",
    "wheel-symlink",
    "packages-symlink",
  ],
)
@pytest.mark.parametrize("errexit", [True, False])
def test_actual_publication_byte_guard(tmp_path: Path, defect: str, errexit: bool) -> None:
  bash = shutil.which("bash")
  if bash is None:
    pytest.skip("The publication guard requires Bash, as does its Ubuntu job")
  packages = tmp_path / "dist/packages"
  packages.mkdir(parents=True)
  sdist, wheel = "celestial_astrology-0.1.0.tar.gz", "celestial_astrology-0.1.0-py3-none-any.whl"
  (packages / sdist).write_bytes(b"synthetic sdist")
  (packages / wheel).write_bytes(b"synthetic wheel")
  environment = {
    **os.environ,
    "DIST_DIR": "dist",
    "RELEASE_VERSION": "0.1.0",
    "SDIST_NAME": sdist,
    "WHEEL_NAME": wheel,
    "SDIST_SHA256": hashlib.sha256((packages / sdist).read_bytes()).hexdigest(),
    "WHEEL_SHA256": hashlib.sha256((packages / wheel).read_bytes()).hexdigest(),
  }
  guard = _workflow()["jobs"]["publish-pypi"]["steps"][1]["run"]
  if not errexit:
    guard = guard.replace("set -euo pipefail", "set -uo pipefail")
  baseline = subprocess.run(
    (bash, "-c", guard), cwd=tmp_path, env=environment, capture_output=True, timeout=15
  )
  assert baseline.returncode == 0, baseline.stderr.decode(errors="replace")
  assert baseline.stdout.decode().splitlines() == [
    f"dist/packages/{sdist}: OK",
    f"dist/packages/{wheel}: OK",
  ]
  if defect == "digest":
    environment["WHEEL_SHA256"] = "0" * 64
  elif defect == "digest-shape":
    environment["WHEEL_SHA256"] += "\nmalformed"
  elif defect == "digest-uppercase":
    environment["WHEEL_SHA256"] = "A" * 64
  elif defect == "bytes":
    (packages / wheel).write_bytes(b"different download")
  elif defect == "extra":
    (packages / "unexpected.whl").touch()
  elif defect == "filename":
    environment["SDIST_NAME"] = "../unexpected.tar.gz"
  elif defect == "filename-newline":
    environment["WHEEL_NAME"] += "\nmalformed"
  elif defect == "version":
    environment["RELEASE_VERSION"] = "0.1.0\nunsafe"
  elif defect in ("wheel-symlink", "packages-symlink"):
    path = packages / wheel if defect == "wheel-symlink" else packages
    outside = tmp_path / "outside"
    path.rename(outside)
    try:
      path.symlink_to(outside, target_is_directory=defect == "packages-symlink")
    except OSError as exc:
      pytest.skip(f"Symlinks unavailable: {exc}")
  result = subprocess.run(
    (bash, "-c", guard), cwd=tmp_path, env=environment, capture_output=True, timeout=15
  )
  assert (result.returncode == 0) == (defect == "none"), result.stderr.decode(errors="replace")
