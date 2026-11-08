"""cjf panel -- run an app in a SteamVR panel of its own, at any size.

Game Mode draws every app on one 1920x1080 overlay, whatever size the
app's screen is set to. A panel is a second gamescope on SteamVR's
overlay interface with one app inside and a screen of the size you
give: a remote desktop of two 1920x1080 monitors at 3840x1080, pixel
for pixel. It is the kit's build of gamescope (`cjf install
gamescope-panel`), whose one patch lets the VR backend start above
1080p; the host's aborts there.

    cjf panel start [--size WxH] [--width METRES] [--name NAME] [--fullscreen] [--wayland] [--env VAR=VALUE]... [--] COMMAND [ARGS...]
    cjf panel desktop [--size WxH] [--width METRES] [--name NAME]
    cjf panel stop [NAME]
    cjf panel status
    cjf panel log [NAME] [--lines N]

--size        the panel's screen, in pixels: default 1920x1080, or
              [panel] size in the kit's config file.
--width       how wide the panel is, in metres: default 1.5 m tall, so
              2.67 m for 16:9 (the session's own) and 5.33 m for
              3840x1080. SteamVR's dashboard places it; its bar moves it.
--name        the panel's name, for stop, log and the overlay: default
              the command's name.
--fullscreen  every window the size of the panel (gamescope's
              --force-windows-fullscreen), for an app that opens no
              dialogs, such as KRDC with its --fullscreen.
--wayland     offer Wayland (xdg-shell) to the app and leave Qt's
              platform alone. Default: X11 through gamescope's
              Xwayland, with QT_QPA_PLATFORM=xcb for Qt apps, the path
              gamescope is built around.
--env         more for the app's environment, repeatable.
              XCURSOR_SIZE=32 unless given: the session's 256 px
              cursor would cover a good part of the panel.

A panel is a transient user service, cjf-panel-NAME, started with
systemd-run from the user manager's environment, which has SteamVR's
paths, so it outlives the terminal; it ends when the app exits, `stop`
ends it sooner (three seconds: gamescope ignores SIGTERM and is killed),
`status` lists the panels, `log` is its journal. The command is
resolved on this shell's PATH, since the service's is the system's. A
panel needs SteamVR up, which Game Mode is. Every window in a panel
gets the one size, so a second app wants a second panel.

KRDC at the size of a PC's two monitors:
    cjf panel start --size 3840x1080 --fullscreen -- krdc --fullscreen rdp://HOST
with Resolution set to "Match screen" in KRDC's settings for that host.

`desktop` runs SteamOS's own Desktop Mode in a panel, with a screen of
--size instead of the 1280x800 Steam's Desktop entry gives it: the
same /usr/bin/steamos-nested-desktop, copied with KWin's size changed.
It is the same desktop, with the same settings and runtime directory,
so it can't run while Steam's is up, and Steam's can't while it is.
Close it from Plasma's menu, or `cjf panel stop desktop`. For larger
text, set the scale in Plasma's display settings: KWin's own --scale
is overridden by the saved screen configuration.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import click

from .. import cmdline, config
from . import desktops
from ..cmdline import Error, Options, pass_options

DEFAULT_SIZE = "1920x1080"
HEIGHT_METRES = 1.5
# The cursor image the host has (the session's own holo-cursor.png
# isn't in the image), the hotspot Frametop uses with it.
CURSOR = "/usr/share/steamos/steamos-cursor.png"
CURSOR_HOTSPOT = "5,3"
UNIT_PREFIX = "cjf-panel-"
# SteamOS's Desktop Mode: Plasma under a nested KWin in a runtime dir
# of its own, which Steam's Desktop entry runs. The script writes a
# kwin_wayland_wrapper of its own with KWin's windowed size on one
# line, which is where a panel's size goes.
DESKTOP_SCRIPT = Path("/usr/bin/steamos-nested-desktop")
DESKTOP_NAME = "desktop"
_KWIN_SIZE = re.compile(r"(kwin_wayland_wrapper .*?)--width \d+ --height \d+")


def gamescope_binary() -> Path:
    """The gamescope the pacman-home package builds for ~/.local
    (data/pkgbuilds/gamescope-panel)."""
    return Path.home() / ".local/lib/gamescope-panel/bin/gamescope"


def parse_size(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", text)
    if not m or int(m.group(1)) == 0 or int(m.group(2)) == 0:
        raise Error(f"--size wants WIDTHxHEIGHT in pixels, like 3840x1080; got {text!r}")
    return int(m.group(1)), int(m.group(2))


def default_size() -> str:
    return str(config.get("panel", "size", DEFAULT_SIZE))


def default_width(width: int, height: int) -> float:
    """A panel 1.5 m tall, whatever its shape: 2.67 m for 16:9, the
    width the session gives its own overlay."""
    return round(HEIGHT_METRES * width / height, 2)


def unit_name(name: str) -> str:
    """The transient unit's name. systemd allows letters, digits and
    :-_.\\ in a unit name; anything else here becomes a dash. The
    same for a name that is already one, so stop and log can take a
    name from status."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-.") or "panel"
    return UNIT_PREFIX + safe


def panel_name(unit: str) -> str:
    return unit.removeprefix(UNIT_PREFIX).removesuffix(".service")


def gamescope_argv(binary: Path, size: tuple[int, int], width_m: float, name: str,
                   fullscreen: bool, wayland: bool, command: list[str]) -> list[str]:
    """gamescope on the OpenVR backend as its own overlay: output and
    nested size the same, so the app's screen is the panel's pixels
    one to one, and the control bar with its keyboard and close buttons."""
    w, h = size
    argv = [str(binary), "--backend", "openvr",
            "-W", str(w), "-H", str(h), "-w", str(w), "-h", str(h),
            "--vr-overlay-key", f"cjf.panel.{name}",
            "--vr-overlay-default-name", name,
            "--vr-overlay-physical-width", f"{width_m:g}",
            "--vr-overlay-show-immediately",
            "--vr-overlay-enable-click-stabilization",
            "--vr-overlay-enable-control-bar",
            "--vr-overlay-enable-control-bar-keyboard",
            "--vr-overlay-enable-control-bar-close",
            "--cursor", CURSOR, "--cursor-hotspot", CURSOR_HOTSPOT]
    if fullscreen:
        argv.append("--force-windows-fullscreen")
    if wayland:
        argv.append("--expose-wayland")
    return argv + ["--", *command]


def environment(wayland: bool, extra: list[str]) -> dict[str, str]:
    env = {} if wayland else {"QT_QPA_PLATFORM": "xcb"}
    env["XCURSOR_SIZE"] = "32"
    for item in extra:
        if "=" not in item:
            raise Error(f"--env wants VAR=VALUE; got {item!r}")
        key, value = item.split("=", 1)
        env[key] = value
    return env


def desktop_script(text: str, size: tuple[int, int]) -> str:
    """SteamOS's Desktop Mode script with KWin's windowed size, which it
    hard-wires on the kwin_wayland_wrapper line it writes, replaced by
    the panel's. (KWin's --scale on that line does nothing: KScreen
    applies the saved configuration, scale 1, over it.)"""
    w, h = size
    flags = f"--width {w} --height {h}"
    out, n = _KWIN_SIZE.subn(lambda m: m.group(1) + flags, text)
    if n != 1:
        raise Error(f"{DESKTOP_SCRIPT} isn't the script the kit knows: one kwin_wayland_wrapper "
                    f"line with --width and --height expected, {n} found")
    return out


def desktop_script_path(size: tuple[int, int]) -> Path:
    """Where the copy goes, named by its size: the shell reads a script
    as it runs it, so a copy for another size is another file."""
    return config.cache_dir() / "panel" / f"desktop-{size[0]}x{size[1]}.sh"


def desktop_environment() -> dict[str, str]:
    """QT_QPA_PLATFORM=wayland, not start's xcb: the script passes the
    environment on to Plasma, and a plasmashell on xcb under the nested
    KWin draws the desktop but makes no panel windows at all."""
    return environment(True, ["QT_QPA_PLATFORM=wayland"])


def wrapped(unit: str, command: list[str]) -> list[str]:
    """The app, then the unit's end. gamescope's OpenVR backend keeps
    running after its child exits and ignores SIGTERM and SIGINT (the
    host's binary does the same), so the shell that ran the app stops
    the unit, whose stop timeout then kills gamescope. The app is $@,
    the unit $0."""
    return ["/bin/sh", "-c", '"$@"; systemctl --user stop --no-block "$0"', unit + ".service", *command]


def run_argv(unit: str, env: dict[str, str], argv: list[str]) -> list[str]:
    """systemd-run for the panel: a transient service in the user
    manager, collected when it ends however it ends, quiet about it.
    A stop sends SIGTERM, which ends the app, and SIGKILL three seconds
    later, which is what ends gamescope."""
    return ["systemd-run", "--user", "--collect", "--quiet", "--unit", unit,
            "--description", f"cjf panel {panel_name(unit)}",
            "--property", "TimeoutStopSec=3",
            *(f"--setenv={k}={v}" for k, v in env.items()), "--", *argv]


def parse_units(text: str) -> list[tuple[str, str]]:
    """(panel name, sub-state) per line of `systemctl --user list-units
    --plain --no-legend --all 'cjf-panel-*'`: UNIT LOAD ACTIVE SUB ..."""
    found = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0].startswith(UNIT_PREFIX) and parts[0].endswith(".service"):
            found.append((panel_name(parts[0]), parts[3]))
    return found


def panels(opts: Options) -> list[tuple[str, str]]:
    text = cmdline.output(opts, ["systemctl", "--user", "list-units", "--plain", "--no-legend",
                                 "--all", f"{UNIT_PREFIX}*"], default="")
    return parse_units(text or "")


def pick_name(opts: Options, name: str | None, verb: str) -> str:
    if name:
        return name
    names = [n for n, _ in panels(opts)]
    if not names:
        raise Error("no panel runs")
    if len(names) > 1:
        raise Error(f"which panel? cjf panel {verb} NAME, one of: {', '.join(names)}")
    return names[0]


# --- the commands ---------------------------------------------------------

@click.group(cls=cmdline.Group, help=__doc__,
             short_help="run an app in a SteamVR panel of its own, at any size")
def panel() -> None:
    pass


def require_gamescope() -> Path:
    binary = gamescope_binary()
    if not binary.is_file():
        raise Error(f"no gamescope for panels at {cmdline.tilde(binary)}: cjf install gamescope-panel (about ten minutes)")
    if not shutil.which("systemd-run"):
        raise Error("missing required command: systemd-run")
    return binary


def launch(opts: Options, binary: Path, name: str, size: tuple[int, int], width_m: float | None,
           fullscreen: bool, wayland: bool, env: dict[str, str], command: list[str], shown: str) -> int:
    """The panel: gamescope's arguments, the unit, the check that no
    panel of the name runs, and systemd-run. `command` is what runs,
    `shown` how the message names it."""
    w, h = size
    width_m = width_m or default_width(w, h)
    unit = unit_name(name)
    if any(n == panel_name(unit) and state == "running" for n, state in panels(opts)):
        raise Error(f"panel {panel_name(unit)} runs already: cjf panel stop {panel_name(unit)}")
    argv = gamescope_argv(binary, size, width_m, name, fullscreen, wayland, wrapped(unit, command))
    cmdline.say("would start" if opts.check else "start",
                f"panel {name}: {w}x{h}, {width_m:g} m wide, {shown} (unit {unit})")
    if opts.check:
        return 0
    cmdline.run(opts, run_argv(unit, env, argv))
    print(f"log: cjf panel log {panel_name(unit)}   stop: cjf panel stop {panel_name(unit)}")
    return 0


@panel.command(cls=cmdline.Command, help="Start COMMAND in a panel of its own.",
               context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False})
@click.option("--size", default=None, help="WIDTHxHEIGHT in pixels; default 1920x1080, or [panel] size in the config.")
@click.option("--width", "width_m", type=float, default=None, help="The panel's width in metres; default 1.5 m tall.")
@click.option("--name", default=None, help="The panel's name; default the command's.")
@click.option("--fullscreen", is_flag=True, help="Every window the size of the panel.")
@click.option("--wayland", is_flag=True, help="Offer Wayland to the app; default X11, QT_QPA_PLATFORM=xcb.")
@click.option("--env", "env_items", multiple=True, metavar="VAR=VALUE", help="More for the app's environment.")
@click.argument("command", nargs=-1, type=click.UNPROCESSED, required=True)
@pass_options
def start(opts: Options, size: str | None, width_m: float | None, name: str | None,
          fullscreen: bool, wayland: bool, env_items: tuple[str, ...], command: tuple[str, ...]) -> int:
    binary = require_gamescope()
    exe = shutil.which(command[0])
    if not exe:
        raise Error(f"no {command[0]} on PATH")
    return launch(opts, binary, name or Path(command[0]).name, parse_size(size or default_size()), width_m,
                  fullscreen, wayland, environment(wayland, list(env_items)), [exe, *command[1:]], " ".join(command))


@panel.command(cls=cmdline.Command, help="SteamOS's Desktop Mode in a panel, with a screen of --size.")
@click.option("--size", default=None, help="WIDTHxHEIGHT in pixels; default 1920x1080, or [panel] size in the config.")
@click.option("--width", "width_m", type=float, default=None, help="The panel's width in metres; default 1.5 m tall.")
@click.option("--name", default=DESKTOP_NAME, show_default=True, help="The panel's name.")
@pass_options
def desktop(opts: Options, size: str | None, width_m: float | None, name: str) -> int:
    binary = require_gamescope()
    if not DESKTOP_SCRIPT.is_file():
        raise Error(f"no {DESKTOP_SCRIPT}: this isn't a Steam Frame's SteamOS")
    stock = desktops.desktops()["stock"]
    if stock.running():
        raise Error(f"{stock.label} runs already ({cmdline.tilde(stock.socket)}): close it first; "
                    "a panel's is the same desktop, and its script empties that directory")
    wh = parse_size(size or default_size())
    script = desktop_script(DESKTOP_SCRIPT.read_text(), wh)
    path = desktop_script_path(wh)
    cmdline.say("would write" if opts.check else "write",
                f"{cmdline.tilde(path)}: {DESKTOP_SCRIPT} with KWin at {wh[0]}x{wh[1]}")
    if not opts.check:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(script)
        path.chmod(0o755)
    return launch(opts, binary, name, wh, width_m, True, False, desktop_environment(), [str(path)],
                  f"{DESKTOP_SCRIPT.name} at {wh[0]}x{wh[1]}")


@panel.command(cls=cmdline.Command, help="Stop a panel: the one running, or NAME.")
@click.argument("name", required=False)
@pass_options
def stop(opts: Options, name: str | None) -> int:
    unit = unit_name(pick_name(opts, name, "stop"))
    cmdline.say("would stop" if opts.check else "stop", f"panel {panel_name(unit)} ({unit})")
    if opts.check:
        return 0
    cmdline.run(opts, ["systemctl", "--user", "stop", unit + ".service"])
    return 0


@panel.command(cls=cmdline.Command, help="Whether the gamescope is installed, and the panels.")
@pass_options
def status(opts: Options) -> int:
    binary = gamescope_binary()
    print("gamescope-panel: " + (f"installed, {cmdline.tilde(binary)}" if binary.is_file()
                                 else "not installed (cjf install gamescope-panel)"))
    found = panels(opts)
    if not found:
        print("panels: none")
        return 0
    for n, state in found:
        print(f"panel {n}: {state}")
    return 0


@panel.command(cls=cmdline.Command, help="A panel's journal: the one running, or NAME's.")
@click.argument("name", required=False)
@click.option("--lines", type=int, default=30, help="How many lines; default 30.")
@pass_options
def log(opts: Options, name: str | None, lines: int) -> int:
    unit = unit_name(pick_name(opts, name, "log"))
    argv = ["journalctl", "--user", "-u", unit + ".service", "-n", str(lines), "--no-pager", "-o", "cat"]
    cmdline.log(opts, "+ " + " ".join(argv))
    return subprocess.run(argv).returncode
