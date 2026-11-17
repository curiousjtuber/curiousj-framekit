"""One module per kind of catalog item. Each exposes a class with:

    status(item, opts) -> catalog.Status      the state now, no network
    install(item, opts, args) -> bool         install or update; True
                                              when something changed
    uninstall(item, opts) -> bool             remove, or print the steps
    options -> str                            the item options install
                                              takes after NAME, for help

`args` are the words after the item's name on the command line, parsed
by the kind (--trust for Tailscale, on or off for the cursor), so the catalog
stays declarative and each kind's quirks stay in its module."""

from __future__ import annotations

from importlib import import_module

from ..catalog import Item

MODULES = {
    "config": "config",
    "pacman-home": "pacman_home",
    "system-service": "tailscale",
}


def for_item(item: Item):
    try:
        module = import_module(f".{MODULES[item.kind]}", __package__)
    except KeyError:
        raise ValueError(f"{item.name}: unknown kind {item.kind}") from None
    return module.Kind()
