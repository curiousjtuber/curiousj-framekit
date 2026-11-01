"""The kit's own files: ~/.config/curiousj-framekit/config.toml for the
choices that used to live in marker lines (the software cursor, the
cursor size, the RDP port, the Flatpak scope), and
~/.local/state/curiousj-framekit/ for what commands record.

The config file is small and flat, one table per concern, so it is
written here without a TOML library; tomllib reads it back. A write
goes through cmdline.write_file, so it is shown as a diff and asked
about like any other file."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from . import cmdline
from .cmdline import Options

NAME = "curiousj-framekit"


def _xdg(var: str, default: Path) -> Path:
    base = os.environ.get(var)
    # A terminal inside Frametop's desktop has XDG_CONFIG_HOME and
    # XDG_STATE_HOME pointed at the desktop's own dirs; the kit's files
    # are the user's, so those are not honoured.
    if base and not base.rstrip("/").endswith("/frametop"):
        return Path(base) / NAME
    return default / NAME


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", Path.home() / ".config")


def state_dir() -> Path:
    return _xdg("XDG_STATE_HOME", Path.home() / ".local/state")


def config_path() -> Path:
    return config_dir() / "config.toml"


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or config_path()
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as e:
        raise cmdline.Error(f"{cmdline.tilde(path)} is not valid TOML: {e}") from None


def get(section: str, key: str, default: Any = None, path: Path | None = None) -> Any:
    return load(path).get(section, {}).get(key, default)


def _literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list):
        return "[" + ", ".join(_literal(v) for v in value) + "]"
    raise TypeError(f"can't write {type(value).__name__} to the config file")


def dumps(data: dict[str, Any], header: str | None = None) -> str:
    """The config as text: a header, then one [table] per section with
    its keys, each value a TOML literal, in the order given."""
    header = header or "the kit's choices. Its commands edit this; edits by hand are kept."
    out = [f"# {NAME}: {header}\n"]
    for section, values in data.items():
        if not isinstance(values, dict):
            raise TypeError(f"top-level values go in a section, not {section!r}")
        if not values:
            continue
        out.append(f"\n[{section}]\n")
        for key, value in values.items():
            out.append(f"{key} = {_literal(value)}\n")
    return "".join(out)


def save(opts: Options, data: dict[str, Any], path: Path | None = None, **kw) -> bool:
    """Write the whole config; True when the file changed."""
    return cmdline.write_file(opts, path or config_path(), dumps(data), **kw)


def set_value(opts: Options, section: str, key: str, value: Any,
              path: Path | None = None, **kw) -> bool:
    """Set one key, or remove it with value None; True when the file
    changed."""
    path = path or config_path()
    data = load(path)
    table = data.setdefault(section, {})
    if value is None:
        table.pop(key, None)
        if not table:
            data.pop(section, None)
    else:
        table[key] = value
    return save(opts, data, path, **kw)
