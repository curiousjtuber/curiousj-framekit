"""pacman-home, and cjf pkg -- packages that live under ~/.local: the ones
built from the kit's PKGBUILDs and stock binary packages relocated there.
pacman-home is pacman with its database, cache and log under ~/.local
too, so the Frame's read-only root is never touched and no root is
needed; cjf pkg builds and rewrites PKGBUILDs for that prefix.

    pacman-home -U PKG.pkg.tar.zst     install or upgrade a package built for ~/.local
    pacman-home -Q [-l PKG | -o FILE]   what is installed, a package's files, a file's owner
    pacman-home -R PKG                  remove one
    pacman-home check PKG...            which of a package's files fall outside ~/.local
                                        (-U refuses such a package)
    pacman-home outdated                every installed package against Arch Linux ARM's
                                        repositories, or the AUR for one they lack, and
                                        against the kit's PKGBUILD for it, by version
                                        (the release number after the dash is this repo's
                                        own, so it isn't compared)
    pacman-home relocate NAME|FILE [--allow-missing-libs] [-U options]
                                        a stock binary package, its /usr tree moved under
                                        ~/.local, then installed: NAME is fetched from Arch
                                        Linux ARM (ALARM_MIRROR overrides the mirror), FILE
                                        is a package you have. Refused when the host lacks a
                                        library it needs, unless told to allow it
    pacman-home keyring [--check]       Arch Linux ARM's signing keys in this database's own
                                        keyring, so its packages are taken only with a valid
                                        signature; relocate NAME does this itself the first
                                        time. --check only says whether they are there
    any other pacman operation and options pass through

    cjf pkg build [NAME|DIR] [--clean | --keep] [-- MAKEPKG-OPTIONS]
                                        makepkg -f for the kit's PKGBUILD NAME (emacs,
                                        pacman), in a copy of its directory under
                                        ~/.cache/curiousj-framekit/build/, or in DIR, or
                                        here; pacman-home -U the result, then offer to
                                        delete what the build left behind
    cjf pkg homeify NAME [FILE] [--into DIR]
                                        Arch's PKGBUILD for NAME (or the AUR's, or FILE),
                                        rewritten for a ~/.local prefix into NAME/ under
                                        the current directory (or DIR), the original kept
                                        as PKGBUILD.upstream and the diff printed
    cjf pkg outdated                    pacman-home outdated

pacman refuses to install or remove unless it runs as root, whatever
paths it is given, so the non-query operations run under fakeroot:
pacman is told it is root, writes the files as you, and the root
ownership it then sets is faked for the session, so the files end up
yours. The configuration is written to ~/.local/etc/pacman.conf from
the real paths each run, since pacman.conf expands no ~ or variables.
relocate uses a second one, pacman-alarm.conf beside it, that adds Arch
Linux ARM's repositories; the plain one has none, so that -U never
pulls a /usr package from them to satisfy a dependency.

The pacman run is the host's: 7.1 with libalpm 16 since SteamOS 0.5.7
(6.1 before, which is why the kit carried a pacman 7 of its own under
~/.local until then; dropped on 2026-11-06). The ldconfig run it
attempts after every transaction fails on the read-only root and says
so; the transaction is done by then. When a SteamOS update takes a
library from under a package here (0.5.7 bumped gpgme's and libxml2's
sonames), `cjf installed` shows the package as outdated, by ldd over
its programs and libraries, for `cjf update` to rebuild. This database
knows only what it installed itself, so for -U the package's dependencies are checked
against the host's database and the satisfied ones are passed as
--assume-installed; a dependency the host lacks is still an error.

Arch Linux ARM signs its packages, and relocate NAME only takes one with
a valid signature (its databases aren't signed). The keys come from its
archlinuxarm-keyring package, fetched once with signatures off, since
there is no key to check it with yet; what stands in for that is the
trusted key fingerprint recorded here, checked against archlinuxarm.org
on 2026-10-15: a keyring package whose trusted list differs is refused.

relocate suits a program that needs no file outside its own tree. It
refuses a package with files under /etc or /var, or under the parts of
/usr that only work from there (systemd and udev directories, polkit,
system D-Bus services), drops the install scriptlet, points absolute
symlinks into /usr at ~/.local, and refuses a package whose libraries
the host cannot supply, a glibc or Qt newer than the host's among them.
What it cannot see is a program that looks for its data under /usr at
run time; that one needs a build from a PKGBUILD instead.

homeify's rewrite: the prefix given to configure, cmake, meson
(arch-meson too) and make, with sysconfdir and localstatedir under it;
the *dir= flags that name /usr; /usr, /etc, /var and /opt under $pkgdir
and in backup=; aarch64 added to arch; makepkg's debug split and lto
turned off; the install scriptlet dropped; and PKG_CONFIG_PATH and an
rpath for ~/.local/lib exported in build(). A PKGBUILD that runs cargo
gets the rpath in RUSTFLAGS too, since rustc ignores LDFLAGS, and a
makedepends that mise's shims provide is unlisted, since makepkg checks
them against the host's packages. It ends with the makedepends and
depends the host lacks. Review the result before building; what a build
system hardcodes shows up afterwards as a file outside ~/.local, which
`pacman-home check` lists and `-U` refuses.
"""

from __future__ import annotations

import difflib
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import click

from .. import cmdline, config, where
from ..cmdline import Error, Options, pass_options

PROG = "pacman-home"
ALARM_MIRROR_DEFAULT = "https://fl.us.mirror.archlinuxarm.org"
# Arch Linux ARM's trusted keys, as archlinuxarm-trusted in its keyring
# package lists them: the Build System key that signs every package
# (archlinuxarm-keyring 20240419-2). A keyring package that lists other
# keys is refused, so check archlinuxarm.org/about/package-signing
# before updating this list.
ALARM_TRUSTED = ("68B3537F39A313B3E574D06777193F152BDBE6A6",)
HOST_PACMAN = "/usr/bin/pacman"
QUERY_OPS = {"-Q", "-T", "-V", "-F", "--query", "--deptest", "--version", "--files", "--help"}
USR_ONLY = ("usr/lib/systemd", "usr/lib/udev", "usr/lib/sysusers.d", "usr/lib/tmpfiles.d",
            "usr/lib/modules", "usr/lib/firmware", "usr/share/polkit-1",
            "usr/share/dbus-1/system-services", "usr/share/dbus-1/system.d", "usr/lib/security")


# --- paths and configuration ---------------------------------------------

_probes: dict[str, tuple[tuple[int, ...] | None, str]] = {}


def probe(path: str | Path) -> tuple[tuple[int, ...] | None, str]:
    """(version, problem) of the pacman at path, from `pacman --version`:
    the version as a tuple, or None and the one-line reason it can't run.
    Once per path per run."""
    key = str(path)
    if key not in _probes:
        try:
            proc = subprocess.run([key, "--version"], text=True, capture_output=True)
        except OSError as e:
            _probes[key] = (None, e.strerror or str(e))
        else:
            if proc.returncode != 0:
                err = (proc.stderr.strip().splitlines() or [f"exit status {proc.returncode}"])[-1]
                _probes[key] = (None, re.sub(r"^.*: error while loading shared libraries: ", "", err))
            else:
                m = re.search(r"Pacman v(\d+)\.(\d+)\.(\d+)", proc.stdout)
                _probes[key] = (tuple(int(x) for x in m.groups()) if m else (), "")
    return _probes[key]


class Paths:
    def __init__(self, home: Path | None = None):
        self.home = home or Path.home()
        self.local = self.home / ".local"
        self.in_pkg = str(self.local).lstrip("/") + "/"      # home/<user>/.local/
        self.conf = self.local / "etc/pacman.conf"
        self.alarm_conf = self.local / "etc/pacman-alarm.conf"
        self.cache = self.local / "var/cache/pacman/pkg"
        self.gpgdir = self.local / "etc/pacman.d/gnupg"
        self.keyrings = self.local / "share/pacman/keyrings"
        self.mirror = os.environ.get("ALARM_MIRROR", ALARM_MIRROR_DEFAULT)
        self.pacman = HOST_PACMAN
        self.pacman_key = "/usr/bin/pacman-key"
        self.version = probe(self.pacman)[0]

    def conf_text(self) -> str:
        # RootDir stays /: a prefix build's files carry absolute paths
        # under $HOME. Everything pacman keeps for itself is pointed under
        # ~/.local. HookDir is added to the system hook directory, not
        # substituted for it, but the system hooks trigger on /usr paths
        # that these packages never touch.
        text = ("# Written by curiousj-framekit's pacman-home on each run; edits here are lost.\n"
                "[options]\nRootDir  = /\n"
                f"DBPath   = {self.local}/var/lib/pacman\nCacheDir = {self.cache}\n"
                f"LogFile  = {self.local}/var/log/pacman.log\nHookDir  = {self.local}/etc/pacman.d/hooks\n"
                f"GPGDir   = {self.gpgdir}\nLocalFileSigLevel = Optional\n")
        # pacman 7 runs downloads in a Landlock sandbox, and the Frame
        # kernel has no Landlock; a pacman 6 (the host's before SteamOS
        # 0.5.7) would not know the directive.
        if self.version and self.version >= (7,):
            text += "DisableSandboxFilesystem\n"
        return text

    def alarm_conf_text(self) -> str:
        repos = "".join(f"\n[{r}]\nSigLevel = Required DatabaseOptional\n"
                        f"Server = {self.mirror}/$arch/$repo\n" for r in ("core", "extra", "alarm"))
        return ("# Written by curiousj-framekit's pacman-home on each run; edits here are lost.\n"
                f"[options]\nInclude = {self.conf}\nArchitecture = aarch64\n" + repos)

    def write_confs(self) -> None:
        for d in (self.local / "var/lib/pacman", self.cache, self.local / "var/log",
                  self.local / "etc/pacman.d/hooks", self.gpgdir):
            d.mkdir(parents=True, exist_ok=True)
        self.conf.write_text(self.conf_text())
        self.alarm_conf.write_text(self.alarm_conf_text())


def say(what: str, detail: str = "") -> None:
    print(f"{what:<10} {cmdline.tilde(detail)}", file=sys.stderr, flush=True)


def fakeroot() -> list[str]:
    """fakeroot, unless already inside one: it refuses to nest."""
    return [] if os.environ.get("FAKEROOTKEY") else ["fakeroot"]


def pacman(paths: Paths, conf: Path, *args: str, root: bool = False, check: bool = True,
           capture: bool = True) -> subprocess.CompletedProcess:
    argv = (fakeroot() if root else []) + [paths.pacman, "--config", str(conf), *args]
    try:
        proc = subprocess.run(argv, text=True, capture_output=capture)
    except FileNotFoundError:
        # A host without pacman (a CI runner standing in for the Frame)
        # gets the kit's own error, which a status pass shows as `?`.
        raise Error(f"can't run {argv[0]}: not found") from None
    if check and proc.returncode != 0:
        err = (proc.stderr or "").strip() if capture else ""
        raise Error(f"{' '.join(argv[-len(args) - 2:])} failed" + (f": {err}" if err else ""))
    return proc


def op_of(args: list[str]) -> str:
    """The pacman operation among args: the first uppercase letter of the
    first short-option group, or its long form; it is not always args[0]."""
    for arg in args:
        if arg in ("--sync", "--upgrade", "--remove", "--query", "--deptest", "--database",
                   "--files", "--version", "--help"):
            return arg
        if arg.startswith("--"):
            continue
        if re.match(r"^-[A-Z]", arg):
            return arg[:2]
    return ""


# --- check: a package's files outside ~/.local ----------------------------

def tar_list(pkg: Path) -> list[str]:
    proc = subprocess.run(["bsdtar", "-tf", str(pkg)], text=True, capture_output=True)
    if proc.returncode != 0:
        raise Error(f"can't list {pkg}: {proc.stderr.strip()}")
    return proc.stdout.splitlines()


def outside_prefix(entries: list[str], in_pkg: str) -> list[str]:
    """The entries not under the prefix: not .PKGINFO and the like, not
    under home/<user>/.local/, not a parent of it (home/, home/<user>/)."""
    out = []
    for e in entries:
        if re.fullmatch(r"\.[A-Z]+", e):
            continue
        if e.startswith(in_pkg):
            continue
        if e.endswith("/") and in_pkg.startswith(e):
            continue
        out.append(e)
    return out


def check_cmd(paths: Paths, files: list[str]) -> int:
    if not files:
        raise Error("check needs a package file")
    bad = 0
    for f in files:
        pkg = Path(f)
        if not pkg.is_file():
            raise Error(f"no such file: {f}")
        out = outside_prefix(tar_list(pkg), paths.in_pkg)
        if out:
            bad = 1
            print(f"{pkg.name}: files outside {cmdline.tilde(paths.local)}:")
            for e in out[:20]:
                print(f"  {e}")
            if len(out) > 20:
                print(f"  ... {len(out) - 20} more")
        else:
            print(f"{pkg.name}: all files under {cmdline.tilde(paths.local)}")
    return bad


# --- keyring: Arch Linux ARM's signing keys --------------------------------

def have_keyring(paths: Paths) -> bool:
    proc = subprocess.run(["gpg", "--homedir", str(paths.gpgdir), "--batch", "--with-colons",
                           "--list-keys"], text=True, capture_output=True)
    if proc.returncode != 0:
        return False
    return all(f"\nfpr:::::::::{fp}:" in "\n" + proc.stdout for fp in ALARM_TRUSTED)


def ensure_keyring(paths: Paths, force: bool = False) -> None:
    """The keyring populated from the archlinuxarm-keyring package, fetched
    with signatures off (nothing to check it with yet) and held to
    ALARM_TRUSTED instead."""
    if not force and have_keyring(paths):
        return
    for cmd in ("gpg", paths.pacman_key, "bsdtar"):
        if not shutil.which(cmd):
            raise Error(f"missing required command: {cmd}")
    boot = paths.alarm_conf.with_name("pacman-alarm-bootstrap.conf")
    boot.write_text(re.sub(r"^SigLevel = .*$", "SigLevel = Never", paths.alarm_conf.read_text(), flags=re.M))
    say("sync", f"Arch Linux ARM's databases from {paths.mirror}")
    pacman(paths, boot, "-Sy", root=True)
    url = pacman(paths, boot, "-Spdd", "archlinuxarm-keyring", check=False).stdout.strip()
    if not url:
        raise Error("no archlinuxarm-keyring in Arch Linux ARM's repositories")
    name = url.rsplit("/", 1)[-1]
    say("download", f"{name} from {paths.mirror}, with signatures off: the keys to check with are inside")
    pacman(paths, boot, "-Swdd", "--noconfirm", "archlinuxarm-keyring", root=True)
    pkg = paths.cache / name
    shutil.rmtree(paths.keyrings, ignore_errors=True)
    paths.keyrings.mkdir(parents=True)
    proc = subprocess.run(["bsdtar", "-xf", str(pkg), "-C", str(paths.keyrings), "--strip-components",
                           "4", "usr/share/pacman/keyrings"], text=True, capture_output=True)
    if proc.returncode != 0:
        raise Error(f"can't extract {pkg}: {proc.stderr.strip()}")
    gpg_file, trusted_file = paths.keyrings / "archlinuxarm.gpg", paths.keyrings / "archlinuxarm-trusted"
    if not (gpg_file.stat().st_size and trusted_file.stat().st_size):
        raise Error(f"{name} holds no archlinuxarm.gpg and archlinuxarm-trusted")
    listed = sorted(l.split(":")[0] for l in trusted_file.read_text().splitlines()
                    if l.strip() and not l.startswith("#"))
    if listed != sorted(ALARM_TRUSTED):
        raise Error(f"{name} trusts other keys than this kit records (ALARM_TRUSTED): {' '.join(listed)} "
                    "-- check archlinuxarm.org before updating the list")
    # --init makes the local master key that --populate signs the trusted
    # keys with; gpg's own listing may have made an empty pubring already,
    # so the secret key is what says it ran.
    secret = subprocess.run(["gpg", "--homedir", str(paths.gpgdir), "--batch", "--with-colons",
                             "--list-secret-keys"], text=True, capture_output=True).stdout
    if "\nsec:" not in "\n" + secret:
        say("init", f"pacman-key's master key in {paths.gpgdir}")
        proc = subprocess.run([*fakeroot(), paths.pacman_key, "--config", str(paths.alarm_conf), "--init"],
                              text=True, capture_output=True)
        if proc.returncode != 0:
            raise Error(f"pacman-key --init failed in {paths.gpgdir}:\n{proc.stdout}{proc.stderr}")
    say("populate", f"{paths.gpgdir} from {name}")
    proc = subprocess.run([*fakeroot(), paths.pacman_key, "--config", str(paths.alarm_conf),
                           "--populate-from", str(paths.keyrings), "--populate", "archlinuxarm"],
                          text=True, capture_output=True)
    if proc.returncode != 0:
        raise Error(f"pacman-key --populate archlinuxarm failed:\n{proc.stdout}{proc.stderr}")
    if not have_keyring(paths):
        raise Error("the keyring lacks a key of ALARM_TRUSTED after populating")
    for fp in ALARM_TRUSTED:
        say("trusted", fp)


def keyring_cmd(paths: Paths, args: list[str]) -> int:
    if args == ["--check"]:
        if have_keyring(paths):
            say("ok", f"Arch Linux ARM's keys are in {paths.gpgdir}")
            return 0
        say("missing", f"Arch Linux ARM's keys in {paths.gpgdir} (pacman-home keyring)")
        return 1
    if args:
        raise Error("keyring takes --check or nothing")
    ensure_keyring(paths, force=True)
    return 0


# --- relocate: a stock binary package moved under ~/.local -----------------

def sync_alarm(paths: Paths) -> None:
    ensure_keyring(paths)
    say("sync", f"Arch Linux ARM's databases from {paths.mirror}")
    pacman(paths, paths.alarm_conf, "-Sy", root=True)


def query_version(paths: Paths, name: str) -> str | None:
    out = pacman(paths, paths.conf, "-Q", name, check=False).stdout.split()
    return out[1] if len(out) >= 2 else None


def fetch(paths: Paths, name: str) -> Path | None:
    """The package from Arch Linux ARM into the cache; None, with a note,
    when the installed version is already that one."""
    sync_alarm(paths)
    url = pacman(paths, paths.alarm_conf, "-Spdd", name, check=False).stdout.strip()
    if not url:
        raise Error(f"no package {name} in Arch Linux ARM's core, extra or alarm")
    ver = pacman(paths, paths.alarm_conf, "-Spdd", "--print-format", "%v", name).stdout.strip()
    have = query_version(paths, name)
    if have and have == ver:
        say("ok", f"{name} {ver} from Arch Linux ARM is installed")
        return None
    say("download", url)
    pacman(paths, paths.alarm_conf, "-Swdd", "--noconfirm", name, root=True)
    return paths.cache / url.rsplit("/", 1)[-1]


def rewrite_link(target: str, local: Path) -> str | None:
    """Where an absolute symlink into /usr should point once relocated."""
    if target == "/usr":
        return str(local)
    if target.startswith("/usr/"):
        return str(local) + target[len("/usr"):]
    return None


def usr_only_dirs(root: Path) -> list[str]:
    return [d for d in USR_ONLY if (root / d).exists()]


def lib_dirs(lib: Path) -> str:
    """lib and every directory under it, for LD_LIBRARY_PATH: a package's
    own libraries count as supplied."""
    if not lib.is_dir():
        return ""
    return ":".join([str(lib)] + [str(p) for p in lib.rglob("*") if p.is_dir()])


def is_elf(f: Path) -> bool:
    if not f.is_file() or f.is_symlink() or not (os.access(f, os.X_OK) or ".so" in f.name):
        return False
    try:
        with f.open("rb") as fh:
            return fh.read(4) == b"\x7fELF"
    except OSError:
        return False


def ldd_missing(files: list[Path], libdirs: str, root: Path) -> list[tuple[str, str]]:
    """(file relative to root, what ldd says) for the ELF files among
    files with a library the loader can't find, libdirs on
    LD_LIBRARY_PATH. What the loader says on stderr counts too, since
    that is where a symbol version the host's library lacks (a newer
    glibc or Qt) is named."""
    found = set()
    for f in files:
        if not is_elf(f):
            continue
        proc = subprocess.run(["ldd", str(f)], text=True, capture_output=True,
                              env=dict(os.environ, LD_LIBRARY_PATH=libdirs))
        for line in (proc.stdout + proc.stderr).splitlines():
            if "not found" in line:
                lib = re.sub(r"^[^:]*: ", "", line.strip())
                lib = re.sub(r" \(required by .*", "", lib)
                found.add((str(f.relative_to(root)), lib))
    return sorted(found)


def missing_libs(tree: Path) -> list[str]:
    """`file: library` lines for ELF files under tree/bin and tree/lib
    whose libraries the host cannot supply; the package's own library
    directories count as supplied, as they will be under ~/.local/lib."""
    files = [f for sub in ("bin", "lib") if (tree / sub).is_dir() for f in (tree / sub).rglob("*")]
    return [f"    {rel}: {lib}" for rel, lib in ldd_missing(files, lib_dirs(tree / "lib"), tree)]


def broken_libs(paths: Paths, name: str) -> list[tuple[str, str]]:
    """(file, library) for the installed package's programs and libraries
    with a library the host no longer supplies: what a SteamOS update
    that bumps a soname (0.5.7: gpgme, libxml2) leaves of a package
    built against the old one. ~/.local/lib and what is under it count
    as supplied, as the packages' rpaths have them."""
    out = pacman(paths, paths.conf, "-Qlq", name, check=False).stdout
    files = [Path(f) for f in out.splitlines()
             if f.startswith(str(paths.local)) and ("/bin/" in f or "/lib/" in f)]
    return [(rel, re.sub(r" => not found$", "", lib))
            for rel, lib in ldd_missing(files, lib_dirs(paths.local / "lib"), paths.local)]


def relocate_pkg(paths: Paths, pkg: Path, allow: bool) -> Path:
    """The relocated package, written to the cache; its path."""
    if not pkg.is_file():
        raise Error(f"no such file: {pkg}")
    tmp = Path(tempfile.mkdtemp(prefix="pacman-home-"))
    try:
        proc = subprocess.run(["bsdtar", "-xf", str(pkg), "-C", str(tmp)], text=True, capture_output=True)
        if proc.returncode != 0:
            raise Error(f"can't extract {pkg}: {proc.stderr.strip()}")
        for top in tmp.iterdir():
            if top.name.startswith("."):
                continue
            if top.name != "usr":
                raise Error(f"{pkg.name} has files under /{top.name}, which have no place under ~/.local; "
                            "it needs a build from a PKGBUILD instead")
        if not (tmp / "usr").is_dir():
            raise Error(f"{pkg.name} has no files under /usr")
        bad = usr_only_dirs(tmp)
        if bad:
            raise Error(f"{pkg.name} has files that only work from /usr: {' '.join(bad)}")
        if (tmp / ".INSTALL").exists():
            say("drop", "its install scriptlet, which assumes /usr:")
            for line in (tmp / ".INSTALL").read_text(errors="replace").splitlines():
                print(f"    {line}", file=sys.stderr)
            (tmp / ".INSTALL").unlink()
        dest = tmp / paths.in_pkg.rstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        (tmp / "usr").rename(dest)
        for link in dest.rglob("*"):
            if link.is_symlink():
                new = rewrite_link(os.readlink(link), paths.local)
                if new:
                    link.unlink()
                    link.symlink_to(new)
        bad_libs = missing_libs(dest)
        if bad_libs:
            text = "\n".join(bad_libs)
            if allow:
                say("warning", f"libraries the host lacks; the program may not run:\n{text}")
            else:
                raise Error(f"{pkg.name} needs libraries the host lacks (--allow-missing-libs installs anyway):\n{text}")
        info = tmp / ".PKGINFO"
        info.write_text(re.sub(r"^(pkgdesc = .*)$", rf"\1 [relocated under {paths.local} by pacman-home]",
                               info.read_text(), count=1, flags=re.M))
        top = paths.in_pkg.split("/", 1)[0]
        env = dict(os.environ, LANG="C")
        subprocess.run(["bsdtar", "-czf", ".MTREE", "--format=mtree",
                        "--options=!all,use-set,type,uid,gid,mode,time,size,md5,sha256,link",
                        ".PKGINFO", top], cwd=tmp, check=True, env=env)
        out = paths.cache / (re.sub(r"\.pkg\.tar.*$", "", pkg.name) + ".home.pkg.tar.zst")
        subprocess.run(["bsdtar", "--zstd", "-cf", str(out), ".PKGINFO", ".MTREE", top], cwd=tmp, check=True)
        say("relocate", f"{pkg.name} -> {out}")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def relocate_cmd(paths: Paths, args: list[str]) -> None:
    if not args:
        raise Error("relocate needs a package name or file")
    src, rest = args[0], args[1:]
    allow = "--allow-missing-libs" in rest
    rest = [a for a in rest if a != "--allow-missing-libs"]
    if Path(src).is_file():
        pkg = Path(src)
    else:
        found = fetch(paths, src)
        if found is None:
            return
        pkg = found
    out = relocate_pkg(paths, pkg, allow)
    passthrough(paths, ["-U", str(out), *rest])


# --- outdated -------------------------------------------------------------

def pkgbuilds_dir() -> Path:
    """The kit's PKGBUILDs, one directory each (emacs, krdc, fuse2): data/pkgbuilds
    in the package, so an install from git has them as a checkout does."""
    return Path(__file__).resolve().parent.parent / "data" / "pkgbuilds"


def build_dir() -> Path:
    """Where the kit's PKGBUILDs build, ~/.cache/curiousj-framekit/build:
    makepkg writes src/, pkg/, its downloads and the package beside the
    PKGBUILD, which must not happen inside the package."""
    return config.cache_dir() / "build"


def stage(directory: Path) -> tuple[Path, set[str]]:
    """Copy a PKGBUILD directory's files into build_dir()/NAME: the work
    directory, and the names copied, so that what the build adds can be
    told apart afterwards. A copy already there is refreshed."""
    work = build_dir() / directory.name
    work.mkdir(parents=True, exist_ok=True)
    names = set()
    for f in directory.iterdir():
        if f.is_file():
            shutil.copy2(f, work / f.name)
            names.add(f.name)
    return work, names


def pkgbuild_info(directory: Path) -> tuple[str, str, str, list[str]]:
    """(pkgname, pkgver, pkgrel, depends) read the way makepkg does."""
    script = ('source "$1/PKGBUILD" >/dev/null 2>&1 || exit 1; '
              'printf "%s %s %s" "$pkgname" "$pkgver" "$pkgrel"; '
              'for d in "${depends[@]}"; do printf " %s" "${d%%[<>=]*}"; done; echo')
    proc = subprocess.run(["bash", "-c", script, "_", str(directory)], text=True, capture_output=True)
    if proc.returncode != 0:
        raise Error(f"can't read {directory}/PKGBUILD")
    name, ver, rel, *deps = proc.stdout.split()
    return name, ver, rel, deps


def aur_version(name: str) -> str | None:
    try:
        with urllib.request.urlopen(f"https://aur.archlinux.org/rpc/v5/info?arg[]={name}", timeout=20) as r:
            results = json.load(r).get("results", [])
    except (OSError, ValueError):
        return None
    return results[0].get("Version") if results else None


def vercmp(paths: Paths, a: str, b: str) -> int:
    exe = str(Path(paths.pacman).parent / "vercmp")
    out = subprocess.run([exe, a, b], text=True, capture_output=True).stdout.strip()
    try:
        return int(out)
    except ValueError:
        return 0


def pkgbuild_versions() -> dict[str, str]:
    """pkgname -> pkgver for each of the kit's PKGBUILDs that reads."""
    versions = {}
    directory = pkgbuilds_dir()
    if directory.is_dir():
        for d in sorted(directory.iterdir()):
            if (d / "PKGBUILD").is_file():
                try:
                    name, ver, _, _ = pkgbuild_info(d)
                    versions[name] = ver
                except Error:
                    pass
    return versions


def upstream_version(paths: Paths, name: str) -> tuple[str, str] | None:
    """(version, source) for the package upstream: Arch Linux ARM's
    repositories first, the AUR for one they lack; None when neither has
    it. The release after the dash is left out, since it is this repo's
    own. sync_alarm first, or the repositories answer from a stale
    database."""
    info = pacman(paths, paths.alarm_conf, "-Si", name, check=False).stdout
    up = next((l.split(":", 1)[1].strip() for l in info.splitlines() if l.startswith("Version")), "")
    src = "Arch Linux ARM"
    if not up:
        up = aur_version(name) or ""
        src = "AUR"
    if not up:
        return None
    return up.rsplit("-", 1)[0], src


def is_snapshot(version: str) -> bool:
    """A git snapshot's version, as Arch's VCS packages number them."""
    return bool(re.search(r"\.r\d+\.g[0-9a-f]+", version))


def outdated_cmd(paths: Paths) -> int:
    sync_alarm(paths)
    pkgbuilds = pkgbuild_versions()
    print(f"{'package':<14} {'installed':<12} {'pkgbuild':<12} upstream")
    for line in pacman(paths, paths.conf, "-Q", check=False).stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, have = parts[0], parts[1].rsplit("-", 1)[0]
        found = upstream_version(paths, name)
        pb = pkgbuilds.get(name, "")
        if not found:
            up_text = "not found upstream"
        elif vercmp(paths, found[0], have) > 0:
            snapshot = ", a git snapshot" if is_snapshot(found[0]) else ""
            up_text = f"newer: {found[0]} ({found[1]}{snapshot})"
        else:
            up_text = f"current ({found[1]})"
        if pb and pb != have:
            pb += " <- differs"
        print(f"{name:<14} {have:<12} {pb or '-':<12} {up_text}")
    return 0


# --- pacman proper -----------------------------------------------------------

def pkginfo_depends(pkg: Path) -> list[str]:
    proc = subprocess.run(["bsdtar", "-xOf", str(pkg), ".PKGINFO"], text=True, capture_output=True)
    return [l.split("=", 1)[1].strip() for l in proc.stdout.splitlines() if l.startswith("depend =")]


def host_satisfies(dep: str) -> str | None:
    """`name=version` to pass as --assume-installed when the host has dep,
    with the host's version so versioned dependencies are honoured; a
    dependency the host satisfies through a provider is passed by name."""
    if subprocess.run([HOST_PACMAN, "-T", dep], capture_output=True).returncode != 0:
        return None
    name = re.split(r"[<>=]", dep, 1)[0]
    out = subprocess.run([HOST_PACMAN, "-Q", name], text=True, capture_output=True).stdout.split()
    return f"{name}={out[1]}" if len(out) >= 2 else name


def passthrough(paths: Paths, args: list[str]) -> None:
    """exec pacman with the home configuration: under fakeroot unless it is
    a query, and for -U with the package's host-satisfied dependencies
    assumed."""
    op = op_of(args)
    assume: list[str] = []
    if op in ("-U", "--upgrade"):
        for arg in args:
            if ".pkg.tar" not in arg or not Path(arg).is_file():
                continue
            out = outside_prefix(tar_list(Path(arg)), paths.in_pkg)
            if out:
                listed = "\n".join(f"  {e}" for e in out[:10])
                raise Error(f"{Path(arg).name} has files outside {cmdline.tilde(paths.local)}, which this "
                            f"database never installs (pacman-home check lists them):\n{listed}")
            for dep in pkginfo_depends(Path(arg)):
                sat = host_satisfies(dep)
                if sat:
                    assume += ["--assume-installed", sat]
    argv = ([] if op in QUERY_OPS else fakeroot()) + [paths.pacman, "--config", str(paths.conf), *assume, *args]
    sys.stdout.flush()
    sys.stderr.flush()
    os.execvp(argv[0], argv)


def pacman_home_main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        if not args or args[0] in ("-h", "--help"):
            print(__doc__.strip())
            return 0
        where.require_host(PROG)
        paths = Paths()
        paths.write_confs()
        if args[0] == "check":
            return check_cmd(paths, args[1:])
        if args[0] == "outdated":
            return outdated_cmd(paths)
        if args[0] == "keyring":
            return keyring_cmd(paths, args[1:])
        if args[0] == "relocate":
            relocate_cmd(paths, args[1:])
            return 0
        passthrough(paths, args)
        return 0
    except Error as e:
        print(f"{PROG}: {e}", file=sys.stderr)
        return e.code


# --- cjf pkg build ------------------------------------------------------------

def makepkg_wants(tool: str) -> str | None:
    """The makepkg config file that leaves BUILDENV's `tool` (ccache,
    distcc) turned on, the files read in makepkg's order: the system
    one, /etc/makepkg.conf.d, the XDG one, ~/.makepkg.conf. None when it
    is off at the end. A makepkg.conf shared with a PC turns ccache on
    for a Frame that has none, and makepkg then stops with only a
    missing-binary line."""
    script = (
        'on=; for f in "${MAKEPKG_CONF:-/etc/makepkg.conf}" /etc/makepkg.conf.d/*.conf '
        '"${XDG_CONFIG_HOME:-$HOME/.config}/pacman/makepkg.conf" "$HOME/.makepkg.conf"; do '
        '[ -r "$f" ] || continue; was="${BUILDENV[*]-}"; source "$f" >/dev/null 2>&1; '
        '[ "${BUILDENV[*]-}" = "$was" ] && continue; '
        'for e in "${BUILDENV[@]}"; do [ "$e" = "$1" ] && on=$f; [ "$e" = "!$1" ] && on=; done; done; '
        'printf "%s" "$on"')
    out = subprocess.run(["bash", "-c", script, "_", tool], text=True, capture_output=True).stdout
    return out or None


def build(opts: Options, directory: Path, clean: bool | None, extra: list[str]) -> None:
    """makepkg -f in directory, pacman-home -U the result, then offer to
    delete the build artifacts (what the directory's .gitignore covers,
    less PKGBUILD.upstream; in a staged copy, whatever the build added):
    yes with clean True, never with False, asked when None. One of the
    kit's own PKGBUILDs is copied to build_dir() first and built there."""
    if not (directory / "PKGBUILD").is_file():
        raise Error(f"no PKGBUILD in {cmdline.tilde(directory)}")
    for cmd in ("makepkg", "fakeroot"):
        if not shutil.which(cmd):
            raise Error(f"missing required command: {cmd}")
    staged: set[str] | None = None
    if pkgbuilds_dir() in directory.resolve().parents:
        work, staged = stage(directory.resolve())
        say("stage", f"{directory.name}/ -> {work}")
        directory = work
    env = dict(os.environ)
    env.setdefault("MAKEFLAGS", f"-j{os.cpu_count() or 2}")
    # cargo, for a Rust package, comes from mise's shims; they go after the
    # host's directories so that a tool the host has stays the host's.
    shims = Path.home() / ".local/share/mise/shims"
    if shims.is_dir():
        env["PATH"] = env.get("PATH", "") + ":" + str(shims)
    for tool in ("ccache", "distcc"):
        conf = makepkg_wants(tool)
        if conf and not shutil.which(tool, path=env["PATH"]):
            raise Error(f"makepkg's BUILDENV turns {tool} on in {cmdline.tilde(Path(conf))}, and this host has no "
                        f"{tool}; put !{tool} in BUILDENV in ~/.makepkg.conf (read last) or install {tool}")
    say("build", str(directory))
    if subprocess.run(["makepkg", "-f", *extra], cwd=directory, env=env).returncode != 0:
        raise Error(f"makepkg failed in {cmdline.tilde(directory)}")
    built = subprocess.run(["makepkg", "--packagelist", *extra], cwd=directory, env=env,
                           text=True, capture_output=True).stdout.split()
    if not built:
        raise Error("makepkg built nothing it will name")
    say("install", " ".join(Path(b).name for b in built))
    paths = Paths()
    paths.write_confs()
    proc = subprocess.run([sys.executable, "-c", "from curiousj_framekit.frame.pkg import pacman_home_main as m; import sys; sys.exit(m(sys.argv[1:]))",
                           "-U", *built, "--noconfirm"])
    if proc.returncode != 0:
        raise Error("pacman-home -U failed")
    in_git = staged is None and subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--is-inside-work-tree"], capture_output=True).returncode == 0
    if staged is not None:
        junk = [f.name + ("/" if f.is_dir() else "") for f in sorted(directory.iterdir()) if f.name not in staged]
    elif in_git:
        out = subprocess.run(["git", "-C", str(directory), "clean", "-ndX", "-e", "!PKGBUILD.upstream", "."],
                             text=True, capture_output=True).stdout
        junk = [l.removeprefix("Would remove ") for l in out.splitlines() if l.startswith("Would remove ")]
    else:
        junk = [p.name + ("/" if p.is_dir() else "") for p in directory.iterdir()
                if p.name in ("src", "pkg") or ".pkg.tar." in p.name]
    if not junk:
        return
    size = subprocess.run(["du", "-shc", *junk], cwd=directory, text=True, capture_output=True).stdout
    total = size.strip().splitlines()[-1].split()[0] if size.strip() else "?"
    print(f"build artifacts in {cmdline.tilde(directory)}, {total}: {' '.join(junk)}", file=sys.stderr)
    if clean is False or (clean is None and not cmdline.confirm(opts, "Delete them?", False)):
        say("keep", "them (makepkg -R repackages from them in seconds)")
        return
    if in_git:
        subprocess.run(["git", "-C", str(directory), "clean", "-fdqX", "-e", "!PKGBUILD.upstream", "."], check=True)
    else:
        for j in junk:
            p = directory / j.rstrip("/")
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    say("deleted", " ".join(junk))


# --- cjf pkg homeify -----------------------------------------------------------

ARCH_BASE = "https://gitlab.archlinux.org/archlinux/packaging/packages/{name}/-/raw/main/{file}"
AUR_BASE = "https://aur.archlinux.org/cgit/aur.git/plain/{file}?h={name}"
BUILD_EXPORTS = [
    "  # homeify: what is already under ~/.local is found at configure time and at run time.",
    '  export PKG_CONFIG_PATH="$_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"',
    '  export LDFLAGS="${LDFLAGS:-} -Wl,-rpath,$_prefix/lib"',
]
CARGO_EXPORTS = [
    "  # homeify: rustc links through its own driver, so the rpath goes in",
    "  # RUSTFLAGS as well.",
    '  export RUSTFLAGS="${RUSTFLAGS:-} -C link-arg=-Wl,-rpath,$_prefix/lib"',
]
PREFIX_BLOCK = [
    "",
    "# homeify: the prefix, and makepkg's debug split and lto, which",
    "# lengthens a build for nothing here.",
    "_prefix=$HOME/.local",
    "options+=(!debug !lto)",
]


def unlist_block(names: list[str]) -> list[str]:
    return [
        "# homeify: these makedepends come from mise's shims (cjf install rust), not host",
        "# packages, which is all makepkg checks; the build fails plainly without them.",
        f"for _d in {' '.join(names)}; do for _i in \"${{!makedepends[@]}}\"; do",
        '  [[ ${makedepends[_i]} == "$_d" ]] && unset \'makedepends[_i]\'; done; done; unset _d _i',
        "",
    ]


def rewrite_line(line: str) -> str:
    """The substitutions homeify makes to one line of a PKGBUILD."""
    if line.startswith("arch=(") and not re.search(r"aarch64|any", line):
        line = re.sub(r"^arch=\((.*)\)", r"arch=('aarch64' \1)", line)
    line = re.sub(r"^options=\((.*)\)", r"options=(\1 !debug !lto)", line)
    line = re.sub(r"^install=", "# homeify, dropped (nothing would run it): install=", line)
    if line.startswith("backup=("):
        line = re.sub(r"""(["'( ])(etc|usr|var|opt)/""", r"\1${_prefix#/}/\2/", line)
    line = re.sub(r"\barch-meson\b", 'arch-meson --prefix "$_prefix"', line)
    line = re.sub(r"(prefix|PREFIX)=/usr([^A-Za-z0-9_/]|$)", r'\1="$_prefix"\2', line)
    line = re.sub(r"--prefix /usr([^A-Za-z0-9_/]|$)", r'--prefix "$_prefix"\1', line)
    line = re.sub(r"(sysconfdir|SYSCONFDIR)[= ]/etc([^A-Za-z0-9_/]|$)", r'\1="$_prefix/etc"\2', line)
    line = re.sub(r"(localstatedir|LOCALSTATEDIR)[= ]/var([^A-Za-z0-9_/]|$)", r'\1="$_prefix/var"\2', line)
    line = re.sub(r"((dir|DIR)=)/usr(/|[^A-Za-z0-9_]|$)", r'\1"$_prefix"\3', line)
    line = re.sub(r'"(\$\{?pkgdir\}?)"/usr', r'"\1$_prefix"', line)
    line = re.sub(r'"(\$\{?pkgdir\}?)"/(etc|var|opt)\b', r'"\1$_prefix"/\2', line)
    line = re.sub(r"(\$\{?pkgdir\}?)/usr", r"\1$_prefix", line)
    line = re.sub(r"(\$\{?pkgdir\}?)/(etc|var|opt)\b", r"\1$_prefix/\2", line)
    return line


def rewrite(text: str, uses_cargo: bool, from_mise: list[str]) -> str:
    """A PKGBUILD rewritten for the ~/.local prefix."""
    out: list[str] = []
    prefix_added = unlisted = False
    for line in text.splitlines():
        if from_mise and not unlisted and re.match(r"^[a-z_]+ *\(\) *\{", line):
            out += unlist_block(from_mise)
            unlisted = True
        new = rewrite_line(line)
        out.append(new)
        if not prefix_added and re.match(r"^pkg(base|name)=", line):
            out += PREFIX_BLOCK
            prefix_added = True
        if re.match(r"^build *\(\) *\{", line):
            out += BUILD_EXPORTS + (CARGO_EXPORTS if uses_cargo else [])
    return "\n".join(out) + "\n"


def bash_array(pkgbuild: Path, var: str) -> list[str]:
    proc = subprocess.run(["bash", "-c", f'source "$1" >/dev/null 2>&1; printf "%s\\n" "${{{var}[@]}}"', "_",
                           str(pkgbuild)], text=True, capture_output=True)
    return [l for l in proc.stdout.splitlines() if l]


def fetch_text(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read().decode(errors="replace")
    except OSError:
        return None


def homeify(opts: Options, name: str, given: str | None, into: Path | None = None) -> None:
    if not re.fullmatch(r"[a-z0-9@._+-]+", name):
        raise Error(f"not a package name: {name}")
    target = (into or Path.cwd()) / name
    target.mkdir(parents=True, exist_ok=True)
    upstream = target / "PKGBUILD.upstream"
    if given:
        if not Path(given).is_file():
            raise Error(f"no such file: {given}")
        shutil.copy(given, upstream)
        src_of = None
        source = given
    else:
        # Arch's packaging repos first, the AUR when they have no such
        # package. GitLab answers a missing project with a sign-in page and
        # status 200, so the content is checked, not the status.
        is_pkgbuild = lambda t: t is not None and re.search(r"^pkg(name|base)=", t, re.M)  # noqa: E731
        text = fetch_text(ARCH_BASE.format(name=name, file="PKGBUILD"))
        if is_pkgbuild(text):
            source = ARCH_BASE.format(name=name, file="PKGBUILD")
            src_of = lambda f: ARCH_BASE.format(name=name, file=f)  # noqa: E731
        else:
            text = fetch_text(AUR_BASE.format(name=name, file="PKGBUILD"))
            if not is_pkgbuild(text):
                raise Error(f"no PKGBUILD for {name} in Arch's packaging repos or the AUR")
            source = AUR_BASE.format(name=name, file="PKGBUILD") + " (the AUR)"
            src_of = lambda f: AUR_BASE.format(name=name, file=f)  # noqa: E731
        upstream.write_text(text)
        # Files the PKGBUILD lists without a URL live next to it in the repo.
        for src in bash_array(upstream, "source"):
            if "://" in src or "::" in src:
                continue
            body = fetch_text(src_of(src))
            if body is None:
                raise Error(f"can't fetch {src}, listed in source=()")
            (target / src).write_text(body)
    text = upstream.read_text()
    uses_cargo = bool(re.search(r"(^|[^A-Za-z0-9_])cargo( |$)", text, re.M))
    shims = Path.home() / ".local/share/mise/shims"
    from_mise = []
    for d in bash_array(upstream, "makedepends"):
        d = re.split(r"[<>=]", d, 1)[0]
        if (shims / d).exists() or (d == "rust" and (shims / "cargo").exists()):
            from_mise.append(d)
    header = (f"# Rewritten for a $HOME/.local prefix by curiousj-framekit's\n# `cjf pkg homeify` on {time.strftime('%Y-%m-%d')}, from\n"
              f"#   {source}\n# The original is PKGBUILD.upstream. Built on the Frame host with\n"
              "# `cjf pkg build` and installed with pacman-home; see\n# README.md#packages-for-the-host.\n\n")
    result = header + rewrite(text, uses_cargo, from_mise)
    (target / "PKGBUILD").write_text(result)
    if subprocess.run(["bash", "-n", str(target / "PKGBUILD")], capture_output=True).returncode != 0:
        raise Error(f"the rewrite left {target}/PKGBUILD unparsable; see the diff")
    ignore = target / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# makepkg working files\nsrc/\npkg/\n*.pkg.tar.*\n*.tar.*\n*.zip\nPKGBUILD.upstream\n")
    print(f"== {cmdline.tilde(target / 'PKGBUILD')}, against the original (from {source}):")
    if uses_cargo:
        print("   runs cargo: the rpath goes in RUSTFLAGS too")
    if from_mise:
        print(f"   makedepends from mise, unlisted for makepkg: {' '.join(from_mise)}")
    diff = difflib.unified_diff(text.splitlines(keepends=True), result.splitlines(keepends=True),
                                "PKGBUILD.upstream", "PKGBUILD")
    sys.stdout.writelines(list(diff)[2:])
    print()
    print(f"== on this host ({os.uname().machine}):")
    deps = set()
    for var in ("makedepends", "checkdepends", "depends"):
        deps.update(re.split(r"[<>=]", d, 1)[0] for d in bash_array(target / "PKGBUILD", var))
    missing = sorted(d for d in deps if d and subprocess.run([HOST_PACMAN, "-T", d], capture_output=True).returncode != 0)
    if missing:
        print("   not installed, so the build needs them first, homeified too or dropped:")
        for d in missing:
            print(f"     {d}")
    else:
        print("   every makedepends and depends is installed")
    print(f"   next: cjf pkg build {name if target.parent == pkgbuilds_dir() else cmdline.tilde(target)}")


# --- the cjf pkg group --------------------------------------------------------

@click.group(cls=cmdline.Group, help=__doc__,
             short_help="build or relocate a package under ~/.local; pacman-home is its pacman")
def pkg() -> None:
    pass


@pkg.command(cls=cmdline.Command, help="makepkg -f for the kit's PKGBUILD NAME, in a copy under "
                                        "~/.cache/curiousj-framekit/build/ (or in DIR, or here), then pacman-home -U.",
             context_settings={"ignore_unknown_options": True})
@click.argument("target", required=False)
@click.option("--clean", "clean", flag_value=True, default=None, help="Delete the build artifacts without asking.")
@click.option("--keep", "clean", flag_value=False, help="Keep them, ask nothing.")
@click.argument("extra", nargs=-1, type=click.UNPROCESSED)
@pass_options
def build_cmd(opts: Options, target: str | None, clean: bool | None, extra: tuple[str, ...]) -> int:
    where.require_host("pkg build")
    if target is None:
        directory = Path.cwd()
    elif Path(target).is_dir():
        directory = Path(target).resolve()
    else:
        base = pkgbuilds_dir()
        if (base / target / "PKGBUILD").is_file():
            directory = base / target
        else:
            have = " ".join(sorted(d.name for d in base.iterdir() if (d / "PKGBUILD").is_file()))
            raise Error(f"no directory {target}, and no PKGBUILD {target} in the kit (it has: {have})")
    build(opts, directory, clean, [a for a in extra if a != "--"])
    return 0


build_cmd.name = "build"


@pkg.command(cls=cmdline.Command, name="homeify",
             help="Arch's (or the AUR's, or FILE's) PKGBUILD for NAME rewritten for ~/.local.")
@click.argument("name")
@click.argument("file", required=False)
@click.option("--into", type=click.Path(file_okay=False, path_type=Path),
              help="Write NAME/ under this directory instead of the current one.")
@pass_options
def homeify_cmd(opts: Options, name: str, file: str | None, into: Path | None) -> int:
    where.require_host("pkg homeify")
    homeify(opts, name, file, into)
    return 0


@pkg.command(cls=cmdline.Command, name="outdated", help="pacman-home outdated.")
def outdated_sub() -> int:
    where.require_host("pkg outdated")
    paths = Paths()
    paths.write_confs()
    return outdated_cmd(paths)
