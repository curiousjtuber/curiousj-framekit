"""The two Plasma desktops a Frame can run, both nested inside Game
Mode's gamescope with a runtime dir of their own under /run/user/UID:
SteamOS's stock Desktop Mode (nested_plasma, config in ~/.config) and
Frametop's desktop (frametop, config in ~/.config/frametop).

A desktop is "running" when its Wayland socket exists in its runtime
dir, the test krdpd used. A terminal is "inside" a desktop when it is a
KDE session whose XDG_RUNTIME_DIR is that desktop's; only from there
can a running desktop's KWin be told anything, since the nested
session's bus is private to it."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def run_dir() -> Path:
    return Path(f"/run/user/{os.getuid()}")


@dataclass(frozen=True)
class Desktop:
    name: str            # "frametop" or "stock"
    label: str           # for messages
    config_home: Path    # where its kcminputrc and autostart/ live
    runtime: Path        # its XDG_RUNTIME_DIR

    @property
    def socket(self) -> Path:
        return self.runtime / "wayland-0"

    def running(self) -> bool:
        try:
            return self.socket.is_socket()
        except OSError:
            return False


NAMES = ("frametop", "stock")


def desktops(home: Path | None = None, run: Path | None = None) -> dict[str, Desktop]:
    home = home or Path.home()
    run = run or run_dir()
    return {
        "frametop": Desktop("frametop", "Frametop's desktop", home / ".config/frametop",
                            run / "frametop"),
        "stock": Desktop("stock", "SteamOS's Desktop", home / ".config", run / "nested_plasma"),
    }


def here(env: os._Environ | dict = os.environ, home: Path | None = None,
         run: Path | None = None) -> str | None:
    """The desktop this terminal is inside, by its runtime dir, when it is
    a KDE session at all; else None."""
    if env.get("KDE_FULL_SESSION") != "true":
        return None
    runtime = env.get("XDG_RUNTIME_DIR", "").rstrip("/")
    for d in desktops(home, run).values():
        if runtime == str(d.runtime):
            return d.name
    return None


def running_names(home: Path | None = None, run: Path | None = None) -> list[str]:
    """The desktops that run now, Frametop's first."""
    return [n for n, d in desktops(home, run).items() if d.running()]
