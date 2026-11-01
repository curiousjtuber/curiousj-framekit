"""The `upstream` kind: an app installed by its own installer, which
this kit fetches, checks where there is something to check against, and
runs. Three installers, each a function here, chosen by the item's
`installer` field:

  bsmanager      the fork's latest install.sh, run with the words after
                 the name (`--uninstall`, `--appimage FILE`); unpinned,
                 and the AppImage then updates itself
  full-keyboard  the release's SHA256SUMS names the arm64 archive; it is
                 downloaded, checked against them, and its install.sh
                 run. `--version X.Y.Z` takes that release
  frametop       the release's Frametop.zip (about 1.1 GB), checked
                 against the sha256 the catalog records for that
                 version and against the release's SHA256SUMS, unpacked,
                 and its install-release.sh run with the words after the
                 name (`--yes`, `--no-eye-tracker`, `--no-bluetooth`,
                 `--bluetooth`, `--any-steamos`, `--unpack-only`);
                 `--version X.Y.Z` takes another release, checked only
                 against its own sums, which is said
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

from ... import cmdline, where
from ...cmdline import Error, Options
from ..catalog import Item, State, Status
from .base import Base, TempDir, fetch, fetch_text, require_commands, require_user, sha256_of, sum_for, verify

APPIMAGE = Path("/home/steamos/Applications/BSManager.AppImage")
KEYBOARD_ROOT = Path.home() / ".local/share/framekeyboard"
KEYBOARD_LAUNCHER = Path.home() / ".local/bin/framekeyboard"
KEYBOARD_DESKTOP = Path.home() / ".local/share/applications/framekeyboard.desktop"
KEYBOARD_ARCHIVE = re.compile(r"framekeyboard-(\d+\.\d+\.\d+)-aarch64\.tar\.gz$", re.M)
FRAMETOP_RELEASES = Path.home() / ".local/share/frametop/releases"
FRAMETOP_FLAGS = ("--yes", "--no-eye-tracker", "--no-bluetooth", "--bluetooth", "--any-steamos",
                  "--unpack-only")
VERSION_RE = re.compile(r"^v?\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")


def take_version(args: list[str], what: str) -> tuple[str | None, list[str]]:
    """`--version X.Y.Z` out of args, the rest back."""
    rest, version = [], None
    i = 0
    while i < len(args):
        if args[i] == "--version":
            if i + 1 >= len(args) or not VERSION_RE.match(args[i + 1]):
                raise Error(f"{what}: --version needs X.Y.Z")
            version = args[i + 1].lstrip("v")
            i += 2
            continue
        if args[i].startswith("--version="):
            raise Error(f"{what}: write it as --version X.Y.Z")
        rest.append(args[i])
        i += 1
    return version, rest


def current_release(root: Path) -> str | None:
    """The version a `current -> releases/X` link points at."""
    try:
        target = os.readlink(root / "current")
    except OSError:
        return None
    return os.path.basename(target.rstrip("/"))


# --- BSManager -------------------------------------------------------------

def bsmanager_status(item: Item, opts: Options) -> Status:
    return Status(State.OK, "AppImage; updates itself") if APPIMAGE.exists() else Status(State.MISSING)


def bsmanager_install(item: Item, opts: Options, args: list[str]) -> bool:
    require_user()
    require_commands("curl")
    for a in args:
        if a not in ("--uninstall", "--appimage") and not (args.index(a) > 0 and args[args.index(a) - 1] == "--appimage"):
            raise Error(f"bsmanager takes --uninstall or --appimage FILE; got {a}")
    verb = "remove" if "--uninstall" in args else ("update" if APPIMAGE.exists() else "install")
    cmdline.say(f"would {verb}" if opts.check else verb,
                f"BSManager with the fork's latest install.sh {' '.join(args)}".rstrip())
    if opts.check:
        return True
    if not cmdline.confirm(opts, "run the upstream installer?"):
        return False
    with TempDir() as tmp:
        script = tmp / "install.sh"
        fetch(opts, item["installer_url"], script)
        cmdline.run(opts, ["bash", str(script), *args], capture=False)
    return True


# --- Full Keyboard -------------------------------------------------------

def keyboard_status(item: Item, opts: Options) -> Status:
    ver = current_release(KEYBOARD_ROOT)
    return Status(State.OK, ver) if ver else Status(State.MISSING)


def keyboard_install(item: Item, opts: Options, args: list[str]) -> bool:
    require_user()
    version, rest = take_version(args, "full-keyboard")
    if rest:
        raise Error(f"full-keyboard takes --version X.Y.Z; got {' '.join(rest)}")
    repo = item["repo"]
    release = f"download/{version}" if version else "latest/download"
    sums_url = f"{repo}/releases/{release}/SHA256SUMS"
    sums = fetch_text(sums_url)
    archive = next((m.group(0) for line in sums.splitlines()
                    for m in [KEYBOARD_ARCHIVE.search(line)] if m), None)
    if not archive:
        raise Error(f"no arm64 archive listed in {sums_url}")
    found = KEYBOARD_ARCHIVE.search(archive).group(1)
    if (KEYBOARD_ROOT / "releases" / found).exists():
        if current_release(KEYBOARD_ROOT) == found:
            cmdline.say("ok", f"Full Keyboard {found}")
        else:
            cmdline.say("ok", f"Full Keyboard {found} is installed but isn't current; to make it so:")
            print(f"               ln -sfn releases/{found} ~/.local/share/framekeyboard/current")
        return False
    cmdline.say("would install" if opts.check else "install", f"Full Keyboard {found} ({archive})")
    if opts.check:
        return True
    # The running binary is current/bin/framekeyboard, and the launcher
    # execs it; the installer switches the link.
    if cmdline.run(opts, ["pgrep", "-x", "framekeyboard"], check=False, capture=True).returncode == 0:
        raise Error("Full Keyboard is running: close it from its toolbar first")
    if not cmdline.confirm(opts, "download and run its install.sh?"):
        return False
    expected = sum_for(sums, archive)
    if not expected:
        raise Error(f"SHA256SUMS lists {archive} without a sum")
    with TempDir() as tmp:
        path = tmp / archive
        cmdline.say("download", archive)
        fetch(opts, f"{repo}/releases/{release}/{archive}", path)
        cmdline.say("verify", f"{archive} against SHA256SUMS")
        verify(path, expected, archive)
        unpacked = tmp / "x"
        unpacked.mkdir()
        with tarfile.open(path) as tar:
            tar.extractall(unpacked, filter="data")
        installers = list(unpacked.glob("*/install.sh"))
        if len(installers) != 1:
            raise Error(f"{archive} doesn't hold one install.sh")
        cmdline.run(opts, ["bash", str(installers[0])], capture=False)
    print("done: in the headset, open the dashboard and start Full Keyboard from the app launcher")
    return True


def keyboard_uninstall(item: Item, opts: Options) -> bool:
    if cmdline.run(opts, ["pgrep", "-x", "framekeyboard"], check=False, capture=True).returncode == 0:
        raise Error("Full Keyboard is running: close it from its toolbar first")
    changed = False
    for path in (KEYBOARD_LAUNCHER, KEYBOARD_DESKTOP, KEYBOARD_ROOT):
        if not path.exists() and not path.is_symlink():
            continue
        cmdline.say("would remove" if opts.check else "remove", cmdline.tilde(path))
        if opts.check:
            changed = True
            continue
        if not cmdline.confirm(opts, f"remove {cmdline.tilde(path)}?"):
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        changed = True
    if changed and not opts.check:
        print("done: settings kept in ~/.config/framekeyboard")
    return changed


# --- Frametop ---------------------------------------------------------------

def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "frametop-install"


def frametop_status(item: Item, opts: Options) -> Status:
    ver = current_release(FRAMETOP_RELEASES)
    if not ver:
        return Status(State.MISSING)
    if ver != item["version"]:
        return Status(State.OUTDATED, f"{ver} installed, {item['version']} in the catalog")
    return Status(State.OK, ver)


def frametop_install(item: Item, opts: Options, args: list[str]) -> bool:
    require_user()
    where.require_host("frametop")
    version, flags = take_version(args, "frametop")
    reinstall = "--reinstall" in flags
    flags = [f for f in flags if f != "--reinstall"]
    bad = [f for f in flags if f not in FRAMETOP_FLAGS]
    if bad:
        raise Error(f"frametop takes --version X.Y.Z, --reinstall and {' '.join(FRAMETOP_FLAGS)}; "
                    f"got {' '.join(bad)}")
    version = version or item["version"]
    recorded = item["sha256"] if version == item["version"] else None
    have = current_release(FRAMETOP_RELEASES)
    if have == version and not reinstall and not flags:
        cmdline.say("ok", f"Frametop {version} (--reinstall runs its installer again)")
        return False
    cmdline.say("would install" if opts.check else "install",
                f"Frametop {version}" + (f", replacing {have}" if have and have != version else
                                         ", again" if have == version else "")
                + (" (the zip checked against the sha256 recorded here)" if recorded else
                   " (no recorded sha256 for this version: checked only against its own SHA256SUMS)"))
    if opts.check:
        return True
    if not cmdline.confirm(opts, "download Frametop.zip (about 1.1 GB) and run its installer?"):
        return False
    require_commands("curl", "unzip", "podman")
    repo = item["repo"]
    base = f"{repo}/releases/download/v{version}"
    cache = cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    zip_path = cache / f"Frametop-{version}.zip"
    sums = fetch_text(f"{base}/SHA256SUMS")
    listed = sum_for(sums, "Frametop.zip")
    if not listed:
        raise Error("the release's SHA256SUMS doesn't name Frametop.zip")
    if recorded and listed != recorded:
        raise Error("the release's SHA256SUMS names another Frametop.zip than the catalog records: "
                    "the release changed since; --version takes it on its own sums")
    expected = recorded or listed
    if zip_path.exists() and sha256_of(zip_path) == expected:
        cmdline.say("download", f"{cmdline.tilde(zip_path)} is here and checks out")
    else:
        if zip_path.exists():
            cmdline.say("download", f"{cmdline.tilde(zip_path)} is here but doesn't check out: deleted")
            zip_path.unlink()
            (cache / (zip_path.name + ".part")).unlink(missing_ok=True)
        cmdline.say("download", "Frametop.zip, about 1.1 GB (a run that stops resumes it)")
        part = cache / (zip_path.name + ".part")
        try:
            fetch(opts, f"{base}/Frametop.zip", part, resume=True, progress=True)
        except Error:
            raise Error("the download didn't finish: run this again to resume it") from None
        part.rename(zip_path)
        cmdline.say("verify", "Frametop.zip against " + ("the sha256 recorded here" if recorded else "SHA256SUMS"))
        try:
            verify(zip_path, expected, "Frametop.zip")
        except Error:
            zip_path.unlink()
            raise Error("checksum mismatch: the download is deleted, run this again") from None
    unpacked = cache / "unpacked"
    shutil.rmtree(unpacked, ignore_errors=True)
    cmdline.say("unpack", cmdline.tilde(zip_path))
    if cmdline.run(opts, ["unzip", "-q", str(zip_path), "-d", str(unpacked)], check=False, capture=True).returncode != 0:
        shutil.rmtree(unpacked, ignore_errors=True)
        zip_path.unlink()
        raise Error("the zip doesn't unpack: it is deleted, run this again")
    installer = unpacked / "Frametop" / "install-release.sh"
    if not os.access(installer, os.X_OK):
        raise Error("the zip holds no Frametop/install-release.sh")
    cmdline.say("install", f"Frametop {version}, with its install-release.sh")
    proc = subprocess.run([str(installer), *flags])
    shutil.rmtree(unpacked, ignore_errors=True)
    if proc.returncode == 3:
        zip_path.unlink(missing_ok=True)
        raise Error("the image inside the zip is damaged: the download is deleted, run this again")
    if proc.returncode != 0:
        raise Error(f"install-release.sh exited with {proc.returncode}; the download stays in "
                    f"{cmdline.tilde(cache)} for a re-run")
    shutil.rmtree(cache, ignore_errors=True)
    if "--unpack-only" in flags:
        print(f"done: Frametop {version} is in {cmdline.tilde(FRAMETOP_RELEASES / version)}, not installed")
    else:
        print(f"done: Frametop {version} in {cmdline.tilde(FRAMETOP_RELEASES / 'current')}; "
              "restart SteamVR, then Launch a program → Desktop")
    return True


def frametop_uninstall(item: Item, opts: Options) -> bool:
    script = FRAMETOP_RELEASES / "current" / "uninstall.sh"
    if not script.is_file():
        raise Error(f"no release in {cmdline.tilde(FRAMETOP_RELEASES)} to uninstall (Frametop's own: "
                    "curl -fsSL https://frametop.github.io/frametop/uninstall.sh | bash)")
    cmdline.say("would remove" if opts.check else "remove",
                "Frametop, with its release's uninstall.sh (two runs, with a restart between)")
    if opts.check or not cmdline.confirm(opts, "run it?"):
        return opts.check
    # Its second run deletes the releases, itself included: run a copy,
    # pointed at the release.
    with TempDir() as tmp:
        copy = tmp / "uninstall.sh"
        shutil.copy(script, copy)
        cmdline.run(opts, ["bash", str(copy), "--dir", str((FRAMETOP_RELEASES / "current").resolve())],
                    capture=False)
    return True


INSTALLERS = {
    "bsmanager": (bsmanager_status, bsmanager_install,
                  lambda item, opts: bsmanager_install(item, opts, ["--uninstall"]),
                  "[--uninstall | --appimage FILE]"),
    "full-keyboard": (keyboard_status, keyboard_install, keyboard_uninstall, "[--version X.Y.Z]"),
    "frametop": (frametop_status, frametop_install, frametop_uninstall,
                 "[--version X.Y.Z] [--reinstall] [--yes] [--no-eye-tracker] [--no-bluetooth | --bluetooth] "
                 "[--any-steamos] [--unpack-only]"),
}
# full-keyboard checks the latest release each time, so --all may run it.
UPDATES = {"full-keyboard"}


class Kind(Base):
    def _routines(self, item: Item):
        try:
            return INSTALLERS[item["installer"]]
        except KeyError:
            raise Error(f"{item.name}: no upstream installer named {item.get('installer')}") from None

    def status(self, item: Item, opts: Options) -> Status:
        return self._routines(item)[0](item, opts)

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        return self._routines(item)[1](item, opts, args)

    def uninstall(self, item: Item, opts: Options) -> bool:
        return self._routines(item)[2](item, opts)

    def options_for(self, item: Item) -> str:
        return self._routines(item)[3]

    def updates_item(self, item: Item) -> bool:
        return item.get("installer") in UPDATES
