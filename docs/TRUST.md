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
| `waypipe` | Arch Linux ARM's Build System key, pinned by fingerprint in pacman-home | the package's PGP signature, by pacman; the keyring once, against the pinned fingerprint |
| `emacs` | gnu.org's release tarball, your review of the PKGBUILD | the BLAKE2 sum in the PKGBUILD, by makepkg |
| `krdc` | download.kde.org's and pub.freerdp.com's release tarballs, LibVNCServer's GitHub tag archive and qtkeychain's GitHub repository, your review of the PKGBUILD and the patches | the BLAKE2 sums in the PKGBUILD, by makepkg; qtkeychain by the commit pinned there |
| `fuse2` | libfuse's GitHub release tarball, your review of the PKGBUILD | the BLAKE2 sums in the PKGBUILD, by makepkg |
| `krdpserver` | download.kde.org's release tarballs and qtkeychain's GitHub repository, your review of the PKGBUILD and the patches | the BLAKE2 sums in the PKGBUILD, by makepkg; qtkeychain by the commit pinned there |
| `gamescope-panel` | the gamescope, wlroots, openvr and other git repositories on GitHub and freedesktop.org, your review of the PKGBUILD and the patch | every git source pinned to a commit in the PKGBUILD, glm and stb to the revisions in gamescope's wrap files; the patch's BLAKE2 sum, by makepkg |
| `xwayland-satellite` | xwayland-satellite's GitHub repository and crates.io, your review of the PKGBUILD | the git source pinned to a commit in the PKGBUILD; every crate by the checksum in Cargo.lock, by cargo --locked |
| `wayvr` | WayVR's GitHub repository, crates.io and the git repositories its Cargo.lock names, your review of the PKGBUILD and the patches | the git source pinned to a commit in the PKGBUILD; every crate by the checksum or commit in Cargo.lock, by cargo --locked; the patches' BLAKE2 sums, by makepkg |

`cjf outdated` asks the same sources for their newest version and
changes nothing; `cjf update` then installs through the same steps as
`cjf install`, so the table holds for an update too. Nothing the kit
installs runs as root except Tailscale. The common root of trust is
TLS to GitHub, gnu.org, download.kde.org, pkgs.tailscale.com and one
ALARM mirror, plus each project's own account.
Everything is in the open: the kit's kinds are in `install/kinds/`,
and every source has public code.
What differs is whether anything stands between a changed upstream
artifact and your headset.

What a package manager installs, or an upstream's own instructions,
is no longer in the catalog, so not in this table: rust through mise,
Homebrew and zsh, distrobox, curiousj-tools, the Flatpak apps
(Moonlight, Deskflow, Stream Frame), Nerd Fonts, BSManager, Full
Keyboard and Frametop. [simple-installs.md](simple-installs.md) has
each one's commands, its upstream's page and its trust; BSManager's
and distrobox's unpinned installers are the weakest of them. Frametop
keeps its section below, for what was found in its release.

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

## Tailscale

The kit downloads a release and checks it against a sha256 published
beside it. That catches a corrupt download, not a replaced release,
since the sum comes from the same place. The tarball comes from
pkgs.tailscale.com and installs as a root system daemon, so the trust
is Tailscale's TLS and Tailscale itself.


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

## What would raise the floor, for the base and the host packages

- A pinned release and recorded sha256 for mise's installer.
- A digest for the arch image.

## KRdp's server

`cjf install krdpserver` builds krdp 6.6.7 from the kit's PKGBUILD,
`src/curiousj_framekit/data/pkgbuilds/krdpserver/`, the same tier as
KRDC below: the krdp, kpipewire and extra-cmake-modules tarballs come
from download.kde.org with their BLAKE2 sums in the PKGBUILD, recorded
after a check against the Plasma and Frameworks release signatures;
qtkeychain is a git source pinned to a commit; the two patches are
in this repo with their sums. It links the host's FreeRDP and
Frameworks and installs under `~/.local` through `pacman-home -U`,
unsandboxed, as a distribution's krdp would be; KWin grants it the
screencast and input interfaces through the desktop file the package
puts in `~/.local/share/applications`, as it would any client it can
match to one.

## KRDC

`cjf install krdc` builds KRDC from the kit's PKGBUILD,
`src/curiousj_framekit/data/pkgbuilds/krdc/`, the same tier as Emacs
and pacman: the KDE Gear tarball and the extra-cmake-modules tarball
come from download.kde.org with their BLAKE2 sums in the PKGBUILD,
recorded after a check against the KDE release signatures, so a
changed tarball fails makepkg; FreeRDP's tarball, the package's own
copy of the library since 2026-11-11, comes from pub.freerdp.com the
same way, its sum recorded after a check against its maintainer's
signature; LibVNCServer's, for the VNC backend since 2026-11-12, is
GitHub's archive of the release tag, which nobody signs: its sum was
recorded after a check that the archive holds the files of the tag's
commit, the one Arch's libvncserver package pins by checksum;
qtkeychain is a git source pinned to a commit, which
makepkg checks out and nothing else. The four patches, three of KRDC
and one of FreeRDP, are in this repo for review, each with its own
sum. The package installs under
`~/.local` through `pacman-home -U`, unsandboxed, as a distribution's
KRDC would be. Until 2026-11-03 this item was the Flathub flatpak,
under Flathub's trust
([simple-installs.md](simple-installs.md#flatpak-apps)); a copy of it
stays installed and shadowed.

## Frametop

Frametop is installed by its own instructions now
([simple-installs.md](simple-installs.md#frametop)), by their release
route, `get.sh --release`, not the build on the headset. Until
2026-11-17 `cjf install frametop` took the same release with one
thing added, a sha256 recorded for the version it named. Release 0.2.2
was checked end to end on 2026-10-15; this is what was found.

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
the day after. The sha256 the kit's installer recorded turned that into
"the artifact that was checked" rather than "whatever the account
publishes next"; `get.sh` has only the release's own `SHA256SUMS`, so
that is given up, and simple-installs.md keeps the 0.2.2 sum to
compare by hand.

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

**Frametop's default route is weaker.** The one-liner pipes `get.sh`
from GitHub Pages into bash, and its first two choices clone a branch
head and build on the headset in a Fedora container that pulls
unpinned packages; the project's own `pack/README.md` calls that
recipe the weak point. The release route is the maintainer's answer to
it. `get.sh` itself is fetched from GitHub Pages unpinned either way.

## What would raise the floor, for the apps

- Upstream, for Frametop: signed tags, GitHub's build-provenance
  attestation on the release, and an independent reproduction of the
  zip.
