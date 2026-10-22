"""Inspect retained release files and consume the same wheel. 检查保留的发行文件并消费同一 wheel。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZipFile

if __package__ in (None, ""):
  sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import astrology
from astrology._distribution import DISTRIBUTION_NAME
from tools.check import (
  check_missing_metadata,
  check_readme_examples,
  check_sdist,
  check_wheel,
  run,
)
from tools.installed_check import acceptance_chart

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_NAME = DISTRIBUTION_NAME.replace("-", "_")


@dataclass(frozen=True)
class ReleaseIdentity:
  """Requested release version and full source commit. 请求的发行版本及完整源码提交号。"""

  version: str
  source_sha: str

  def __post_init__(self) -> None:
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.version) is None:
      raise ValueError("Release version must have three numeric components")
    if re.fullmatch(r"[0-9a-f]{40}", self.source_sha) is None:
      raise ValueError("Release source must be a full lowercase commit SHA")

  @property
  def sdist_name(self) -> str:
    """Expected source-distribution filename. 预期的源码分发文件名。"""
    return f"{NORMALIZED_NAME}-{self.version}.tar.gz"

  @property
  def wheel_name(self) -> str:
    """Expected platform-independent wheel filename. 预期的平台无关 wheel 文件名。"""
    return f"{NORMALIZED_NAME}-{self.version}-py3-none-any.whl"


def _project(root: Path) -> dict[str, Any]:
  project: dict[str, Any] = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
    "project"
  ]
  return project


def _git(root: Path, *arguments: str) -> str:
  return subprocess.check_output(("git", "-C", str(root), *arguments), text=True).strip()


def release_identity(root: Path, environment: Mapping[str, str]) -> ReleaseIdentity:
  """Resolve explicit release inputs; PR validation may use project metadata.

  解析显式发行输入；PR 验证可以使用项目元数据中的版本。
  """
  project = _project(root)
  requested = environment.get("RELEASE_VERSION", "")
  if environment.get("GITHUB_EVENT_NAME") == "pull_request" and not requested:
    requested = project["version"]
  identity = ReleaseIdentity(requested, environment.get("RELEASE_SHA", ""))
  if project["name"] != DISTRIBUTION_NAME or project["version"] != identity.version:
    raise ValueError("Requested release identity differs from project metadata")
  return identity


def check_checkout(root: Path, identity: ReleaseIdentity) -> None:
  """Require the named unchanged source checkout. 要求检出的源码与指定提交一致且没有未提交变更。"""
  if _git(root, "rev-parse", "HEAD") != identity.source_sha:
    raise ValueError("Checked-out source differs from the requested SHA")
  if _git(root, "status", "--porcelain", "--untracked-files=all"):
    raise ValueError("Release checkout has uncommitted files")


def validate(root: Path, identity: ReleaseIdentity, environment: Mapping[str, str]) -> None:
  """Check the PR or manual-main invocation before building. 构建前检查 PR 或手动 main 调用。"""
  check_checkout(root, identity)
  event = environment.get("GITHUB_EVENT_NAME")
  if event == "pull_request":
    return
  if event != "workflow_dispatch" or environment.get("GITHUB_REF") != "refs/heads/main":
    raise ValueError("Publication preparation requires a manual dispatch on main")
  remote = _git(root, "ls-remote", "origin", "refs/heads/main").split()
  if remote != [identity.source_sha, "refs/heads/main"]:
    raise ValueError("Requested source is not the current remote main")


def _digest(path: Path) -> str:
  with path.open("rb") as stream:
    return hashlib.file_digest(stream, "sha256").hexdigest()


def _safe_name(name: str) -> None:
  path = PurePosixPath(name)
  if (
    not name
    or path.is_absolute()
    or "\\" in name
    or any(part in ("", ".", "..") for part in name.split("/"))
  ):
    raise ValueError("Unsafe archive member path")


def _sdist_members(path: Path, identity: ReleaseIdentity) -> dict[str, bytes]:
  prefix = f"{NORMALIZED_NAME}-{identity.version}"
  members: dict[str, bytes] = {}
  seen: set[str] = set()
  with tarfile.open(path) as archive:
    for member in archive.getmembers():
      name = member.name.rstrip("/")
      _safe_name(name)
      if name in seen or name.split("/", 1)[0] != prefix:
        raise ValueError("Duplicate member or unexpected sdist root")
      seen.add(name)
      if member.isdir():
        continue
      if not member.isfile() or "/" not in name:
        raise ValueError("Sdist must contain only regular files and directories")
      stream = archive.extractfile(member)
      if stream is None:
        raise ValueError("Unreadable sdist member")
      with stream:
        members[name.split("/", 1)[1]] = stream.read()
  return members


def _wheel_members(path: Path) -> dict[str, bytes]:
  members: dict[str, bytes] = {}
  seen: set[str] = set()
  with ZipFile(path) as archive:
    for member in archive.infolist():
      name = member.filename.rstrip("/")
      _safe_name(name)
      if name in seen:
        raise ValueError("Duplicate wheel member")
      seen.add(name)
      mode = stat.S_IFMT(member.external_attr >> 16)
      if member.is_dir():
        if mode not in (0, stat.S_IFDIR):
          raise ValueError("Wheel directory has an unsupported file type")
        continue
      if mode not in (0, stat.S_IFREG):
        raise ValueError("Wheel must contain regular files")
      members[name] = archive.read(member)
  return members


def _check_metadata(content: bytes, project: Mapping[str, Any]) -> None:
  metadata = BytesParser().parsebytes(content)
  if metadata["Name"] != project["name"] or metadata["Version"] != project["version"]:
    raise ValueError("Archive metadata has a different release identity")
  if {part.strip() for part in (metadata["Requires-Python"] or "").split(",")} != {
    part.strip() for part in project["requires-python"].split(",")
  }:
    raise ValueError("Archive metadata changed the supported Python range")
  if sorted(value.replace(" ", "") for value in metadata.get_all("Requires-Dist", [])) != sorted(
    project["dependencies"]
  ):
    raise ValueError("Archive metadata changed the runtime dependency policy")


def _inventory(
  members: Mapping[str, bytes], expected: Mapping[str, bytes], generated: set[str]
) -> list[dict[str, object]]:
  if missing := set(expected) - set(members):
    raise ValueError(f"Archive is missing source members: {sorted(missing)}")
  if extra := set(members) - set(expected) - generated:
    raise ValueError(f"Archive has unexpected members: {sorted(extra)}")
  for name, content in expected.items():
    if members[name] != content:
      raise ValueError(f"Archive member differs from the source checkout: {name}")
  return [
    {"path": name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    for name, content in sorted(members.items())
  ]


def _source_bytes(root: Path, name: str) -> bytes:
  source = root / name
  if source.is_symlink() or not source.is_file():
    raise ValueError("Release source members must be regular files")
  return source.read_bytes()


def _packages(directory: Path, identity: ReleaseIdentity) -> Path:
  if (
    directory.is_symlink()
    or not directory.is_dir()
    or {path.name for path in directory.iterdir()} - {"packages", "manifest.json"}
  ):
    raise ValueError("Release directory has an unexpected entry or file type")
  packages = directory / "packages"
  names = {identity.sdist_name, identity.wheel_name}
  if (
    packages.is_symlink() or not packages.is_dir() or {p.name for p in packages.iterdir()} != names
  ):
    raise ValueError("Release package directory must contain exactly the named sdist and wheel")
  for name in names:
    path = packages / name
    if path.is_symlink() or not path.is_file():
      raise ValueError("Release artifacts must be regular files")
  return packages


def inspect_distributions(
  root: Path, identity: ReleaseIdentity, directory: Path
) -> dict[str, object]:
  """Bind archive members and metadata to this source; return their manifest.

  将归档成员及元数据与当前源码绑定，并返回清单。
  """
  packages = _packages(directory, identity)
  sdist, wheel = packages / identity.sdist_name, packages / identity.wheel_name
  check_sdist(sdist)
  check_wheel(wheel, identity.version)
  tracked = _git(root, "ls-files", "-z").split("\0")
  sources: dict[str, bytes] = {}
  sdist_members = _sdist_members(sdist, identity)
  for name in sdist_members:
    if name in tracked:
      sources[name] = _source_bytes(root, name)
  package_sources = {
    name.removeprefix("src/"): _source_bytes(root, name)
    for name in tracked
    if name.startswith("src/astrology/")
  }
  if not package_sources or not {"src/" + name for name in package_sources}.issubset(sources):
    raise ValueError("Sdist is missing tracked package sources")
  egg_info = f"src/{NORMALIZED_NAME}.egg-info/"
  generated_sdist = {
    "PKG-INFO",
    "setup.cfg",
    *(
      egg_info + name
      for name in (
        "PKG-INFO",
        "SOURCES.txt",
        "requires.txt",
        "dependency_links.txt",
        "top_level.txt",
      )
    ),
  }
  dist_info = f"{NORMALIZED_NAME}-{identity.version}.dist-info/"
  wheel_members = _wheel_members(wheel)
  project = _project(root)
  _check_metadata(sdist_members["PKG-INFO"], project)
  _check_metadata(wheel_members[dist_info + "METADATA"], project)
  wheel_sources = {
    **package_sources,
    dist_info + "licenses/LICENSE": _source_bytes(root, "LICENSE"),
  }
  inventories = {
    identity.sdist_name: _inventory(sdist_members, sources, generated_sdist),
    identity.wheel_name: _inventory(
      wheel_members,
      wheel_sources,
      {dist_info + name for name in ("METADATA", "WHEEL", "RECORD", "top_level.txt")},
    ),
  }
  return {
    "schema_version": 1,
    "distribution": DISTRIBUTION_NAME,
    "version": identity.version,
    "source_sha": identity.source_sha,
    "corpus_version": astrology.load_catalog().version,
    "requires_python": project["requires-python"],
    "dependencies": project["dependencies"],
    "artifacts": {
      name: {
        "sha256": _digest(packages / name),
        "size": (packages / name).stat().st_size,
        "members": members,
      }
      for name, members in inventories.items()
    },
  }


def prepare(root: Path, identity: ReleaseIdentity, directory: Path, output: Path | None) -> None:
  """Inspect already-checked files and emit their identity/digests without rebuilding.

  检查已通过检查的文件并输出身份及摘要，不重新构建。
  """
  check_checkout(root, identity)
  manifest = inspect_distributions(root, identity, directory)
  with (directory / "manifest.json").open("x", encoding="utf-8") as stream:
    json.dump(manifest, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
  if output is not None:
    values = {
      "version": identity.version,
      "source_sha": identity.source_sha,
      "sdist_name": identity.sdist_name,
      "wheel_name": identity.wheel_name,
      "sdist_sha256": _digest(directory / "packages" / identity.sdist_name),
      "wheel_sha256": _digest(directory / "packages" / identity.wheel_name),
    }
    with output.open("a", encoding="utf-8") as stream:
      stream.writelines(f"{key}={value}\n" for key, value in values.items())


def verify(
  root: Path, identity: ReleaseIdentity, directory: Path, environment: Mapping[str, str]
) -> None:
  """Verify external digest expectations before inspecting the artifact manifest.

  先核对外部传入的预期摘要，再检查制品清单。
  """
  packages = _packages(directory, identity)
  for name, variable in (
    (identity.sdist_name, "SDIST_SHA256"),
    (identity.wheel_name, "WHEEL_SHA256"),
  ):
    expected = environment.get(variable, "")
    path = packages / name
    if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
      raise ValueError("Expected artifact digest must be a lowercase SHA-256")
    if path.is_symlink() or not path.is_file() or _digest(path) != expected:
      raise ValueError("Artifact bytes differ from the build-job digest")
  manifest = directory / "manifest.json"
  if manifest.is_symlink() or not manifest.is_file():
    raise ValueError("Release manifest must be a regular file")
  if json.loads(manifest.read_text(encoding="utf-8")) != inspect_distributions(
    root, identity, directory
  ):
    raise ValueError("Release manifest differs from the source and artifact inventory")


def consume(
  root: Path, identity: ReleaseIdentity, directory: Path, environment: Mapping[str, str]
) -> None:
  """Install the retained wheel and compare it with this runner's source result.

  安装保留的 wheel，并与当前 runner 上源码计算的结果比较。
  """
  check_checkout(root, identity)
  verify(root, identity, directory, environment)
  with tempfile.TemporaryDirectory(
    prefix="astrology-release-", dir=environment.get("SCRATCH")
  ) as temporary:
    work = Path(temporary)
    expected_chart = work / "source-chart.json"
    expected_chart.write_text(astrology.dumps_chart(acceptance_chart()), encoding="utf-8")
    consumer = work / "consumer"
    run(("uv", "venv", "--python", sys.executable, str(consumer)), cwd=work)
    python = consumer / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run(
      (
        "uv",
        "pip",
        "install",
        "--python",
        str(python),
        str(directory / "packages" / identity.wheel_name),
      ),
      cwd=work,
    )
    script = root / "tools/installed_check.py"
    corpus = astrology.load_catalog().version
    for mode in ((), ("-O",)):
      run(
        (str(python), *mode, "-I", str(script), identity.version, corpus, "--knowledge-only"),
        cwd=work,
      )
      check_readme_examples(root, python, work, mode)
      run(
        (
          str(python),
          *mode,
          "-I",
          str(script),
          identity.version,
          corpus,
          "--expected-chart",
          str(expected_chart),
        ),
        cwd=work,
      )
    check_missing_metadata(consumer, python, script, expected_chart)


def main() -> None:
  """Run one explicit release-tool operation. 执行一个显式的发行工具操作。"""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("operation", choices=("validate", "prepare", "consume"))
  arguments = parser.parse_args()
  identity = release_identity(ROOT, os.environ)
  directory = ROOT / "dist"
  if arguments.operation == "validate":
    validate(ROOT, identity, os.environ)
  elif arguments.operation == "prepare":
    output = os.environ.get("GITHUB_OUTPUT")
    prepare(ROOT, identity, directory, Path(output) if output else None)
  else:
    consume(ROOT, identity, directory, os.environ)


if __name__ == "__main__":
  main()
