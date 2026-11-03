"""The `uv-tool` kind: a Python command-line tool installed with uv,
which the base put in place. Today curiousj-tools; the kit itself is
installed the same way and `cjf outdated` checks it with this module.

Where the tool came from is in its direct_url.json, as pip records it:
a git install carries the commit, so the check is `git ls-remote` of
the source against it and the update `uv tool upgrade`; an editable
checkout (`uv tool install --editable DIR`) carries the directory, so
the check is that checkout's HEAD against its origin and the update
`git pull --ff-only` there, which is how a checkout is deployed."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ... import cmdline
from ...cmdline import Error, Options
from ..catalog import Check, Fresh, Item, State, Status
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


def tools_dir() -> Path:
    out = cmdline.run(Options(), [uv_path(), "tool", "dir"], check=False, capture=True).stdout.strip()
    return Path(out) if out else Path.home() / ".local/share/uv/tools"


def direct_url(tool: str) -> dict:
    """The tool's direct_url.json, {} when it has none (a PyPI install)."""
    dist = tool.replace("-", "_")
    for path in sorted((tools_dir() / tool).glob(f"lib/python*/site-packages/{dist}-*.dist-info/direct_url.json")):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            continue
    return {}


def origin_of(direct: dict) -> tuple[str, str] | None:
    """("git", url, commit) collapsed to (kind, where): ("git", url)
    for a git install, ("editable", directory) for a checkout, None for
    anything else (PyPI, a wheel)."""
    url = direct.get("url", "")
    if direct.get("dir_info", {}).get("editable") and url.startswith("file://"):
        return "editable", url.removeprefix("file://")
    if direct.get("vcs_info", {}).get("vcs") == "git":
        return "git", url
    return None


def remote_head(opts: Options, where: str) -> tuple[str, str]:
    """(commit, what was asked): HEAD of a git URL; for a checkout, the
    tip of the branch it tracks (origin/dev, say) at that remote, or
    the remote's HEAD when it tracks none."""
    if where.startswith(("http://", "https://", "git@", "ssh://", "git://")):
        argv, what = ["git", "ls-remote", where, "HEAD"], where
    else:
        tracked = cmdline.run(opts, ["git", "-C", where, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                              check=False, capture=True).stdout.strip()
        remote, _, branch = tracked.partition("/")
        if not branch:
            remote, branch = "origin", "HEAD"
        argv = ["git", "-C", where, "ls-remote", remote, branch if branch == "HEAD" else f"refs/heads/{branch}"]
        what = f"{remote}/{branch} of {cmdline.tilde(where)}"
    proc = cmdline.run(opts, argv, check=False, capture=True, timeout=60)
    if proc.returncode != 0 or not proc.stdout.split():
        raise Error(f"{' '.join(argv)} failed: {proc.stderr.strip()}")
    return proc.stdout.split()[0], what


def check_tool(opts: Options, tool: str, installed: str) -> Check:
    """The check for any uv tool, the kit included."""
    origin = origin_of(direct_url(tool))
    if origin is None:
        return Check(Fresh.UNKNOWN, installed, note="not from git; uv tool upgrade tells")
    kind, where = origin
    if kind == "git":
        have = direct_url(tool)["vcs_info"].get("commit_id", "")
    else:
        have = cmdline.run(opts, ["git", "-C", where, "rev-parse", "HEAD"], check=False,
                           capture=True).stdout.strip()
        if not have:
            return Check(Fresh.UNKNOWN, installed, note=f"{cmdline.tilde(where)} isn't a git checkout")
    found, source = remote_head(opts, where)
    if have == found:
        return Check(Fresh.CURRENT, f"{installed} {have[:7]}", source=source)
    return Check(Fresh.OUTDATED, f"{installed} {have[:7]}", found[:7], source,
                 f"git pull --ff-only in {cmdline.tilde(where)}" if kind == "editable" else "")


def update_tool(opts: Options, tool: str) -> bool:
    origin = origin_of(direct_url(tool))
    if origin and origin[0] == "editable":
        where = origin[1]
        cmdline.say("would pull" if opts.check else "pull", f"{cmdline.tilde(where)} (git pull --ff-only)")
        if opts.check:
            return True
        cmdline.run(opts, ["git", "-C", where, "pull", "--ff-only"], capture=False)
        return True
    cmdline.say("would upgrade" if opts.check else "upgrade", f"{tool} (uv tool upgrade)")
    if opts.check:
        return True
    cmdline.run(opts, [uv_path(), "tool", "upgrade", tool], capture=False)
    return True


class Kind(Base):
    def check(self, item: Item, opts: Options, status: Status) -> Check:
        if status.state != State.OK:
            return Check(Fresh.UNKNOWN, note=status.detail)
        return check_tool(opts, item["tool"], status.detail)

    def update(self, item: Item, opts: Options) -> bool:
        if not installed_version(opts, item["tool"]):
            return self.install(item, opts, [])
        return update_tool(opts, item["tool"])

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
