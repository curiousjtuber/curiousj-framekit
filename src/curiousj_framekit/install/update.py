"""cjf outdated, cjf update -- the installed items against their
upstreams, and the newer ones installed.

    cjf outdated [NAME...]     every installed item (or those named) against
                               its upstream, and the kit itself; the network
    cjf update [NAME...]       the same, then install what is outdated,
                               asked once; `cjf --check update` only lists

`cjf installed` sees what is here without the network; this asks the
other side: Flathub and the apps' own remotes (flatpak remote-ls
--updates), Arch Linux ARM and the AUR (as pacman-home outdated), the
GitHub releases, pkgs.tailscale.com, Homebrew, mise, and git for the
kit and the tools installed from a checkout. The checks run together,
and each line is one of:

    current     what is installed is what is there
    outdated    a newer one is there; `cjf update` installs it, the way
                `cjf install NAME` again does, or the kind's own way
                (Tailscale's binaries over the old ones, brew upgrade,
                mise upgrade, git pull --ff-only in a checkout)
    behind      upstream moved past what the kit pins: the version in a
                PKGBUILD, or Frametop's in the catalog. That is a bump in
                the kit, said on the line, not an install here
    ?           no way to tell: BSManager updates itself, the cursor is
                two files

`cjf update NAME` with a current NAME does nothing and says so.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata

import click

from .. import cmdline, where
from ..cmdline import Error, Options, pass_options
from . import catalog, kinds
from .catalog import Check, Fresh, State

KIT = "curiousj-framekit"


def check_lines(checks: dict[str, Check], width: int | None = None) -> list[str]:
    width = width or max(len(n) for n in checks)
    out = []
    for name, c in checks.items():
        parts = []
        if c.fresh == Fresh.CURRENT:
            parts.append(c.installed)
        elif c.fresh in (Fresh.OUTDATED, Fresh.BEHIND) and c.available == c.installed:
            parts.append(c.installed)     # the same version again: a rebuild, said in the note
        elif c.fresh in (Fresh.OUTDATED, Fresh.BEHIND):
            parts.append(f"{c.installed or '?'} -> {c.available}")
        elif c.installed:
            parts.append(c.installed)
        if c.source:
            parts.append(f"({c.source})")
        text = " ".join(parts)
        if c.note:
            text += f"; {c.note}" if text else c.note
        out.append(f"{c.fresh.value:<9} {name:<{width}}  {text}")
    return out


def kit_check(opts: Options) -> Check:
    from .kinds import uv_tool
    try:
        version = metadata.version(KIT)
    except metadata.PackageNotFoundError:
        return Check(Fresh.UNKNOWN, note="not installed as a package")
    try:
        return uv_tool.check_tool(opts, KIT, version)
    except Error as e:
        return Check(Fresh.UNKNOWN, version, note=f"can't tell: {e}")


def run_checks(items: dict[str, catalog.Item], statuses: dict[str, catalog.Status],
               opts: Options, with_kit: bool) -> tuple[dict[str, Check], list[str]]:
    """The checks for the installed items, run together; and the names
    of the items that aren't installed."""
    installed = [n for n, s in statuses.items() if s.state != State.MISSING]
    missing = [n for n in items if n not in installed]
    print(f"checking {len(installed) + with_kit} installed items upstream...", file=sys.stderr, flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {n: pool.submit(catalog.check_of, items[n], opts, statuses[n]) for n in installed}
        kit = pool.submit(kit_check, opts) if with_kit else None
        checks = {n: f.result() for n, f in futures.items()}
        if kit:
            checks["kit"] = kit.result()
    return checks, missing


def chosen(items: dict[str, catalog.Item], names: tuple[str, ...]) -> dict[str, catalog.Item]:
    for name in names:
        if name not in items and name != "kit":
            raise Error(f"no catalog item named {name}; cjf installed lists them")
    return {n: it for n, it in items.items() if not names or n in names}


@click.command(cls=cmdline.Command, help=__doc__,
               short_help="every installed item against its upstream: current, outdated, behind")
@click.argument("names", nargs=-1)
@pass_options
def outdated(opts: Options, names: tuple[str, ...]) -> int:
    where.require_frame("outdated")
    items = chosen(catalog.load(), names)
    statuses = catalog.all_status(items, opts)
    checks, missing = run_checks(items, statuses, opts, with_kit=not names or "kit" in names)
    print("\n".join(check_lines(checks)))
    if missing and not names:
        print(f"not installed: {' '.join(missing)}")
    return 0


@click.command(cls=cmdline.Command, help=__doc__,
               short_help="install the newer versions cjf outdated finds")
@click.argument("names", nargs=-1)
@pass_options
def update(opts: Options, names: tuple[str, ...]) -> int:
    where.require_frame("update")
    items = chosen(catalog.load(), names)
    statuses = catalog.all_status(items, opts)
    checks, _ = run_checks(items, statuses, opts, with_kit=not names or "kit" in names)
    todo = [n for n, c in checks.items() if c.fresh == Fresh.OUTDATED]
    shown = {n: c for n, c in checks.items() if c.fresh != Fresh.CURRENT} if not names else checks
    if shown:
        print("\n".join(check_lines(shown, max(len(n) for n in checks))))
    if not todo:
        print("nothing to update")
        return 0
    if not opts.check and not cmdline.confirm(opts, f"update {', '.join(todo)}?"):
        return cmdline.EXIT_ABORT
    changed = 0
    failed: list[str] = []
    for name in todo:
        print(f"--- {name}", flush=True)
        try:
            if name == "kit":
                from .kinds import uv_tool
                done = uv_tool.update_tool(opts, KIT)
            else:
                done = kinds.for_item(items[name]).update(items[name], opts)
            changed += bool(done)
        except Error as e:
            if len(todo) == 1:
                raise
            cmdline.say("failed", f"{name}: {e}")
            failed.append(name)
    if opts.check:
        print("run without --check to apply" if changed else "nothing to change")
    else:
        print(f"done: {changed} updated" if changed else "nothing to do")
    if failed:
        print(f"failed: {' '.join(failed)}")
        return 1
    return 0
