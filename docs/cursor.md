## Mouse cursor in Desktop Mode

In Desktop Mode the mouse moves but its cursor isn't drawn. KWin puts
the cursor on a hardware plane, which the headset's view doesn't show.
`KWIN_FORCE_SW_CURSOR=1` makes KWin draw it into the frame itself.
SteamOS 0.5.6 draws the controller's mouse-mode cursor on its own, but
not a real mouse's, Deskflow's for one, so the fix stays the default.
The fix comes from Cas and Chary XR's [Steam Frame: 10 Things To Do
FIRST](https://www.youtube.com/watch?v=jtW2mQd5qYI), credited there to
ThrillSeeker.

systemd reads `~/.config/environment.d` at login, and KWin reads the
variable once, at its start, so a change takes a reboot; nothing
switches it in a running desktop. `env | grep KWIN` in a Desktop Mode
Konsole confirms it.

`cjf cursor software` manages the file,
`~/.config/environment.d/90-kwin-software-cursor.conf`:

```bash
cjf cursor software            # what is set, SteamOS's default, and what the running desktop got
cjf cursor software on         # the software cursor for the next sessions
cjf cursor software off        # without it
cjf cursor software default    # the default again, on
```

`setup.sh` runs `cjf cursor software auto`: the default where nothing was chosen.
Interactive, with nothing in place, it offers the software cursor
instead. `on` and `off` are a choice it keeps, written into the file
with a marker line (`KWIN_FORCE_SW_CURSOR=0` for `off`, so a later run
neither reinstalls nor removes it); `default` forgets the choice. A file
there that isn't steam-frame-utils' is left alone by `auto` and
`default`, and backed up by `on` and `off`. Frametop's session script
sets the variable for its own KWin, so `cjf cursor software` doesn't change the
Frametop desktop's cursor.
[docs/desktop-cursor.md](desktop-cursor.md) has what was found on
0.5.6.

### Cursor size

Both desktops start inside Game Mode's gamescope, and inherit its
`XCURSOR_SIZE=256` and `XCURSOR_THEME=steam` (gamescope exports them,
and `/usr/lib/steamos/gamescope-onready` imports them into the systemd
user environment). KWin takes those two over the size and theme Plasma
keeps in `kcminputrc` (`[Mouse] cursorSize` and `cursorTheme`, 24 and
`breeze_cursors` by default), so the cursor comes up huge and System
Settings' choice is lost at the next start.

`cjf cursor size` sets it for the running desktop:

```bash
cjf cursor size 32
```

It writes `kcminputrc` and tells KWin to reload it, the way System
Settings' Cursors page does, so the cursor changes at once. With no size
it prints the current one; `--theme NAME` sets the theme as well. From a
terminal inside a desktop it changes that desktop. From SSH or Game Mode
it changes the one that runs (Frametop's first), or the one `--desktop
frametop|stock` names; with neither running it saves the setting for
both. Apps that draw their own cursor, X11 ones and some older toolkits,
size it from the `XCURSOR_SIZE` the desktop started with.

At each start KWin takes gamescope's variables again, so `cjf cursor software`
(and `setup.sh` through it) installs
`curiousj-framekit-cursor.desktop` in each desktop's autostart dir; it runs `cjf cursor apply`, which gives KWin the saved setting
without changing it. The cursor is 256 px for the second or two until
Plasma reaches autostart. SteamOS 0.5.6 keeps the size itself, but only
without the software cursor; with it the desktops take gamescope's 256
px again, so the entry goes wherever the `environment.d` file does, and
is removed with `cjf cursor software off`.

The obvious place, a script in `plasma-workspace/env/` exporting the
variables before KWin starts, doesn't work on the Frame, and that's
worth knowing for anything else one might put there. Plasma sources
every env script, the system ones in `/etc/xdg` first, in one shell that
then prints the environment back. SteamOS's
`/etc/xdg/plasma-workspace/env/set-return-icon.sh` does `set -eu` and
reads `/sys/class/dmi/id/board_name`, a DMI node the arm64 Frame doesn't
have, so the shell dies there and startplasma gets nothing back: no env
script takes effect, SteamOS's own language and ibus ones included. The
systemd user environment is no way in either: the desktops run on a
private D-Bus (`dbus-run-session`), where startplasma's import of it
fails.
