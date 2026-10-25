"""Retained-artifact identity, content and consumption. 保留制品的身份、内容及消费检查。"""

import hashlib
import json
import subprocess
import sys
import tarfile
from collections.abc import Sequence
from dataclasses import FrozenInstanceError, dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

import astrology
from tools import check as checker
from tools import release
from tools.check import PACKAGE_FILES, SDIST_FILES

SHA = "a" * 40
IDENTITY = release.ReleaseIdentity("0.1.0", SHA)
METADATA = (
  b"Metadata-Version: 2.4\nName: celestial-astrology\nVersion: 0.1.0\n"
  b"Requires-Python: <3.15,>=3.11\nRequires-Dist: celestial-calendar==0.8.0\n"
  b"Requires-Dist: tzdata==2026.5\nDescription-Content-Type: text/markdown\n\n"
  b"[Documentation](https://example.org/)\n"
)


@dataclass
class ReleaseFiles:
  root: Path
  directory: Path
  sdist_members: dict[str, bytes]
  wheel_members: dict[str, bytes]

  def write(self) -> None:
    packages = self.directory / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    with tarfile.open(packages / IDENTITY.sdist_name, "w:gz") as archive:
      for name, content in self.sdist_members.items():
        member = tarfile.TarInfo(f"celestial_astrology-0.1.0/{name}")
        member.size = len(content)
        archive.addfile(member, BytesIO(content))
    with ZipFile(packages / IDENTITY.wheel_name, "w") as archive:
      for name, content in self.wheel_members.items():
        archive.writestr(name, content)

  def expectations(self) -> dict[str, str]:
    return {
      variable: hashlib.sha256((self.directory / "packages" / name).read_bytes()).hexdigest()
      for name, variable in (
        (IDENTITY.sdist_name, "SDIST_SHA256"),
        (IDENTITY.wheel_name, "WHEEL_SHA256"),
      )
    }


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReleaseFiles:
  root = tmp_path / "source"
  root.mkdir()
  source_names = {*SDIST_FILES, *("src/" + name for name in PACKAGE_FILES), "LICENSE"}
  sources = {name: ("source:" + name).encode() for name in source_names}
  sources["pyproject.toml"] = (
    b'[project]\nname="celestial-astrology"\nversion="0.1.0"\nrequires-python=">=3.11,<3.15"\n'
    b'dependencies=["celestial-calendar==0.8.0", "tzdata==2026.5"]\n'
  )
  for name, content in sources.items():
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

  def git(_root: Path, *arguments: str) -> str:
    if arguments == ("ls-files", "-z"):
      return "\0".join(sorted(sources)) + "\0"
    if arguments == ("rev-parse", "HEAD"):
      return SHA
    if arguments == ("ls-remote", "origin", "refs/heads/main"):
      return SHA + "\trefs/heads/main"
    if arguments == ("status", "--porcelain", "--untracked-files=all"):
      return ""
    raise AssertionError(arguments)

  monkeypatch.setattr(release, "_git", git)
  dist_info = "celestial_astrology-0.1.0.dist-info/"
  wheel = {
    name.removeprefix("src/"): content
    for name, content in sources.items()
    if name.startswith("src/astrology/")
  }
  wheel.update(
    {
      dist_info + "METADATA": METADATA,
      dist_info + "licenses/LICENSE": sources["LICENSE"],
      dist_info + "WHEEL": b"Wheel-Version: 1.0\n",
      dist_info + "RECORD": b"",
    }
  )
  result = ReleaseFiles(root, tmp_path / "dist", {**sources, "PKG-INFO": METADATA}, wheel)
  result.write()
  return result


@pytest.mark.parametrize("version", ["", "0.1", "0.1.0rc1", "0.1.0\n", "../0.1.0"])
def test_release_version_rejects_non_release_inputs(version: str) -> None:
  with pytest.raises(ValueError, match="three numeric"):
    release.ReleaseIdentity(version, SHA)


@pytest.mark.parametrize("sha", ["", "a" * 39, "A" * 40, "g" * 40, SHA + "\n"])
def test_release_sha_must_be_full_lowercase(sha: str) -> None:
  with pytest.raises(ValueError, match="full lowercase"):
    release.ReleaseIdentity("0.1.0", sha)


@pytest.mark.parametrize("field", ["version", "source_sha"])
def test_release_identity_is_immutable_and_names_the_files(field: str) -> None:
  assert IDENTITY.sdist_name == "celestial_astrology-0.1.0.tar.gz"
  assert IDENTITY.wheel_name == "celestial_astrology-0.1.0-py3-none-any.whl"
  with pytest.raises(FrozenInstanceError):
    setattr(IDENTITY, field, "changed")


@pytest.mark.parametrize("event", ["pull_request", "workflow_dispatch"])
def test_release_inputs_match_project_metadata(files: ReleaseFiles, event: str) -> None:
  env = {"GITHUB_EVENT_NAME": event, "RELEASE_SHA": SHA, "RELEASE_VERSION": "0.1.0"}
  assert release.release_identity(files.root, env) == IDENTITY
  env.pop("RELEASE_VERSION")
  if event == "pull_request":
    assert release.release_identity(files.root, env) == IDENTITY
  else:
    with pytest.raises(ValueError, match="three numeric"):
      release.release_identity(files.root, env)
  env["RELEASE_VERSION"] = "0.2.0"
  with pytest.raises(ValueError, match="differs from project"):
    release.release_identity(files.root, env)


@pytest.mark.parametrize(
  ("arguments", "response", "message"),
  [
    (("rev-parse", "HEAD"), "b" * 40, "requested SHA"),
    (("status", "--porcelain", "--untracked-files=all"), "?? unexpected.py", "uncommitted"),
    (("ls-remote", "origin", "refs/heads/main"), "b" * 40 + "\trefs/heads/main", "remote main"),
  ],
)
def test_release_rejects_source_drift(
  files: ReleaseFiles,
  monkeypatch: pytest.MonkeyPatch,
  arguments: tuple[str, ...],
  response: str,
  message: str,
) -> None:
  original = release._git
  monkeypatch.setattr(
    release, "_git", lambda root, *args: response if args == arguments else original(root, *args)
  )
  with pytest.raises(ValueError, match=message):
    release.validate(
      files.root,
      IDENTITY,
      {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main"},
    )


@pytest.mark.parametrize(
  "environment",
  [
    {"GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main"},
    {"GITHUB_EVENT_NAME": "pull_request_target", "GITHUB_REF": "refs/heads/main"},
    {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/tags/v0.1.0"},
    {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/other"},
  ],
)
def test_only_pr_validation_or_manual_main_is_admitted(
  files: ReleaseFiles, environment: dict[str, str]
) -> None:
  with pytest.raises(ValueError, match="manual dispatch on main"):
    release.validate(files.root, IDENTITY, environment)


@pytest.mark.parametrize("event", ["pull_request", "workflow_dispatch"])
def test_accepted_validation_paths(files: ReleaseFiles, event: str) -> None:
  release.validate(
    files.root, IDENTITY, {"GITHUB_EVENT_NAME": event, "GITHUB_REF": "refs/heads/main"}
  )


def test_prepare_retains_complete_inventory_and_independent_digests(files: ReleaseFiles) -> None:
  output = files.directory.parent / "job-output"
  release.prepare(files.root, IDENTITY, files.directory, output)
  manifest = json.loads((files.directory / "manifest.json").read_text())
  assert manifest["distribution"] == "celestial-astrology"
  assert manifest["source_sha"] == SHA
  assert manifest["version"] == "0.1.0"
  assert manifest["schema_version"] == 1
  assert manifest["corpus_version"] == astrology.load_catalog().version
  assert manifest["requires_python"] == ">=3.11,<3.15"
  assert manifest["dependencies"] == ["celestial-calendar==0.8.0", "tzdata==2026.5"]
  for name, variable in (
    (IDENTITY.sdist_name, "SDIST_SHA256"),
    (IDENTITY.wheel_name, "WHEEL_SHA256"),
  ):
    assert manifest["artifacts"][name]["sha256"] == files.expectations()[variable]
    assert manifest["artifacts"][name]["members"]
    assert (
      manifest["artifacts"][name]["size"] == (files.directory / "packages" / name).stat().st_size
    )
    assert files.expectations()[variable] in output.read_text()
  release.verify(files.root, IDENTITY, files.directory, files.expectations())
  with pytest.raises(FileExistsError):
    release.prepare(files.root, IDENTITY, files.directory, None)


@pytest.mark.parametrize("artifact", ["sdist", "wheel"])
@pytest.mark.parametrize("defect", ["extra", "source", "metadata-python", "metadata-dependency"])
def test_inspection_rejects_changed_sources_metadata_and_extra_members(
  files: ReleaseFiles, artifact: str, defect: str
) -> None:
  members = files.sdist_members if artifact == "sdist" else files.wheel_members
  metadata = "PKG-INFO" if artifact == "sdist" else "celestial_astrology-0.1.0.dist-info/METADATA"
  package = "src/astrology/chart.py" if artifact == "sdist" else "astrology/chart.py"
  if defect == "extra":
    members[".review/unexpected.txt"] = b"synthetic extra"
  elif defect == "source":
    members[package] = b"different source"
  elif defect == "metadata-python":
    members[metadata] = members[metadata].replace(b"<3.15,>=3.11", b">=3.12")
  else:
    members[metadata] = members[metadata].replace(
      b"celestial-calendar==0.8.0", b"celestial-calendar>=0.8.0"
    )
  files.write()
  with pytest.raises(
    ValueError, match=r"unexpected members|differs from the source|Python range|dependency policy"
  ):
    release.inspect_distributions(files.root, IDENTITY, files.directory)


def test_source_change_and_missing_tracked_resource_are_detected(files: ReleaseFiles) -> None:
  (files.root / "src/astrology/chart.py").write_bytes(b"source drift")
  with pytest.raises(ValueError, match="differs from the source"):
    release.inspect_distributions(files.root, IDENTITY, files.directory)
  files.sdist_members.pop("src/astrology/chart.py")
  files.write()
  with pytest.raises(ValueError, match="missing package resources"):
    release.inspect_distributions(files.root, IDENTITY, files.directory)


@pytest.mark.parametrize(("field", "value"), [("Name", "other-project"), ("Version", "0.0.9")])
def test_sdist_generated_metadata_must_match_release_identity(
  files: ReleaseFiles, field: str, value: str
) -> None:
  original = "celestial-astrology" if field == "Name" else "0.1.0"
  files.sdist_members["PKG-INFO"] = METADATA.replace(
    f"{field}: {original}\n".encode(), f"{field}: {value}\n".encode()
  )
  files.write()
  with pytest.raises(ValueError, match="different release identity"):
    release.inspect_distributions(files.root, IDENTITY, files.directory)


@pytest.mark.parametrize("missing_from", ["sdist", "wheel"])
def test_archives_must_include_tracked_package_files_beyond_the_required_list(
  files: ReleaseFiles, monkeypatch: pytest.MonkeyPatch, missing_from: str
) -> None:
  name = "src/astrology/additional.py"
  content = b"synthetic additional package source"
  (files.root / name).write_bytes(content)
  if missing_from == "wheel":
    files.sdist_members[name] = content
  original = release._git
  monkeypatch.setattr(
    release,
    "_git",
    lambda root, *args: (
      original(root, *args) + name + "\0" if args == ("ls-files", "-z") else original(root, *args)
    ),
  )
  files.write()
  message = (
    "Sdist is missing tracked package sources"
    if missing_from == "sdist"
    else r"missing source members.*astrology/additional\.py"
  )
  with pytest.raises(ValueError, match=message):
    release.inspect_distributions(files.root, IDENTITY, files.directory)


@pytest.mark.parametrize("defect", ["extra-file", "missing-wheel", "missing-directory"])
def test_package_directory_has_exactly_two_files(files: ReleaseFiles, defect: str) -> None:
  packages = files.directory / "packages"
  if defect == "extra-file":
    (packages / "extra.whl").touch()
  elif defect == "missing-wheel":
    (packages / IDENTITY.wheel_name).unlink()
  else:
    packages.rename(files.directory.parent / "other")
  with pytest.raises(ValueError, match="exactly the named"):
    release.inspect_distributions(files.root, IDENTITY, files.directory)


def test_release_directory_rejects_unexpected_non_package_files(files: ReleaseFiles) -> None:
  (files.directory / "unexpected.txt").touch()
  with pytest.raises(ValueError, match="unexpected entry"):
    release.inspect_distributions(files.root, IDENTITY, files.directory)


def test_release_artifact_symlink_is_rejected_even_when_target_bytes_match(
  files: ReleaseFiles,
) -> None:
  artifact = files.directory / "packages" / IDENTITY.wheel_name
  outside = files.directory.parent / "retained-wheel"
  artifact.rename(outside)
  try:
    artifact.symlink_to(outside)
  except OSError as exc:
    pytest.skip(f"Symlinks unavailable: {exc}")
  with pytest.raises(ValueError, match="artifacts must be regular files"):
    release.inspect_distributions(files.root, IDENTITY, files.directory)


def test_source_reader_rejects_missing_files_and_directories(tmp_path: Path) -> None:
  for name in ("missing", "directory"):
    if name == "directory":
      (tmp_path / name).mkdir()
    with pytest.raises(ValueError, match="regular files"):
      release._source_bytes(tmp_path, name)


def test_source_reader_rejects_symlink_before_reading_target(tmp_path: Path) -> None:
  target = tmp_path / "synthetic-target"
  target.write_bytes(b"synthetic content")
  link = tmp_path / "link"
  try:
    link.symlink_to(target)
  except OSError as exc:
    pytest.skip(f"Symlinks unavailable: {exc}")
  with pytest.raises(ValueError, match="regular files"):
    release._source_bytes(tmp_path, "link")


@pytest.mark.parametrize("name", ["", "/absolute", "../parent", "a/../b", "a//b", "a/./b", "a\\b"])
def test_archive_paths_are_canonical_and_relative(name: str) -> None:
  with pytest.raises(ValueError, match="Unsafe archive"):
    release._safe_name(name)


@pytest.mark.parametrize(
  ("defect", "message"),
  [
    ("duplicate", "Duplicate sdist member"),
    ("link", "regular files"),
    ("root", "Unexpected sdist root"),
  ],
)
def test_sdist_rejects_ambiguous_or_link_members(tmp_path: Path, defect: str, message: str) -> None:
  path = tmp_path / "source.tar.gz"
  with tarfile.open(path, "w:gz") as archive:
    name = "other-0.1.0/file" if defect == "root" else "celestial_astrology-0.1.0/file"
    member = tarfile.TarInfo(name)
    if defect == "link":
      member.type = tarfile.SYMTYPE
      member.linkname = "outside"
    archive.addfile(member, BytesIO())
    if defect == "duplicate":
      archive.addfile(member, BytesIO())
  with pytest.raises(ValueError, match=message):
    release._sdist_members(path, IDENTITY)


def test_wheel_rejects_duplicate_members_with_different_bytes(tmp_path: Path) -> None:
  path = tmp_path / "wheel.whl"
  with ZipFile(path, "w") as archive:
    archive.writestr("astrology/__init__.py", b"first member")
    with pytest.warns(UserWarning, match="Duplicate name"):
      archive.writestr("astrology/__init__.py", b"different member")
  with pytest.raises(ValueError, match="Duplicate wheel member"):
    release._wheel_members(path)


@pytest.mark.parametrize("mode", [0, 0o40755, 0o100644])
def test_wheel_directory_entries_must_have_directory_or_unspecified_type(
  tmp_path: Path, mode: int
) -> None:
  path = tmp_path / "wheel.whl"
  with ZipFile(path, "w") as archive:
    member = ZipInfo("astrology/")
    member.external_attr = mode << 16
    archive.writestr(member, b"")
  if mode == 0o100644:
    with pytest.raises(ValueError, match="directory has an unsupported file type"):
      release._wheel_members(path)
  else:
    assert release._wheel_members(path) == {}


def test_wheel_rejects_link_members(tmp_path: Path) -> None:
  path = tmp_path / "wheel.whl"
  with ZipFile(path, "w") as archive:
    member = ZipInfo("astrology/link")
    member.external_attr = 0o120777 << 16
    archive.writestr(member, "outside")
  with pytest.raises(ValueError, match="regular files"):
    release._wheel_members(path)


@pytest.mark.parametrize(
  "defect", ["missing-digest", "uppercase-digest", "bytes", "manifest", "missing-manifest"]
)
def test_verify_does_not_trust_only_the_downloaded_manifest(
  files: ReleaseFiles, defect: str
) -> None:
  release.prepare(files.root, IDENTITY, files.directory, None)
  environment = files.expectations()
  if defect == "missing-digest":
    environment.pop("WHEEL_SHA256")
  elif defect == "uppercase-digest":
    environment["SDIST_SHA256"] = "A" * 64
  elif defect == "bytes":
    (files.directory / "packages" / IDENTITY.wheel_name).write_bytes(b"changed download")
  elif defect == "manifest":
    path = files.directory / "manifest.json"
    data = json.loads(path.read_text())
    data["source_sha"] = "b" * 40
    path.write_text(json.dumps(data))
  else:
    (files.directory / "manifest.json").unlink()
  with pytest.raises(ValueError, match=r"lowercase SHA-256|build-job digest|manifest"):
    release.verify(files.root, IDENTITY, files.directory, environment)


def test_consumer_installs_only_retained_wheel_and_keeps_all_acceptance_modes(
  files: ReleaseFiles, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  release.prepare(files.root, IDENTITY, files.directory, None)
  commands: list[tuple[str, ...]] = []
  readmes: list[tuple[str, ...]] = []
  missing_metadata: list[Path] = []

  def capture(command: Sequence[str], *, cwd: Path) -> None:
    commands.append(tuple(command))
    assert cwd.is_relative_to(tmp_path)
    if "--expected-observations" in command:
      assert Path(command[command.index("--expected-observations") + 1]).read_text() == (
        "runner-local-source-result"
      )
      assert Path(command[command.index("--expected-cross-observations") + 1]).read_text() == (
        "runner-local-cross-result"
      )

  monkeypatch.setattr(checker, "run", capture)
  monkeypatch.setattr("tools.installed_check.acceptance_chart", lambda: None)
  monkeypatch.setattr(
    "tools.installed_check.chart_observations", lambda _chart: "runner-local-source-result"
  )
  monkeypatch.setattr("tools.installed_check.acceptance_cross_aspects", lambda: None)
  monkeypatch.setattr(
    "tools.installed_check.cross_observations", lambda _result: "runner-local-cross-result"
  )
  monkeypatch.setattr(
    checker, "check_readme_examples", lambda root, python, work, mode: readmes.append(mode)
  )
  monkeypatch.setattr(
    checker,
    "check_missing_metadata",
    lambda env, python, script: missing_metadata.append(script),
  )
  environment = {**files.expectations(), "SCRATCH": str(tmp_path)}
  release.consume(files.root, IDENTITY, files.directory, environment)
  install = [command for command in commands if command[:3] == ("uv", "pip", "install")]
  assert len(install) == 1
  assert install[0][-1] == str(files.directory / "packages" / IDENTITY.wheel_name)
  assert not any("build" in command or "tools/check.py" in command for command in commands)
  consumers = [
    command for command in commands if str(files.root / "tools/installed_check.py") in command
  ]
  assert len(consumers) == 4
  assert ["--knowledge-only" in command for command in consumers] == [True, False, True, False]
  assert ["-O" in command for command in consumers] == [False, False, True, True]
  assert ["--expected-cross-observations" in command for command in consumers] == [
    False,
    True,
    False,
    True,
  ]
  assert all("-I" in command and "0.1.0" in command for command in consumers)
  assert readmes == [(), ("-O",)]
  assert len(missing_metadata) == 1


@pytest.mark.parametrize("operation", ["validate", "prepare", "consume"])
def test_cli_routes_only_the_selected_operation(
  files: ReleaseFiles, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
  calls: list[str] = []
  monkeypatch.setattr(release, "ROOT", files.root)
  monkeypatch.setattr(release, "release_identity", lambda root, env: IDENTITY)
  monkeypatch.setattr(sys, "argv", ["release.py", operation])
  monkeypatch.setattr(release, "validate", lambda root, identity, env: calls.append("validate"))
  monkeypatch.setattr(
    release, "prepare", lambda root, identity, directory, output: calls.append("prepare")
  )
  monkeypatch.setattr(
    release, "consume", lambda root, identity, directory, env: calls.append("consume")
  )
  release.main()
  assert calls == [operation]


def test_git_probe_uses_the_selected_repository(
  monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
  calls: list[tuple[str, ...]] = []

  def output(command: tuple[str, ...], *, text: bool) -> str:
    assert text
    calls.append(command)
    return SHA + "\n"

  monkeypatch.setattr(subprocess, "check_output", output)
  assert release._git(tmp_path, "rev-parse", "HEAD") == SHA
  assert calls == [("git", "-C", str(tmp_path), "rev-parse", "HEAD")]
