"""Check or explicitly publish one retained Gitee release. 检查或显式发布一份保留的 Gitee 发行。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

if __package__ in (None, ""):
  sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import release

GITHUB = "https://github.com/0xf3cd/astrology.git"
GITEE = "https://gitee.com"
DOWNLOAD_ORIGINS = frozenset({GITEE})
READ_ORIGINS = DOWNLOAD_ORIGINS | {"https://api.github.com", "https://pypi.org"}
MAX_FILE = 64 * 1024 * 1024
MAX_JSON = 2 * 1024 * 1024
MAX_PAGES = 20


class MirrorError(ValueError):
  """A safe operator diagnostic. 可安全显示给操作者的诊断。"""


class UncertainWrite(MirrorError):
  """A write needs anonymous readback before further action. 写入须先匿名回读再继续。"""


def _origin(url: str, origins: frozenset[str]) -> None:
  parts = urlsplit(url)
  if (
    parts.scheme != "https"
    or parts.username is not None
    or parts.password is not None
    or parts.port not in (None, 443)
    or f"https://{parts.hostname}" not in origins
    or parts.fragment
  ):
    raise MirrorError("Unsupported anonymous HTTPS origin")


class _Redirects(HTTPRedirectHandler):
  def __init__(self, origins: frozenset[str], writing: bool) -> None:
    self.origins, self.writing = origins, writing

  def redirect_request(
    self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
  ) -> Request | None:
    if self.writing:
      raise UncertainWrite("Credentialed redirect refused; inspect anonymous state")
    _origin(newurl, self.origins)
    return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http(
  url: str,
  *,
  data: bytes | None = None,
  content_type: str = "",
  limit: int = MAX_JSON,
  missing: bool = False,
  origins: frozenset[str] = READ_ORIGINS,
) -> bytes | None:
  _origin(url, frozenset({GITEE}) if data is not None else origins)
  opener = build_opener(ProxyHandler({}), _Redirects(origins, data is not None))
  request = Request(url, data=data)
  if data is not None:
    request.add_header("Content-Type", content_type)
  try:
    with opener.open(request, timeout=60) as response:
      result: bytes = response.read(limit + 1)
    if len(result) > limit:
      error = UncertainWrite if data is not None else MirrorError
      raise error("Remote response exceeds the size bound")
    return result
  except HTTPError as exc:
    status = exc.code
    exc.close()
    if data is None and missing and status == 404:
      return None
    error = UncertainWrite if data is not None else MirrorError
    raise error(f"HTTP operation failed (status {status}); no automatic retry") from None
  except (OSError, URLError):
    error = UncertainWrite if data is not None else MirrorError
    raise error("HTTP operation failed; no automatic retry") from None


def _json(url: str, *, missing: bool = False) -> Any:
  content = _http(url, missing=missing)
  return None if content is None else json.loads(content)


def _object(value: Any) -> dict[str, Any]:
  if not isinstance(value, dict):
    raise MirrorError("Expected an API object")
  return value


def _items(value: Any) -> list[dict[str, Any]]:
  if not isinstance(value, list):
    raise MirrorError("Expected an API list")
  return [_object(item) for item in value]


def _id(value: Any) -> int:
  if type(value) is not int or value <= 0:
    raise MirrorError("Invalid remote record ID")
  return int(value)


def _git(
  root: Path,
  arguments: Sequence[str],
  *,
  anonymous: bool = False,
) -> subprocess.CompletedProcess[str]:
  environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
  with tempfile.TemporaryDirectory(dir=os.environ.get("SCRATCH")) as temporary:
    if anonymous:
      environment = {
        key: os.environ[key] for key in ("PATH", "SYSTEMROOT") if key in os.environ
      } | {
        "HOME": temporary,
        "XDG_CONFIG_HOME": temporary,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "never",
      }
    try:
      result = subprocess.run(
        ("git", *arguments),
        cwd=Path(temporary) if anonymous else root,
        env=environment,
        capture_output=True,
        timeout=120,
        check=False,
      )
      return subprocess.CompletedProcess(
        result.args,
        result.returncode,
        result.stdout.decode("utf-8"),
        "",
      )
    except (OSError, subprocess.TimeoutExpired):
      raise MirrorError("Git operation failed; inspect partial remote state") from None


def _refs(root: Path, url: str, refs: tuple[str, ...]) -> dict[str, str]:
  result = _git(root, ("ls-remote", url, *refs), anonymous=True)
  if result.returncode:
    raise MirrorError("Anonymous Git read failed")
  found: dict[str, str] = {}
  for line in result.stdout.splitlines():
    fields = line.split()
    if (
      len(fields) != 2
      or fields[1] not in refs
      or fields[1] in found
      or re.fullmatch("[0-9a-f]{40}", fields[0]) is None
    ):
      raise MirrorError("Unexpected remote ref response")
    found[fields[1]] = fields[0]
  return found


def _peeled(refs: Mapping[str, str], tag: str) -> str | None:
  if tag + "^{}" in refs and tag not in refs:
    raise MirrorError("Peeled tag has no tag ref")
  return refs.get(tag + "^{}", refs.get(tag))


def _target(repository: str, branch: str) -> str:
  if re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", repository) is None:
    raise MirrorError("Use an explicit Gitee namespace/repository")
  if (
    re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch) is None
    or ".." in branch
    or "//" in branch
    or branch.endswith(("/", "."))
    or any(part.startswith(".") or part.endswith(".lock") for part in branch.split("/"))
  ):
    raise MirrorError("Invalid landing branch")
  return GITEE + "/api/v5/repos/" + "/".join(quote(part, safe="") for part in repository.split("/"))


def _notes(root: Path, identity: release.ReleaseIdentity) -> str:
  result = _git(root, ("show", f"{identity.source_sha}:docs/zh-CN/releases.md"))
  if result.returncode:
    raise MirrorError("Cannot read Chinese notes from the accepted Git object")
  text = result.stdout.replace("\r\n", "\n")
  sections = list(re.finditer(r"^## ([^\n]+)(?:\n|$)", text, re.MULTILINE))
  selected = [index for index, item in enumerate(sections) if item[1] == identity.version]
  if len(selected) != 1:
    raise MirrorError("Chinese release section is missing or duplicated")
  index = selected[0]
  end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
  body = text[sections[index].end() : end]
  if not body.strip():
    raise MirrorError("Chinese release section is empty")
  return body


def _files(
  root: Path,
  identity: release.ReleaseIdentity,
  directory: Path,
) -> dict[str, bytes]:
  tag = "refs/tags/v" + identity.version
  if _peeled(_refs(root, GITHUB, (tag, tag + "^{}")), tag) != identity.source_sha:
    raise MirrorError("GitHub tag differs from the accepted source")
  github = _object(
    _json("https://api.github.com/repos/0xf3cd/astrology/releases/tags/v" + identity.version)
  )
  if (
    github.get("tag_name") != "v" + identity.version
    or github.get("draft") is not False
    or github.get("prerelease") is not False
  ):
    raise MirrorError("GitHub Release is not the accepted stable release")
  names = {identity.wheel_name, identity.sdist_name, "manifest.json"}
  expected: dict[str, tuple[int, str]] = {}
  for asset in _items(github.get("assets")):
    name, size, digest = asset.get("name"), asset.get("size"), asset.get("digest")
    if (
      not isinstance(name, str)
      or name not in names
      or name in expected
      or type(size) is not int
      or not 0 < size <= MAX_FILE
      or not isinstance(digest, str)
      or re.fullmatch("sha256:[0-9a-f]{64}", digest) is None
      or asset.get("state") != "uploaded"
    ):
      raise MirrorError("Invalid, duplicate or unexpected GitHub asset metadata")
    expected[name] = (size, digest.removeprefix("sha256:"))
  if set(expected) != names:
    raise MirrorError("GitHub Release lacks the original three assets")
  pypi = _object(_json(f"https://pypi.org/pypi/celestial-astrology/{identity.version}/json"))
  if _object(pypi.get("info")).get("version") != identity.version:
    raise MirrorError("PyPI release identity differs")
  packages = _items(pypi.get("urls"))
  if len(packages) != 2 or {item.get("filename") for item in packages} != names - {"manifest.json"}:
    raise MirrorError("PyPI distribution filenames differ")
  for item in packages:
    if _object(item.get("digests")).get("sha256") != expected[item["filename"]][1]:
      raise MirrorError("PyPI and GitHub distribution digests differ")
  release._packages(directory, identity)
  buffers: dict[str, bytes] = {}
  for name, (size, digest) in expected.items():
    path = directory / ("packages/" + name if name != "manifest.json" else name)
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
      raise MirrorError("Original file type or size differs")
    with path.open("rb") as stream:
      content = stream.read(size + 1)
    if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
      raise MirrorError("Original raw file digest differs")
    buffers[name] = content
  with tempfile.TemporaryDirectory(dir=os.environ.get("SCRATCH")) as temporary:
    snapshot = Path(temporary)
    (snapshot / "packages").mkdir()
    for name, content in buffers.items():
      (snapshot / ("packages/" + name if name != "manifest.json" else name)).write_bytes(content)
    release.verify(
      root,
      identity,
      snapshot,
      {
        "WHEEL_SHA256": expected[identity.wheel_name][1],
        "SDIST_SHA256": expected[identity.sdist_name][1],
      },
    )
  return buffers


def _inventory(url: str, buffers: Mapping[str, bytes]) -> set[str]:
  records: list[dict[str, Any]] = []
  ids: set[int] = set()
  for page in range(1, MAX_PAGES + 1):
    batch = _items(_json(url + f"?page={page}&per_page=100&direction=asc"))
    if len(batch) > 100:
      raise MirrorError("Attachment page exceeds the bound")
    for item in batch:
      record_id = _id(item.get("id"))
      if record_id in ids:
        raise MirrorError("Repeated attachment ID in pagination")
      ids.add(record_id)
    records.extend(batch)
    if len(batch) < 100:
      break
  else:
    raise MirrorError("Attachment pagination exceeds the bound")
  present: set[str] = set()
  for item in records:
    record_id, name = _id(item.get("id")), item.get("name")
    if not isinstance(name, str) or name not in buffers or name in present:
      raise MirrorError(f"Unexpected or duplicate attachment (ID {record_id})")
    data = buffers[name]
    if type(item.get("size")) is not int or item["size"] != len(data):
      raise MirrorError(f"Conflicting attachment size (ID {record_id})")
    downloaded = _http(
      url + f"/{record_id}/download",
      limit=len(data),
      origins=DOWNLOAD_ORIGINS,
    )
    if downloaded is None or hashlib.sha256(downloaded).digest() != hashlib.sha256(data).digest():
      raise MirrorError(f"Conflicting attachment bytes (ID {record_id})")
    present.add(name)
  return present


def _post(url: str, fields: Mapping[str, str], file: tuple[str, bytes] | None = None) -> None:
  if not url.startswith(GITEE + "/api/v5/repos/"):
    raise MirrorError("Invalid credentialed API destination")
  token = os.environ.get("GITEE_ACCESS_TOKEN", "")
  if not token:
    raise MirrorError("GITEE_ACCESS_TOKEN is required for API writes")
  values = {**fields, "access_token": token}
  data, content_type = urlencode(values).encode(), "application/x-www-form-urlencoded"
  if file is not None:
    boundary = uuid.uuid4().hex
    parts = [
      f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
      for key, value in values.items()
    ]
    name, content = file
    parts.extend(
      [
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n".encode(),
        content,
        f"\r\n--{boundary}--\r\n".encode(),
      ]
    )
    data, content_type = b"".join(parts), "multipart/form-data; boundary=" + boundary
  _http(url, data=data, content_type=content_type)


def _release(url: str, tag: str, body: str) -> dict[str, Any] | None:
  value = _json(url + "/releases/tags/" + quote(tag, safe=""), missing=True)
  if value is None:
    return None
  record = _object(value)
  _id(record.get("id"))
  if (
    record.get("tag_name") != tag
    or record.get("name") != tag
    or record.get("prerelease") is not False
    or not isinstance(record.get("body"), str)
    or record["body"].replace("\r\n", "\n") != body
  ):
    raise MirrorError("Existing Gitee release metadata conflicts")
  return record


def mirror(
  root: Path,
  identity: release.ReleaseIdentity,
  repository: str,
  branch: str,
  directory: Path,
  *,
  publish: bool = False,
) -> None:
  """Verify retained bytes and remote state; publish only when explicit.

  核验保留字节及远端状态；仅在显式请求时发布。
  """
  url = _target(repository, branch)
  release.release_identity(
    root,
    {"RELEASE_VERSION": identity.version, "RELEASE_SHA": identity.source_sha},
  )
  release.check_checkout(root, identity)
  buffers, body = _files(root, identity, directory), _notes(root, identity)
  branch_ref, tag_ref = "refs/heads/" + branch, "refs/tags/v" + identity.version
  git_url, tag = GITEE + "/" + repository + ".git", "v" + identity.version
  repo = _object(_json(url))
  if repo.get("public") is not True:
    raise MirrorError("Gitee repository must be publicly readable")
  refs = _refs(root, git_url, (branch_ref, tag_ref, tag_ref + "^{}"))
  default = repo.get("default_branch")
  if default != branch and (default not in (None, "") or refs):
    raise MirrorError("Gitee default branch differs; operator configuration required")
  if default != branch:
    empty = _git(root, ("ls-remote", git_url), anonymous=True)
    if empty.returncode or empty.stdout.strip():
      raise MirrorError("Cannot establish an empty public repository")
  if _peeled(refs, tag_ref) not in (None, identity.source_sha):
    raise MirrorError("Gitee tag conflicts")
  if branch_ref in refs and refs[branch_ref] != identity.source_sha:
    ancestry = _git(root, ("merge-base", "--is-ancestor", refs[branch_ref], identity.source_sha))
    if ancestry.returncode:
      raise MirrorError("Landing branch is ahead, divergent or has unknown ancestry")
  record = _release(url, tag, body)
  present = (
    set()
    if record is None
    else _inventory(
      url + f"/releases/{_id(record['id'])}/attach_files",
      buffers,
    )
  )
  if not publish:
    print(f"Read-only check passed: {len(present)}/3 attachments; publication not performed")
    return
  if (record is None or present != set(buffers)) and not os.environ.get("GITEE_ACCESS_TOKEN"):
    raise MirrorError("GITEE_ACCESS_TOKEN is required before publication writes")
  for ref in (branch_ref, tag_ref):
    resolved = refs.get(ref) if ref == branch_ref else _peeled(refs, ref)
    if resolved != identity.source_sha:
      try:
        result = _git(
          root,
          (
            "-c",
            "push.followTags=false",
            "push",
            "--no-mirror",
            "--no-follow-tags",
            "--recurse-submodules=no",
            git_url,
            identity.source_sha + ":" + ref,
          ),
        )
      except MirrorError:
        result = None
      observed = _refs(root, git_url, (ref, ref + "^{}") if ref == tag_ref else (ref,))
      commit = observed.get(ref) if ref == branch_ref else _peeled(observed, ref)
      if commit != identity.source_sha:
        raise MirrorError("Ref transfer incomplete; inspect partial remote state")
      if result is None or result.returncode:
        print("Git write reported failure; anonymous readback confirms the selected ref")
  final_refs = _refs(root, git_url, (branch_ref, tag_ref, tag_ref + "^{}"))
  if (
    final_refs.get(branch_ref) != identity.source_sha
    or _peeled(final_refs, tag_ref) != identity.source_sha
  ):
    raise MirrorError("Ref readback differs from the accepted source")
  if _object(_json(url)).get("default_branch") != branch:
    raise MirrorError("Default-branch readback differs; operator configuration required")
  if record is None:
    with suppress(UncertainWrite):
      _post(
        url + "/releases",
        {
          "tag_name": tag,
          "name": tag,
          "body": body,
          "prerelease": "false",
          "target_commitish": identity.source_sha,
        },
      )
    record = _release(url, tag, body)
    if record is None:
      raise UncertainWrite("Release creation is unconfirmed; inspect before an explicit rerun")
  attachments = url + f"/releases/{_id(record['id'])}/attach_files"
  present = _inventory(attachments, buffers)
  for name, data in buffers.items():
    if name not in present:
      try:
        _post(attachments, {}, (name, data))
      except UncertainWrite:
        observed_names = _inventory(attachments, buffers)
        if name not in observed_names:
          raise UncertainWrite("Upload is unconfirmed; inspect before an explicit rerun") from None
      present = _inventory(attachments, buffers)
      if name not in present:
        raise UncertainWrite("Upload is unconfirmed; inspect before an explicit rerun")
  if _inventory(attachments, buffers) != set(buffers):
    raise MirrorError("Final attachment inventory is incomplete")
  if _release(url, tag, body) is None:
    raise MirrorError("Final release readback is missing")
  print("Mirror verified by anonymous ref, default-branch, notes and three-file readback")


def main() -> None:
  """Run an explicit check or publication command. 执行显式检查或发布命令。"""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("operation", choices=("check", "publish"))
  parser.add_argument("--version", required=True)
  parser.add_argument("--sha", required=True)
  parser.add_argument("--repository", required=True)
  parser.add_argument("--branch", required=True)
  parser.add_argument("--files", type=Path, required=True)
  args = parser.parse_args()
  try:
    mirror(
      release.ROOT,
      release.ReleaseIdentity(args.version, args.sha),
      args.repository,
      args.branch,
      args.files,
      publish=args.operation == "publish",
    )
  except MirrorError as exc:
    parser.exit(1, str(exc) + "\n")
  except (ValueError, TypeError, KeyError, OSError):
    parser.exit(1, "Mirror verification failed; no automatic retry or rollback\n")


if __name__ == "__main__":
  main()
