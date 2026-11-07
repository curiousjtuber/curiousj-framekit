## Apps

Each app is a catalog item now: `cjf install frametop`, `cjf install
moonlight`, and so on, with the options the scripts took after the name
(`cjf install --help` lists them), and `cjf uninstall NAME`. The text
below still names the scripts; the behaviour is the same.

`apps/` holds one installer per app. `setup.sh` doesn't run them; each
is run by hand, and a re-run updates. The header comment of each has the
details and the uninstall steps. [TRUST.md](TRUST.md) says
what each one verifies, who is trusted at the root, and what the app
gets on the headset.

| Script | App | Where it goes |
|---|---|---|
| `install-stream-frame.sh [--yes]` | [Stream Frame](https://streamframe.app), for watching, recording and screenshotting the headset from another device | Flatpak `com.boxtree.StreamFrame`, in the user installation, from Boxtree's repo; no root |
| `install-moonlight.sh [--yes]` | [Moonlight](https://moonlight-stream.org), for streaming games from a Sunshine or GeForce Experience host | Flatpak `com.moonlight_stream.Moonlight`, in the user installation, from Flathub; no root |
| `install-krdc.sh [--yes]` | [KRDC](https://apps.kde.org/krdc), KDE's RDP and VNC client, for a Plasma desktop shared with KRdp | was Flatpak `org.kde.krdc` from Flathub; since 2026-11-03 `cjf install krdc` builds KRDC with the kit's patch from the kit's PKGBUILD, a pacman-home package under `~/.local`, and the flatpak, if installed, is shadowed ([krdc-embed-cursor.md](krdc-embed-cursor.md)) |
| `install-deskflow.sh [--yes]` | [Deskflow](https://deskflow.org), keyboard and mouse sharing, so a PC's mouse and keyboard reach the Frametop desktop | Flatpak `org.deskflow.deskflow`, in the user installation, from Flathub; no root |
| `install-bsmanager.sh` | [BSManager](https://github.com/DaVarga/bs-manager), DaVarga's arm64 fork, for Beat Saber versions, mods and maps | `~/Applications/BSManager.AppImage`, with a menu entry and the BeatSaver OneClick links |
| `install-full-keyboard.sh [--version X.Y.Z \| --uninstall]` | [Full Keyboard](https://github.com/TaiKeid/steam-frame-full-keyboard), TaiKeid's full-size virtual keyboard for the dashboard and local apps | `~/.local/share/framekeyboard`, with the launcher `~/.local/bin/framekeyboard` and a menu entry |
| `install-frametop.sh [--version X.Y.Z] [--yes] [--no-eye-tracker] [--no-bluetooth \| --bluetooth] [--any-steamos] [--unpack-only] \| --uninstall` | [Frametop](https://github.com/Frametop/frametop), the multi-screen Plasma desktop and 3D mouse that run on the Frame itself | `~/.local/share/frametop/releases/<version>`, with a podman image and container from the release's `Frametop.zip`, and services in the home directory; two optional parts use sudo |
| `install-krdp.sh [--bundle [FILE] \| --uninstall]` | [KRdp](https://invent.kde.org/plasma/krdp)'s server, krdpserver, for serving a Plasma desktop on the Frame over RDP to KRDC, Remmina or Windows Remote Desktop | Flatpak `io.github.curiousjtuber.Krdp`, built here on KDE's runtime, in the user installation; no root. Run with `cjf rdp`, or KRdp Server in the menu |

- **The Flatpak apps** go into the user installation,
  `~/.local/share/flatpak`, like Frametop and krdpserver: no root and no
  polkit, so the scripts work over SSH, and SteamOS updates keep the
  home directory. Each pulls its KDE runtime into the user installation
  too, even when a system one would do, so removing system Flatpaks
  later can't break it. A system copy, say one Discover installed, is
  reported: the user copy wins the menu and `flatpak run`, so remove the
  system one with `sudo flatpak uninstall --system <app>`. Run the
  scripts on the host, not in a distrobox.
- **Stream Frame** is the app Discover installs from the website, from
  the same repo. The first install also pulls the KDE runtime from
  Flathub, a few hundred MB, and asks first unless given `--yes`. It
  needs ffmpeg on the headset, and SteamOS already has it in `/usr/bin`.
- **Moonlight** comes from Flathub because Ubuntu 26.04 has no
  `moonlight-qt` for arm64. The first install pulls KDE runtime 6.11,
  about 400 MB, and asks first unless given `--yes`. The sandbox can
  reach gamescope, so it can also be added as a non-Steam game for Game
  Mode.
- **KRDC** is for desktop work, Moonlight for games. KRdp, Plasma's
  Remote Desktop, streams every monitor as one picture and moves the
  pointer through KWin, so it lines up on a multi-monitor host, where
  Sunshine's absolute mouse spans the whole desktop but the stream shows
  one monitor. Run it on the host. It uses the KDE runtime 6.10 that
  Stream Frame already installs. On the PC, run `krdpserver` with
  `--plasma` (a systemd drop-in for `app-org.kde.krdpserver.service`):
  without it, KRdp goes through the desktop portal, whose permission
  prompt shows on the PC's screen, and KRDC gets a blank blue screen
  until someone answers it there. KRdp sends KRDC the pointer's shape,
  drawn at the Frame's own pointer, so a mouse moved at the PC shows
  only as focus changes. Two patches fix that, one on each side, both
  meant for upstream: `pc/krdpserver-embed-cursor/krdp-embed-cursor.sh
  install` builds krdpserver from the Plasma release the PC runs into
  `~/.local` as a second server beside `krdp` on port 3390, on any
  distribution with Plasma 6, and `cjf install krdc` on the Frame (the
  same script, `krdc-embed-cursor.sh install`, on the PC) builds KRDC
  with a "Remote pointer: painted into the video by the server" option
  per host; on the Frame it shadows the flatpak's menu entry and takes
  over its hosts and bookmarks. With the option on, KRDC advertises no
  pointer cache, and
  the patched server paints the PC's pointer into the video for that
  connection and tells KRDC to draw none, so the headset sees where the
  PC's mouse is; a stock KRDC is served as upstream does. Turn off
  KRDC's View → Show Local Cursor unless you want your own pointer over
  the PC's. KRDC picks a server by port, and the stock one on 3389 is
  never touched; [the PC side](../pc/README.md) and
  [krdc-embed-cursor.md](krdc-embed-cursor.md) have the commands
  and the rebuild after an update.
- **Deskflow** makes the Frame a client of the PC's mouse and keyboard,
  with no streaming: the pointer crosses an edge of the PC's screen into
  the Frametop desktop. Run it on the host. It uses the KDE runtime 6.11
  that Moonlight already installs. On Wayland the client injects input
  through the RemoteDesktop portal, the route KRdp takes into the nested
  KWin, so it works where krdpd does. The first start asks once in the
  headset to allow remote control, and Deskflow keeps the portal's
  restore token, so later starts don't ask. The PC side, the server,
  needs the InputCapture portal; Plasma 6.7 offers it.
- **BSManager** runs the fork's own `install.sh` from its latest
  release, passing on `--uninstall` and `--appimage FILE`. After that,
  BSManager updates itself. It needs the `fuse2` item, installed first:
  SteamOS 0.5.7 dropped fuse2 from the image, and an AppImage's runtime
  loads `libfuse.so.2` to mount itself (`dlopen(): error loading
  libfuse.so.2` otherwise), so the kit builds it for
  `~/.local/lib/fuse2` ([packages.md](packages.md)) and the menu entry
  `install.sh` writes
  is given that directory on `LD_LIBRARY_PATH`; `cjf installed` shows
  `bsmanager` as outdated while the entry lacks it, as after a re-run
  of `install.sh` by hand.
- **Full Keyboard** is a separate app, not a replacement for the system
  keyboard: start it from the dashboard's app launcher, with the VR
  session running. It types into the dashboard and local apps, not into
  streamed VR games. The script checks the release archive against its
  `SHA256SUMS` and runs the `install.sh` inside it, which keeps the
  previous release for rollback and refuses one already installed, so a
  re-run with nothing newer just says so. Close the keyboard before
  updating. `--uninstall` keeps the settings in
  `~/.config/framekeyboard`.
- **Frametop** comes as one release file, `Frametop.zip`, that its CI
  builds from the tagged commit on an arm64 runner: a podman image with
  everything compiled, and its installer. The script records the zip's
  sha256 for the version it names, checks the download against it and
  against the release's `SHA256SUMS`, and runs the zip's
  `install-release.sh`, which checks the image file against the sha256
  in the zip's `frametop-release.json`, loads it, copies the release's
  files out and runs their `install.sh`: nothing compiles, and nothing
  else downloads but the table of tested SteamOS builds, which the zip
  also carries for offline. A release replaced on GitHub fails the
  recorded sum; `--version` takes another release and then has only
  `SHA256SUMS` to check against, which it says. The SteamVR driver, the
  services and the desktop go in the home directory. Frametop's own eye
  tracker, a root service in `/etc/frametop`, and the Bluetooth fixes,
  in `/etc/steamframe`, are the two parts that ask for sudo, and each is
  offered, not forced. For 0.2.2, the zip's scripts and the source tree
  inside its image were compared with the tagged commit: identical.
  Frametop's commits and tags aren't signed, so GitHub's TLS and the
  maintainer's account are the root of trust, as for Full Keyboard and
  BSManager. A source checkout in `~/frametop` is left alone, but the
  launcher's Desktop entry and the services switch to the release; that
  checkout's `install.sh` switches them back.
- **KRdp's server** is the other direction: the Frame as the RDP host,
  for seeing and using a Plasma desktop that runs on it (Frametop's, or
  SteamOS's stock Desktop) from a PC. SteamOS has no krdp and Flathub
  only has the client, so the kit builds it, two ways.
  `cjf install krdpserver` builds krdp 6.4.5 on the Frame against the
  host's own FreeRDP, Frameworks and Qt, in a few minutes, as a
  `pacman-home` package under `~/.local/lib/krdpserver`; the PKGBUILD
  (`src/curiousj_framekit/data/pkgbuilds/krdpserver/`) says why that
  release, the newest whose minimums both the stable and the beta
  SteamOS meet, and what it carries: a kpipewire of its own with the
  cursor fix below and ffmpeg 8's spelling of the H.264 profiles,
  qtkeychain, and one line of krdp 6.8's FreeRDP 3.32 fix. It is
  unsandboxed, so KWin grants it the capture through the desktop file
  the package puts in `~/.local/share/applications`, whose Exec is the
  binary. A SteamOS update that changes a library it links shows in
  `cjf installed` and `cjf update` rebuilds it, as with KRDC.
  `cjf install krdp` builds the flatpak instead, on KDE's runtime with
  its own FreeRDP and kpipewire, pinned and patched as the manifest in
  the kit (`src/curiousj_framekit/data/krdp/`) explains (krdp 6.7.5
  gets 6.8's NLA login, which works with FreeRDP 3.32 clients;
  kpipewire crashes on the 256 px cursor gamescope sets). krdp 6.8
  itself has to wait for a SteamOS with KWin 6.7 or later: it needs a
  newer screencast protocol than the Frame's KWin speaks (0.5.7 beta's
  6.6.2 is one version short), so it streams nothing on the Frame; the
  `krdp-6.8` branch holds that manifest. The first run installs the KDE
  6.11 SDK and flatpak-builder (about 1 GB to download) and builds for
  half an hour; later runs rebuild only what changed. KWin lets the
  sandboxed server capture through the app's desktop file, so neither
  desktop needs KWin's permission checks turned off. Nothing starts
  either by itself. `--bundle` also writes the build as one `.flatpak`
  file, which another aarch64 device installs with `flatpak --user
  install FILE` and no build. GitHub builds the same bundle on an arm64
  runner (`.github/workflows/krdp-flatpak.yml`) when the manifest
  changes, and attaches it to the release when a `krdp-*` tag is
  pushed.
- **`cjf rdp start [--desktop frametop|stock|DIR] [--port N] [--user
  NAME] [--address ADDR]`**, `stop`, `status`, `log`, `password [NEW |
  --generate]` runs that server by hand: the `~/.local` build when it
  is installed, else the flatpak (`start --flatpak` picks the flatpak
  regardless; `status` says which runs). It serves Frametop's desktop
  when that runs (the stock Desktop only with `--force`: on SteamOS
  0.4.5 its KWin, 6.2.5 on the X11 backend inside gamescope, crashes in
  its screencast plugin as soon as a client connects, which leaves a
  bare KWin until you log out of it; Frametop's KWin, on the Wayland
  backend, streams fine), on port 3391 by default: 3389 is SteamOS's own
  xrdp, which logs into a separate X11 session, and 3390 is Frametop
  Remote Access's krdp when that is on, so `cjf rdp` runs beside either.
  The login is the Frame's user with the password in
  `~/.config/krdpd/password`, made at the first start; the self-signed
  certificate there is what clients accept once. The Frame's firewall
  already allows every port above 1024 on the LAN (see
  [Firewall](tailscale.md#firewall)), and RDP brings its own TLS and login (NLA);
  `--address` with the tailnet address keeps it off the LAN. Over RDP,
  Frametop's screens you aren't looking at draw slowly, since only
  Frametop Remote Access asks ft-screens for full rate.
- **KRdp Server**, the menu entry `install-krdp.sh` adds, is
  `cjf rdp gui`: a window that starts and stops the same server and
  shows where to connect, the password, and the log. It runs `cjf rdp` for
  everything, so the two never disagree, and the server keeps running
  after the window closes. It's GTK 4 and libadwaita through Python, all
  in SteamOS's image, so it needs nothing installed; run it on the host,
  from either desktop.
- **`cjf panel start [--size WxH] [--width METRES] [--name NAME]
  [--fullscreen] [--wayland] [--env VAR=VALUE] -- COMMAND`**, `stop`,
  `status`, `log` runs any app in a SteamVR panel of its own with a
  screen of exactly that size, beside Game Mode, which scales every app
  to one 1920x1080 overlay: KRDC at 3840x1080 shows a PC's two
  monitors pixel for pixel. It runs the gamescope `cjf install
  gamescope-panel` builds for `~/.local` (about ten minutes), the
  host's release with one patch, since the host's binary aborts above
  1080p on a fixed-size upload buffer. [panel.md](panel.md) has the
  why and the limits.
- **`bsmanager [--no-gpu]`** shows the Frame's BSManager in a
  window on a Linux PC's Wayland desktop, through waypipe. In the
  headset, start BSManager from Steam instead. It runs in either of two
  places:
  - On the Frame, where `setup.sh` puts it on `PATH`, in a session
    opened from the PC with `waypipe --remote-bin
    /home/steamos/.local/bin/waypipe ssh steamos@frame.local`. From a
    distrobox it runs on the host, and it refuses without the session's
    `WAYLAND_DISPLAY`.
  - On the PC, copied there, where it opens that session itself. HOST
    defaults to `$FRAME_HOST`, or else `steamos@frame.local`.

  The Frame needs `setup.sh --waypipe`, and `bsmanager` runs the
  AppImage with the `fuse2` item's directory on `LD_LIBRARY_PATH`, as
  the menu entry does. BSManager allows one instance,
  so the script stops if it's already running on the Frame: a second
  launch would hand off to the first and exit, and no window would show
  on the PC. `--no-gpu` is for a blank or crashing window; in a session
  opened by hand, also pass `-n` to waypipe.
