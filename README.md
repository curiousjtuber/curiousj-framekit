# curiousj-framekit

curiousj's kit for the Steam Frame: one command, `cjf`, for the things
I do to the headset's arm64 SteamOS, with its immutable root and A/B
updates. Everything lives in the home directory, the one partition an
update keeps. Formerly `steam-frame-utils`, a set of shell scripts;
[docs/reorg/plan.md](docs/reorg/plan.md) records why and how it became
this.

The contents are personal: the catalog is my list of what goes on a
Frame, the Beat Saber tools my habits, the Emacs build my editor. It is
in the open because the reasons are worth reading, and because each
part is also a worked answer to "how do I put X on the Frame".

## Install

On the Frame, over SSH or from a Konsole in Desktop Mode:

```bash
curl -LsSf https://raw.githubusercontent.com/curiousjtuber/curiousj-framekit/main/install.sh | sh
```

It says what it will install (mise, then uv and fzf through it, then
the kit as a uv tool: `cjf` and `curiousj-framekit` in `~/.local/bin`),
asks once, and ends with `cjf init`, the base: `~/.local/bin` on
`PATH`, one `init.sh` the rc files source, the podman shim, the cursor
fix. No root. Run it again to upgrade. From a checkout, so that edits
are live:

```bash
uv tool install --editable ~/curiousj-framekit && cjf init
```

A Frame still set up by `steam-frame-utils`' `setup.sh` moves over
with `cjf migrate`, which the kit had up to 0.5.1: install that
release, run it once, then update.

## Commands

| | |
|---|---|
| `cjf` | the menu: every command below, picked with fzf (ENTER runs it); a command with actions of its own gets a menu of them, a required argument is asked for, `help` on any menu is that command's `--help`, and the command line it ran is printed at the end, to type next time |
| `cjf status [--all]` | the versions of SteamOS, SteamVR and the Steam client, the kit's own, the headset's battery, the cursor, Tailscale, the RDP server; `--all` adds the catalog |
| `cjf install [NAME...]` | install or update a catalog item, or pick from the catalog; each item's options after its name (`cjf install --help`) |
| `cjf installed [--trust]` | every catalog item's state, without the network; `--trust` adds the root of trust and what is checked ([docs/TRUST.md](docs/TRUST.md)) |
| `cjf outdated [NAME...]` | every installed item, and the kit, against its upstream: current, outdated, behind (upstream moved past what the kit pins, so the fix is a bump here), or no way to tell |
| `cjf update [NAME...]` | install what `outdated` finds newer, asked once; `cjf --check update` only lists |
| `cjf uninstall NAME` | remove one item, or print the steps; refused while an installed item needs it |
| `cjf init` | the base, again: it changes only what differs |
| `cjf init --remove` | the base taken out again, before uninstalling the kit |
| `cjf cursor size\|theme\|apply\|software` | the mouse cursor in Desktop Mode and Frametop's desktop: its size and theme, and Desktop Mode's software cursor ([docs/cursor.md](docs/cursor.md)) |
| `cjf wifi [--all]` | the saved Wi-Fi networks in range, strongest first; Desktop Mode has no network applet |
| `cjf vr [off [left\|right]]` | the headset's battery from the kernel, then SteamVR's controllers with theirs (and the AA cell's voltage under load and the NiMH charge left, worked back from the firmware's percentage); `off` as the dashboard's power menu does |
| `cjf controllers [off [NAME]]` | the Steam Controllers paired over Bluetooth, with battery; `off` with Valve's own HID command |
| `cjf rdp start\|stop\|status\|log\|password\|gui` | KRdp's server for a Plasma desktop on the Frame, for KRDC, Remmina or Windows Remote Desktop ([docs/apps.md](docs/apps.md)) |
| `cjf pkg build\|homeify\|outdated` | packages built for `~/.local` from the kit's PKGBUILDs; `pacman-home` is their pacman ([docs/packages.md](docs/packages.md)) |
| `cjf after-update` | what to re-check after a SteamOS update, as one command, each check ending in ok or in the command that fixes it |
| `pacman-home` | pacman for the packages under `~/.local`: `-Q`, `-U`, `-R`, `check`, `outdated`, `relocate`, `keyring` |
| `beat-saber-recent` | the songs Beat Saber played in its recent launches; `--install-hook` sets the launch options that record every launch |
| `bsmanager` | BSManager on the Frame in a window on a Linux PC, through waypipe |

The global options go first: `cjf --check install emacs` says what
would happen and changes nothing; `cjf --yes install emacs` asks
nothing; `-v` logs each command run. Every change to a file is shown as
a diff and asked about, and the file is backed up with a timestamp.

## The catalog

| Item | What |
|---|---|
| `cursor` | the software mouse cursor in Desktop Mode, and the cursor size entry |
| `tailscale` | Tailscale as a system service that survives updates (sudo); `--trust` opens the tailnet past SSH ([docs/tailscale.md](docs/tailscale.md)) |
| `waypipe` | Arch Linux ARM's package, relocated under `~/.local` |
| `emacs`, `krdc`, `fuse2` | Emacs with PGTK, KRDC with hardware H.264 decode and the kit's "Remote pointer" option, in place of the Flatpak ([docs/krdc-embed-cursor.md](docs/krdc-embed-cursor.md)), and libfuse 2 for the AppImages (SteamOS 0.5.7 dropped it), built on the Frame for `~/.local` from the kit's PKGBUILDs |
| `krdpserver` | KRdp's server, built on the Frame for `~/.local` against the host's libraries (a few minutes; `cjf rdp` runs it) |
| `gamescope-panel` | gamescope built on the Frame for `~/.local` with one patch, so that its VR backend starts above 1080p; `cjf panel` runs an app, or SteamOS's Desktop Mode, in it as a SteamVR panel of any size ([docs/panel.md](docs/panel.md)) |
| `wayvr` | [WayVR](https://github.com/wayvr-org/wayvr) built on the Frame for `~/.local`, with three patches: a virtual output of any size, so a panel can pass 2560x1440, `xwayland-satellite` found beside the binary, and a fix for apps and the dashboard opening on the floor before the overlays were first shown; `wayvrctl` from the same commit comes with it, and the `xwayland-satellite` item, its X server for X11 apps, is installed first. Both need cargo. The AppImage stays the simple install ([docs/simple-installs.md](docs/simple-installs.md#wayvr)) |

[docs/install.md](docs/install.md) has the reasons behind each part,
[docs/apps.md](docs/apps.md) the apps in detail, [docs/TRUST.md](docs/TRUST.md)
what each one checks.

The catalog holds only what the kit has to do itself. What a package
manager installs, or an upstream's own instructions, is in
[docs/simple-installs.md](docs/simple-installs.md), each with its
commands and the upstream page they come from: rust (`mise use`),
Homebrew, wl-clipboard and zsh (`brew install`), curiousj-tools (`uv
tool install`), the Flatpaks Moonlight, Deskflow and Stream Frame
(`flatpak install`), and distrobox, Nerd Fonts, BSManager, Full
Keyboard, [Frametop](https://github.com/Frametop/frametop) and WayVR
by their own installers.

## Layout

| Path | |
|---|---|
| `src/curiousj_framekit/` | the package: `frame/` (the Frame's own: cursor, wifi, vr, controllers, rdp, panel, pkg, after-update), `install/` (the catalog and its kinds, init, status), `beatsaber/`, `shell/` (init.sh and the shims), `data/` (the KRdp manifest and patches, the KRDC build script and patch, the RDP GUI) |
| `src/curiousj_framekit/data/pkgbuilds/` | the kit's PKGBUILDs, built for `~/.local` in `~/.cache/curiousj-framekit/build/`: emacs, krdc, fuse2, krdpserver, gamescope-panel, wayvr, xwayland-satellite |
| `pc/` | the PC side: krdpserver patched to paint the PC's pointer into the video for a viewer that asks, built by script, and what the Frame's docs assume there ([pc/README.md](pc/README.md)) |
| `src/curiousj_framekit/data/krdc-embed-cursor/` | KRDC with the option that asks for it: the patch, which the Frame's PKGBUILD applies too, and the script that builds it on the PC ([docs/krdc-embed-cursor.md](docs/krdc-embed-cursor.md)) |
| `docs/` | [install.md](docs/install.md), [simple-installs.md](docs/simple-installs.md), [apps.md](docs/apps.md), [tailscale.md](docs/tailscale.md), [shell-init.md](docs/shell-init.md), [cursor.md](docs/cursor.md), [packages.md](docs/packages.md), [krdc-embed-cursor.md](docs/krdc-embed-cursor.md), [panel.md](docs/panel.md), [patches.md](docs/patches.md) (every patch the kit carries and where it stands upstream), [TRUST.md](docs/TRUST.md); and the memos: [the desktop cursor on 0.5.6](docs/desktop-cursor.md), [packages under ~/.local](docs/home-packages.md), [paru](docs/paru.md), [the proximity sensor](docs/proximity-sensor.md), [the screen reader](docs/orca-screen-reader.md), [Arch distrobox images](docs/arch-distrobox-images.md); `notes/` has the AA calibration data |
| `docs/reorg/` | the reorganization from `steam-frame-utils`, closed 2026-11-01: [plan.md](docs/reorg/plan.md) (its decisions), [steps.md](docs/reorg/steps.md) (its stages), [scenarios.md](docs/reorg/scenarios.md) (the usage it aimed at) |
| `install.sh` | the bootstrap: mise, uv, fzf, the kit, `cjf init` |
| `tests/` | pytest, over the pure logic and the shell files (`bash -n`, `zsh -n`) |

## Where things go on the Frame

| | |
|---|---|
| `~/.local/bin` | `cjf`, `curiousj-framekit`, `pacman-home`, `beat-saber-recent`, `bsmanager`, uv's and mise's commands |
| `~/.local/share/curiousj-framekit/` | `init.sh` and the completion files, `shims/podman` |
| `~/.config/curiousj-framekit/config.toml` | the choices: the software cursor, the RDP port |
| `~/.local/state/curiousj-framekit/` | the Beat Saber song history, what `after-update` last saw |
| `~/.bashrc`, `~/.zshrc`, `~/.distroboxrc` | one marked block each, which `cjf init` keeps |

To take the kit off the Frame, undo the base first: uv removes `cjf`
and nothing `cjf` wrote.

```bash
cjf init --remove && uv tool uninstall curiousj-framekit
```

`cjf init --remove` takes out `init.sh`, the completion files, the
shim, the marked blocks and the cursor fix, and names what it leaves:
the `~/.local/bin` line on `PATH`, the catalog's items (`cjf uninstall
NAME`), what [docs/simple-installs.md](docs/simple-installs.md)
installed, and the config, state and cache directories.

The host and its distroboxes share the home directory, so `cjf` runs in
a box too; what needs the host says so, with the
`distrobox-host-exec` line to run instead.
