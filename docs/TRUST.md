# How far to trust what the kit installs

What each catalog item fetches, who is trusted at the root, and what
would catch a changed download, as the catalog records it
(`cjf installed --trust` prints the same two columns). The table is
generated from `install/catalog.toml`; a test keeps them in step. The
sections below were checked on 2026-10-15 against the scripts the kit
replaced, and hold for the kit's kinds, which do the same steps. ALARM
is Arch Linux ARM.

| Item | Root of trust | What's checked |
|---|---|---|
| `cursor` | this kit | nothing to fetch: two files in the home directory |
| `tailscale` | pkgs.tailscale.com, Tailscale | the tarball against the .sha256 beside it |
| `homebrew` | Homebrew's git repository and bottles | each bottle against the sha256 in its formula; the installer itself is curl | bash of HEAD, run once |
| `zsh` | Homebrew | the bottle against the sha256 in its formula |
| `rust` | mise's download checks, rust-lang.org | mise's own |
| `nerd-fonts` | GitHub's TLS, the nerd-fonts project | each archive against the release's SHA-256.txt; data, not code |
| `waypipe` | Arch Linux ARM's Build System key, pinned by fingerprint in pacman-home | the package's PGP signature, by pacman; the keyring once, against the pinned fingerprint |
| `emacs` | gnu.org's release tarball, your review of the PKGBUILD | the BLAKE2 sum in the PKGBUILD, by makepkg |
| `pacman` | gitlab.archlinux.org's release tarball, your review of the PKGBUILD | the BLAKE2 sum in the PKGBUILD, by makepkg |
| `distrobox` | GitHub's TLS, distrobox's account | nothing: curl | sh of the main branch, unpinned |
| `curiousj-tools` | GitHub's TLS, curiousjtuber's account | nothing beyond TLS: a git checkout built by uv |
| `frametop` | GitHub's TLS and the Frametop organization's account | the release zip against the sha256 recorded here, then the image inside against the zip's own metadata |
| `stream-frame` | Boxtree's GPG key, fetched once over HTTPS from streamframe.app | every commit's signature, by flatpak |
| `moonlight` | Flathub's GPG key, fetched once over HTTPS | every commit's signature, by flatpak |
| `krdc` | download.kde.org's release tarballs and qtkeychain's GitHub repository, your review of the PKGBUILD and the patch | the BLAKE2 sums in the PKGBUILD, by makepkg; qtkeychain by the commit pinned there |
| `deskflow` | Flathub's GPG key, fetched once over HTTPS | every commit's signature, by flatpak |
| `krdp` | KDE and FreeRDP's release tarballs, your own review of the manifest and patches | every source pinned by sha256 in the manifest; patches in this kit; built on KDE's SDK from Flathub |
| `bsmanager` | GitHub's TLS and DaVarga's account, continuously | nothing: the fork's latest install.sh, then an AppImage that updates itself |
| `full-keyboard` | GitHub's TLS and TaiKeid's account | the archive against the release's own SHA256SUMS |

Nothing runs as root except Tailscale, the one-time creation of
`/home/linuxbrew`, and Frametop's two optional parts. The common root
of trust is TLS to GitHub, gnu.org, download.kde.org,
pkgs.tailscale.com, Flathub, streamframe.app and one ALARM mirror, plus
each project's own account.
Everything is in the open: the kit's kinds are in `install/kinds/`, the
flatpaks have public manifests, and the GitHub apps have public source.
What differs is whether anything stands between a changed upstream
artifact and your headset.

## The base: mise, uv, the kit

`install.sh` fetches mise's installer from mise.run and runs it, then
`mise use -g uv fzf`, trusting mise's download checks, and installs the
kit with `uv tool install` from GitHub over TLS. None of it is pinned
beyond TLS and the accounts; all of it stays in the home directory.

## The pkgbuilds

Emacs and pacman come from gnu.org and gitlab.archlinux.org as release
tarballs with BLAKE2 sums in the PKGBUILD, so a changed tarball fails
makepkg. They build on the host against its own libraries and install
under `~/.local` with `pacman-home -U`, no root. `homeify` fetches
Arch's or the AUR's PKGBUILD and prints the rewrite for review before
anything builds, so a person is in the loop. This is the same tier as
KRdp's server among the apps.

## Tailscale and Nerd Fonts

Both download a release and check it against a sha256 published beside
it. That catches a corrupt download, not a replaced release, since the
sum comes from the same place. Tailscale's tarball comes from
pkgs.tailscale.com and installs as a root system daemon, so the trust is
Tailscale's TLS and Tailscale itself. Nerd Fonts are data rather than
code and stay in the home directory, so the stakes are low.


## Homebrew

Bottles are checked against the sha256 in each formula, and formulae
come from Homebrew's git repository, so a package is as trustworthy as
Homebrew. The installer itself is `curl | bash` of `HEAD` of Homebrew's
install repository, unpinned, run once.

## waypipe for the host

`cjf install waypipe` goes through `pacman-home relocate`, which takes
ALARM's package only with a valid signature (`SigLevel = Required`). The
keys come from ALARM's `archlinuxarm-keyring` package, fetched once with
signatures off, since there is nothing to check it with yet; what stands
in for that is the fingerprint of ALARM's Build System key, recorded in
`pacman-home` and checked against archlinuxarm.org on 2026-10-15, which
a keyring that trusts other keys fails. From then on a mirror can only
serve what that key signed: on the Frame, a package with one byte
changed was refused on its signature. ALARM's databases aren't signed,
so which versions exist is still the mirror's word, as with every
pacman. Until 2026-10-15 this route ran with `SigLevel = Never` and the
database's checksum alone.

## distrobox

Both are `curl | sh` with nothing pinned. distrobox's install script is
fetched from the `main` branch of its GitHub repository, so what runs
changes with every upstream commit; Frametop, by contrast, pins
distrobox to a commit. mise comes from mise.run, and `mise use -g rust`
then pulls the Rust toolchain through mise, trusting mise's own download
checks. Both install only into the home directory, which limits the
blast radius, but it is the same pattern BSManager is marked weakest for
among the apps.

## What would raise the floor, for the base and the host packages

- A pinned release and recorded sha256 for distrobox's installer, as
  Frametop does, and the same for mise.
- A digest for the arch image.

## KRdp's server

`cjf install krdp` builds from
the manifest the kit ships, `src/curiousj_framekit/data/krdp/io.github.curiousjtuber.Krdp.yml`. Every source is a release
tarball from download.kde.org or GitHub with its sha256 in the manifest,
and the two patches live in this repo. The build runs on KDE's SDK
pulled from Flathub by flatpak-builder. A changed tarball fails the
build instead of installing. The CI bundle built on GitHub's arm64
runner carries an attestation as well. The sandbox holds the network,
the GPU, flatpak's Wayland socket, PipeWire and `~/.config/krdpd`
read-only.

## KRDC

`cjf install krdc` builds KRDC from the kit's PKGBUILD,
`src/curiousj_framekit/data/pkgbuilds/krdc/`, the same tier as Emacs
and pacman: the KDE Gear tarball and the extra-cmake-modules tarball
come from download.kde.org with their BLAKE2 sums in the PKGBUILD,
recorded after a check against the KDE release signatures, so a
changed tarball fails makepkg; qtkeychain is a git source pinned to a
commit, which makepkg checks out and nothing else. The patch is in
this repo for review, with its own sum. The package installs under
`~/.local` through `pacman-home -U`, unsandboxed, as a distribution's
KRDC would be. Until 2026-11-03 this item was the Flathub flatpak,
under the trust below; a copy of it stays installed and shadowed.

## Moonlight and Deskflow

The remote is added from Flathub's `.flatpakrepo` file over HTTPS. That
file carries Flathub's GPG key, and flatpak checks every commit it pulls
against it. Flathub builds from public manifests with a review step. The
trust is Flathub's signing key, the first HTTPS fetch of it, and the
upstream project. `flatpak info --show-permissions APP` shows what each
sandbox reaches.

## Stream Frame

The same mechanism, but the remote is Boxtree's own at streamframe.app,
so the key and every build come from one vendor with no third party's
review. The trust is the first HTTPS fetch of their repo file and then
Boxtree outright. Flatpak's sandbox still applies.

## Frametop

`cjf install frametop` takes Frametop's release route, not its `curl |
bash` one. Release 0.2.2 was checked end to end on 2026-10-15; this is
what was found.

**The release artifact is coherent.** The zip's sha256 matches GitHub's
server-computed asset digest, the release's `SHA256SUMS` and the
FrameDrop manifest. The `frametop-image.tar` inside matches the sha256
in `frametop-release.json`, and the OCI config digest matches the
recorded image ID. The zip's four scripts (`install-release.sh`,
`frametop-install.sh`, `progress.py`, `askpass`) are byte-identical to
the tagged commit `24a86dc`, and so is the whole source tree in the
image's `/src/frametop`, with only the `build/` outputs added. The
installer's recorded sha256 is that zip.

**The build is pinned and meant to be reproducible.** The release
workflow runs only on `v*` tags, with every GitHub Action pinned to a
commit SHA. The Containerfile pins the Fedora toolbox base image by
digest, Python packages by `uv.lock`, OpenVR to a tagged release with
checked hashes, and distrobox to a commit. The Fedora packages dnf
installs are the one input that isn't pinned. The zip is built with
fixed timestamps so the same inputs give the same file. Nobody outside
the project has reproduced it yet.

**Nothing is signed.** The commits and the v0.2.2 tag are unsigned. The
release is drafted by the Actions bot and published by a person. There
is no build-provenance attestation. The root of trust is GitHub's TLS
plus control of the Frametop organization, which is one person's
project: DeeJanuz wrote about nine tenths of the commits, the
organization was created on 2026-10-08, and the repository moved into it
the day after. The recorded sha256 in the installer turns that into "the
artifact that was checked" rather than "whatever the account publishes
next"; `--version` gives that up and says so.

**The build runs on a third party's machines.** Depot's arm64 runners,
not GitHub-hosted ones. Depot can see the build and could in principle
alter it. Reproducibility is the counter, once someone reproduces it.

**It gets a lot of the headset.** A SteamVR driver loaded into vrserver,
user services for the input relay, pointer and power, a container made
from the image through distrobox with the usual host access, and the
desktop session. Two optional parts need root and are offered, not
forced: the eye tracker's frame grabber, installed as a root service
under `/etc/frametop`, and the Bluetooth fixes under `/etc/steamframe`.
Both are kept through SteamOS updates by `/etc/atomic-update.conf.d`
entries. Hand tracking, when turned on, gives its camera broker
`cap_sys_ptrace`, `cap_perfmon` and `cap_dac_read_search`.
`--no-eye-tracker` and `--no-bluetooth` refuse the root parts.

**What leaves the headset.** Nothing phones home. The outbound calls in
the tree are the release downloads, the fetch of `pack/steamos.json`
from the repository's main branch at install time (data only, parsed and
used to say tested, untested or broken; the zip's copy serves offline,
and `FRAMETOP_STEAMOS_TABLE=none` turns the fetch off), and the Hand
Recorder's upload of hand recordings to a Hugging Face dataset, which
asks for consent and a login first and is not part of the stable
release.

**Frametop's own route is weaker.** The one-liner pipes `get.sh` from
GitHub Pages into bash, clones a branch head, and builds on the headset
in a Fedora container that pulls unpinned packages; the project's own
`pack/README.md` calls that recipe the weak point. The release route is
the maintainer's answer to it, and this installer adds the pin.

## Full Keyboard

`cjf install full-keyboard` checks the archive against the release's
`SHA256SUMS`, but that file comes from the same release, so it only
catches a corrupt or truncated download. Whoever can replace the archive
can replace the sums. The archive's `install.sh` then runs unsandboxed
in the home directory. The trust is GitHub's TLS and TaiKeid's account.

## BSManager

`cjf install bsmanager` fetches whatever `releases/latest` points at and
runs it, unpinned and unchecked: curl-pipe-bash with an extra step. That
script fetches an AppImage, which runs unsandboxed and then updates
itself from the fork's releases. The trust is GitHub's TLS and DaVarga's
account, for every later update too, with no way to tell a replaced
release from a new one.

## What would raise the floor, for the apps

- A recorded sha256 in `cjf install bsmanager` for a pinned release, and
  one in `cjf install full-keyboard` beside the release's own sums, so a
  replaced release fails there as it does for Frametop.
- Upstream, for Frametop: signed tags, GitHub's build-provenance
  attestation on the release, and an independent reproduction of the
  zip.
