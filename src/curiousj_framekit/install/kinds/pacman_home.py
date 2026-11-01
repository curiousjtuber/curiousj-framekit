"""The `pacman-home` kind: a package under ~/.local in pacman-home's
database, either relocated from Arch Linux ARM's binary package
(waypipe) or built here with makepkg from pkgbuilds/frame/NAME (emacs,
pacman). Until stage 5 ports them, the work is done by the checkout's
bin/pacman-home and makepkg; this kind finds the checkout from an
editable install, or from `[pkg] checkout` in the config.

A package built here is outdated when pacman-home's version differs
from the PKGBUILD's pkgver-pkgrel; a relocated one is checked against
Arch Linux ARM by `pacman-home outdated`, which needs the network, so
`installed` shows only what is there."""

from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path

from ... import cmdline, config
from ...cmdline import Error, Options
from ..catalog import Item, State, Status
from .base import Base, require_commands


def checkout() -> Path | None:
    """The repo checkout: the package's grandparent when installed
    editable, or [pkg] checkout in the config."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pkgbuilds" / "frame").is_dir() and (parent / "bin" / "pacman-home").exists():
            return parent
    conf = config.get("pkg", "checkout")
    if conf:
        p = Path(os.path.expanduser(conf))
        if (p / "pkgbuilds" / "frame").is_dir():
            return p
    return None


def pacman_home_path() -> str:
    co = checkout()
    if co and (co / "bin/pacman-home").exists():
        return str(co / "bin/pacman-home")
    found = shutil.which("pacman-home")
    if found:
        return found
    raise Error("pacman-home is missing: it lives in the checkout's bin/ until stage 5; "
                "set [pkg] checkout in the config to where the checkout is")


def installed_version(opts: Options, package: str) -> str | None:
    out = cmdline.run(opts, [pacman_home_path(), "-Q", package], check=False, capture=True).stdout
    parts = out.split()
    return parts[1] if len(parts) >= 2 else None


def pkgbuild_info(directory: Path) -> tuple[str, str, list[str]]:
    """(pkgname, pkgver-pkgrel, depends) from a PKGBUILD, read the way
    makepkg does."""
    script = ('source "$1/PKGBUILD" >/dev/null 2>&1 || exit 1; '
              'printf "%s %s-%s" "$pkgname" "$pkgver" "$pkgrel"; '
              'for d in "${depends[@]}"; do printf " %s" "${d%%[<>=]*}"; done; echo')
    proc = cmdline.run(Options(), ["bash", "-c", script, "_", str(directory)], check=False, capture=True)
    if proc.returncode != 0:
        raise Error(f"can't read {directory}/PKGBUILD")
    name, ver, *deps = proc.stdout.split()
    return name, ver, deps


class Kind(Base):
    updates = True

    def status(self, item: Item, opts: Options) -> Status:
        try:
            have = installed_version(opts, item["package"])
        except Error as e:
            return Status(State.UNKNOWN, str(e))
        if not have:
            return Status(State.MISSING)
        if item.get("pkgbuild"):
            co = checkout()
            if co:
                try:
                    _, want, _ = pkgbuild_info(co / "pkgbuilds/frame" / item["pkgbuild"])
                except Error:
                    want = None
                if want and want != have:
                    return Status(State.OUTDATED, f"{have} installed, {want} in the PKGBUILD")
        return Status(State.OK, have)

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        self.no_args(item, args)
        require_commands("pacman", "fakeroot")
        status = self.status(item, opts)
        pacman_home = pacman_home_path()
        if item.get("relocate"):
            if status.state == State.OK:
                cmdline.say("ok", f"{item['package']} {status.detail} from Arch Linux ARM, in pacman-home's database")
                cmdline.note("pacman-home outdated says whether Arch Linux ARM has a newer one; "
                             "this re-relocates when it does")
            keyring = cmdline.run(opts, [pacman_home, "keyring", "--check"], check=False, capture=True)
            if keyring.returncode != 0:
                cmdline.say("would install" if opts.check else "install",
                            "Arch Linux ARM's signing keys into pacman-home's keyring")
                if not opts.check:
                    cmdline.run(opts, [pacman_home, "keyring"], capture=False)
            bin_ = Path.home() / ".local/bin" / item["package"]
            if (bin_.exists() or bin_.is_symlink()) and \
                    cmdline.run(opts, [pacman_home, "-Qo", str(bin_)], check=False, capture=True).returncode != 0:
                dest = bin_.with_name(f"{bin_.name}.bak-{cmdline.stamp()}")
                cmdline.say("would back up" if opts.check else "back up",
                            f"{cmdline.tilde(bin_)}, not pacman-home's -> {cmdline.tilde(dest)}")
                if not opts.check:
                    shutil.move(bin_, dest)
            cmdline.say("would relocate" if opts.check else "relocate",
                        f"{item['package']} from Arch Linux ARM under ~/.local (pacman-home relocate)")
            if opts.check:
                return True
            cmdline.run(opts, [pacman_home, "relocate", item["package"], "--noconfirm"], capture=False)
            return True

        co = checkout()
        if not co:
            raise Error(f"building {item['package']} needs the checkout's pkgbuilds/frame/{item['pkgbuild']}; "
                        "set [pkg] checkout in the config to where the checkout is")
        directory = co / "pkgbuilds/frame" / item["pkgbuild"]
        name, want, deps = pkgbuild_info(directory)
        if status.state == State.OK:
            cmdline.say("ok", f"{name} {status.detail}, in pacman-home's database")
            return False
        bin_ = Path.home() / ".local/bin" / ("emacs" if name == "emacs-wayland" else name)
        if (bin_.exists() or bin_.is_symlink()) and status.state == State.MISSING and \
                cmdline.run(opts, [pacman_home, "-Qo", str(bin_)], check=False, capture=True).returncode != 0:
            cmdline.say("skip", f"{cmdline.tilde(bin_)} exists and isn't pacman-home's; left alone")
            return False
        have = installed_version(opts, name)
        cmdline.say("would build" if opts.check else "build",
                    f"{name} {want}{', replacing ' + have if have else ''} "
                    f"(makepkg in {cmdline.tilde(directory)}, pacman-home -U)")
        if opts.check:
            return True
        if not cmdline.confirm(opts, f"build {name}? (emacs takes about three minutes)"):
            return False
        require_commands("makepkg")
        env = dict(os.environ)
        env.setdefault("MAKEFLAGS", f"-j{os.cpu_count() or 2}")
        # cargo, for a Rust package, comes from mise's shims; they go after
        # the host's directories so that a tool the host has stays the host's.
        shims = Path.home() / ".local/share/mise/shims"
        if shims.is_dir():
            env["PATH"] = env.get("PATH", "") + ":" + str(shims)
        cmdline.run(opts, ["makepkg", "-f"], cwd=str(directory), env=env, capture=False)
        built = cmdline.run(opts, ["makepkg", "--packagelist"], cwd=str(directory), capture=True).stdout.split()
        cmdline.run(opts, [pacman_home, "-U", *built, "--noconfirm"], capture=False)
        return True

    def uninstall(self, item: Item, opts: Options) -> bool:
        have = installed_version(opts, item["package"])
        if not have:
            return False
        cmdline.say("would remove" if opts.check else "remove", f"{item['package']} {have} (pacman-home -R)")
        if opts.check or not cmdline.confirm(opts, f"pacman-home -R {item['package']}?"):
            return opts.check
        cmdline.run(opts, [pacman_home_path(), "-R", item["package"], "--noconfirm"], capture=False)
        return True
