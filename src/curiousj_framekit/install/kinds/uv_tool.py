"""The `uv-tool` kind: a Python command-line tool installed with uv,
which the base put in place. Today curiousj-tools."""

from __future__ import annotations

import shutil
from pathlib import Path

from ... import cmdline
from ...cmdline import Error, Options
from ..catalog import Item, State, Status
from .base import Base


def uv_path() -> str:
    for candidate in (shutil.which("uv"), Path.home() / ".local/share/mise/shims/uv",
                      Path.home() / ".local/bin/uv"):
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise Error("uv is missing; it is part of the base: run install.sh again")


def installed_version(opts: Options, tool: str) -> str | None:
    out = cmdline.run(opts, [uv_path(), "tool", "list"], check=False, capture=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == tool:
            return parts[1]
    return None


class Kind(Base):
    updates = True

    def status(self, item: Item, opts: Options) -> Status:
        try:
            ver = installed_version(opts, item["tool"])
        except Error as e:
            return Status(State.MISSING, str(e))
        return Status(State.OK, ver) if ver else Status(State.MISSING)

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        self.no_args(item, args)
        uv = uv_path()
        ver = installed_version(opts, item["tool"])
        if ver:
            cmdline.say("would upgrade" if opts.check else "upgrade", f"{item['tool']} {ver} (uv tool upgrade)")
            if not opts.check:
                cmdline.run(opts, [uv, "tool", "upgrade", item["tool"]], capture=False)
            return True
        cmdline.say("would install" if opts.check else "install", f"{item['tool']} from {item['source']} (uv tool install)")
        if opts.check:
            return True
        cmdline.run(opts, [uv, "tool", "install", item["source"]], capture=False)
        return True

    def uninstall(self, item: Item, opts: Options) -> bool:
        if not installed_version(opts, item["tool"]):
            return False
        cmdline.say("would remove" if opts.check else "remove", f"{item['tool']} (uv tool uninstall)")
        if opts.check or not cmdline.confirm(opts, f"uv tool uninstall {item['tool']}?"):
            return opts.check
        cmdline.run(opts, [uv_path(), "tool", "uninstall", item["tool"]], capture=False)
        return True
