"""The `pacman-home` kind: a package under ~/.local in pacman-home's
database, either relocated from Arch Linux ARM's binary package
(waypipe) or built here with makepkg from the kit's own PKGBUILD
(emacs, pacman; data/pkgbuilds/NAME in the package, so every install
has them). The work is frame/pkg.py's; this kind maps the catalog
entry onto it. A build runs in ~/.cache/curiousj-framekit/build/NAME,
a copy of the PKGBUILD's directory, not inside the package.

A package built here is outdated when pacman-home's version differs
from the PKGBUILD's pkgver-pkgrel; a relocated one is checked against
Arch Linux ARM by `pacman-home outdated`, which needs the network, so
`installed` shows only what is there."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from ... import cmdline
from ...cmdline import Error, Options
from ...frame import pkg
from ..catalog import Item, State, Status
from .base import Base, require_commands


def paths() -> pkg.Paths:
    p = pkg.Paths()
    p.write_confs()
    return p


def owned(p: pkg.Paths, path: Path) -> bool:
    return pkg.pacman(p, p.conf, "-Qo", str(path), check=False).returncode == 0


def pkg_install(file: Path) -> None:
    """pacman-home -U FILE, in a child so that its exec stays contained."""
    proc = subprocess.run([sys.executable, "-c",
                           "from curiousj_framekit.frame.pkg import pacman_home_main as m; import sys; "
                           "sys.exit(m(sys.argv[1:]))", "-U", str(file), "--noconfirm"])
    if proc.returncode != 0:
        raise Error("pacman-home -U failed")


class Kind(Base):
    updates = True

    def status(self, item: Item, opts: Options) -> Status:
        p = pkg.Paths()
        if not os.access(p.pacman, os.X_OK):
            # No pacman, no database to ask, and nothing to write under
            # ~/.local for the question.
            return Status(State.UNKNOWN, f"no pacman here ({p.pacman})")
        try:
            p.write_confs()
            have = pkg.query_version(p, item["package"])
        except Error as e:
            return Status(State.UNKNOWN, str(e))
        if not have:
            return Status(State.MISSING)
        if item.get("pkgbuild"):
            base = pkg.pkgbuilds_dir()
            if (base / item["pkgbuild"] / "PKGBUILD").is_file():
                try:
                    _, ver, rel, _ = pkg.pkgbuild_info(base / item["pkgbuild"])
                    want = f"{ver}-{rel}"
                except Error:
                    want = None
                if want and want != have:
                    return Status(State.OUTDATED, f"{have} installed, {want} in the PKGBUILD")
        return Status(State.OK, have)

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        self.no_args(item, args)
        require_commands("pacman", "fakeroot", "bsdtar")
        status = self.status(item, opts)
        p = paths()
        if item.get("relocate"):
            if status.state == State.OK:
                cmdline.say("ok", f"{item['package']} {status.detail} from Arch Linux ARM, "
                                  "in pacman-home's database")
            if not pkg.have_keyring(p):
                cmdline.say("would install" if opts.check else "install",
                            "Arch Linux ARM's signing keys into pacman-home's keyring")
                if not opts.check:
                    pkg.ensure_keyring(p)
            bin_ = Path.home() / ".local/bin" / item["package"]
            if (bin_.exists() or bin_.is_symlink()) and not owned(p, bin_):
                dest = bin_.with_name(f"{bin_.name}.bak-{cmdline.stamp()}")
                cmdline.say("would back up" if opts.check else "back up",
                            f"{cmdline.tilde(bin_)}, not pacman-home's -> {cmdline.tilde(dest)}")
                if not opts.check:
                    shutil.move(bin_, dest)
            cmdline.say("would relocate" if opts.check else "relocate",
                        f"{item['package']} from Arch Linux ARM under ~/.local, when its version "
                        "differs (pacman-home relocate)")
            if opts.check:
                return True
            found = pkg.fetch(p, item["package"])
            if found is None:
                return False
            pkg_install(pkg.relocate_pkg(p, found, allow=False))
            return True

        directory = pkg.pkgbuilds_dir() / item["pkgbuild"]
        name, ver, rel, _ = pkg.pkgbuild_info(directory)
        want = f"{ver}-{rel}"
        if status.state == State.OK:
            cmdline.say("ok", f"{name} {status.detail}, in pacman-home's database")
            return False
        bin_ = Path.home() / ".local/bin" / ("emacs" if name == "emacs-wayland" else name)
        if status.state == State.MISSING and (bin_.exists() or bin_.is_symlink()) and not owned(p, bin_):
            cmdline.say("skip", f"{cmdline.tilde(bin_)} exists and isn't pacman-home's; left alone")
            return False
        have = pkg.query_version(p, name)
        cmdline.say("would build" if opts.check else "build",
                    f"{name} {want}{', replacing ' + have if have else ''} "
                    f"(makepkg in {cmdline.tilde(pkg.build_dir() / item['pkgbuild'])}, pacman-home -U)")
        if opts.check:
            return True
        if not cmdline.confirm(opts, f"build {name}? (emacs takes about three minutes)"):
            return False
        pkg.build(opts, directory, clean=False if opts.yes else None, extra=[])
        return True

    def uninstall(self, item: Item, opts: Options) -> bool:
        p = paths()
        have = pkg.query_version(p, item["package"])
        if not have:
            return False
        cmdline.say("would remove" if opts.check else "remove",
                    f"{item['package']} {have} (pacman-home -R)")
        if opts.check or not cmdline.confirm(opts, f"pacman-home -R {item['package']}?"):
            return opts.check
        proc = pkg.pacman(p, p.conf, "-R", item["package"], "--noconfirm", root=True, check=False,
                          capture=False)
        return proc.returncode == 0
