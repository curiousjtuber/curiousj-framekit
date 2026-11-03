"""The catalog: the optional items, read from catalog.toml, and the
state of each on this Frame. Each item has a kind, and the kind's
module (install/kinds/) knows how to tell the item's state and how to
install or remove it. This module is the data side, shared by `cjf
install`, `cjf installed`, `cjf status --all` and the `needs()` check
commands make at their start."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from enum import Enum
from importlib import resources
from typing import Any

from ..cmdline import Error, Options


class State(Enum):
    OK = "ok"
    MISSING = "missing"
    OUTDATED = "outdated"
    UNKNOWN = "?"


@dataclass(frozen=True)
class Item:
    name: str
    kind: str
    description: str
    needs: tuple[str, ...] = ()
    needs_root: bool = False
    data: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass
class Status:
    state: State
    detail: str = ""      # "0.11.2-1", "2 of 2 fonts", "pid 4102"

    def __str__(self) -> str:
        return self.state.value + (f" ({self.detail})" if self.detail else "")


class Fresh(Enum):
    """An installed item against its upstream, which takes the network:
    what `cjf outdated` shows and `cjf update` acts on."""
    CURRENT = "current"
    OUTDATED = "outdated"    # a newer one is there; cjf update installs it
    BEHIND = "behind"        # upstream moved past what the kit pins (a
                             # PKGBUILD, the catalog): a bump here, not an
                             # install there
    UNKNOWN = "?"            # no way to tell


@dataclass
class Check:
    fresh: Fresh
    installed: str = ""      # "1.102.4", "0.11.3-1", "582a119"
    available: str = ""      # "1.104.5"; for BEHIND, the upstream version
    source: str = ""         # "Flathub", "Arch Linux ARM", "the catalog"
    note: str = ""           # "bump the PKGBUILD", "updates itself"


KNOWN_KEYS = {"kind", "description", "needs", "needs_root"}


def load() -> dict[str, Item]:
    """The items, in the catalog's order."""
    text = (resources.files("curiousj_framekit") / "install" / "catalog.toml").read_text()
    raw = tomllib.loads(text)
    items: dict[str, Item] = {}
    for name, entry in raw.get("item", {}).items():
        data = {k: v for k, v in entry.items() if k not in KNOWN_KEYS}
        items[name] = Item(name, entry["kind"], entry["description"],
                           tuple(entry.get("needs", ())), bool(entry.get("needs_root", False)),
                           data)
    return items


def resolve(items: dict[str, Item], wanted: list[str]) -> list[Item]:
    """wanted and what they need, in an order that puts a need before the
    item, the catalog's order otherwise. An unknown name is an Error."""
    for name in wanted:
        if name not in items:
            raise Error(f"no catalog item named {name}; cjf installed lists them")
    chosen: list[str] = []

    def add(name: str, chain: tuple[str, ...]) -> None:
        if name in chosen:
            return
        if name in chain:
            raise Error(f"the catalog has a cycle of needs: {' -> '.join(chain + (name,))}")
        for need in items[name].needs:
            if need not in items:
                raise Error(f"{name} needs {need}, which the catalog doesn't have")
            add(need, chain + (name,))
        chosen.append(name)

    for name in wanted:
        add(name, ())
    order = list(items)
    return [items[n] for n in sorted(chosen, key=order.index)]


def status_of(item: Item, opts: Options) -> Status:
    """The item's state now, without the network."""
    from . import kinds
    return kinds.for_item(item).status(item, opts)


def all_status(items: dict[str, Item], opts: Options) -> dict[str, Status]:
    return {name: status_of(item, opts) for name, item in items.items()}


def check_of(item: Item, opts: Options, status: Status) -> Check:
    """The installed item against its upstream, with the network. An
    item whose local state is already outdated (the kit's PKGBUILD or
    catalog moved, a part is missing) is outdated whatever upstream
    says, with the local reason as the note."""
    from . import kinds
    try:
        check = kinds.for_item(item).check(item, opts, status)
    except Error as e:
        check = Check(Fresh.UNKNOWN, status.detail, note=f"can't tell: {e}")
    if status.state == State.OUTDATED and check.fresh in (Fresh.CURRENT, Fresh.UNKNOWN):
        return Check(Fresh.OUTDATED, check.installed, check.available, check.source or "this kit",
                     status.detail)
    return check


def needs(item_name: str, what: str, opts: Options | None = None) -> None:
    """For a command that needs an item installed: refuse in one line with
    the install command when it isn't."""
    items = load()
    if item_name not in items:
        raise Error(f"{what} needs the {item_name} item, which the catalog doesn't have")
    status = status_of(items[item_name], opts or Options())
    if status.state == State.MISSING:
        item = items[item_name]
        short = item.description.split(" (")[0]
        raise Error(f"{what} needs the {item_name} item ({short}): cjf install {item_name}")
