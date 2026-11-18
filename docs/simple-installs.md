# Simple installs: a package manager, or upstream's instructions

Things for the Frame that need no code from the kit. Each is
either a package manager's install (mise, Homebrew, Flatpak, uv) or a
matter of following the project's own install instructions, which each
entry links. They were catalog items until 2026-11-17 (`cjf install
zsh` and so on); the catalog now holds only what the kit has to do
itself: a build from a PKGBUILD, a relocated package, a system
service, the cursor fix. So `cjf installed`, `cjf outdated` and `cjf
update` no longer see these, and each entry names its own update and
removal.

Run them on the host, not in a distrobox. mise and uv are the base,
which `install.sh` puts in place; the shell init (`cjf init`) already
puts Homebrew, mise's tools and `~/.local/bin` on `PATH` when they are
there ([shell-init.md](shell-init.md)).

Where an upstream installer is a script, the lines below save it to a
file and run the file, as the kit did, so a download cut short runs
nothing.

| What | How | Upstream's instructions | Update | Remove |
|---|---|---|---|---|
| [rust](#rust) | `mise use -g rust` | [mise: Rust](https://mise.jdx.dev/lang/rust.html) | `mise upgrade rust` | `mise unuse -g rust` |
| [Homebrew](#homebrew) | its installer, after one `sudo` line | [Homebrew on Linux](https://docs.brew.sh/Homebrew-on-Linux) | `brew update` | its own `uninstall.sh` |
| [wl-clipboard](#homebrew) | `brew install wl-clipboard` | [the formula](https://formulae.brew.sh/formula/wl-clipboard) | `brew upgrade wl-clipboard` | `brew uninstall wl-clipboard` |
| [zsh](#zsh) | `brew install zsh` | [the formula](https://formulae.brew.sh/formula/zsh) | `brew upgrade zsh` | `brew uninstall zsh` |
| [distrobox](#distrobox) | its installer, with `--prefix ~/.local` | [distrobox: installation](https://distrobox.it/#installation) | the installer again | `~/.local/bin/distrobox-uninstall --prefix ~/.local` |
| [curiousj-tools](#curiousj-tools) | `uv tool install` from git | [its README](https://github.com/curiousjtuber/curiousj-tools), [uv: tools](https://docs.astral.sh/uv/guides/tools/) | `uv tool upgrade curiousj-tools` | `uv tool uninstall curiousj-tools` |
| [Moonlight](#flatpak-apps) | `flatpak --user install flathub com.moonlight_stream.Moonlight` | [Flathub's page](https://flathub.org/apps/com.moonlight_stream.Moonlight) | `flatpak --user update` | `flatpak --user uninstall com.moonlight_stream.Moonlight` |
| [Deskflow](#flatpak-apps) | `flatpak --user install flathub org.deskflow.deskflow` | [Flathub's page](https://flathub.org/apps/org.deskflow.deskflow) | `flatpak --user update` | `flatpak --user uninstall org.deskflow.deskflow` |
| [Stream Frame](#flatpak-apps) | its own Flatpak remote, then `flatpak --user install` | [streamframe.app](https://streamframe.app/) | `flatpak --user update` | `flatpak --user uninstall com.boxtree.StreamFrame` |
| [Nerd Fonts](#nerd-fonts) | a release archive unpacked into `~/.local/share/fonts` | [Font Installation, option 1](https://github.com/ryanoasis/nerd-fonts#font-installation) | the same again | delete the font's folder, `fc-cache -f` |
| [BSManager](#bsmanager) | the fork's `install.sh`, with `fuse2` first | [the fork's Steam Frame page](https://github.com/DaVarga/bs-manager/blob/HEAD/docs/steam-frame.md) | it updates itself | its `install.sh --uninstall` |
| [Full Keyboard](#full-keyboard) | its installer AppImage | [Quick install](https://github.com/TaiKeid/steam-frame-full-keyboard#quick-install) | from its own Settings | its `uninstall.sh` |
| [Frametop](#frametop) | its `get.sh --release` | [Install on the headset](https://github.com/Frametop/frametop#install-on-the-headset) | Update Frametop in its menu, or `get.sh` again | its `uninstall.sh` |
| [WayVR](#wayvr) | its aarch64 AppImage through Gear Lever; `wayvrctl` built with cargo | [Installing on Steam Frame](https://github.com/wayvr-org/wayvr#installing-on-steam-frame) | a newer AppImage, then `wayvrctl` again | in Gear Lever; delete `~/.local/bin/wayvrctl` |

## rust

Instructions: <https://mise.jdx.dev/lang/rust.html>

```bash
mise use -g rust
```

For cargo, which a Rust package built with `cjf pkg` needs; `cjf pkg
homeify` takes cargo from mise's shims. The version is mise's business
(`latest`). Trust: mise's own download checks, rust-lang.org.

## Homebrew

Instructions: <https://docs.brew.sh/Homebrew-on-Linux> (the installer
line is on <https://brew.sh>)

```bash
sudo install -d -o "$USER" -g "$(id -gn)" /home/linuxbrew
```

```bash
curl -fsSLo /tmp/brew-install.sh https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh && NONINTERACTIVE=1 bash /tmp/brew-install.sh
```

```bash
/home/linuxbrew/.linuxbrew/bin/brew install wl-clipboard
```

The first line is the one use of sudo: Homebrew's installer can't ask
for a password unattended, so the directory is made for the user and
the installer then needs none. The prefix has to be the default,
`/home/linuxbrew/.linuxbrew`, since the arm64 Linux bottles are built
for it alone ([install.md](install.md#homebrew) has the rest of the
why). A new shell has `brew` on `PATH`. wl-clipboard is `wl-copy` and
`wl-paste`, which SteamOS lacks.

To remove Homebrew itself:

```bash
curl -fsSLo /tmp/brew-uninstall.sh https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh && NONINTERACTIVE=1 bash /tmp/brew-uninstall.sh
```

Trust: the installer is `HEAD` of Homebrew's install repository,
unpinned, run once. After that each bottle is checked against the
sha256 in its formula, and the formulae come from Homebrew's git
repository, so a package is as trustworthy as Homebrew.

## zsh

Instructions: <https://formulae.brew.sh/formula/zsh>

```bash
brew install zsh
```

```bash
touch ~/.zshrc && cjf init
```

The second line is for a first install: with a `~/.zshrc` in place zsh
skips its new-user menu, and `cjf init` writes its block only into an
rc file that exists.

## distrobox

Instructions: <https://distrobox.it/#installation>, the curl line with
`--prefix`

```bash
curl -fsSLo /tmp/distrobox-install https://raw.githubusercontent.com/89luca89/distrobox/main/install && sh /tmp/distrobox-install --prefix ~/.local
```

The same line updates it. What makes distrobox work from Desktop Mode
and Frametop's desktop is not here but in `cjf init`: the podman shim
and the block in `~/.distroboxrc`
([shell-init.md](shell-init.md#distroboxrc)).

Trust: nothing is pinned or checked. The script is whatever the `main`
branch of distrobox's repository holds, which may be past the latest
release; GitHub's TLS and distrobox's account are the root. It
installs only into the home directory.

## curiousj-tools

Instructions: <https://github.com/curiousjtuber/curiousj-tools>; uv's
side is <https://docs.astral.sh/uv/guides/tools/>

```bash
uv tool install git+https://github.com/curiousjtuber/curiousj-tools
```

sshtsf, xssh, pssh and the rest. Trust: nothing beyond TLS, a git
checkout built by uv.

## Flatpak apps

Instructions: <https://flathub.org/setup> for the remote, and each
app's page: [Moonlight](https://flathub.org/apps/com.moonlight_stream.Moonlight),
[Deskflow](https://flathub.org/apps/org.deskflow.deskflow),
[Stream Frame](https://streamframe.app/). Those pages install
system-wide through Discover; the lines here are the same apps in the
user installation.

Into the user installation, `~/.local/share/flatpak`: no root and no
polkit, so the lines work over SSH, and a SteamOS update keeps them.
The remote first, once:

```bash
flatpak --user remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

```bash
flatpak --user install flathub com.moonlight_stream.Moonlight
```

```bash
flatpak --user install flathub org.deskflow.deskflow
```

Stream Frame comes from Boxtree's own remote, and its runtime from
Flathub, so it wants both:

```bash
flatpak --user remote-add --if-not-exists stream-frame https://streamframe.app/flatpak/stream-frame.flatpakrepo
```

```bash
flatpak --user install stream-frame com.boxtree.StreamFrame
```

Moonlight and Deskflow use the KDE runtime 6.11, about 400 MB the
first time; Stream Frame the 6.10 one, a few hundred MB more.
[apps.md](apps.md) says what each app is for and how it is set up.

Two things the kit's installer looked after, by hand now:

- **The runtime in the same installation.** A runtime in the system
  installation satisfies a user install, and removing it later breaks
  the app. To have the user installation hold its own:

  ```bash
  flatpak --user install flathub "$(flatpak --user info --show-runtime com.moonlight_stream.Moonlight)"
  ```

- **A second copy.** If Discover installed the app system-wide, the
  user copy wins the menu and `flatpak run`; `sudo flatpak uninstall
  --system APP` removes the other.

`flatpak --user uninstall --unused` removes a runtime nothing uses any
more.

Trust: a remote's `.flatpakrepo` file, fetched once over HTTPS,
carries its GPG key, and flatpak checks every commit against it.
Flathub builds from public manifests with a review step. Stream
Frame's remote is Boxtree's own, so the key and every build come from
one vendor with no third party's review. The sandbox applies to all
three; `flatpak info --show-permissions APP` shows what each reaches.

## Nerd Fonts

Instructions: <https://github.com/ryanoasis/nerd-fonts#font-installation>,
option 1, the release archive

```bash
for f in JetBrainsMono NerdFontsSymbolsOnly; do
    mkdir -p ~/.local/share/fonts/NerdFonts/$f
    curl -fL https://github.com/ryanoasis/nerd-fonts/releases/latest/download/$f.tar.xz |
        tar -xJ -C ~/.local/share/fonts/NerdFonts/$f
done
mkdir -p ~/.config/fontconfig/conf.d
cp ~/.local/share/fonts/NerdFonts/NerdFontsSymbolsOnly/*.conf ~/.config/fontconfig/conf.d/
fc-cache -f
```

The root filesystem is read-only, but fonts don't need it: fontconfig
also reads `~/.local/share/fonts`, under Wayland and X11 alike, and
Flatpak apps see that folder too. It is on `/home`, so SteamOS updates
keep it, and the distroboxes share it.

- **The names** are the release's archives without `.tar.xz`, from the
  [latest release](https://github.com/ryanoasis/nerd-fonts/releases/latest):
  `JetBrainsMono`, `FiraCode`, `Hack`, `Meslo`, and so on. The two
  above are the ones the kit's item installed.
- **`NerdFontsSymbolsOnly`** adds only the icons, so apps left on
  another font show them too. The `cp` line installs the fontconfig
  rule its archive carries, which makes every font fall back to it for
  the icon code points.
- **Afterwards,** restart apps that are already running. In Konsole,
  pick the `… Nerd Font Mono` family, so each icon is one column wide.
- **To update,** run the lines again; they unpack over what is there.
  To remove a font, delete its folder (and the rule in
  `~/.config/fontconfig/conf.d` for the symbols) and run `fc-cache
  -f`.

The kit's item also checked each archive against the release's
`SHA-256.txt`, beside the archives in the same release, and kept the
release tag in a `.version` file per font to tell an old one; a folder
it made still has that file, which nothing reads now.

Trust: GitHub's TLS and the nerd-fonts project. Data, not code, and it
stays in the home directory, so the stakes are low.

## BSManager

Instructions:
<https://github.com/DaVarga/bs-manager/blob/HEAD/docs/steam-frame.md>

```bash
cjf install fuse2
```

```bash
curl -fsSLo /tmp/bsmanager-install.sh https://github.com/DaVarga/bs-manager/releases/latest/download/install.sh && bash /tmp/bsmanager-install.sh
```

```bash
sed -i "s|^Exec=\(env LD_LIBRARY_PATH=[^ ]* \)\?|Exec=env LD_LIBRARY_PATH=$HOME/.local/lib/fuse2 |" ~/.local/share/applications/bs-manager.desktop
```

DaVarga's arm64 fork, through its own installer:
`~/Applications/BSManager.AppImage`, a menu entry and the BeatSaver
OneClick links. The script also takes `--uninstall` and `--appimage
FILE`.

The other two lines are for SteamOS 0.5.7 and later, which dropped
fuse2: an AppImage's runtime loads `libfuse.so.2` to mount itself
(`dlopen(): error loading libfuse.so.2` otherwise). `fuse2` is the
kit's package of that one library ([packages.md](packages.md)), and
the `sed` line gives the menu entry its directory on
`LD_LIBRARY_PATH`. From a shell the kit's init does the same, and the
`bsmanager` command, for a window on the PC, sets it itself. Run the
`sed` line again after running `install.sh` again, since it rewrites
the entry; a second run of the line changes nothing.

Trust: the weakest here. The script is whatever `releases/latest`
points at, unpinned and unchecked; it fetches an AppImage that runs
unsandboxed and then updates itself from the fork's releases. GitHub's
TLS and DaVarga's account are the root, for every later update too,
with no way to tell a replaced release from a new one.

## Full Keyboard

Instructions:
<https://github.com/TaiKeid/steam-frame-full-keyboard#quick-install>,
and [Install manually](https://github.com/TaiKeid/steam-frame-full-keyboard#install-manually)
for the archive

```bash
curl -fLo ~/Downloads/Full_Keyboard_installer-aarch64.AppImage https://github.com/TaiKeid/steam-frame-full-keyboard/releases/latest/download/Full_Keyboard_installer-aarch64.AppImage && chmod +x ~/Downloads/Full_Keyboard_installer-aarch64.AppImage && ~/Downloads/Full_Keyboard_installer-aarch64.AppImage
```

[TaiKeid's keyboard](https://github.com/TaiKeid/steam-frame-full-keyboard)
for the dashboard and local apps. Its releases now ship an installer
of their own (0.19.1 does), an AppImage made to be downloaded in the
Frame's browser and double-clicked; the line above is the same from a
Konsole in Desktop Mode. It is a window with questions (replace the
native keyboard, swipe typing, streaming support), so it wants a
desktop, not an SSH session. It installs under
`~/.local/share/framekeyboard`, updates, downgrades and uninstalls,
and closes a running keyboard first. This line has not been run from here: if the AppImage stops on
`libfuse.so.2`, `cjf install fuse2` and a new shell, as for BSManager.

After that the keyboard updates itself: Settings shows a dot when a
release is out, installs it with one button, and rolls back by itself
if the new one fails to start. That is why the kit no longer tracks
it; until 2026-11-17 `cjf install full-keyboard` fetched the release
archive, checked it against the release's `SHA256SUMS` and ran the
`install.sh` inside.

Over SSH, or to take a given version, that archive route still works
by hand, as the project's README has it (with the keyboard closed):

```bash
cd ~/Downloads
base=https://github.com/TaiKeid/steam-frame-full-keyboard/releases/latest/download
curl -fLO $base/SHA256SUMS
f=$(awk '{print $2}' SHA256SUMS | tr -d '*')
curl -fLO $base/$f
sha256sum -c SHA256SUMS && tar -xzf $f && bash ${f%.tar.gz}/install.sh
```

A manual install leaves native replacement, start with SteamOS and
swipe typing off, where the installer asks. The uninstaller keeps the
settings in `~/.config/framekeyboard` unless given `--purge`.

Trust: GitHub's TLS and TaiKeid's account, for every later update too.
The installer's SHA-256 is in each release's notes and the archive's
in `SHA256SUMS`, but both come from the same release, so they catch a
corrupt download, not a replaced one. It all runs unsandboxed in the
home directory, without root.

## Frametop

Instructions: <https://github.com/Frametop/frametop#install-on-the-headset>

```bash
curl -fsSLo /tmp/frametop-get.sh https://frametop.github.io/frametop/get.sh && bash /tmp/frametop-get.sh --release
```

[Frametop](https://github.com/Frametop/frametop), the multi-screen
Plasma desktop and 3D mouse that run on the Frame itself. Run it from
a Konsole in Desktop Mode. `--release` is the third choice of its
installer's menu: the stable release, already built, as one file,
`Frametop.zip` (about 1.1 GB). `get.sh` downloads it, checks it
against the release's `SHA256SUMS`, unpacks it and runs its
`install-release.sh`, which checks this SteamOS build against the
releases' table, loads the podman image and installs under
`~/.local/share/frametop/releases/<version>`: nothing compiles on the
headset. Without `--release` it asks, and the first two choices clone
the repository into `~/frametop` and build there, the route the
project's own `pack/README.md` calls the weak point.

- **Options** go after `--release`: `--version V` for a given release,
  `--experimental` for the newest of any kind, `--any-steamos` to
  install on a build the release is marked broken on. `get.sh`'s
  header lists the rest.
- **The two sudo parts** are offered, not forced: Frametop's own eye
  tracker, a root service in `/etc/frametop`, and the Bluetooth fixes
  in `/etc/steamframe`. Everything else goes in the home directory.
  SteamVR restarts once at the end.
- **Which release is installed:**
  `readlink ~/.local/share/frametop/releases/current`; `cjf
  after-update` prints it too.
- **To update,** Update Frametop in the launcher's Frametop entry, or
  the line above again.
- **To remove,** Frametop's own uninstaller, twice, with a restart
  between:

  ```bash
  curl -fsSLo /tmp/frametop-uninstall.sh https://frametop.github.io/frametop/uninstall.sh && bash /tmp/frametop-uninstall.sh
  ```

- **A source checkout** in `~/frametop` is left alone, but the
  launcher's Desktop entry and the services switch to the release;
  that checkout's `install.sh` switches them back.

What the kit's item added, and what is gone with it: it recorded the
sha256 of one release's zip and refused any other, so that what
installed was the artifact that had been checked, not whatever the
account published next. For 0.2.2 that is
`2afa2a949010a05f98bd5181bb2bebe34778fff9d57c3a8a4e042da1a366588e`;
`sha256sum` of a `Frametop.zip` from
<https://github.com/Frametop/frametop/releases/tag/v0.2.2> shows
whether it is still that file. `get.sh` checks against the release's
own `SHA256SUMS`, which catches a corrupt download, not a replaced
release.

Trust: GitHub's TLS and the Frametop organization's account; nothing
is signed. [TRUST.md](TRUST.md#frametop) has what was found when
release 0.2.2 was checked end to end, and how much of the headset
Frametop gets.

## WayVR

Instructions: <https://github.com/wayvr-org/wayvr#installing-on-steam-frame>

[WayVR](https://github.com/wayvr-org/wayvr) puts apps around you as
overlays, each window its own, from a Wayland compositor inside it.
Never a catalog item. Upstream calls its Steam Frame support
experimental. The aarch64 AppImage is a nightly: an artifact of the
[Build AppImage](https://github.com/wayvr-org/wayvr/actions/workflows/build-appimage.yml)
workflow's topmost green run, `WayVR-main-aarch64.AppImage.zip`, which
GitHub hands out only to a logged-in account, so it is a browser
download, not a curl line. Then
[Gear Lever](https://flathub.org/apps/it.mijorus.gearlever) installs
it:

```bash
flatpak --user install flathub it.mijorus.gearlever
```

```bash
unzip WayVR-main-aarch64.AppImage.zip && flatpak run it.mijorus.gearlever --integrate WayVR-aarch64.AppImage
```

That leaves `~/AppImages/wayvr.appimage` and a menu entry,
`~/.local/share/applications/wayvr.desktop`, which upstream's page
says how to edit. Settings and the saved layout are in
`~/.config/wayvr/conf.d`. Its AppImage runs without `fuse2`.

### wayvrctl, and a window of a given size

WayVR's launcher offers four pixel counts (480p to 1440p) in five
shapes. `wayvrctl`, its command-line client, takes any size, but it
is not in the AppImage and upstream's releases build it for x86_64
only. So it is built on the Frame, with cargo ([rust](#rust)), about
four minutes:

```bash
git clone https://github.com/wayvr-org/wayvr ~/src/wayvr
```

```bash
cd ~/src/wayvr && cargo build --release -p wayvrctl && install -m755 target/release/wayvrctl ~/.local/bin/
```

Build it from the AppImage's own commit, since the two speak one
protocol: WayVR's first log line names it ("Welcome to wayvr v.
26.8.0-2df0c63"), and `git checkout` takes it. After a newer
AppImage, `git pull` and the second line again.

```bash
wayvrctl process-launch --resolution 2560x1080 --pos floating --env QT_QPA_PLATFORM=wayland -- krdc rdp://HOST
```

Measured on 2026-11-17, commit 2df0c63, sizes read back through
`wayvrctl`:

- **Exact up to 2560x1440.** 1500x700 gave the app 1500x700;
  3840x1080 gave 2560x1080. The cap is WayVR's one virtual output,
  a constant (`WAYVR_SCREEN_RES` in `wayvr/src/backend/wayvr/mod.rs`).
  For more, `cjf panel` ([panel.md](panel.md)).
- **A saved size wins.** WayVR keeps each app's last window size in
  `zz-saved-state.json5` (`WindowSize`, by app ID) and gives a new
  window that, whatever `--resolution` says. An app that was never
  resized there has none.
- **A window that is up** takes a size too. The name is from
  `wayvrctl window-list`, and this size is the overlay's, WayVR's
  frame included: 10 wider and 58 taller than the app's.

  ```bash
  wayvrctl window-attrib "wayvr/app/15:org.kde.dolphin" set window_size 1510x758
  ```

- **It is a first size, not a screen.** The app may resize itself
  within the output, unlike in a panel.
- **`--env`** takes its variables separated by commas. `--name` did
  not show in `process-list`, which had the command's name.

To start WayVR from SSH or a service, not from its menu entry:

```bash
systemd-run --user --setenv=LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 ~/AppImages/wayvr.appimage
```

Without the variable it stops with "Will not use OpenVR: Context init
failed": the `libopenvr_api.so` in the AppImage loads SteamVR's client
from `/opt/steamvr/bin/linux64`, the x86-64 one. SteamVR's own arm64
`libopenvr_api.so`, found first, loads the right one.

Trust: a nightly of the `main` branch, unsigned and unpinned, from
GitHub's Actions storage; GitHub's TLS and the wayvr-org account are
the root. It runs unsandboxed and makes a uinput device, so it can
type and click as you. `wayvrctl` is built from the same repository's
source, with its crates from crates.io by `Cargo.lock`.
