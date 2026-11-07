# Installing things: the catalog, and how setup.sh did it

The kit installs optional things from its catalog: `cjf install NAME`,
`cjf install` bare to pick, `cjf installed` for every item's state as
the Frame has it, `cjf outdated` for the same against each upstream
(the network), `cjf update` to install what that finds newer, `cjf
uninstall NAME`, and `cjf install --help` for each item's options.
[TRUST.md](TRUST.md) says what each item checks. The sections below
are the README's from before the kit, kept for the reasons behind each
part: what `setup.sh` did, and Homebrew and Nerd Fonts in particular.
Where they name `setup.sh --x` or an `install-*.sh`, read `cjf install
x`; the `arch` distrobox and its box routes are gone (the host route
is the one).

## Setup

Since stage 4 of the reorganization `setup.sh` is gone: `cjf init` is
the base, and every optional part is a catalog item installed with
`cjf install NAME`, picked from `cjf install` bare, and listed by `cjf
installed`. The text below describes the `setup.sh` options the catalog
replaced; its reasons still hold, and the docs are rewritten in stage 6.

```bash
~/steam-frame-utils/setup.sh
```

With no options, on a terminal, it is an interactive installer: it goes
through the options below in its usual order, and each part that is
installed shows as `ok`, while each part that is missing is asked about
there and installed right away. emacs and waypipe are asked as host, box
or neither. Every change is asked about before it is made: a copy, a
backup or an install on its own line (`copy ~/.config/...? [Y/n]`), and
a change to `~/.bashrc`, `~/.zshrc`, `~/.profile` or `~/.distroboxrc`
with its diff, the file copied to `<file>.bak-<timestamp>` before the
run first changes it. A part just taken up isn't asked again for each of
its steps. Enter takes the default: for a missing part, yes on a first
run (the [fresh-Frame](install.md#a-fresh-frame) set) and no on a re-run, so
pressing Enter through a re-run adds nothing; for a change to what is
there, yes. Switching a route in place takes the option. Inside a
distrobox it asks only what the box allows. Without a terminal, or with
any option, it asks nothing.

```bash
~/steam-frame-utils/setup.sh --check
```

```bash
~/steam-frame-utils/setup.sh [--brew] [--zsh] [--arch] [--emacs[=host|box]] [--waypipe[=host|box]] [--mise] [--packages[=NAME,...]] [--tailscale[=trust]] [--nerd-fonts[=NAME,...]]
```

`--check` reports what would change and changes nothing. A re-run
touches only what is missing or out of date, so after pulling this repo,
run it again.

Always, whatever the options:

| What | How |
|---|---|
| `~/.local/bin` first in `PATH` | adds `export PATH=~/.local/bin:$PATH` to `~/.bashrc` and `~/.profile`, unless a line there already puts `~/.local/bin` on `PATH` |
| distrobox | installs into `~/.local` if `~/.local/bin/distrobox` is missing |
| `bin/` | goes on `PATH` from this checkout, through `shell-init/bin.sh` (see [Shell init](shell-init.md#shell-init)), so a `git pull` updates its scripts. A copy in `~/.local/bin` from an earlier version would come first, so it is backed up to `<file>.bak-<timestamp>` |
| the shell init | `cjf init` writes `~/.local/share/curiousj-framekit/init.sh` and the block at the top of `~/.bashrc`, and of `~/.zshrc` if that exists, that sources it (see [Shell init](shell-init.md#shell-init)) |

Options add the rest, and each one also fixes only what's missing:

| Option | What |
|---|---|
| `--brew` | Homebrew in `/home/linuxbrew/.linuxbrew` if it isn't there, wl-clipboard (`wl-copy` and `wl-paste`) from it, and `shell-init/brew.sh` in the block at the top of `~/.bashrc` and `~/.zshrc` (see [Homebrew](install.md#homebrew)). Uses sudo once, to create `/home/linuxbrew`. Refused inside a distrobox |
| `--zsh` | implies `--brew`. zsh from Homebrew, and an empty `~/.zshrc` if there is none, so zsh skips its new-user menu |
| `--arch` | creates the `arch` distrobox from `docker.io/menci/archlinuxarm:latest`, Arch Linux ARM, if it doesn't exist (see [Arch-based distrobox images for arm64](arch-distrobox-images.md) for why that image, and for the pacman sandbox the box is created without). The image is about 0.7 GB and the first start takes a few minutes, so it says so and asks first; `--yes` skips the question |
| `--emacs` | emacs from one of two sources (see [emacs and waypipe: host or box](install.md#emacs-and-waypipe-host-or-box)). `=host`: `pkgbuilds/frame/emacs/` built here and installed under `~/.local` by `pacman-home`, the same as `--packages=emacs-wayland`. `=box`: implies `--arch`; emacs-wayland, the pgtk build, in the box, with `emacs` and `emacsclient` exported to `~/.local/bin` (an export left by another box is replaced; anything else there is left alone). Bare, it keeps the route in place, host when there is none. Switching asks before replacing what is there; `--yes` answers |
| `--waypipe` | waypipe for the host from one of two sources (same section), and `shell-init/waypipe.sh` in `~/.bashrc` and `~/.zshrc` (see [The waypipe function](shell-init.md#the-waypipe-function)). `=host`, or `=arch`, its old name: Arch Linux ARM's package relocated under `~/.local` by `install-waypipe.sh` through `pacman-home`; it doesn't update waypipe, `install-waypipe.sh` does. `=box`: implies `--arch`; a copy of the box's `/usr/bin/waypipe`, the same package, which pacman in the box keeps current (`distrobox upgrade arch`) and a re-run refreshes. Bare and switching as for `--emacs` |
| `--mise` | [mise](https://mise.jdx.dev) in `~/.local/bin` if it isn't there, `shell-init/mise.sh` in the `end` block of `~/.bashrc` and `~/.zshrc` unless the file activates mise already, and rust through it, `mise use -g rust`, for a Rust package in `pkgbuilds/frame/` (see [mise](shell-init.md#mise)). It doesn't update the tools; `mise upgrade` does |
| `--packages` | the packages in `pkgbuilds/frame/`, built with makepkg and installed with `pacman-home`: each one `pacman-home` doesn't have at its PKGBUILD's version, in dependency order (see [Packages for the host](packages.md#packages-for-the-host)); `--packages=NAME,...` for some of them. A Rust package needs `--mise` for cargo |
| `--tailscale` | fixes what's missing of the install, with sudo: `install-tailscale.sh` if the binaries or the unit are gone, otherwise just `systemctl enable`/`start`. Adds `shell-init/tailscale.sh`. `--tailscale=trust` also puts `tailscale0` in firewalld's `trusted` zone. Logging in is only reported. Without the option, what's missing is still reported |
| `--nerd-fonts` | runs `install-nerd-fonts.sh` for each font not installed yet: `JetBrainsMono` and `NerdFontsSymbolsOnly`, or a comma-separated list such as `--nerd-fonts=FiraCode,Hack`. It doesn't update installed ones; `install-nerd-fonts.sh` does that |

The rest of the setup, such as mise and tmux, is personal and not part
of this.

The host and its distroboxes share the home directory, so `setup.sh`
runs inside a distrobox too. What needs the host is refused there:
`--tailscale`, `--brew`, `--zsh`, `--packages` and `--emacs=host`, and
`--arch`, `--emacs=box` and `--waypipe=box` in any box but `arch`. From
the host, the box's part of `--emacs=box` and `--waypipe=box` runs
through `distrobox enter arch`.

### emacs and waypipe: host or box

Both come in two forms, and both forms put the same names in
`~/.local/bin`, so one is in place at a time. The **host** route, the
default, is `pacman-home`'s: emacs built from `pkgbuilds/frame/emacs/`
on the Frame itself, waypipe relocated from Arch Linux ARM's package
(see [Packages for the host](packages.md#packages-for-the-host)). It needs no
container to start, sees the Frame's own `/usr`, D-Bus and processes,
and is updated by a rebuild (`--packages`) or by `install-waypipe.sh`;
what it cannot do is run inside a distrobox, where the host's libraries
aren't ([docs/home-packages.md](home-packages.md)). The **box**
route is the `arch` distrobox's: emacs-wayland installed there with
`emacs` and `emacsclient` exported, waypipe copied out. Its emacs starts
through `distrobox enter` and sees the box's `/usr`, but works from the
host and from every box alike, and pacman in the box keeps both current.

`setup.sh` reads which route is in place from the files themselves:
`pacman-home` owns the host route's, the box's emacs is a distrobox
export, its waypipe a plain copy nothing owns. A bare `--emacs` or
`--waypipe` keeps what it finds and takes host when there is nothing;
`=host` or `=box` against the other route asks before replacing it
(`pacman-home -R`, or removing the exports or backing the copy up),
`--yes` answers, and with no terminal the installed route stays.
`--packages` skips emacs-wayland while the box's export is in place;
`--emacs=host` is the switch.

`bin/` and `shell-init/` are used from the checkout: `bin/` goes on
`PATH`, and the rc files source `shell-init/`, so a `git pull` updates
both. Other files are copied, not linked, so they keep working if this
checkout moves or goes. A file that differs is moved to
`<file>.bak-<timestamp>` first. Inserted text sits between `# >>>
steam-frame-utils: <name> >>>` and `# <<< … <<<` markers, and a re-run
replaces it in place; edit the source here, not the copy. A shell-init
file isn't inserted into an rc file that already defines the same alias
or function some other way.


## A fresh Frame

The whole of this on a new Frame, from a clone at `~/steam-frame-utils`:

```bash
~/steam-frame-utils/setup.sh --brew --zsh --waypipe --mise --packages --tailscale=trust --nerd-fonts
```

That is one run: `~/.local/bin` on `PATH`, distrobox, the cursor fix and
the rc blocks; Homebrew with zsh and wl-clipboard; waypipe relocated
from Arch Linux ARM; mise with rust; the package in `pkgbuilds/frame/`,
emacs, built here and installed under `~/.local`
(`--emacs=box --waypipe=box` in place of `--packages`'s emacs and
`--waypipe` take the distrobox route instead, see [emacs and waypipe:
host or box](install.md#emacs-and-waypipe-host-or-box)); Tailscale as a system
service, which asks for sudo and then for a login in a browser; and the
fonts. The builds take about six minutes in all. The apps under `apps/`
are separate installers, run by hand; `--arch` creates the arch
distrobox, which only the box route needs. Not in this repo: Steam's own
settings, the emacs configuration, mise tools beyond rust, and anything
written into `~/.bashrc` by hand.

## Homebrew

`setup.sh --brew` installs Homebrew with its official installer, in the
default prefix `/home/linuxbrew/.linuxbrew`. Homebrew builds its arm64
Linux bottles for that prefix only; anywhere else, every formula builds
from source. `/home` is its own partition, so the install survives
SteamOS updates. The installer can't ask for a sudo password when it
runs unattended, so `setup.sh` creates `/home/linuxbrew` for the
`steamos` user first, and the installer then needs no sudo at all.

Homebrew supports arm64 Linux in full only on Ubuntu, so on SteamOS it
is unsupported, though it works: the Frame's glibc 2.39 is the minimum
the bottles need. zsh comes from here rather than a distrobox, which
starts it in about half the time, and so does wl-clipboard, which
SteamOS lacks. emacs is built for the host from `pkgbuilds/frame/emacs/`
or exported from the arch box, and waypipe is Arch Linux ARM's package,
relocated or copied from that box: Homebrew's emacs is terminal-only,
and it has no waypipe.

`shell-init/brew.sh` runs `brew shellenv` unless Homebrew's `bin` is on
`PATH` already. It goes in the block at the top of the rc files, so
`~/.local/bin`, put on `PATH` further down, stays ahead of Homebrew. A
distrobox doesn't see `/home/linuxbrew`, so there it does nothing.

## Nerd Fonts

```bash
~/steam-frame-utils/install-nerd-fonts.sh [NAME...]
```

The root filesystem is read-only, but fonts don't need it. fontconfig
also reads `~/.local/share/fonts`, under Wayland and X11 alike, and
Flatpak apps see that folder too. It's on `/home`, so SteamOS updates
keep it, and the distroboxes share it.

- **NAME** is a release archive without `.tar.xz`, from the [latest
  release](https://github.com/ryanoasis/nerd-fonts/releases/latest):
  `JetBrainsMono`, `FiraCode`, `Hack`, `Meslo`, and so on. With no NAME,
  it installs `JetBrainsMono` and `NerdFontsSymbolsOnly`.
- **Each font** goes in `~/.local/share/fonts/NerdFonts/NAME`, along
  with the release tag in `.version`. A re-run replaces only fonts older
  than the latest release, and checks each archive against the release's
  `SHA-256.txt`.
- **`NerdFontsSymbolsOnly`** adds only the icons, so apps left on
  another font show them too. Its fontconfig rule goes in
  `~/.config/fontconfig/conf.d`, and makes every font fall back to it
  for the icon code points.
- **Afterwards,** restart apps that are already running; the script
  lists the new families. In Konsole, pick the `… Nerd Font Mono`
  family, so each icon is one column wide.

To uninstall a font, delete its folder and run `fc-cache -f`. The
script's header comment has the steps.
