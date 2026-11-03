# KRDC with the Remote pointer option

KRDC, KDE's RDP client, with one option added per host: "Remote
pointer: painted into the video by the server". It is the viewer side
of [the PC's krdpserver-embed-cursor](../pc/README.md): a headset that
watches a PC's desktop wants to see where the PC's mouse is, and KRdp
sends only the pointer's shape, for the viewer to draw at its own
pointer. RDP has no flag for "paint it for me". What it has is the
pointer capability set, where a client says how many pointer shapes it
can cache. With the option on, KRDC advertises none, which says it
cannot draw shapes; stock KRdp means to refuse such a client but
checks before the client's capabilities arrive and crashes on it
instead, the patched KRdp paints its own pointer into the video for it.
Off, the client is upstream's exactly.

Both patches are meant for upstream, KRdp and KRDC, so they stay
small: one preference and one condition on each side, no new protocol.
The server's part is harmless alone, since nothing sends it a zero
until the client's lands. Until then the kit builds the client, two
ways from one patch. On the Frame it is the `krdc` catalog item, a
package for `~/.local` from the kit's PKGBUILD
(`src/curiousj_framekit/data/pkgbuilds/krdc/`), like Emacs:

```bash
cjf install krdc
```

in place of the flatpak the item used to install. The host lacks
extra-cmake-modules and qtkeychain, so the PKGBUILD carries both, the
first for the build only. `cjf installed` shows pacman-home's version
and says outdated once the PKGBUILD's moves on (a new release, or a
`pkgrel` bump for a changed patch); `cjf update` rebuilds it then; `cjf uninstall krdc` is `pacman-home -R krdc`, and leaves the
flatpak, if any, as the menu's KRDC again. On the PC, where cjf does
not run, the script does the same build from the checkout, on any
distribution with KDE Frameworks 6 and FreeRDP 3:

```bash
src/curiousj_framekit/data/krdc-embed-cursor/krdc-embed-cursor.sh install
```

It downloads krdc 26.08.2 (`--version` for another), checks the
signature against the KDE Gear release keys (fetching a missing one by
fingerprint), applies the patch, and builds into
`~/.local/lib/krdc-embed-cursor`, a prefix of its own, the layout the
package has too: KRDC's RDP
and VNC backends are Qt plugins that Qt finds only through
`QT_PLUGIN_PATH`, so `~/.local/bin/krdc` is a launcher that sets it and
runs the build's binary. The launcher shadows a distribution's `krdc`
on PATH, and `~/.local/share/applications/org.kde.krdc.desktop` shadows
the distribution's or the flatpak's menu entry, so KRDC from the menu
is this one. A flatpak KRDC's hosts and bookmarks are copied to
`~/.config/krdcrc` and `~/.local/share/krdc` when there are none yet,
by the package's launcher on its first run and by the script at
install; the passwords are in the wallet, which both use. The flatpak
itself stays until you remove it (`flatpak --user uninstall
org.kde.krdc`). The script's `status` says what is installed and what
the menu and PATH run; its `uninstall` puts the distribution's or the
flatpak's KRDC back and keeps the configuration; `--help` lists the
options. On the PC the build needs the
distribution's development packages for Qt 6, KF6, FreeRDP 3, libssh
and qtkeychain, plus extra-cmake-modules; when cmake can't find one,
the script prints the package list for Arch, Fedora or Debian/Ubuntu.

Then, in the PC's host entry (port 3390), Settings → Remote pointer →
Painted into the video by the server, and View → Show Local Cursor off
unless you want your own pointer drawn over the PC's. The server's
journal (`journalctl --user -u krdpserver-embed-cursor.service`) says
"Client has no pointer cache, the host's pointer goes into the video"
for the connection. Against the stock server on 3389 the option
brings the server down (krdp 6.8 evicts from an empty pointer cache),
so leave it off for that entry; other servers are untested.

After a KDE Gear update on the PC, `install` again builds the release
the script names; `--version` builds another, as long as the patch
still applies. On the Frame a new release is a `pkgver` bump and a new
sum in the PKGBUILD, then `cjf install krdc` again.
