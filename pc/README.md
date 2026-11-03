# The PC side

What a PC does for a Steam Frame, as far as this kit is concerned: a
build script, an Arch package, and the commands the kit's own docs
assume on the PC. Nothing here runs on the Frame, and nothing in the
kit's catalog looks under `pc/`. The PC runs Plasma 6 on Wayland; the
script builds on any distribution, Frame Control's package is Arch's,
and other distros get it by other means.

If a PC command ever comes, it is a second package in this repository,
`curiousj-framekit-pc`, installed with `uv tool install
"git+https://github.com/curiousjtuber/curiousj-framekit#subdirectory=pc"`;
today there is none ([the plan](../docs/reorg/plan.md), Q9).

## `krdpserver-embed-cursor/`

krdpserver, KDE's RDP server, patched to paint the PC's pointer into
the video for a viewer that asks, built from the krdp release that
matches your Plasma and installed under `~/.local` as a second server
beside the distribution's `krdp`, on its own port. KRdp sends a viewer
the pointer's shape, which the viewer draws at its own pointer, so
moving the mouse at the PC shows in the stream on the Frame only as
focus changes. A viewer that advertises no pointer cache, which is
what [KRDC with the kit's patch](../krdc-embed-cursor/) does when its
"Remote pointer" option is on, is one that cannot draw shapes; upstream
means to refuse it but checks too early and crashes on it instead,
this build serves it with KWin painting the PC's pointer into the
frames and the viewer told to draw none, so the headset sees where the
PC's mouse is. A viewer with a pointer cache is served as
upstream does. `EmbedCursor=true` in `[General]` of
`~/.config/krdpserverrc` (`install --embed-all`; the script writes the
key `false` otherwise) does it for every viewer; the stock server
ignores the key. For the Frame + Deskflow + Frametop + KRDC scenario;
any distribution with Plasma 6 on Wayland.

Two servers, not a switch: the distribution's
`app-org.kde.krdpserver.service` keeps port 3389 for viewers that draw
their own pointer, and the user unit the script writes,
`krdpserver-embed-cursor.service`, listens on 3390 for the one that
wants the pointer in the stream. A viewer picks by port, and the stock
unit is never touched. Both read `krdpserverrc`, so users, passwords
and the certificate are shared, and each puts its own RDP Server icon
in the tray.

```bash
pc/krdpserver-embed-cursor/krdp-embed-cursor.sh install
```

downloads the krdp release `krdpserver --version` reports, checks its
signature against the Plasma release keys (fetching a missing one by
fingerprint), applies the patch, builds, installs the binary and its
private `libKRdp` under `~/.local`, writes the unit, and runs `start`.
`--port N` picks another port, `--help` lists the rest. The build needs
the distribution's development packages for Qt 6, KF6, FreeRDP 3,
kpipewire, libei, xkbcommon, PAM and qtkeychain, plus
extra-cmake-modules and plasma-wayland-protocols; when cmake can't
find one, the script prints the package list for Arch, Fedora or
Debian/Ubuntu. KRDC on the Frame then connects to the PC's port 3390
with the host's "Remote pointer" option on, and View → Show Local
Cursor off unless you want your own pointer drawn over the PC's.

`start` enables the unit, now and at login; `stop` disables it; `status`
shows the unit, the port, the firewall, and whether the installed build
still matches the Plasma running. The firewall is handled apart from
the unit: a PC that lets 3389 in usually has a rule for it and none
for 3390, and the server logs nothing for a packet it never gets.
`start` checks and opens the port when it is closed, in ufw or
firewalld, the one step that needs root (sudo, so run it in a
terminal; when sudo can't ask, the script prints the command for you).
`stop` leaves the rule, so stopping and starting again asks for no
password; `firewall close` removes it, `firewall open` adds it, and
`firewall` alone says which it is. Another firewall is yours to open.

The unit passes `--plasma`: without it, KRdp goes through the desktop
portal, whose permission prompt shows on the PC's screen while KRDC on
the Frame sees a blank blue screen. The stock server needs the same,
through a drop-in of its own:

```bash
d=~/.config/systemd/user/app-org.kde.krdpserver.service.d
```

```bash
mkdir -p "$d" && printf '[Service]\nExecStart=\nExecStart=/usr/bin/krdpserver --plasma\n' > "$d/plasma.conf"
```

```bash
systemctl --user daemon-reload && systemctl --user restart app-org.kde.krdpserver.service
```

**After a Plasma update.** The private `libKRdp` is built against that
release's kpipewire, so run `install` again: it sees the installed
version differ from Plasma's and rebuilds, then restarts the unit
(`status` says when). If the patch no longer applies, upstream moved
the code and the patch needs refreshing. `uninstall` stops the server,
closes the port and removes everything `install` put in place. The
script's header has the layout decisions (a private library directory
with a RUNPATH, so the patched library loads rather than the
distribution's `libKRdp.so.6`). An earlier form of this was an Arch
package, `krdpserver-embed-cursor` beside `krdp`, pinned to krdp's
version; if it is still installed, the user unit overrides its unit of
the same name, and `sudo pacman -R krdpserver-embed-cursor` retires it.

## `pkgbuilds/frame-control-bin`

[Frame Control](https://github.com/saphid/frame-control), the PC-side
app for the Frame, as an Arch package built from the `.deb` each
release's workflow publishes, checked against the sha256 from its
`SHA256SUMS`, so what pacman installs is byte for byte the tested
release. Its own updater sees a package install and only announces a
release; updating is bumping `pkgver` and the two sums, then:

```bash
cd pc/pkgbuilds/frame-control-bin && makepkg -si
```

The header explains the two changes to the `.deb`'s layout
(`/opt/frame-control` without a space in the path, `chrome-sandbox`
left 0755).

## Commands the Frame's docs assume on the PC

- **BSManager in a window on the PC**, through waypipe (the Frame needs
  `cjf install waypipe` and `cjf install bsmanager`):

  ```bash
  waypipe --remote-bin /home/steamos/.local/bin/waypipe ssh steamos@frame.local bsmanager
  ```

- **The Frame's desktop on the PC**: `cjf rdp start` on the Frame, then
  KRDC to `frame.local:3391`; see [docs/apps.md](../docs/apps.md).
- **The PC's mouse and keyboard on the Frametop desktop**: Deskflow's
  server on the PC (it needs the InputCapture portal, which Plasma 6.7
  offers), `cjf install deskflow` on the Frame.
