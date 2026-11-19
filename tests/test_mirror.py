"""Verified mirror state and credential boundaries. 核验镜像状态及凭据边界。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from tests.test_release import IDENTITY, SHA, ReleaseFiles
from tests.test_release import files as files
from tools import mirror, release

API = "https://gitee.com/api/v5/repos/example/project"
BRANCH = "refs/heads/main"
TAG = "refs/tags/v0.1.0"
NOTES = "\n中文发行。\n\n"


@dataclass
class Remote:
  files: ReleaseFiles
  buffers: dict[str, bytes]
  github: dict[str, Any]
  pypi: dict[str, Any]
  refs: dict[str, str] = field(default_factory=lambda: {BRANCH: SHA, TAG: SHA})
  repo: dict[str, Any] = field(default_factory=lambda: {"public": True, "default_branch": "main"})
  record: dict[str, Any] | None = None
  attachments: list[dict[str, Any]] = field(default_factory=list)
  downloads: dict[int, bytes] = field(default_factory=dict)
  writes: list[tuple[str, Any]] = field(default_factory=list)
  reads: list[str] = field(default_factory=list)
  notes: str = "# Notes\n\n## 0.1.0\n" + NOTES + "## 0.0.9\nolder\n"
  ancestor: int = 0
  ambiguous: str = ""
  observe_write: bool = True

  def get(self, url: str, *, missing: bool = False) -> Any:
    self.reads.append(url)
    if url.startswith("https://api.github.com/"):
      return self.github
    if url.startswith("https://pypi.org/"):
      return self.pypi
    if url == API:
      return self.repo
    if "/releases/tags/" in url:
      assert missing
      return self.record
    if "/attach_files?" in url:
      page = int(url.split("page=")[1].split("&")[0])
      return self.attachments[(page - 1) * 100 : page * 100]
    raise AssertionError(url)

  def http(self, url: str, **kwargs: Any) -> bytes:
    assert kwargs["origins"] == mirror.DOWNLOAD_ORIGINS
    assert "data" not in kwargs
    return self.downloads[int(url.split("/")[-2])]

  def git(
    self,
    root: Path,
    arguments: Sequence[str],
    *,
    anonymous: bool = False,
  ) -> subprocess.CompletedProcess[str]:
    assert root == self.files.root
    args = tuple(arguments)
    if args[0] == "ls-remote":
      assert anonymous
      refs = {TAG: SHA} if args[1] == mirror.GITHUB else self.refs
      selected = (
        refs if len(args) == 2 else {key: val for key, val in refs.items() if key in args[2:]}
      )
      output = "".join(f"{val}\t{key}\n" for key, val in selected.items())
      return subprocess.CompletedProcess(args, 0, output)
    assert not anonymous
    if args[0] == "show":
      assert args[1] == f"{SHA}:docs/zh-CN/releases.md"
      return subprocess.CompletedProcess(args, 0, self.notes)
    if args[0] == "merge-base":
      return subprocess.CompletedProcess(args, self.ancestor, "")
    assert args[:5] == ("-c", "push.followTags=false", "push", "--no-mirror", "--no-follow-tags")
    assert args[5:7] == ("--recurse-submodules=no", "https://gitee.com/example/project.git")
    sha, ref = args[7].split(":")
    assert sha == SHA and ref in (BRANCH, TAG)
    self.writes.append(("git", ref))
    self.refs[ref] = sha
    if not self.repo.get("default_branch"):
      self.repo["default_branch"] = "main"
    return subprocess.CompletedProcess(args, 0, "")

  def post(
    self,
    url: str,
    fields: Mapping[str, str],
    file: tuple[str, bytes] | None = None,
  ) -> None:
    self.writes.append((url, file if file is not None else dict(fields)))
    if self.observe_write:
      if file is None:
        assert fields["target_commitish"] == SHA
        self.record = {"id": 1, **fields, "prerelease": False}
      else:
        name, data = file
        record_id = len(self.attachments) + 1
        self.attachments.append({"id": record_id, "name": name, "size": len(data)})
        self.downloads[record_id] = data
    if self.ambiguous == ("release" if file is None else "upload"):
      raise mirror.UncertainWrite("synthetic ambiguous response")

  def run(self, *, publish: bool = False) -> None:
    mirror.mirror(
      self.files.root,
      IDENTITY,
      "example/project",
      "main",
      self.files.directory,
      publish=publish,
    )

  def complete(self) -> None:
    self.post(
      API + "/releases",
      {
        "tag_name": "v0.1.0",
        "name": "v0.1.0",
        "body": NOTES,
        "target_commitish": SHA,
      },
    )
    for file in self.buffers.items():
      self.post(API + "/releases/1/attach_files", {}, file)
    self.writes.clear()


@pytest.fixture
def remote(files: ReleaseFiles, monkeypatch: pytest.MonkeyPatch) -> Remote:
  release.prepare(files.root, IDENTITY, files.directory, None)
  buffers = {
    name: (files.directory / ("packages/" + name if name != "manifest.json" else name)).read_bytes()
    for name in (IDENTITY.wheel_name, IDENTITY.sdist_name, "manifest.json")
  }
  github = {
    "tag_name": "v0.1.0",
    "draft": False,
    "prerelease": False,
    "assets": [
      {
        "name": name,
        "size": len(data),
        "state": "uploaded",
        "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
      }
      for name, data in buffers.items()
    ],
  }
  pypi = {
    "info": {"version": "0.1.0"},
    "urls": [
      {"filename": name, "digests": {"sha256": hashlib.sha256(data).hexdigest()}}
      for name, data in buffers.items()
      if name != "manifest.json"
    ],
  }
  result = Remote(files, buffers, github, pypi)
  monkeypatch.setattr(mirror, "_json", result.get)
  monkeypatch.setattr(mirror, "_http", result.http)
  monkeypatch.setattr(mirror, "_git", result.git)
  monkeypatch.setattr(mirror, "_post", result.post)
  monkeypatch.setenv("GITEE_ACCESS_TOKEN", "synthetic-marker")
  return result


def test_check_is_read_only_with_missing_and_complete_states(
  remote: Remote,
  capsys: pytest.CaptureFixture[str],
) -> None:
  remote.run()
  assert remote.writes == []
  remote.complete()
  remote.run()
  assert remote.writes == []
  assert "3/3" in capsys.readouterr().out


def test_publish_and_idempotent_rerun_use_only_original_three_files(remote: Remote) -> None:
  remote.refs.clear()
  remote.repo["default_branch"] = ""
  remote.run(publish=True)
  assert remote.writes[:2] == [("git", BRANCH), ("git", TAG)]
  assert len(remote.writes) == 6
  assert remote.downloads == dict(enumerate(remote.buffers.values(), 1))
  remote.writes.clear()
  remote.run(publish=True)
  assert remote.writes == []


@pytest.mark.parametrize("defect", ["sha", "dirty", "version"])
def test_wrong_checkout_stops_before_remote_access(
  remote: Remote,
  monkeypatch: pytest.MonkeyPatch,
  defect: str,
) -> None:
  original = release._git
  if defect == "version":
    path = remote.files.root / "pyproject.toml"
    path.write_text(path.read_text().replace('version="0.1.0"', 'version="0.9.0"'))
  else:

    def git(root: Path, *args: str) -> str:
      if args == ("rev-parse", "HEAD") and defect == "sha":
        return "b" * 40
      if args[0] == "status" and defect == "dirty":
        return " M source.py"
      return original(root, *args)

    monkeypatch.setattr(release, "_git", git)
  with pytest.raises(ValueError):
    remote.run(publish=True)
  assert remote.writes == []
  assert remote.reads == []


@pytest.mark.parametrize(
  "defect",
  [
    "tag",
    "draft",
    "prerelease",
    "state",
    "digest",
    "size",
    "name",
    "duplicate",
    "missing",
    "extra",
    "pypi",
  ],
)
def test_authoritative_anchors_reject_bad_metadata(
  remote: Remote,
  monkeypatch: pytest.MonkeyPatch,
  defect: str,
) -> None:
  if defect == "tag":
    original = remote.git

    def git(
      root: Path,
      args: Sequence[str],
      *,
      anonymous: bool = False,
    ) -> subprocess.CompletedProcess[str]:
      result = original(root, args, anonymous=anonymous)
      if mirror.GITHUB in args:
        result.stdout = result.stdout.replace(SHA, "b" * 40)
      return result

    monkeypatch.setattr(mirror, "_git", git)
  elif defect in ("draft", "prerelease"):
    remote.github[defect] = True
  elif defect == "pypi":
    remote.pypi["urls"][0]["digests"]["sha256"] = "0" * 64
  elif defect in ("missing", "duplicate", "extra"):
    if defect == "missing":
      remote.github["assets"].pop()
    else:
      item = dict(remote.github["assets"][0])
      if defect == "extra":
        item["name"] = "unexpected"
      remote.github["assets"].append(item)
  else:
    bad = {"size": 0, "state": "new", "digest": None, "name": "../bad"}
    remote.github["assets"][0][defect] = bad[defect]
  with pytest.raises(mirror.MirrorError):
    remote.run(publish=True)
  assert remote.writes == []


@pytest.mark.parametrize("name", ["manifest.json", IDENTITY.wheel_name, IDENTITY.sdist_name])
def test_changed_raw_bytes_fail_before_semantic_verification(
  remote: Remote,
  monkeypatch: pytest.MonkeyPatch,
  name: str,
) -> None:
  path = remote.files.directory / ("packages/" + name if name != "manifest.json" else name)
  if name == "manifest.json":
    content = json.dumps(json.loads(path.read_bytes()), separators=(",", ":")).encode()
    assert json.loads(content) == json.loads(path.read_bytes())
  else:
    content = b"changed original"
  path.write_bytes(content)
  monkeypatch.setattr(release, "verify", lambda *args: pytest.fail("Raw anchor must run first"))
  with pytest.raises(mirror.MirrorError, match=r"size|digest"):
    remote.run(publish=True)
  assert remote.writes == []


def test_raw_manifest_digest_matters_even_with_equal_length(remote: Remote) -> None:
  path = remote.files.directory / "manifest.json"
  data = path.read_bytes().replace(b"  ", b"\t ", 1)
  assert len(data) == len(path.read_bytes()) and json.loads(data) == json.loads(path.read_bytes())
  path.write_bytes(data)
  with pytest.raises(mirror.MirrorError, match="raw file digest"):
    remote.run(publish=True)
  assert remote.writes == []


def test_semantic_manifest_and_source_agreement_still_run(remote: Remote) -> None:
  path = remote.files.directory / "manifest.json"
  data = path.read_bytes().replace(SHA.encode(), ("b" * 40).encode())
  path.write_bytes(data)
  remote.github["assets"][-1]["digest"] = "sha256:" + hashlib.sha256(data).hexdigest()
  with pytest.raises(ValueError, match="manifest differs"):
    remote.run(publish=True)
  assert remote.writes == []


def test_verified_immutable_buffers_ignore_later_file_changes_and_environment(
  remote: Remote,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  original = remote.post

  def post(url: str, fields: Mapping[str, str], file: tuple[str, bytes] | None = None) -> None:
    if file is None:
      for name in remote.buffers:
        path = remote.files.directory / ("packages/" + name if name != "manifest.json" else name)
        path.write_bytes(b"changed after verification")
    original(url, fields, file)

  monkeypatch.setattr(mirror, "_post", post)
  monkeypatch.setenv("WHEEL_SHA256", "unrelated environment expectation")
  monkeypatch.setenv("SDIST_SHA256", "unrelated environment expectation")
  remote.run(publish=True)
  assert set(remote.downloads.values()) == set(remote.buffers.values())


@pytest.mark.parametrize(
  "defect",
  ["default", "tag", "ahead", "unknown", "not-public", "not-empty"],
)
def test_ref_preflight_fails_without_writes(remote: Remote, defect: str) -> None:
  if defect == "default":
    remote.repo["default_branch"] = "other"
  elif defect == "not-public":
    remote.repo["public"] = False
  elif defect == "not-empty":
    remote.repo["default_branch"] = None
    remote.refs = {"refs/heads/other": SHA}
  elif defect == "tag":
    remote.refs[TAG] = "b" * 40
  else:
    remote.refs[BRANCH] = "b" * 40
    remote.ancestor = 1 if defect == "ahead" else 128
  with pytest.raises(mirror.MirrorError):
    remote.run(publish=True)
  assert remote.writes == []


def test_annotated_tags_are_peeled_and_known_branch_advances_are_non_force(remote: Remote) -> None:
  remote.refs[TAG], remote.refs[TAG + "^{}"] = "b" * 40, SHA
  remote.refs[BRANCH] = "c" * 40
  remote.run(publish=True)
  assert [write for write in remote.writes if write[0] == "git"] == [("git", BRANCH)]


def test_default_branch_is_read_back_after_initial_transfer(
  remote: Remote,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  remote.refs.clear()
  remote.repo["default_branch"] = None
  original = remote.git

  def git(
    root: Path,
    args: Sequence[str],
    *,
    anonymous: bool = False,
  ) -> subprocess.CompletedProcess[str]:
    result = original(root, args, anonymous=anonymous)
    if "push" in args:
      remote.repo["default_branch"] = None
    return result

  monkeypatch.setattr(mirror, "_git", git)
  with pytest.raises(mirror.MirrorError, match="Default-branch readback"):
    remote.run(publish=True)
  assert remote.writes == [("git", BRANCH), ("git", TAG)]


@pytest.mark.parametrize("observed", [False, True])
def test_git_write_timeout_reads_state_without_retry(
  remote: Remote,
  monkeypatch: pytest.MonkeyPatch,
  observed: bool,
) -> None:
  remote.refs.pop(TAG)
  original = remote.git
  attempts: list[tuple[str, ...]] = []

  def git(
    root: Path,
    args: Sequence[str],
    *,
    anonymous: bool = False,
  ) -> subprocess.CompletedProcess[str]:
    if "push" in args:
      attempts.append(tuple(args))
      if observed:
        original(root, args, anonymous=anonymous)
      raise mirror.MirrorError("synthetic timeout")
    return original(root, args, anonymous=anonymous)

  monkeypatch.setattr(mirror, "_git", git)
  if observed:
    remote.run(publish=True)
  else:
    with pytest.raises(mirror.MirrorError, match="Ref transfer incomplete"):
      remote.run(publish=True)
  assert len(attempts) == 1


@pytest.mark.parametrize(
  "notes",
  [
    "## 0.2.0\nmissing\n",
    "## 0.1.0\none\n## 0.1.0\ntwo\n",
    "## 0.1.0\none\n## 0.1.0",
    "## 0.1.0\n\n",
  ],
)
def test_notes_reject_missing_duplicate_or_empty_sections(remote: Remote, notes: str) -> None:
  remote.notes = notes
  with pytest.raises(mirror.MirrorError, match="section"):
    remote.run(publish=True)
  assert remote.writes == []


def test_notes_use_accepted_object_and_only_canonicalize_crlf(remote: Remote) -> None:
  path = remote.files.root / "docs/zh-CN/releases.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("mutable working-tree notes")
  remote.complete()
  assert remote.record is not None
  remote.record["body"] = NOTES.replace("\n", "\r\n")
  remote.notes = remote.notes.replace("\n", "\r\n")
  remote.run()
  remote.record["body"] = NOTES.rstrip()
  with pytest.raises(mirror.MirrorError, match="metadata conflicts"):
    remote.run(publish=True)
  assert remote.writes == []


@pytest.mark.parametrize("defect", ["duplicate", "bytes", "size", "extra", "repeated-id"])
def test_attachment_conflicts_never_write_or_delete(remote: Remote, defect: str) -> None:
  remote.complete()
  if defect == "duplicate":
    remote.attachments.append({**remote.attachments[0], "id": 4})
  elif defect == "repeated-id":
    remote.attachments.append(dict(remote.attachments[0]))
  elif defect == "bytes":
    remote.downloads[1] = b"x" * len(remote.downloads[1])
  elif defect == "size":
    remote.attachments[0]["size"] += 1
  else:
    remote.attachments[0]["name"] = "unexpected"
  with pytest.raises(mirror.MirrorError):
    remote.run(publish=True)
  assert remote.writes == []


@pytest.mark.parametrize("kind", ["release", "upload"])
@pytest.mark.parametrize("observed", [False, True])
def test_ambiguous_posts_read_back_without_blind_retry(
  remote: Remote,
  kind: str,
  observed: bool,
) -> None:
  if kind == "upload":
    remote.complete()
    remote.attachments.pop()
  remote.ambiguous, remote.observe_write = kind, observed
  if observed:
    remote.run(publish=True)
  else:
    with pytest.raises(mirror.UncertainWrite, match="unconfirmed"):
      remote.run(publish=True)
  expected = 4 if kind == "release" and observed else 1
  assert len(remote.writes) == expected


def test_resume_only_missing_attachment(remote: Remote) -> None:
  remote.complete()
  remote.attachments.pop()
  remote.run(publish=True)
  assert remote.writes == [
    (API + "/releases/1/attach_files", ("manifest.json", remote.buffers["manifest.json"])),
  ]


def test_inventory_reads_all_pages_and_rejects_unbounded_work(
  remote: Remote,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[int] = []

  def get(url: str, **kwargs: Any) -> list[dict[str, Any]]:
    page = int(url.split("page=")[1].split("&")[0])
    calls.append(page)
    return [{"id": (page - 1) * 100 + number, "name": "unexpected"} for number in range(1, 101)]

  monkeypatch.setattr(mirror, "_json", get)
  with pytest.raises(mirror.MirrorError, match="pagination exceeds"):
    mirror._inventory(API + "/releases/1/attach_files", remote.buffers)
  assert calls == list(range(1, mirror.MAX_PAGES + 1))
  calls.clear()

  def last_page(url: str, **kwargs: Any) -> list[dict[str, Any]]:
    if "page=2&" in url:
      calls.append(2)
      return []
    return get(url)

  monkeypatch.setattr(mirror, "_json", last_page)
  with pytest.raises(mirror.MirrorError, match="Unexpected"):
    mirror._inventory(API + "/releases/1/attach_files", remote.buffers)
  assert calls == [1, 2]


@pytest.mark.parametrize(
  "repository",
  [
    "https://evil.test/a/b",
    "a/b/c",
    "a/../b",
    "a/b?x=1",
    "a/b.git",
    "a/b\n",
  ],
)
def test_repository_input_cannot_change_credential_origin(repository: str) -> None:
  with pytest.raises(mirror.MirrorError):
    mirror._target(repository, "main")


@pytest.mark.parametrize(
  "branch",
  [
    "-option",
    "refs/../main",
    "a//b",
    ".hidden",
    "a/.b",
    "main.lock",
    "a/",
    "a.",
    "a@{b",
    "a:b",
    "a\\b",
    "main\n",
  ],
)
def test_branch_allowlist(branch: str) -> None:
  with pytest.raises(mirror.MirrorError):
    mirror._target("example/project", branch)


@pytest.mark.parametrize(
  "url",
  [
    "http://gitee.com/a",
    "https://evil.test/a",
    "https://gitee.com:444/a",
    "https://synthetic@gitee.com/a",
  ],
)
def test_anonymous_download_origin_policy(url: str) -> None:
  with pytest.raises(mirror.MirrorError):
    mirror._origin(url, mirror.DOWNLOAD_ORIGINS)


def test_credentialed_redirect_never_constructs_forwarded_request() -> None:
  request = Request(API, data=b"access_token=synthetic-marker")
  for code in (301, 302, 303, 307, 308):
    with pytest.raises(mirror.UncertainWrite, match="redirect refused"):
      mirror._Redirects(mirror.DOWNLOAD_ORIGINS, True).redirect_request(
        request,
        None,
        code,
        "redirect",
        {},
        "https://gitee.com/redirected",
      )
  anonymous = mirror._Redirects(mirror.DOWNLOAD_ORIGINS, False)
  allowed = anonymous.redirect_request(
    Request(API),
    None,
    302,
    "",
    {},
    "https://gitee.com/download",
  )
  assert allowed is not None and allowed.data is None and allowed.headers == {}
  with pytest.raises(mirror.MirrorError):
    anonymous.redirect_request(Request(API), None, 302, "", {}, "https://evil.test/download")


def test_post_uses_documented_body_fields_and_same_file_buffer(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setenv("GITEE_ACCESS_TOKEN", "synthetic-marker")
  calls: list[tuple[str, dict[str, Any]]] = []
  monkeypatch.setattr(mirror, "_http", lambda url, **kwargs: calls.append((url, kwargs)))
  mirror._post(API + "/releases", {"body": "中文"})
  mirror._post(API + "/releases/1/attach_files", {}, ("manifest.json", b"immutable-bytes"))
  assert all("synthetic-marker" not in url for url, _ in calls)
  assert b"access_token=synthetic-marker" in calls[0][1]["data"]
  multipart = calls[1][1]["data"]
  assert b'name="access_token"\r\n\r\nsynthetic-marker' in multipart
  assert b'filename="manifest.json"' in multipart and b"immutable-bytes" in multipart
  assert calls[1][1]["content_type"].startswith("multipart/form-data; boundary=")
  with pytest.raises(mirror.MirrorError):
    mirror._post("https://evil.test/api/v5/repos/a/b", {})
  assert len(calls) == 2


@pytest.mark.parametrize("writing", [False, True])
def test_http_errors_hide_raw_diagnostics_and_never_retry(
  monkeypatch: pytest.MonkeyPatch,
  writing: bool,
) -> None:
  calls: list[Request] = []

  class Opener:
    def open(self, request: Request, *, timeout: int) -> Any:
      calls.append(request)
      assert timeout == 60
      raise URLError("synthetic-secret-in-error")

  monkeypatch.setattr(mirror, "build_opener", lambda *handlers: Opener())
  expected = mirror.UncertainWrite if writing else mirror.MirrorError
  with pytest.raises(expected) as error:
    mirror._http(API, data=b"synthetic-marker" if writing else None)
  assert "synthetic" not in str(error.value) and len(calls) == 1


def test_http_404_only_means_absence_when_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
  class Opener:
    def open(self, request: Request, *, timeout: int) -> Any:
      raise HTTPError(request.full_url, 404, "synthetic-secret", {}, None)  # type: ignore[arg-type]

  monkeypatch.setattr(mirror, "build_opener", lambda *handlers: Opener())
  assert mirror._http(API, missing=True) is None
  with pytest.raises(mirror.MirrorError, match="status 404"):
    mirror._http(API)


def test_anonymous_git_drops_credentials_rewrites_headers_and_local_config(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
  monkeypatch.setenv("GIT_CONFIG_KEY_0", "http.extraHeader")
  monkeypatch.setenv("GIT_CONFIG_VALUE_0", "Authorization: synthetic-marker")
  monkeypatch.setenv("GIT_ASKPASS", "/synthetic/askpass")
  monkeypatch.setenv("GIT_TRACE_CURL", "1")
  calls: list[tuple[str, ...]] = []

  def run(args: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    calls.append(args)
    env = kwargs["env"]
    assert "synthetic" not in str(args) + str(env)
    assert "GIT_CONFIG_COUNT" not in env and "GIT_TRACE_CURL" not in env
    assert env["GIT_CONFIG_NOSYSTEM"] == "1" and env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert Path(env["HOME"]) == kwargs["cwd"] != tmp_path
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    return subprocess.CompletedProcess(args, 0, b"")

  monkeypatch.setattr(subprocess, "run", run)
  mirror._git(tmp_path, ("ls-remote", mirror.GITHUB, TAG), anonymous=True)
  assert calls == [("git", "ls-remote", mirror.GITHUB, TAG)]


def test_ref_reader_peels_annotations_and_rejects_unrequested_refs(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  output = f"{'b' * 40}\t{TAG}\n{SHA}\t{TAG}^{{}}\n"
  monkeypatch.setattr(
    mirror,
    "_git",
    lambda *args, **kwargs: subprocess.CompletedProcess([], 0, output),
  )
  refs = mirror._refs(tmp_path, mirror.GITHUB, (TAG, TAG + "^{}"))
  assert mirror._peeled(refs, TAG) == SHA
  with pytest.raises(mirror.MirrorError, match="Unexpected remote ref"):
    mirror._refs(tmp_path, mirror.GITHUB, (BRANCH,))


@pytest.mark.parametrize("operation", ["check", "publish"])
def test_cli_explicit_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, operation: str) -> None:
  calls: list[bool] = []
  monkeypatch.setattr(
    sys,
    "argv",
    [
      "mirror.py",
      operation,
      "--version",
      "0.1.0",
      "--sha",
      SHA,
      "--repository",
      "example/project",
      "--branch",
      "main",
      "--files",
      str(tmp_path),
    ],
  )
  monkeypatch.setattr(mirror, "mirror", lambda *args, **kwargs: calls.append(kwargs["publish"]))
  mirror.main()
  assert calls == [operation == "publish"]


@pytest.mark.parametrize("writing", [False, True])
def test_http_bounds_and_anonymous_request_fields(
  monkeypatch: pytest.MonkeyPatch,
  writing: bool,
) -> None:
  monkeypatch.setenv("GITEE_ACCESS_TOKEN", "synthetic-marker")
  requests: list[Request] = []
  content = b"okay"

  class Opener:
    def open(self, request: Request, *, timeout: int) -> BytesIO:
      requests.append(request)
      return BytesIO(content)

  def build(*handlers: Any) -> Opener:
    assert handlers[0].proxies == {}
    assert handlers[1].writing is writing
    return Opener()

  monkeypatch.setattr(mirror, "build_opener", build)
  data = b"access_token=synthetic-marker" if writing else None
  assert mirror._http(API, data=data, limit=4) == b"okay"
  assert requests[0].data == data
  assert "Authorization" not in requests[0].headers
  content = b"oversized"
  error = mirror.UncertainWrite if writing else mirror.MirrorError
  with pytest.raises(error, match="size bound"):
    mirror._http(API, data=data, limit=4)
  assert len(requests) == 2


def test_json_and_metadata_shape_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(mirror, "_http", lambda *args, **kwargs: b'{"id":1}')
  assert mirror._json(API) == {"id": 1}
  for check, value in ((mirror._object, []), (mirror._items, {}), (mirror._id, True)):
    with pytest.raises(mirror.MirrorError):
      check(value)
  assert mirror._peeled({TAG: SHA}, TAG) == SHA
  with pytest.raises(mirror.MirrorError, match="no tag ref"):
    mirror._peeled({TAG + "^{}": SHA}, TAG)


def test_missing_write_credential_fails_before_any_write(
  remote: Remote,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.delenv("GITEE_ACCESS_TOKEN")
  remote.refs.clear()
  remote.run()
  with pytest.raises(mirror.MirrorError, match="required before"):
    remote.run(publish=True)
  assert remote.writes == []


def test_lone_carriage_return_in_notes_is_not_normalized(remote: Remote) -> None:
  remote.complete()
  assert remote.record is not None
  remote.record["body"] = NOTES.replace("\n", "\r", 1)
  with pytest.raises(mirror.MirrorError, match="metadata conflicts"):
    remote.run(publish=True)
  assert remote.writes == []
