"""The `mise` kind: a tool through mise, which the base put in place.
Today rust, for cargo, which a Rust PKGBUILD needs. Which version is
mise's business (`latest`, kept current by `mise upgrade`)."""

from __future__ import annotations

import os
from pathlib import Path

from ... import cmdline
from ...cmdline import Error, Options
from ..catalog import Item, State, Status
from .base import Base


def mise_path() -> Path:
    return Path.home() / ".local/bin/mise"


def mise(opts: Options, *args: str, check: bool = True):
    # From $HOME, so that the global config answers rather than some
    # project's .mise.toml.
    return cmdline.run(opts, [str(mise_path()), *args], check=check, capture=True,
                       cwd=str(Path.home()))


class Kind(Base):
    def status(self, item: Item, opts: Options) -> Status:
        if not mise_path().exists():
            return Status(State.MISSING, "mise itself is missing: run install.sh")
        proc = mise(opts, "which", item["command"], check=False)
        if proc.returncode != 0:
            return Status(State.MISSING)
        ver = mise(opts, "exec", "--", item["command"], "--version", check=False).stdout.split()
        return Status(State.OK, ver[1] if len(ver) > 1 else "")

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        self.no_args(item, args)
        if not mise_path().exists():
            raise Error("mise is missing; it is part of the base: run install.sh again")
        if self.status(item, opts).state == State.OK:
            cmdline.say("ok", f"{item['tool']} through mise")
            return False
        cmdline.say("would install" if opts.check else "install",
                    f"{item['tool']} through mise (mise use -g {item['tool']})")
        if opts.check:
            return True
        cmdline.run(opts, [str(mise_path()), "use", "-g", item["tool"]], cwd=str(Path.home()))
        return True

    def uninstall(self, item: Item, opts: Options) -> bool:
        cmdline.say("would remove" if opts.check else "remove", f"{item['tool']} from mise's global config")
        if opts.check or not cmdline.confirm(opts, f"mise unuse -g {item['tool']}?"):
            return opts.check
        cmdline.run(opts, [str(mise_path()), "unuse", "-g", item["tool"]], cwd=str(Path.home()))
        return True
