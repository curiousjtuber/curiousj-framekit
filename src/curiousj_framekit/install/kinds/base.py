"""What the kinds share: the fetch-and-check steps the scripts each had
a copy of, and a base class with the no-op defaults."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

from ... import cmdline
from ...cmdline import Error, Options
from ..catalog import Check, Fresh, Item, State, Status


class Base:
    options = ""

    def status(self, item: Item, opts: Options) -> Status:
        return Status(State.UNKNOWN)

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        raise Error(f"{item.name}: this kind can't install yet")

    def uninstall(self, item: Item, opts: Options) -> bool:
        raise Error(f"{item.name}: no uninstall here; see the docs")

    def check(self, item: Item, opts: Options, status: Status) -> Check:
        """The installed item against its upstream, with the network;
        `status` is the local state, already taken. A kind with no way
        to tell says so."""
        return Check(Fresh.UNKNOWN, status.detail, note="no way to tell")

    def update(self, item: Item, opts: Options) -> bool:
        """Install the newer version `check` found. Installing again is
        how most kinds update; the others override."""
        return self.install(item, opts, [])

    def no_args(self, item: Item, args: list[str]) -> None:
        if args:
            raise Error(f"{item.name} takes no options; got {' '.join(args)}")


def require_user() -> None:
    if os.geteuid() == 0:
        raise Error("run it as your user, not with sudo: it installs into your home directory")


def require_commands(*names: str) -> None:
    missing = [n for n in names if not shutil.which(n)]
    if missing:
        raise Error(f"missing required command{'s' if len(missing) > 1 else ''}: {' '.join(missing)}")


def fetch(opts: Options, url: str, dest: Path, *, resume: bool = False, progress: bool = False) -> None:
    """Download url to dest with curl (it handles redirects, TLS and
    resume as the scripts relied on); an Error names the url on failure."""
    argv = ["curl", "-fL", "--proto", "=https", "-o", str(dest), url]
    argv += ["--progress-bar"] if progress else ["-sS"]
    if resume:
        argv += ["-C", "-"]
    proc = cmdline.run(opts, argv, check=False, capture=not progress)
    if proc.returncode != 0:
        raise Error(f"can't download {url}" + (f": {proc.stderr.strip()}" if proc.stderr else ""))


def fetch_text(url: str, timeout: float = 30) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode(errors="replace")
    except OSError as e:
        raise Error(f"can't download {url}: {e}") from None


def final_url(url: str, timeout: float = 30) -> str:
    """Where url redirects to (a GitHub releases/latest, say)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.geturl()
    except OSError as e:
        raise Error(f"can't reach {url}: {e}") from None


def latest_tag(repo: str) -> str:
    """The tag a GitHub repository's releases/latest redirects to, as
    written (v0.2.2, 1.8.2.5)."""
    tag = final_url(f"{repo}/releases/latest").rstrip("/").rsplit("/", 1)[-1]
    if tag == "latest" or tag == "releases":
        raise Error(f"{repo} has no release")
    return tag


def version_tuple(version: str) -> tuple[int, ...]:
    """The leading dotted numbers of a version, for comparing: v3.5.1 is
    (3, 5, 1), 0.12.0-install-H62l1s is (0, 12, 0). () when it doesn't
    start with a number."""
    m = re.match(r"v?(\d+(?:\.\d+)*)", version.strip())
    return tuple(int(n) for n in m.group(1).split(".")) if m else ()


def newer(candidate: str, installed: str) -> bool:
    """Whether candidate's leading numbers are above installed's. Two
    unnumbered versions are compared as text, unequal meaning newer,
    since a release tag that changed is a release that happened."""
    a, b = version_tuple(candidate), version_tuple(installed)
    if a and b:
        return a > b
    return candidate.strip().lstrip("v") != installed.strip().lstrip("v")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sum_for(sums_text: str, filename: str) -> str | None:
    """The sha256 that a SHA256SUMS-style text gives for filename."""
    for line in sums_text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == filename and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            return parts[0]
    return None


def verify(path: Path, expected: str, what: str) -> None:
    actual = sha256_of(path)
    if actual != expected:
        raise Error(f"checksum mismatch for {what}: expected {expected}, got {actual}")


class TempDir:
    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix="cjf-"))
        return self.path

    def __exit__(self, *exc) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def say_state(item: Item, status: Status) -> None:
    cmdline.say(status.state.value, f"{item.name}" + (f" {status.detail}" if status.detail else ""))
