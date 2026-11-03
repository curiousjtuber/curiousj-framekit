"""The `flatpak` kind: an app from a Flatpak remote, Flathub or the
app's own. What the four scripts did, with two variables: add the remote
if missing, install or update the app, make sure its runtime is in the
same installation (a runtime in the other installation satisfies the
install, and removing it later would break the app), and note a copy in
the other installation.

The scope is `user` by default, as the scripts had it: no root, no
polkit, works over SSH, survives updates in /home. `system` goes through
sudo (`cjf install --system NAME`, or `[flatpak] scope = "system"` in
the config)."""

from __future__ import annotations

import sys
import threading

from ... import cmdline, config
from ...cmdline import Error, Options
from ..catalog import Check, Fresh, Item, State, Status
from .base import Base, require_commands

_updates: dict[str, dict[str, tuple[str, str]]] = {}
_updates_lock = threading.Lock()


def updates_available(opts: Options, scope: str) -> dict[str, tuple[str, str]]:
    """app id -> (version, origin) for every app of the installation
    with an update at its remote: one `flatpak remote-ls --updates` per
    scope, which asks every remote, so it is asked once and shared by
    the checks that run together. The system installation can be read
    without root."""
    with _updates_lock:
        if scope not in _updates:
            proc = cmdline.run(opts, ["flatpak", f"--{scope}", "remote-ls", "--updates", "--app",
                                      "--columns=application,version,origin"],
                               check=False, capture=True, timeout=120)
            if proc.returncode != 0:
                raise Error(f"flatpak --{scope} remote-ls failed: {proc.stderr.strip()}")
            _updates[scope] = parse_updates(proc.stdout)
        return _updates[scope]


def parse_updates(text: str) -> dict[str, tuple[str, str]]:
    found = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            found[parts[0]] = (parts[1], parts[2])
    return found


def scope_of(opts: Options, args: list[str]) -> str:
    if "--system" in args:
        return "system"
    if "--user" in args:
        return "user"
    scope = config.get("flatpak", "scope", "user")
    if scope not in ("user", "system"):
        raise Error(f"[flatpak] scope in the config is {scope!r}; it is user or system")
    return scope


def flatpak(opts: Options, scope: str, *args: str, check: bool = True, capture: bool = True):
    argv = ["flatpak", f"--{scope}", *args]
    if scope == "system":
        argv = ["sudo", *argv]
    return cmdline.run(opts, argv, check=check, capture=capture)


def info(opts: Options, scope: str, ref: str) -> dict[str, str]:
    proc = flatpak(opts, scope, "info", ref, check=False)
    if proc.returncode != 0:
        return {}
    out = {}
    for line in proc.stdout.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


class Kind(Base):
    options = "[--user|--system]  (the installation; default [flatpak] scope, else user)"

    def status(self, item: Item, opts: Options) -> Status:
        app = item["app"]
        for scope in ("user", "system"):
            found = info(opts, scope, app) if scope == "user" else info_system(opts, app)
            if found:
                detail = found.get("Version") or found.get("Commit", "")[:12]
                return Status(State.OK, f"{detail} ({scope})".strip())
        return Status(State.MISSING)

    def check(self, item: Item, opts: Options, status: Status) -> Check:
        app = item["app"]
        for scope in ("user", "system"):
            found = info(opts, scope, app) if scope == "user" else info_system(opts, app)
            if found:
                break
        else:
            return Check(Fresh.UNKNOWN, note="not installed")
        have = found.get("Version") or found.get("Commit", "")[:12]
        update = updates_available(opts, scope).get(app)
        if update:
            # The same version at the remote is a rebuild (a runtime
            # bump, say), which flatpak update takes all the same.
            available = update[0] if update[0] != have else f"{update[0]}, a new build"
            return Check(Fresh.OUTDATED, have, available, update[1])
        return Check(Fresh.CURRENT, have, source=found.get("Origin", item["remote"]))

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        require_commands("flatpak")
        extra = [a for a in args if a not in ("--user", "--system")]
        if extra:
            raise Error(f"{item.name} takes --user or --system only; got {' '.join(extra)}")
        scope = scope_of(opts, args)
        app, remote, url = item["app"], item["remote"], item["remote_url"]
        yes = ["-y"] if opts.yes or not sys.stdin.isatty() else []
        changed = False

        remotes = flatpak(opts, scope, "remotes", "--columns=name", check=False).stdout.split()
        if remote in remotes:
            cmdline.say("ok", f"remote {remote} ({scope})")
        else:
            cmdline.say("would add" if opts.check else "add", f"remote {remote} from {url} ({scope})")
            if not opts.check:
                flatpak(opts, scope, "remote-add", "--if-not-exists", remote, url)
            changed = True

        if info(opts, scope, app) if scope == "user" else info_system(opts, app):
            cmdline.say("would update" if opts.check else "update", f"{app} ({scope})")
            if not opts.check:
                flatpak(opts, scope, "update", *yes, app, capture=False)
        else:
            note = item.get("runtime_note")
            cmdline.say("would install" if opts.check else "install",
                        f"{app} from {remote} ({scope})" + (f"; also {note}" if note else ""))
            if opts.check:
                return True
            if not cmdline.confirm(opts, "proceed with the download?"):
                return False
            flatpak(opts, scope, "install", *yes, remote, app, capture=False)
        changed = True

        if not opts.check:
            runtime = flatpak(opts, scope, "info", "--show-runtime", app, check=False).stdout.strip()
            if runtime and not (info(opts, scope, runtime) if scope == "user" else info_system(opts, runtime)):
                cmdline.say("install", f"runtime {runtime}, into the {scope} installation too")
                flatpak(opts, scope, "install", *yes, "flathub", runtime, capture=False)
            else:
                cmdline.say("ok", f"runtime {runtime}")
            other = "system" if scope == "user" else "user"
            if info_system(opts, app) if other == "system" else info(opts, "user", app):
                cmdline.note(f"a {other} copy of {app} is installed too; the {scope} copy "
                             f"{'takes precedence' if scope == 'user' else 'is shadowed by the user copy'}")
        return changed

    def uninstall(self, item: Item, opts: Options) -> bool:
        app = item["app"]
        changed = False
        for scope in ("user", "system"):
            present = info(opts, "user", app) if scope == "user" else info_system(opts, app)
            if not present:
                continue
            cmdline.say("would remove" if opts.check else "remove", f"{app} ({scope})")
            if opts.check or not cmdline.confirm(opts, f"remove {app} ({scope})?"):
                changed = changed or opts.check
                continue
            flatpak(opts, scope, "uninstall", "-y", app, capture=False)
            changed = True
        if changed and not opts.check:
            cmdline.note("flatpak uninstall --user --unused removes a runtime nothing else uses")
        return changed


def info_system(opts: Options, ref: str) -> dict[str, str]:
    """`flatpak --system info` needs no root to read, so no sudo here."""
    proc = cmdline.run(opts, ["flatpak", "--system", "info", ref], check=False, capture=True)
    if proc.returncode != 0:
        return {}
    out = {}
    for line in proc.stdout.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out
