"""cjf migrate -- move a Frame that steam-frame-utils' setup.sh set up
over to this kit. Run once; a second run finds nothing to do. Every
change is shown and asked about, and files are backed up first.

    cjf migrate

What it does, in order:

  rc files        removes every `# >>> steam-frame-utils: … >>>` block
                  from ~/.bashrc, ~/.zshrc, ~/.profile and
                  ~/.distroboxrc (the blocks that sourced shell-init/
                  from the checkout and put its bin/ on PATH)
  cjf init        then puts the kit's base in place: the init.sh line,
                  the shims, ~/.distroboxrc, the cursor fix. The old
                  autostart entries go with it, and a software-cursor
                  choice recorded as a marker line is carried into the
                  config file.
  Beat Saber      launch options that name the checkout's
                  bin/beat-saber-recent are set to ~/.local/bin's,
                  through the running Steam client
  history         ~/.local/state/steam-frame-utils/beat-saber-songs.tsv
                  is merged into ~/.local/state/curiousj-framekit/ and
                  the old directory removed when empty
  KRdp Server     the menu entry's Exec, if it names bin/krdpd-gui,
                  becomes `cjf rdp gui`
  ~/.local/bin    a copy of an old bin/ script left there by an earlier
                  setup.sh (second line `# steam-frame-utils:`) is backed
                  up out of the way

pacman-home's files under ~/.local/etc and ~/.local/var are pacman's
layout and stay. The checkout itself is not moved: do that last, with
`uv tool install --force --editable` from the new place.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import click

from .. import blocks, cmdline, where
from ..cmdline import Options, pass_options
from ..frame import steam
from ..beatsaber import recent
from . import init as init_mod

OLD_SCRIPTS = ("frame-versions", "wifi-known", "cursor-size", "sw-cursor", "steam-controller",
               "vr-controllers", "krdpd", "krdpd-gui", "beat-saber-recent", "bsmanager", "podman",
               "pacman-home", "makepkg-home")
MENU_ENTRY = ".local/share/applications/io.github.curiousjtuber.Krdpd.desktop"


def remove_old_blocks(opts: Options, rc: Path) -> bool:
    if not rc.exists():
        return False
    text = rc.read_text()
    found = blocks.names(text, blocks.OLD_PREFIX)
    if not found:
        return False
    new = text
    for part in found:
        new = blocks.remove(new, part, blocks.OLD_PREFIX)
    cmdline.say("found", f"{cmdline.tilde(rc)}: steam-frame-utils block{'s' if len(found) > 1 else ''} "
                + ", ".join(found))
    return cmdline.write_file(opts, rc, new)


def new_hook(was: str, new_path: str) -> str | None:
    """The launch options with the checkout's beat-saber-recent replaced
    by new_path, or None when they don't name it."""
    marker = "steam-frame-utils/bin/beat-saber-recent"
    if marker not in was:
        return None
    out = []
    for word in was.split():
        out.append(new_path if word.endswith(marker) else word)
    return " ".join(out)


def migrate_launch_options(opts: Options) -> bool:
    try:
        was = steam.launch_options(recent.APPID)["was"]
    except cmdline.Error as e:
        cmdline.say("skip", f"Beat Saber launch options: {e}")
        return False
    new = new_hook(was, str(Path.home() / ".local/bin/beat-saber-recent"))
    if new is None:
        cmdline.say("ok", "Beat Saber launch options" + (": not the old hook" if was else ": none set"))
        return False
    cmdline.say("would set" if opts.check else "set", f"Beat Saber launch options: {new}")
    if opts.check:
        return True
    if not cmdline.confirm(opts, "set them through the Steam client?"):
        return False
    result = steam.launch_options(recent.APPID, new, force=True)
    if result.get("now") != new:
        raise cmdline.Error(f"the client did not take the launch options (it has '{result.get('now')}')")
    return True


def migrate_history(opts: Options) -> bool:
    old = recent.OLD_HIST
    if not old.exists():
        return False
    new = recent.history_path()
    lines = sorted(set(recent.read_history(new, old)))
    cmdline.say("would move" if opts.check else "move",
                f"{cmdline.tilde(old)} -> {cmdline.tilde(new)}")
    if opts.check:
        return True
    if not cmdline.confirm(opts, "move it?"):
        return False
    new.parent.mkdir(parents=True, exist_ok=True)
    new.write_text("".join(ln + "\n" for ln in lines))
    old.unlink()
    try:
        old.parent.rmdir()
    except OSError:
        pass
    return True


def migrate_menu_entry(opts: Options) -> bool:
    entry = Path.home() / MENU_ENTRY
    if not entry.is_file():
        return False
    text = entry.read_text()
    lines = text.splitlines()
    changed = False
    for i, line in enumerate(lines):
        if line.startswith("Exec=") and line.endswith("/bin/krdpd-gui"):
            lines[i] = f"Exec={cmdline.cjf_path()} rdp gui"
            changed = True
    if not changed:
        cmdline.say("ok", f"{cmdline.tilde(entry)}: runs cjf rdp gui")
        return False
    return cmdline.write_file(opts, entry, "\n".join(lines) + "\n")


def backup_old_copies(opts: Options) -> bool:
    changed = False
    bindir = Path.home() / ".local/bin"
    for name in OLD_SCRIPTS:
        old = bindir / name
        if not old.is_file() or old.is_symlink():
            continue
        try:
            second = old.read_text(errors="replace").splitlines()[1]
        except (OSError, IndexError):
            continue
        if not second.startswith("# steam-frame-utils:"):
            continue
        dest = old.with_name(f"{name}.bak-{cmdline.stamp()}")
        cmdline.say("would back up" if opts.check else "back up",
                    f"{cmdline.tilde(old)} -> {cmdline.tilde(dest)}, an old copy of bin/{name}")
        if opts.check:
            changed = True
        elif cmdline.confirm(opts, f"back up {cmdline.tilde(old)}?"):
            shutil.move(old, dest)
            changed = True
    return changed


@click.command(cls=cmdline.Command, help=__doc__,
               short_help="move a Frame set up by steam-frame-utils to this kit")
@pass_options
def migrate(opts: Options) -> int:
    where.require_frame("migrate")
    home = Path.home()
    changed = False
    for rc in (home / ".bashrc", home / ".zshrc", home / ".profile", home / ".distroboxrc"):
        changed |= remove_old_blocks(opts, rc)
    init_changed = init_mod.run_init(opts)
    changed |= any(init_changed.values())
    changed |= migrate_launch_options(opts)
    changed |= migrate_history(opts)
    changed |= migrate_menu_entry(opts)
    changed |= backup_old_copies(opts)
    if not changed:
        print("nothing to do: this Frame is on the kit")
    elif opts.check:
        print("run without --check to apply")
    else:
        if init_changed["conf"]:
            print("reboot: environment.d is read at login, KWin takes the variable at its start")
        print("done: open a new shell; a second run finds nothing to do")
    return 0
