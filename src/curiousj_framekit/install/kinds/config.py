"""The `config` kind: an item that is a file or two the kit writes, with
no download. Today only the cursor: the software cursor's environment.d
file and the size entry, which `cjf cursor software` manages."""

from __future__ import annotations

from ... import config
from ...cmdline import Options
from ...frame import cursor
from ..catalog import Item, State, Status
from .base import Base


class Kind(Base):
    options = "[on|off|default]  (the software cursor; default: keep the choice, on when none)"

    def status(self, item: Item, opts: Options) -> Status:
        value, kind = cursor.conf_state(cursor.read_text(cursor.conf_path()),
                                        config.get("cursor", "software"))
        if kind == "none":
            return Status(State.MISSING)
        if kind == "other":
            return Status(State.UNKNOWN, "a file that isn't the kit's")
        return Status(State.OK, f"software cursor {value}")

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        verb = "auto"
        if args:
            if len(args) > 1 or args[0] not in ("on", "off", "default"):
                from ...cmdline import Error
                raise Error("cursor takes on, off or default")
            verb = args[0]
        rc = cursor.set_software(opts, verb)
        return rc in (100, 101) if verb == "auto" else True

    def uninstall(self, item: Item, opts: Options) -> bool:
        return cursor.set_software(opts, "off") == 0
