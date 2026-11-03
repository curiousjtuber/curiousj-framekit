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
import json

from ..catalog import Check, Fresh, Item, State, Status
from .base import Base, TempDir, fetch

PREFIX = Path("/home/linuxbrew/.linuxbrew")
BREW = PREFIX / "bin/brew"
INSTALLER = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"


def brew(opts: Options, *args: str, check: bool = True, capture: bool = True):
    env = dict(os.environ, HOMEBREW_NO_ENV_HINTS="1")
    return cmdline.run(opts, [str(BREW), *args], check=check, capture=capture, env=env)


def has_formula(opts: Options, name: str) -> bool:
    return BREW.exists() and brew(opts, "list", "--formula", name, check=False).returncode == 0


def outdated_formulae(opts: Options, names: list[str]) -> dict[str, tuple[str, str]]:
    """formula -> (installed, current) for those of `names` that brew
    says are outdated; it fetches Homebrew's API data itself."""
    proc = brew(opts, "outdated", "--formula", "--json", *names, check=False)
    if proc.returncode != 0:
        raise Error(f"brew outdated failed: {proc.stderr.strip()}")
    return parse_outdated(proc.stdout)


def parse_outdated(text: str) -> dict[str, tuple[str, str]]:
    try:
        data = json.loads(text or "{}")
    except ValueError:
        raise Error("brew outdated printed no JSON") from None
    return {f["name"]: (", ".join(f.get("installed_versions", [])), f.get("current_version", ""))
            for f in data.get("formulae", []) if "name" in f}


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

    def check(self, item: Item, opts: Options, status: Status) -> Check:
        if where.in_container() or not BREW.exists():
            return Check(Fresh.UNKNOWN, note=status.detail)
        formulae = [f for f in item.get("formulae", []) if has_formula(opts, f)]
        outdated = outdated_formulae(opts, formulae) if formulae else {}
        if outdated:
            return Check(Fresh.OUTDATED, " ".join(v[0] for v in outdated.values()),
                         " ".join(v[1] for v in outdated.values()), "Homebrew", " ".join(outdated))
        ver = brew(opts, "--version", check=False).stdout.split("\n")[0].replace("Homebrew ", "")
        return Check(Fresh.CURRENT, ver if item.name == "homebrew" else " ".join(formulae), source="Homebrew")

    def update(self, item: Item, opts: Options) -> bool:
        """brew upgrade for the item's outdated formulae; the rest, a
        missing formula say, is the install's."""
        where.require_host(item.name)
        formulae = [f for f in item.get("formulae", []) if has_formula(opts, f)]
        outdated = outdated_formulae(opts, formulae) if formulae and BREW.exists() else {}
        if not outdated:
            return self.install(item, opts, [])
        for name, (have, current) in outdated.items():
            cmdline.say("would upgrade" if opts.check else "upgrade", f"{name} {have} -> {current} (brew upgrade)")
        if opts.check:
            return True
        brew(opts, "upgrade", *outdated, capture=False)
        return True

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
