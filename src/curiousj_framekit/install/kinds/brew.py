"""The `brew` kind: Homebrew itself, and formulae from it. The default
prefix, /home/linuxbrew/.linuxbrew, since Homebrew's arm64 Linux
bottles are built for it alone; /home survives SteamOS updates. The
installer can't ask for a sudo password unattended, so the directory is
created for the user first, with sudo once, and the installer then
needs none. Items: `homebrew` (Homebrew plus wl-clipboard), `zsh`."""

from __future__ import annotations

import os
import pwd
from pathlib import Path

from ... import cmdline, where
from ...cmdline import Error, Options
from ..catalog import Item, State, Status
from .base import Base, TempDir, fetch

PREFIX = Path("/home/linuxbrew/.linuxbrew")
BREW = PREFIX / "bin/brew"
INSTALLER = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"


def brew(opts: Options, *args: str, check: bool = True, capture: bool = True):
    env = dict(os.environ, HOMEBREW_NO_ENV_HINTS="1")
    return cmdline.run(opts, [str(BREW), *args], check=check, capture=capture, env=env)


def has_formula(opts: Options, name: str) -> bool:
    return BREW.exists() and brew(opts, "list", "--formula", name, check=False).returncode == 0


class Kind(Base):
    def status(self, item: Item, opts: Options) -> Status:
        if where.in_container():
            return Status(State.UNKNOWN, "a distrobox doesn't see /home/linuxbrew")
        if not BREW.exists():
            return Status(State.MISSING)
        formulae = item.get("formulae", [])
        missing = [f for f in formulae if not has_formula(opts, f)]
        if missing:
            return Status(State.OUTDATED, f"missing {' '.join(missing)}")
        if item.name == "homebrew":
            ver = brew(opts, "--version", check=False).stdout.split("\n")[0].replace("Homebrew ", "")
            return Status(State.OK, ver)
        return Status(State.OK)

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        self.no_args(item, args)
        where.require_host(item.name)
        changed = False
        if not BREW.exists():
            if item.name != "homebrew":
                raise Error(f"{item.name} needs homebrew: cjf install homebrew")
            cmdline.say("would install" if opts.check else "install",
                        f"Homebrew into {PREFIX} (sudo once, to create {PREFIX.parent})")
            if opts.check:
                changed = True
            elif cmdline.confirm(opts, "install Homebrew?"):
                parent = PREFIX.parent
                if not os.access(parent.parent, os.W_OK) or not parent.exists():
                    user = pwd.getpwuid(os.getuid())
                    cmdline.run(opts, ["sudo", "install", "-d", "-o", user.pw_name, "-g",
                                       str(user.pw_gid), str(parent)], capture=False)
                with TempDir() as tmp:
                    script = tmp / "install.sh"
                    fetch(opts, INSTALLER, script)
                    cmdline.run(opts, ["bash", str(script)], capture=False,
                                env=dict(os.environ, NONINTERACTIVE="1"))
                changed = True
            else:
                return False
        else:
            ver = brew(opts, "--version", check=False).stdout.split("\n")[0]
            if item.name == "homebrew":
                cmdline.say("ok", ver)
        for formula in item.get("formulae", []):
            if BREW.exists() and has_formula(opts, formula):
                cmdline.say("ok", f"{formula} from Homebrew")
                continue
            cmdline.say("would brew install" if opts.check else "brew install", formula)
            if not opts.check:
                brew(opts, "install", formula, capture=False)
            changed = True
        return changed

    def uninstall(self, item: Item, opts: Options) -> bool:
        if item.name == "homebrew":
            raise Error("Homebrew's own uninstaller: "
                        "NONINTERACTIVE=1 bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)\"")
        changed = False
        for formula in item.get("formulae", []):
            if not has_formula(opts, formula):
                continue
            cmdline.say("would remove" if opts.check else "remove", f"{formula} (brew uninstall)")
            if opts.check or not cmdline.confirm(opts, f"brew uninstall {formula}?"):
                changed = changed or opts.check
                continue
            brew(opts, "uninstall", formula, capture=False)
            changed = True
        return changed
