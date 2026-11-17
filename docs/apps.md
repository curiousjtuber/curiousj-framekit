# Apps

What each app is for on the Frame, what it needs set up, and the kit's
commands that go with it. How each is installed is elsewhere: the ones
the kit builds are catalog items (`cjf install NAME`,
[packages.md](packages.md)), the rest are in
[simple-installs.md](simple-installs.md) with their upstream's
instructions. [TRUST.md](TRUST.md) says who is trusted for what.

| App | For | Install |
|---|---|---|
| [Frametop](#frametop) | a multi-screen Plasma desktop and 3D mouse, running on the Frame itself | [its own installer](simple-installs.md#frametop) |
| [KRDC](#krdc) | a PC's desktop in the headset, over RDP or VNC | `cjf install krdc` |
| [Moonlight](#moonlight) | games streamed from a Sunshine or GeForce Experience host | [Flatpak](simple-installs.md#flatpak-apps) |
| [Deskflow](#deskflow) | the PC's mouse and keyboard on the Frame's desktop, no streaming | [Flatpak](simple-installs.md#flatpak-apps) |
| [Stream Frame](#stream-frame) | watching, recording and screenshotting the headset from another device | [Flatpak](simple-installs.md#flatpak-apps) |
| [KRdp's server](#krdps-server-and-cjf-rdp) | the other direction: the Frame's Plasma desktop on a PC, over RDP | `cjf install krdpserver`, run by `cjf rdp` |
| [A panel of any size](#cjf-panel) | one app, or Desktop Mode, in a SteamVR panel of its own | `cjf install gamescope-panel`, run by `cjf panel` |
| [Full Keyboard](#full-keyboard) | a full-size keyboard for the dashboard and local apps | [its own installer](simple-installs.md#full-keyboard) |
| [BSManager](#bsmanager) | Beat Saber versions, mods and maps | [its own installer](simple-installs.md#bsmanager) |

Run them on the host, not in a distrobox.

## Frametop

[Frametop](https://github.com/Frametop/frametop) is a Plasma desktop
on several screens placed around you, each a SteamVR overlay of its
own, with a 3D mouse. Launch a program → Desktop starts it once it is
installed; SteamOS's own single-screen desktop stays in the same list
as Native Desktop.

- **Where it lives.** The release goes in
  `~/.local/share/frametop/releases/<version>`, with a podman image
  and a container made from it, a SteamVR driver, and user services:
  all in the home directory. Its own eye tracker, a root service in
  `/etc/frametop`, and the Bluetooth fixes in `/etc/steamframe` are
  the two parts that ask for sudo, and each is offered, not forced.
- **A source checkout** in `~/frametop` can sit beside a release. The
  launcher's Desktop entry and the services point at whichever was
  installed last; `cjf after-update` says which.
- **Its own XDG dirs.** A terminal inside it has `XDG_CONFIG_HOME` and
  `XDG_STATE_HOME` pointed at the desktop's; the kit's shell init
  keeps mise and the kit's own files on the usual ones
  ([shell-init.md](shell-init.md#frametop-terminals)).
- **The kit's commands that know about it:** `cjf cursor` sets its
  cursor as well as Desktop Mode's ([cursor.md](cursor.md)), and `cjf
  rdp` serves its desktop to a PC, below.

## KRDC

[KRDC](https://apps.kde.org/krdc), KDE's RDP and VNC client, is for
desktop work on a PC from the headset; Moonlight is for games. KRdp,
Plasma's Remote Desktop, streams every monitor as one picture and
moves the pointer through KWin, so it lines up on a multi-monitor
host, where Sunshine's absolute mouse spans the whole desktop but the
stream shows one monitor.

- **On the PC, run `krdpserver` with `--plasma`** (a systemd drop-in
  for `app-org.kde.krdpserver.service`). Without it KRdp goes through
  the desktop portal, whose permission prompt shows on the PC's
  screen, and KRDC gets a blank blue screen until someone answers it
  there.
- **The PC's pointer.** KRdp sends KRDC the pointer's shape, drawn at
  the Frame's own pointer, so a mouse moved at the PC shows only as
  focus changes. Two patches fix that, one on each side, both meant
  for upstream. The kit's KRDC has a per-host option, "Remote pointer:
  painted into the video by the server", and the PC's patched
  krdpserver, a second server on port 3390 beside the stock one on
  3389, paints its pointer into the video for a client that asks.
  Turn off KRDC's View → Show Local Cursor unless you want your own
  pointer over the PC's. [krdc-embed-cursor.md](krdc-embed-cursor.md)
  and [the PC side](../pc/README.md) have the commands and the rebuild
  after an update.
- **Two monitors, pixel for pixel:** in a panel of its own, with `cjf
  panel`, below.
- **What the kit's build carries** besides the option: a FreeRDP of
  its own with hardware H.264 decode, and libvncclient for VNC. A
  Flathub KRDC, if installed, is shadowed and its hosts and bookmarks
  are taken over.

## Moonlight

[Moonlight](https://moonlight-stream.org) streams games from a PC
running Sunshine or GeForce Experience. The Flatpak's sandbox can
reach gamescope, so it can also be added to Steam as a non-Steam game
and started from Game Mode.

## Deskflow

[Deskflow](https://deskflow.org) makes the Frame a client of the PC's
mouse and keyboard, with no streaming: the pointer crosses an edge of
the PC's screen into the Frame's desktop, SteamOS's own Desktop Mode
or Frametop's.

- **On the Frame** the client injects input through the RemoteDesktop
  portal, the route KRdp takes into the nested KWin. The first start
  asks once in the headset to allow remote control, and Deskflow keeps
  the portal's restore token, so later starts don't ask.
- **On the PC** the server needs the InputCapture portal; Plasma 6.7
  offers it.

## Stream Frame

[Stream Frame](https://streamframe.app) shows the headset's view on
another device, and records and screenshots it. It is the app Discover
installs from the website, from the same Flatpak repository. It needs
ffmpeg on the headset, which SteamOS already has in `/usr/bin`.

## KRdp's server and `cjf rdp`

The other direction: the Frame as the RDP host, for seeing and using a
Plasma desktop that runs on it (Frametop's, or SteamOS's stock
Desktop) from a PC, with KRDC, Remmina or Windows Remote Desktop.
SteamOS has no krdp and Flathub only has the client, so the kit builds
it.

```bash
cjf rdp start [--desktop frametop|stock|DIR] [--port N] [--user NAME] [--address ADDR]
```

`stop`, `status`, `log` and `password [NEW | --generate]` are the
rest; nothing starts by itself.

- **Which desktop.** Frametop's when that runs. The stock Desktop only
  with `--force`: on SteamOS 0.4.5 its KWin, 6.2.5 on the X11 backend
  inside gamescope, crashed in its screencast plugin as soon as a
  client connected, which leaves a bare KWin until you log out of it.
  Frametop's KWin, on the Wayland backend, streams fine.
- **The port** is 3391 by default: 3389 is SteamOS's own xrdp, which
  logs into a separate X11 session, and 3390 is Frametop Remote
  Access's krdp when that is on, so `cjf rdp` runs beside either.
- **The login** is the Frame's user with the password in
  `~/.config/krdpd/password`, made at the first start; the self-signed
  certificate there is what clients accept once.
- **The network.** The Frame's firewall already allows every port
  above 1024 on the LAN ([Firewall](tailscale.md#firewall)), and RDP
  brings its own TLS and login (NLA); `--address` with the tailnet
  address keeps it off the LAN.
- **Over RDP,** Frametop's screens you aren't looking at draw slowly,
  since only Frametop Remote Access asks ft-screens for full rate.
- **KRdp Server**, the menu entry the package adds, is `cjf rdp gui`:
  a window that starts and stops the same server and shows where to
  connect, the password, and the log. It runs `cjf rdp` for
  everything, so the two never disagree, and the server keeps running
  after the window closes. It is GTK 4 and libadwaita through Python,
  all in SteamOS's image; run it on the host, from either desktop.

The package is krdp 6.4.5, built on the Frame against the host's own
FreeRDP, Frameworks and Qt in a few minutes, under
`~/.local/lib/krdpserver`. Its PKGBUILD
(`src/curiousj_framekit/data/pkgbuilds/krdpserver/`) says why that
release, the newest whose minimums both the stable and the beta
SteamOS meet, and what it carries: a kpipewire of its own with a
cursor fix and ffmpeg 8's spelling of the H.264 profiles, qtkeychain,
and one line of krdp 6.8's FreeRDP 3.32 fix
([patches.md](patches.md)).

- **No permission bypass.** It is unsandboxed, so KWin grants it the
  capture through the desktop file the package puts in
  `~/.local/share/applications`, whose Exec is the binary.
- **After a SteamOS update** that changes a library it links, `cjf
  installed` shows it and `cjf update` rebuilds it, as with KRDC.
- **krdp 6.8 has to wait** for a SteamOS with KWin 6.7 or later: it
  needs a newer screencast protocol than the Frame's KWin speaks
  (0.5.7 beta's 6.6.2 is one version short), so it streams nothing on
  the Frame.
- **The old Flatpak.** Until 2026-11-14 the kit built the server as a
  Flatpak, `io.github.curiousjtuber.Krdp`. If it is still installed,
  `flatpak --user uninstall io.github.curiousjtuber.Krdp` removes it,
  `org.kde.Sdk` and `org.flatpak.Builder` with it if nothing else uses
  them, and `~/.cache/krdpd/flatpak` is its build state.

## `cjf panel`

```bash
cjf panel start [--size WxH] [--width METRES] [--name NAME] [--fullscreen] [--wayland] [--env VAR=VALUE] -- COMMAND
```

Runs any app in a SteamVR panel of its own with a screen of exactly
that size, beside Game Mode, which scales every app to one 1920x1080
overlay: KRDC at 3840x1080 shows a PC's two monitors pixel for pixel.
`stop`, `status` and `log` are the rest, and `cjf panel desktop --size
WxH` runs SteamOS's own Desktop Mode in one, with a screen of that
size in place of its 1280x800. It runs the gamescope that `cjf install
gamescope-panel` builds, the host's release with one patch.
[panel.md](panel.md) has the why and the limits.

## Full Keyboard

[Full Keyboard](https://github.com/TaiKeid/steam-frame-full-keyboard)
is TaiKeid's full-size virtual keyboard: arrow keys, a numpad, Ctrl
and Alt, in a panel you type on with the controller laser. It types
into the dashboard, Steam's text fields and apps running on the Frame.

- **Beside the system keyboard, or in its place.** Installed by hand
  it is a separate app, started from the dashboard's app launcher with
  the VR session running. Its installer asks whether it should replace
  the native keyboard and start with SteamOS; both are in its Settings
  afterwards.
- **It updates itself** from its Settings, and rolls back if a new
  release fails to start.
- **Settings** are in `~/.config/framekeyboard`, which its uninstaller
  keeps.

## BSManager

[BSManager](https://github.com/DaVarga/bs-manager), DaVarga's arm64
fork, manages Beat Saber versions, mods and maps:
`~/Applications/BSManager.AppImage`, a menu entry and the BeatSaver
OneClick links. In the headset, start it from Steam. It updates
itself.

It needs the `fuse2` item on SteamOS 0.5.7 and later, which dropped
fuse2 from the image: an AppImage's runtime loads `libfuse.so.2` to
mount itself (`dlopen(): error loading libfuse.so.2` otherwise). The
kit builds that one library for `~/.local/lib/fuse2`
([packages.md](packages.md)), and the menu entry has to name that
directory on `LD_LIBRARY_PATH`, which a line in
[simple-installs.md](simple-installs.md#bsmanager) sees to.

### `bsmanager`: its window on a PC

```bash
waypipe --remote-bin /home/steamos/.local/bin/waypipe ssh steamos@frame.local bsmanager
```

Run on the PC, that shows the Frame's BSManager in a window on the
PC's Wayland desktop, through waypipe: `bsmanager [--no-gpu]` is the
kit's command on the Frame, run inside a `waypipe ssh` session.

- **It needs** `cjf install waypipe` and `cjf install fuse2` on the
  Frame, and waypipe on the PC. It runs the AppImage with the fuse2
  directory on `LD_LIBRARY_PATH` itself.
- **From a distrobox** it hands over to the host, and it refuses
  without the session's `WAYLAND_DISPLAY`.
- **One instance.** BSManager allows one, so the command stops if it
  is already running on the Frame: a second launch would hand off to
  the first and exit, and no window would show on the PC.
- **`--no-gpu`** is for a blank or crashing window; pass `-n` to
  waypipe on the PC as well, so the window travels as plain pixels.
