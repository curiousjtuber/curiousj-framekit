# `krdc-embed-cursor/`

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
until the client's lands. Until then this script builds the client on
any distribution with KDE Frameworks 6 and FreeRDP 3, and on the Frame
as it is, where KRDC is a flatpak and the host lacks
extra-cmake-modules and qtkeychain: the script builds those two as
well.

```bash
krdc-embed-cursor/krdc-embed-cursor.sh install
```

on the PC and on the Frame (in the kit's checkout there,
`~/curiousj-framekit`). It downloads krdc 26.08.2 (`--version` for
another), checks the signature against the KDE Gear release keys
(fetching a missing one by fingerprint), applies the patch, and builds
into `~/.local/lib/krdc-embed-cursor`, a prefix of its own: KRDC's RDP
and VNC backends are Qt plugins that Qt finds only through
`QT_PLUGIN_PATH`, so `~/.local/bin/krdc` is a launcher that sets it and
runs the build's binary. The launcher shadows a distribution's `krdc`
on PATH, and `~/.local/share/applications/org.kde.krdc.desktop` shadows
the distribution's or the flatpak's menu entry, so KRDC from the menu
is this one. On the Frame a first install copies the flatpak's hosts
and bookmarks to `~/.config/krdcrc` and `~/.local/share/krdc`; the
passwords are in the wallet, which both use. `status` says what is
installed and what the menu and PATH run; `uninstall` puts the
distribution's or the flatpak's KRDC back and keeps the configuration;
`--help` lists the options. On the PC the build needs the
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
still applies.
