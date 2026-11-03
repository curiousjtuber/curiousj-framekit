"""cjf install, cjf installed, cjf uninstall -- the catalog of optional
items: apps, host packages, services, fonts, and the cursor fix.

    cjf install                       pick items from the catalog (TAB marks several)
    cjf install NAME...               install or update the items named
    cjf install NAME [OPTIONS...]     one item, with its own options (see below)
    cjf installed [--trust]           every item's state; --trust adds the
                                      root of trust and what is checked
    cjf uninstall NAME                remove one item, or print the steps

An installed item is updated by installing it again, as every script
did on a re-run; `cjf outdated` says which have something newer, and
`cjf update` installs those. An item that needs another (zsh needs
homebrew) brings it along, listed up front as one question. The global
options go first: `cjf --check install NAME` says what would happen,
`cjf --yes install NAME` asks nothing.

Items with options of their own:

    cursor         [on|off|default]
    tailscale      [--trust]
    nerd-fonts     [NAME...]
    frametop       [--version X.Y.Z] [--yes] [--no-eye-tracker] [--no-bluetooth | --bluetooth]
                   [--any-steamos] [--unpack-only]
    full-keyboard  [--version X.Y.Z]
    bsmanager      [--uninstall | --appimage FILE]
    krdp           [--bundle [FILE]]
    Flatpak apps   [--user | --system]
"""

from __future__ import annotations

import sys

import click

from .. import cmdline, pick, where
from ..cmdline import Error, Options, pass_options
from . import catalog, kinds
from .catalog import State


def state_lines(items: dict[str, catalog.Item], statuses: dict[str, catalog.Status],
                trust: bool = False) -> list[str]:
    width = max(len(n) for n in items)
    out = []
    for name, item in items.items():
        s = statuses[name]
        detail = f" [{s.detail}]" if s.detail else ""
        line = f"{s.state.value:<9} {name:<{width}}  {item.description}{detail}"
        if trust:
            line += f"\n{'':9} {'':{width}}  trust: {item.get('trust_root', '?')}; checks: {item.get('trust_checks', '?')}"
        out.append(line)
    return out


def split_words(items: dict[str, catalog.Item], words: list[str]) -> tuple[list[str], list[str]]:
    """Leading catalog names, then the rest as one item's options."""
    names: list[str] = []
    i = 0
    while i < len(words) and words[i] in items:
        names.append(words[i])
        i += 1
    rest = words[i:]
    if rest and not rest[0].startswith("-"):
        raise Error(f"no catalog item named {rest[0]}; cjf installed lists them")
    if rest and len(names) != 1:
        raise Error("options after the name go with one item at a time")
    return names, rest


def pick_items(items: dict[str, catalog.Item], statuses: dict[str, catalog.Status]) -> list[str]:
    if not sys.stdin.isatty():
        raise click.UsageError("name the items to install, or run on a terminal to pick them")
    lines = state_lines(items, statuses)
    try:
        chosen = pick.choose_many(lines, "items")
    except cmdline.Abort:
        return []
    return [line.split()[1] for line in chosen]


@click.command(cls=cmdline.Command, help=__doc__, short_help="install or update an optional item: apps, packages, services, fonts",
               context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("words", nargs=-1, type=click.UNPROCESSED)
@pass_options
def install(opts: Options, words: tuple[str, ...]) -> int:
    where.require_frame("install")
    items = catalog.load()
    statuses = catalog.all_status(items, opts)
    names, item_args = split_words(items, list(words))
    if not names:
        names = pick_items(items, statuses)
        if not names:
            return cmdline.EXIT_ABORT
    chosen = catalog.resolve(items, names)
    needed = [it for it in chosen if it.name not in names and statuses[it.name].state == State.MISSING]
    chosen = [it for it in chosen if it.name in names or it.name in {n.name for n in needed}]
    if needed:
        wants = ", ".join(f"{n} needs {', '.join(items[n].needs)}" for n in names if items[n].needs)
        print(f"{wants}, which {'is' if len(needed) == 1 else 'are'}n't installed. Install together:")
        for it in chosen:
            print(f"  {it.name:<14} {it.description}")
        if not opts.check and not cmdline.confirm(opts, "continue?"):
            return cmdline.EXIT_ABORT
    changed = 0
    failed: list[str] = []
    for it in chosen:
        kind = kinds.for_item(it)
        print(f"--- {it.name}", flush=True)
        args_for = item_args if len(names) == 1 and it.name == names[0] else []
        try:
            if kind.install(it, opts, args_for):
                changed += 1
        except Error as e:
            if len(chosen) == 1:
                raise
            # One item's trouble shouldn't stop the others; it is said
            # here and the run ends with 1.
            cmdline.say("failed", f"{it.name}: {e}")
            failed.append(it.name)
    if opts.check:
        print("run without --check to apply" if changed else "nothing to change")
    else:
        print(f"done: {changed} changed" if changed else "nothing to do")
    if failed:
        print(f"failed: {' '.join(failed)}")
        return 1
    return 0


@click.command(cls=cmdline.Command, help="Every catalog item's state.",
               short_help="every catalog item's state: installed, missing, outdated")
@click.option("--trust", is_flag=True, help="Also the root of trust and what is checked.")
@pass_options
def installed(opts: Options, trust: bool) -> int:
    where.require_frame("installed")
    items = catalog.load()
    print("\n".join(state_lines(items, catalog.all_status(items, opts), trust)))
    return 0


@click.command(cls=cmdline.Command, help="Remove one catalog item, or print the steps.",
               short_help="remove one catalog item")
@click.argument("name")
@pass_options
def uninstall(opts: Options, name: str) -> int:
    where.require_frame("uninstall")
    items = catalog.load()
    if name not in items:
        raise Error(f"no catalog item named {name}; cjf installed lists them")
    item = items[name]
    dependants = [n for n, it in items.items() if name in it.needs
                  and catalog.status_of(it, opts).state != State.MISSING]
    if dependants:
        cmdline.note(f"{', '.join(dependants)} need{'s' if len(dependants) == 1 else ''} {name}")
    changed = kinds.for_item(item).uninstall(item, opts)
    if opts.check:
        print("run without --check to apply" if changed else "nothing to change")
    elif not changed:
        print("nothing to do")
    return 0
