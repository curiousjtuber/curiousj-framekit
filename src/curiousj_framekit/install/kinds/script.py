"""The `installer-script` kind: a project's own `curl | sh` installer
into ~/.local. Today distrobox. The script is saved to a file before it
runs, so a cut-off download runs nothing, but it is otherwise unpinned
and unchecked, which the trust columns say."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from ... import cmdline
from ...cmdline import Error, Options
from ..catalog import Check, Fresh, Item, State, Status
from .base import Base, TempDir, fetch, latest_tag, newer, require_commands


class Kind(Base):
    def status(self, item: Item, opts: Options) -> Status:
        bin_ = Path.home() / ".local/bin" / item["command"]
        if not os.access(bin_, os.X_OK):
            return Status(State.MISSING)
        ver = cmdline.output(opts, [str(bin_), *item.get("version_args", ["--version"])], default="") or ""
        return Status(State.OK, ver.strip().split(":")[-1].strip().split("\n")[0])

    def check(self, item: Item, opts: Options, status: Status) -> Check:
        if status.state != State.OK or not item.get("repo"):
            return Check(Fresh.UNKNOWN, status.detail, note="no release to compare with")
        found = latest_tag(item["repo"]).lstrip("v")
        if newer(found, status.detail):
            return Check(Fresh.OUTDATED, status.detail, found, "GitHub release",
                         "its installer takes the main branch, which may be past the release")
        return Check(Fresh.CURRENT, status.detail, source="GitHub release")

    def update(self, item: Item, opts: Options) -> bool:
        status = self.status(item, opts)
        if status.state != State.OK:
            return self.install(item, opts, [])
        return self.run_installer(item, opts, f"{item.name} {status.detail}, again")

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        self.no_args(item, args)
        status = self.status(item, opts)
        if status.state == State.OK:
            cmdline.say("ok", f"{item['command']} {status.detail}")
            return False
        return self.run_installer(item, opts, item.name)

    def run_installer(self, item: Item, opts: Options, what: str) -> bool:
        require_commands("curl")
        argv = [os.path.expanduser(a) for a in item.get("args", [])]
        cmdline.say("would install" if opts.check else "install",
                    f"{what} with its installer from {item['url']} {' '.join(argv)}".rstrip())
        if opts.check:
            return True
        if not cmdline.confirm(opts, f"run {item.name}'s installer?"):
            return False
        with TempDir() as tmp:
            script = tmp / "install.sh"
            fetch(opts, item["url"], script)
            cmdline.run(opts, ["sh", str(script), *argv], capture=False)
        return True

    def uninstall(self, item: Item, opts: Options) -> bool:
        raise Error(f"{item.name}: remove it with its own uninstaller; for distrobox, "
                    "~/.local/bin/distrobox-uninstall --prefix ~/.local")
