"""Where a command is running, asked once and answered the same way
everywhere: on the Frame or on a PC, inside a distrobox or on the host,
in which desktop, and with which Wayland display.

The Frame is detected positively, from /etc/os-release: SteamOS with
VARIANT_ID "vr" (the Deck's is "steamdeck"). Everything else is a PC.
CJF_ASSUME_FRAME=1 says "treat this machine as the Frame" for a build
that runs somewhere else, such as the krdp flatpak on a CI runner.

The desktops both run inside Game Mode's gamescope with a runtime dir
of their own under /run/user/UID: nested_plasma for SteamOS's stock
Desktop Mode, frametop for Frametop's desktop. A plain /run/user/UID is
Game Mode or an SSH session. Game Mode is an X11 session whose Wayland
socket is named only in GAMESCOPE_WAYLAND_DISPLAY."""

from __future__ import annotations

import os
from pathlib import Path

from .cmdline import Error

OS_RELEASE = Path("/etc/os-release")
CONTAINER_MARK = Path("/run/.containerenv")

DESKTOPS = {"nested_plasma": "stock", "frametop": "frametop"}


def os_release(path: Path = OS_RELEASE) -> dict[str, str]:
    """The KEY=value pairs of an os-release file, quotes removed; {} when
    there is none."""
    info: dict[str, str] = {}
    try:
        text = path.read_text()
    except OSError:
        return info
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        info[key.strip()] = value
    return info


def is_frame(info: dict[str, str] | None = None,
             env: os._Environ | dict = os.environ) -> bool:
    if env.get("CJF_ASSUME_FRAME") == "1":
        return True
    info = os_release() if info is None else info
    return info.get("ID") == "steamos" and info.get("VARIANT_ID") == "vr"


def in_container(env: os._Environ | dict = os.environ,
                 mark: Path = CONTAINER_MARK) -> bool:
    """Inside a distrobox (or any container distrobox-like enough to set
    CONTAINER_ID or leave /run/.containerenv)."""
    return bool(env.get("CONTAINER_ID")) or mark.exists()


def desktop(env: os._Environ | dict = os.environ) -> str | None:
    """"stock", "frametop", or None (Game Mode, SSH, a PC), from the
    runtime dir the session was given."""
    runtime = env.get("XDG_RUNTIME_DIR", "")
    return DESKTOPS.get(os.path.basename(runtime.rstrip("/")))


def wayland_display(env: os._Environ | dict = os.environ) -> str | None:
    """The Wayland socket name a client should use: WAYLAND_DISPLAY, or in
    Game Mode gamescope's own; None when there is none."""
    return env.get("WAYLAND_DISPLAY") or env.get("GAMESCOPE_WAYLAND_DISPLAY") or None


def describe(info: dict[str, str] | None = None,
             env: os._Environ | dict = os.environ) -> str:
    """One phrase for messages: "the Frame's host, in Desktop Mode",
    "a container", "a PC (CachyOS Linux)". A distrobox sees its own
    /etc/os-release, so from inside one the Frame can't be told apart
    from any other host; the refusals say what to do instead."""
    info = os_release() if info is None else info
    if in_container(env):
        return "a container"
    if is_frame(info, env):
        where = {"stock": "in Desktop Mode", "frametop": "in Frametop's desktop"}
        d = desktop(env)
        return "the Frame's host" + (f", {where[d]}" if d else "")
    name = info.get("PRETTY_NAME") or info.get("NAME") or "unknown OS"
    return f"a PC ({name})"


def require_frame(what: str = "this command") -> None:
    """Raise Error unless this is the Frame's host. (A box can't be told
    to be on the Frame, see describe; so this is require_host under
    another name, kept for the reading: "needs the Frame" versus "needs
    the host".)"""
    require_host(what)


def require_host(what: str = "this command") -> None:
    """Raise Error unless this is the Frame's host: not a PC, not a box.
    From a distrobox the message names the way through to the host, as
    the scripts used to take it themselves."""
    if in_container():
        raise Error(f"{what} runs on the Frame's host, not in a container; "
                    f"from a distrobox: distrobox-host-exec cjf {what}")
    if not is_frame():
        raise Error(f"{what} runs on the Frame; this is {describe()}")


def require_pc(what: str = "this command") -> None:
    if is_frame():
        raise Error(f"{what} runs on a PC, not on the Frame")
