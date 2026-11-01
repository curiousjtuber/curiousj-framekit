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
from ..catalog import Item, State, Status


class Base:
    options = ""
    # Whether `cjf install --all` runs an item of this kind that is ok,
    # because installing again is how it updates (a Flatpak, a uv tool).
    # Kinds where that would redo a long install for nothing (Frametop's
    # 1.1 GB, a build) leave it False and are run by --all only when
    # outdated.
    updates = False

    def status(self, item: Item, opts: Options) -> Status:
        return Status(State.UNKNOWN)

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        raise Error(f"{item.name}: this kind can't install yet")

    def uninstall(self, item: Item, opts: Options) -> bool:
        raise Error(f"{item.name}: no uninstall here; see the docs")

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
