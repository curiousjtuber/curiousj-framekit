"""cjf cursor -- the mouse cursor in a Plasma desktop on the Frame,
SteamOS's stock Desktop Mode or Frametop's: its size and theme, and
Desktop Mode's software cursor.

    cjf cursor size [SIZE] [--theme NAME] [--desktop frametop|stock]
    cjf cursor theme NAME [--desktop frametop|stock]
    cjf cursor apply [--desktop frametop|stock]
    cjf cursor software [on|off|default]

size: with no SIZE it prints the desktop's size and theme. SIZE is in
pixels, 24 by default in Plasma; gamescope's own cursor is 256. --theme
also sets the theme (breeze_cursors, Breeze_Light, Adwaita, steam, ...).
apply sets nothing: it gives KWin the saved setting again, for the
autostart entry `software on` installs, since at each start KWin takes
gamescope's XCURSOR_SIZE=256 and XCURSOR_THEME=steam over kcminputrc
until told to reread it.

Run from a terminal inside a desktop, size and theme change that one
and KWin redraws its cursor at once. Elsewhere (SSH, Game Mode) they
change the desktop that runs, Frametop's first, or with --desktop the
one named, and the setting is saved: it applies when that desktop next
starts, or when `cjf cursor apply` runs from a terminal inside it. With
neither running the setting is saved for both. It goes in the desktop's
kcminputrc, where System Settings keeps it too. An app that draws its
own cursor (X11 apps, some older toolkits) keeps the size the desktop
started with.

software: the software mouse cursor of the stock Desktop Mode, on or
off for the next sessions: KWIN_FORCE_SW_CURSOR in
~/.config/environment.d, which systemd reads at login, so a change
takes a reboot. With no argument it says what is set. The default is
on: without it KWin puts the cursor on a hardware plane the headset's
view doesn't show. SteamOS 0.5.6 draws the controller's mouse-mode
cursor on its own, but not a real mouse's, Deskflow's for one (see
docs/desktop-cursor.md). on and off are a choice kept in the kit's
config file, so a later `cjf init` neither removes nor reinstalls the
file; default forgets the choice. A file there that isn't the kit's is
backed up by on and off, and left alone by default. The cursor-size
autostart entry goes with the software cursor, since with it the
desktops take gamescope's 256 px again: into ~/.config/autostart, and
~/.config/frametop/autostart when Frametop is installed. Frametop's own
session script sets the variable for its desktop.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import click

from .. import cmdline, config, where
from ..cmdline import Options, pass_options
from . import desktops

CONF_NAME = "90-kwin-software-cursor.conf"
ON_TEXT = "KWIN_FORCE_SW_CURSOR=1\n"
OFF_TEXT = "KWIN_FORCE_SW_CURSOR=0\n"
OLD_MARKER = "# steam-frame-utils: sw-cursor"
ENTRY_NAME = "curiousj-framekit-cursor.desktop"
ENTRY_TITLE = "Name=curiousj-framekit cursor size"
OLD_ENTRY_NAME = "steam-frame-utils-cursor.desktop"
OLD_ENTRY_TITLE = "Name=steam-frame-utils cursor size"
DESKTOP_CHOICE = click.Choice(["frametop", "stock"])


# --- size and theme ----------------------------------------------------

def read_key(opts: Options, d: desktops.Desktop, key: str) -> str:
    env = dict(os.environ, XDG_CONFIG_HOME=str(d.config_home))
    out = cmdline.run(opts, ["kreadconfig6", "--file", "kcminputrc", "--group", "Mouse",
                             "--key", key], capture=True, check=False, env=env).stdout
    return out.strip()


def write_key(opts: Options, d: desktops.Desktop, key: str, value: str) -> None:
    env = dict(os.environ, XDG_CONFIG_HOME=str(d.config_home))
    cmdline.run(opts, ["kwriteconfig6", "--file", "kcminputrc", "--group", "Mouse",
                       "--key", key, value], env=env)


def describe_size(opts: Options, d: desktops.Desktop) -> str:
    size = read_key(opts, d, "cursorSize") or "24"
    theme = read_key(opts, d, "cursorTheme") or "breeze_cursors"
    return f"{d.name:<9} {size} px, {theme}"


def notify_kwin(opts: Options) -> None:
    """Tell this session's KWin to reread [Mouse] from kcminputrc, as
    System Settings' Cursors page does: KGlobalSettings' CursorChanged
    (5)."""
    cmdline.run(opts, ["dbus-send", "--session", "--type=signal", "/KGlobalSettings",
                       "org.kde.KGlobalSettings.notifyChange", "int32:5", "int32:0"])


def targets(desktop: str | None, here: str | None, running: list[str]) -> list[str]:
    """Which desktops a size or theme change goes to."""
    if desktop:
        return [desktop]
    if here:
        return [here]
    if running:
        return [running[0]]
    return list(desktops.NAMES)


def theme_exists(theme: str, home: Path | None = None) -> bool:
    home = home or Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    return any((d / theme / "cursors").is_dir()
               for d in (data / "icons", home / ".icons", Path("/usr/share/icons")))


def change(opts: Options, size: int | None, theme: str | None, desktop: str | None,
           apply: bool) -> int:
    where.require_host("cursor")
    if size is not None and not 8 <= size <= 512:
        raise cmdline.Error("SIZE is a number of pixels, 8 to 512")
    if theme and not theme_exists(theme):
        raise cmdline.Error(f"no cursor theme {theme} in ~/.local/share/icons, ~/.icons "
                            "or /usr/share/icons")
    all_desktops = desktops.desktops()
    here = desktops.here()
    for name in targets(desktop, here, desktops.running_names()):
        d = all_desktops[name]
        if size is None and not theme and not apply:
            print(describe_size(opts, d))
            continue
        if name != "stock" and not d.config_home.is_dir():
            raise cmdline.Error(f"{cmdline.tilde(d.config_home)} is missing: is Frametop installed?")
        if size is not None:
            write_key(opts, d, "cursorSize", str(size))
        if theme:
            write_key(opts, d, "cursorTheme", theme)
        if name == here:
            notify_kwin(opts)
            note = "applied"
        elif apply:
            note = "not this terminal's desktop; nothing to apply to"
        elif d.running():
            note = "saved; run `cjf cursor apply` from a terminal inside it to apply now"
        else:
            note = "saved; it applies when that desktop starts"
        print(f"{describe_size(opts, d)}: {note}")
    return 0


@click.group(cls=cmdline.Group, help=__doc__,
             short_help="the mouse cursor in Desktop Mode and Frametop's desktop")
def cursor() -> None:
    pass


@cursor.command(cls=cmdline.Command, help="Show or set the cursor's size, in pixels.")
@click.argument("size", required=False, type=int)
@click.option("--theme", help="Also set the cursor theme.")
@click.option("--desktop", type=DESKTOP_CHOICE, help="Which desktop, when not inside one.")
@pass_options
def size(opts: Options, size: int | None, theme: str | None, desktop: str | None) -> int:
    return change(opts, size, theme, desktop, False)


@cursor.command(cls=cmdline.Command, help="Set the cursor theme.")
@click.argument("name")
@click.option("--desktop", type=DESKTOP_CHOICE, help="Which desktop, when not inside one.")
@pass_options
def theme(opts: Options, name: str, desktop: str | None) -> int:
    return change(opts, None, name, desktop, False)


@cursor.command(cls=cmdline.Command,
                help="Give KWin the saved size and theme again (the autostart entry runs this).")
@click.option("--desktop", type=DESKTOP_CHOICE, help="Which desktop, when not inside one.")
@pass_options
def apply(opts: Options, desktop: str | None) -> int:
    return change(opts, None, None, desktop, True)


# --- the software cursor ------------------------------------------------

def conf_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".config/environment.d" / CONF_NAME


def conf_state(text: str | None, choice: bool | None) -> tuple[str, str]:
    """(value, kind) for the environment.d file: value "on", "off" or
    "" (unknown), kind "none", "default", "chosen" or "other". An old
    steam-frame-utils marker file counts as chosen."""
    if text is None:
        return "", "none"
    if text == ON_TEXT:
        return "on", "chosen" if choice is not None else "default"
    if text == OFF_TEXT:
        return "off", "chosen" if choice is not None else "default"
    lines = text.splitlines()
    if lines and lines[0].startswith(OLD_MARKER):
        chosen = lines[0][len(OLD_MARKER):].strip()
        if chosen in ("on", "off"):
            return chosen, "chosen"
    return "", "other"


def describe_state(value: str, kind: str) -> str:
    return {"none": "none",
            "default": "on, the default",
            "chosen": f"{value}, chosen with cjf cursor software {value}",
            "other": "not the kit's: left alone"}[kind]


def entry_text(cjf: str) -> str:
    return ("[Desktop Entry]\nType=Application\n" + ENTRY_TITLE + "\n"
            "Comment=Gives KWin the saved cursor size again; each start it takes gamescope's "
            "256 px until told to reread kcminputrc\n"
            f"Exec={cjf} cursor apply\nOnlyShowIn=KDE;\nX-KDE-autostart-phase=2\n"
            "NoDisplay=true\n")


def is_our_entry(text: str) -> bool:
    return ENTRY_TITLE in text.splitlines() or OLD_ENTRY_TITLE in text.splitlines()


def autostart_dirs(home: Path | None = None) -> list[tuple[Path, bool]]:
    """(dir, present) for each desktop's config home: the stock one always,
    Frametop's when installed."""
    home = home or Path.home()
    return [(home / ".config", True),
            (home / ".config/frametop", (home / ".config/frametop").is_dir())]


def read_text(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None if not path.exists() and not path.is_symlink() else ""
        return path.read_text()
    except OSError:
        return ""


def put_conf(opts: Options, text: str, why: str) -> bool:
    """Write the environment.d file (write_file backs up a differing one)."""
    path = conf_path()
    current = read_text(path)
    if current == text:
        cmdline.say("ok", f"{cmdline.tilde(path)}: {why}")
        return False
    return cmdline.write_file(opts, path, text)


def put_entries(opts: Options) -> bool:
    """The autostart entry into each desktop's autostart dir; an old
    steam-frame-utils entry there goes."""
    changed = False
    text = entry_text(cmdline.cjf_path())
    for base, present in autostart_dirs():
        dst = base / "autostart" / ENTRY_NAME
        if not present:
            cmdline.say("skip", f"{cmdline.tilde(dst)}: no Frametop; re-run after installing it")
            continue
        old = base / "autostart" / OLD_ENTRY_NAME
        if old.exists() and is_our_entry(read_text(old) or ""):
            changed |= cmdline.remove_file(opts, old, "the old name")
        changed |= cmdline.write_file(opts, dst, text)
    return changed


def remove_entries(opts: Options) -> bool:
    changed = False
    for base, present in autostart_dirs():
        for name in (ENTRY_NAME, OLD_ENTRY_NAME):
            dst = base / "autostart" / name
            if not dst.exists() and not dst.is_symlink():
                continue
            if is_our_entry(read_text(dst) or ""):
                changed |= cmdline.remove_file(
                    opts, dst, "without the software cursor the size keeps")
            else:
                cmdline.say("skip", f"{cmdline.tilde(dst)} isn't the kit's entry; left alone")
    if not changed:
        cmdline.say("ok", "no cursor size entry: without the software cursor the size keeps")
    return changed


def show_software(opts: Options) -> int:
    path = conf_path()
    value, kind = conf_state(read_text(path), config.get("cursor", "software"))
    cmdline.say("set", f"{describe_state(value, kind)} ({cmdline.tilde(path)})")
    stock = desktops.desktops()["stock"]
    cmdline.say("Desktop Mode", "running (KWin took the file at its start)" if stock.running()
                else "not running")
    for base, _ in autostart_dirs():
        for name in (ENTRY_NAME, OLD_ENTRY_NAME):
            if (base / "autostart" / name).is_file():
                cmdline.say("size entry", cmdline.tilde(base / "autostart" / name))
    return 0


def set_software(opts: Options, verb: str) -> int:
    """on, off, default or auto; auto is what `cjf init` runs. Exit 100
    when the environment.d file changed (a reboot applies it), 101 when
    only the autostart entries did."""
    path = conf_path()
    choice = config.get("cursor", "software")
    value, kind = conf_state(read_text(path), choice)
    conf_changed = entry_changed = False
    want = None
    if verb in ("on", "off"):
        if choice != (verb == "on"):
            config.set_value(opts, "cursor", "software", verb == "on")
        conf_changed = put_conf(opts, ON_TEXT if verb == "on" else OFF_TEXT,
                                f"software cursor {verb}, chosen")
        want = verb
    elif verb == "auto" and kind == "chosen":
        cmdline.say("ok", f"{cmdline.tilde(path)}: {describe_state(value, kind)}")
        if choice is None and value:
            # an old marker file: carry the choice into the config file
            config.set_value(opts, "cursor", "software", value == "on")
        want = value
    elif kind == "other":
        cmdline.say("skip", f"{cmdline.tilde(path)} isn't the kit's cursor fix; left alone")
    else:
        if verb == "default" and choice is not None:
            config.set_value(opts, "cursor", "software", None)
        conf_changed = put_conf(opts, ON_TEXT, "the software cursor, the default")
        want = "on"

    if want == "on":
        entry_changed = put_entries(opts)
    elif want == "off":
        entry_changed = remove_entries(opts)

    if verb == "auto":
        return 100 if conf_changed else 101 if entry_changed else 0
    if not conf_changed and not entry_changed:
        print("nothing to change")
    elif opts.check:
        print("run without --check to apply")
    else:
        if conf_changed:
            print("reboot: environment.d is read at login, KWin takes the variable at its start")
        if entry_changed:
            print("the cursor size autostart entry runs at a desktop's next start")
    return 0


@cursor.command(cls=cmdline.Command,
                help="Desktop Mode's software cursor for the next sessions: on, off, or the "
                     "default (on); with no argument, what is set. auto is what cjf init runs.")
@click.argument("verb", required=False, type=click.Choice(["on", "off", "default", "auto"]))
@pass_options
def software(opts: Options, verb: str | None) -> int:
    where.require_host("cursor software")
    if verb is None:
        return show_software(opts)
    return set_software(opts, verb)
