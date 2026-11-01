# The PC side

What a PC does for a Steam Frame, as far as this kit is concerned: two
Arch packages, and the commands the kit's own docs assume on the PC.
Nothing here runs on the Frame, and nothing in the kit's catalog looks
under `pc/`. The PC is an Arch or CachyOS machine; other distros get
the same programs by other means and the same instructions otherwise.

If a PC command ever comes, it is a second package in this repository,
`curiousj-framekit-pc`, installed with `uv tool install
"git+https://github.com/curiousjtuber/steam-frame-utils#subdirectory=pc"`;
today there is none (reorg-plan.md, Q9).

## `pkgbuilds/krdpserver-embed-cursor`

krdpserver, KDE's RDP server, with an `EmbedCursor` option, as a
package beside the distro's `krdp`. KRdp sends a viewer the pointer's
shape, which the viewer draws at its own pointer, so moving the mouse
at the PC shows in the stream on the Frame only as focus changes. With
`EmbedCursor=true` in `[General]` of `~/.config/krdpserverrc`, KWin
paints the PC's pointer into the frames and the viewer draws none, so
the headset sees where the PC's mouse is. Off, the server is upstream's
exactly. For the Frame + Deskflow + Frametop + KRDC scenario.

```bash
cd pc/pkgbuilds/krdpserver-embed-cursor && makepkg -sri
```

makepkg verifies the tarball's signature with your keyring, so import
KDE's release keys once (`validpgpkeys` in the PKGBUILD), or pass
`--skippgpcheck`; the sha256 is checked either way.

Switching is a user systemd drop-in, beside the one that adds
`--plasma` to krdpserver (without `--plasma`, KRdp goes through the
desktop portal, whose permission prompt shows on the PC's screen while
KRDC on the Frame sees a blank blue screen):

```bash
d=~/.config/systemd/user/app-org.kde.krdpserver.service.d
```

```bash
printf '[Service]\nExecStart=\nExecStart=/usr/bin/krdpserver-embed-cursor --plasma\n' > "$d/zz-embed-cursor.conf"
```

```bash
systemctl --user daemon-reload && systemctl --user restart app-org.kde.krdpserver.service
```

Removing `zz-embed-cursor.conf` and running the last line again goes
back to the stock server; remove it before uninstalling the package.
The option itself:

```bash
kwriteconfig6 --file krdpserverrc --group General --key EmbedCursor --type bool true
```

then restart the service; it reads the key once at start. In KRDC on
the Frame, turn off View → Show Local Cursor, or it draws its own on
top.

**After a Plasma update.** `pkgver` must equal `pacman -Q krdp`: the
private libKRdp is compiled against that release's kpipewire, so the
package pins `krdp` to it, and a Plasma point release makes `pacman
-Syu` refuse until this is rebuilt. Bump `pkgver`, run `updpkgsums`,
`makepkg -sri`, restart the service; or update first with
`--assume-installed krdp=<old version>`. If the patch no longer
applies, upstream moved the code and the patch needs refreshing. The
PKGBUILD's header has the layout decisions (a private library
directory with a RUNPATH, so the patched library loads rather than
`/usr/lib/libKRdp.so.6`).

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
