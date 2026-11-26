#!/usr/bin/env bash
# krdpserver-embed-cursor: KDE's krdpserver with an EmbedCursor option,
# built from the krdp release that matches the Plasma this PC runs and
# installed under ~/.local as a second RDP server on its own port, for
# the PC that serves its desktop to KRDC on the Frame. Any distribution
# with Plasma 6 on Wayland: nothing here goes through the distribution's
# package manager except the build dependencies, which this script names
# when cmake can't find one. Not for the Frame: the Frame's server is
# the package `cjf install krdpserver` builds.
#
# krdp sends a viewer the pointer's shape, which the viewer draws at its
# own pointer, so moving the mouse at the PC shows in the stream as
# focus changes with no pointer. With krdp-embed-cursor.patch, a viewer
# that advertises no pointer cache (KRDC with this repository's
# krdc-embed-cursor patch and its "Remote pointer" option on) gets KWin's
# own pointer painted into the frames and is told to draw none, so the
# headset sees where the PC's mouse is; a viewer that draws its own
# pointer is served as upstream does. EmbedCursor=true in [General] of
# ~/.config/krdpserverrc (--embed-all) does it for every viewer; this
# script writes the key false otherwise. The stock binary ignores it.
#
# Two patches, in the order upstream is being asked for them:
# krdp-pointer-cache-check.patch is a fix alone (a viewer without a
# pointer cache is refused where stock krdp crashed), and
# krdp-embed-cursor.patch, the feature, applies on top of it.
#
# Two servers, not a switch: the distribution's app-org.kde.krdpserver
# .service keeps port 3389 for viewers that draw their own pointer, and
# the user unit this script writes, krdpserver-embed-cursor.service,
# listens on 3390 (--port) for the one that wants the pointer in the
# stream. A viewer picks by port; the stock unit is never touched. The
# unit passes --plasma: this server exists for a headset, which can't
# answer the desktop portal's prompt on the PC's screen. Both servers
# read krdpserverrc, so users, passwords and the certificate are shared.
#
# Under ~/.local because that is what every distribution leaves to the
# user: no root, no package database, and no version pin to block the
# next update. The patch changes libKRdp, not only the server, so the
# build keeps its own copy of the library in a private directory,
# ~/.local/lib/krdpserver-embed-cursor, with a RUNPATH for it in the
# binary (KDE_INSTALL_LIBDIR is what puts it there), so the patched
# library loads rather than the distribution's libKRdp.so.6. The KCM,
# desktop file, upstream unit and translations build but stay in the
# staging directory: the distribution's krdp supplies them.
#
# The krdp release built is the one `krdpserver --version` (or
# `plasmashell --version`) reports, since the private libKRdp is
# compiled against that release's kpipewire. After a Plasma update, run
# install again: it sees the version differ and rebuilds, then restarts
# the unit. The tarball's signature is checked against the Plasma
# release keys below; a missing key is fetched by fingerprint.
#
# One release is pinned below, the one the patches were last made to
# fit, with its tarball's sha256. When the host's release rejects a
# patch or doesn't build, install builds the pinned one against the
# host's libraries and says so, and status keeps saying it, so a
# Plasma update costs the newer krdp, not the server; refresh the
# patches, move the pin, and install --force. It can't help when the
# pinned release no longer compiles against a newer kpipewire: then
# what is installed stays. A patch the host's release already has is
# skipped, which is how the fix ends once upstream ships it. --version
# builds exactly that release, with no fallback.
#
# The firewall is handled apart from the unit: a PC that lets 3389 in
# usually has a rule for it and none for 3390, and the server logs
# nothing for a packet it never gets. start checks and opens the port
# when it is closed, the one step that needs root (sudo; ufw or
# firewalld, another firewall is left to you, with a note); stop leaves
# the rule, so stopping and starting again asks for no password, and
# `firewall close` removes it when wanted. When sudo can't ask for a
# password, the script prints the command instead of running it.
#
# Usage: krdp-embed-cursor.sh COMMAND [options]
#   install [--port N] [--version V] [--prefix DIR] [--force]
#           [--embed-all] [--no-verify] [--no-enable]
#                 build krdp with the patch, install under --prefix
#                 (default ~/.local), write the unit for --port
#                 (default 3390), write EmbedCursor, then start
#   start         enable the unit, now and at login; open its port in
#                 the firewall if it is closed (sudo only then)
#   stop          disable the unit; the firewall rule stays
#   firewall [open|close]
#                 show whether the port is open, or open or close it
#                 in ufw or firewalld (sudo)
#   status        the unit, the port, the firewall, and whether the
#                 installed build matches the Plasma running
#   uninstall [--no-enable]
#                 stop, close the port, then remove the unit, the
#                 binary, the library and the build cache;
#                 krdpserverrc keeps EmbedCursor
#   --version V   the krdp release to build (default: the host's,
#                 or the pinned one when that takes no patch)
#   --embed-all   EmbedCursor=true: the pointer in the video for every
#                 viewer, not only one that asks (asks: advertises no
#                 pointer cache)
#   --force       rebuild even when the installed version matches
#   --no-verify   skip the signature check
#   --no-enable   write the unit, but leave systemd and the firewall
#                 alone (also for uninstall)
# CMAKE_PREFIX_PATH is passed through to cmake for a dependency that
# is installed somewhere cmake doesn't look.

set -euo pipefail

name=krdpserver-embed-cursor
here=$(cd "$(dirname "$0")" && pwd)
prefix=$HOME/.local
default_port=3390
port=
version=
force=0
embed_all=0
enable=1
verify=1
cache=${XDG_CACHE_HOME:-$HOME/.cache}/$name
unit_dir=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
unit=$unit_dir/$name.service
# Plasma release signers, as Arch's krdp PKGBUILD lists them, and
# Bhushan Shah's key of 2026-11-05, which signed 6.8.3: taken from
# KDE's release keyring (invent.kde.org/sysadmin/release-keyring,
# keys/bshah@key2.asc, added 2026-11-09); his old key doesn't certify
# it.
release_keys=(
  E0A3EB202F8E57528E13E72FD7574483BB57B18D # Jonathan Esk-Riddell
  0AAC775BB6437A8D9AF7A3ACFE0784117FBCE11D # Bhushan Shah
  58743C0A93487794BC44ECE873C3D7758E7A544A # Bhushan Shah, from 2026-11-05
  D07BD8662C56CB291B316EB2F5675605C74E02CF # David Edmundson
  1FA881591C26B276D7A5518EEAAF29B42A678C20 # Marco Martin
)
# The pin: the krdp release the two patches were last made to fit and
# run on (2026-11-26), with its tarball's sha256, taken after the
# signature check. install builds it when the host's release rejects a
# patch or doesn't build, and the sum stands in for the signature, so a
# new signing key can't keep a vetted release from building. Move both
# when the patches are refreshed for a newer release.
known_good=6.8.3
known_good_sha256=8a80e5a5e0f3e7b665752a60264ac36367431d6d8865cd5797370010a819a40b

say() { printf '%s: %s\n' "$name" "$*"; }
die() { printf '%s: %s\n' "$name" "$*" >&2; exit 1; }
usage() { sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \{0,1\}//'; }

command=${1:-}
[ $# -gt 0 ] && shift
action=
case $command in
  install|start|stop|status|uninstall) ;;
  firewall)
    case ${1:-} in
      open|close) action=$1; shift ;;
      ''|-*) ;;
      *) die "firewall takes open or close, not '$1'" ;;
    esac ;;
  -h|--help|help|'') usage; [ -n "$command" ] && exit 0 || exit 1 ;;
  *) die "unknown command $command (see --help)" ;;
esac
while [ $# -gt 0 ]; do
  case $1 in
    --port) port=${2:?--port needs a number}; shift ;;
    --version) version=${2:?--version needs a release}; shift ;;
    --prefix) prefix=${2:?--prefix needs a directory}; shift ;;
    --force) force=1 ;;
    --embed-all) embed_all=1 ;;
    --no-enable) enable=0 ;;
    --no-verify) verify=0 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option $1 for $command (see --help)" ;;
  esac
  shift
done
[ "$(id -u)" -ne 0 ] || die "run as the user whose Plasma session serves the desktop, not root"
case $prefix in /*) ;; *) die "--prefix needs an absolute path" ;; esac

bindir=$prefix/bin
libdir=$prefix/lib/$name

# The port the unit was written for, so start, stop and status agree
# with install; --port on install picks it, nothing else does.
port_from_unit() {
  [ -r "$unit" ] && sed -n 's/^ExecStart=.*--port \([0-9]*\).*/\1/p' "$unit" | head -1
}
if [ -z "$port" ]; then
  port=$(port_from_unit || true)
  port=${port:-$default_port}
fi
case $port in *[!0-9]*|'') die "--port needs a number, not '$port'" ;; esac

systemd() { [ "$enable" -eq 1 ] && command -v systemctl >/dev/null; }

host_version() {
  local v
  for cmd in krdpserver plasmashell; do
    if command -v "$cmd" >/dev/null; then
      v=$("$cmd" --version 2>/dev/null | awk 'NR==1 {print $NF}')
      [ -n "$v" ] && { echo "$v"; return; }
    fi
  done
  return 1
}

installed_version() {
  [ -r "$libdir/version" ] && cat "$libdir/version"
}

# The Plasma release the pinned krdp was installed for in place of its
# own, when install fell back to it.
held_for() {
  [ -r "$libdir/held-for" ] && cat "$libdir/held-for"
}

# --- firewall ---------------------------------------------------------

firewall_kind() {
  if command -v ufw >/dev/null && systemctl is-active --quiet ufw 2>/dev/null; then
    echo ufw
  elif command -v firewall-cmd >/dev/null && systemctl is-active --quiet firewalld 2>/dev/null; then
    echo firewalld
  else
    echo none
  fi
}

# Runs a command through sudo when sudo can ask for a password (a
# terminal) or already has one; otherwise prints it for the user.
as_root() {
  if command -v sudo >/dev/null && { [ -t 0 ] || sudo -n true 2>/dev/null; }; then
    sudo "$@"
  else
    say "needs root, run it yourself: sudo $*"
    return 1
  fi
}

open_port() {
  case $(port_open) in
    "open in "*) say "port $port is already open in the firewall"; return 0 ;;
  esac
  case $(firewall_kind) in
    ufw)
      say "opening $port/tcp in ufw"
      as_root ufw allow "$port/tcp" ;;
    firewalld)
      say "opening $port/tcp in firewalld, now and permanently"
      as_root firewall-cmd --add-port="$port/tcp" \
        && as_root firewall-cmd --permanent --add-port="$port/tcp" ;;
    none)
      say "no ufw or firewalld running; if another firewall filters this PC, let $port/tcp in" ;;
  esac
}

close_port() {
  case $(port_open) in
    "NOT open"*|"no ufw"*) return 0 ;;
  esac
  case $(firewall_kind) in
    ufw)
      say "closing $port/tcp in ufw"
      as_root ufw delete allow "$port/tcp" ;;
    firewalld)
      say "closing $port/tcp in firewalld"
      as_root firewall-cmd --remove-port="$port/tcp" \
        && as_root firewall-cmd --permanent --remove-port="$port/tcp" ;;
    none) ;;
  esac
}

# What status can tell without root: ufw's rules file is often
# world-readable, firewalld answers --list-ports for some users.
port_open() {
  case $(firewall_kind) in
    ufw)
      if [ -r /etc/ufw/user.rules ]; then
        grep -q -- "--dport $port -j ACCEPT" /etc/ufw/user.rules && echo "open in ufw" || echo "NOT open in ufw (start opens it)"
      else
        echo "ufw is running; its rules need root to read (sudo ufw status)"
      fi ;;
    firewalld)
      local ports
      if ports=$(firewall-cmd --list-ports 2>/dev/null); then
        case " $ports " in *" $port/tcp "*) echo "open in firewalld" ;; *) echo "NOT open in firewalld (start opens it)" ;; esac
      else
        echo "firewalld is running; its rules need root to read"
      fi ;;
    none) echo "no ufw or firewalld running" ;;
  esac
}

# --- commands ---------------------------------------------------------

do_start() {
  [ -x "$bindir/$name" ] || die "nothing installed at $bindir/$name; run install first"
  [ -r "$unit" ] || die "no unit at $unit; run install first"
  if ! systemd; then
    say "unit at $unit; --no-enable leaves systemd and the firewall to you"
    return
  fi
  systemctl --user daemon-reload
  # reenable, not enable: an enable symlink left by a packaged copy of
  # this unit points at its /usr/lib file and would dangle once the
  # package goes; reenable makes it point at the unit written here.
  systemctl --user -q reenable "$name.service"
  # install restarts, to run what it just built; start leaves a running
  # server, and its viewer, alone.
  if [ "${1:-}" = restart ] || ! systemctl --user is-active --quiet "$name.service"; then
    systemctl --user restart "$name.service"
    sleep 1
  fi
  systemctl --user is-active --quiet "$name.service" \
    || die "$name.service did not stay up: journalctl --user -u $name.service"
  say "$name.service is running on port $port; point the viewer there (KRDC: Remote pointer on in the host's settings, View > Show Local Cursor off)"
  open_port
}

do_stop() {
  if ! systemd; then
    say "--no-enable: leaving systemd alone"
    return
  fi
  if systemctl --user list-unit-files --quiet "$name.service" 2>/dev/null | grep -q .; then
    systemctl --user -q disable --now "$name.service"
    say "$name.service stopped and disabled"
  else
    say "no $name.service known to systemd"
  fi
  case $(port_open) in
    "open in "*) say "port $port stays open in the firewall; \`firewall close\` removes the rule" ;;
  esac
}

do_firewall() {
  case $action in
    open) open_port ;;
    close) close_port ;;
    '') say "port $port: $(port_open)" ;;
  esac
}

do_status() {
  local inst host
  if [ -x "$bindir/$name" ]; then
    inst=$(installed_version || echo "unknown version")
    host=$(host_version || echo "no Plasma found")
    if [ "$inst" = "$host" ]; then
      say "installed krdp $inst, matching Plasma $host"
    elif [ "$inst" = "$known_good" ] && [ "$(held_for || true)" = "$host" ]; then
      say "installed krdp $inst, the pinned release, on Plasma $host: the patches don't fit $host yet (install --force tries again)"
    else
      say "installed krdp $inst, Plasma is $host: run install to rebuild"
    fi
  else
    say "not installed (no $bindir/$name); run install"
  fi
  if command -v systemctl >/dev/null && [ -r "$unit" ]; then
    say "unit: $(systemctl --user is-enabled "$name.service" 2>/dev/null || echo not-found), $(systemctl --user is-active "$name.service" 2>/dev/null || true)"
  else
    say "unit: none at $unit"
  fi
  if command -v ss >/dev/null; then
    if ss -ltn 2>/dev/null | grep -q ":$port "; then
      say "port $port: listening"
    else
      say "port $port: nothing listening"
    fi
  fi
  say "firewall: $(port_open)"
  if [ -e "/usr/lib/systemd/user/$name.service" ]; then
    say "a packaged copy is installed too (/usr/lib/systemd/user/$name.service); the unit in ~/.config overrides it, and the package can go (on Arch: sudo pacman -R $name)"
  fi
}

do_uninstall() {
  do_stop
  if systemd; then close_port; fi
  rm -f "${unit:?}" "${bindir:?}/${name:?}"
  rm -rf "${libdir:?}" "${cache:?}"
  if systemd; then systemctl --user daemon-reload; fi
  say "removed; krdpserverrc still has its EmbedCursor key, which the stock server ignores"
}

# What the build needs, by distribution family, for when cmake can't
# find one. Debian's list is its krdp source package's; Fedora's follows
# its kf6-*-devel naming; Arch ships headers with the libraries.
dependency_hint() {
  local id
  id=$(. /etc/os-release 2>/dev/null && echo "${ID:-} ${ID_LIKE:-}")
  case " $id " in
    *" arch "*|*" cachyos "*|*" manjaro "*|*" endeavouros "*)
      say "on Arch: sudo pacman -S --needed base-devel cmake ninja extra-cmake-modules plasma-wayland-protocols qt6-base qt6-declarative qt6-wayland kconfig kcoreaddons kcrash kdbusaddons kguiaddons ki18n kcmutils kstatusnotifieritem kpipewire freerdp libxkbcommon pam qtkeychain-qt6 libei" ;;
    *" fedora "*|*" rhel "*)
      say "on Fedora: sudo dnf install cmake ninja-build gcc-c++ extra-cmake-modules plasma-wayland-protocols-devel qt6-qtbase-devel qt6-qtbase-private-devel qt6-qtdeclarative-devel qt6-qtwayland-devel kf6-kconfig-devel kf6-kcoreaddons-devel kf6-kcrash-devel kf6-kdbusaddons-devel kf6-kguiaddons-devel kf6-ki18n-devel kf6-kcmutils-devel kf6-kstatusnotifieritem-devel kpipewire-devel freerdp-devel libxkbcommon-devel pam-devel qtkeychain-qt6-devel libei-devel" ;;
    *" debian "*|*" ubuntu "*|*" neon "*)
      say "on Debian or Ubuntu: sudo apt install build-essential cmake ninja-build gettext extra-cmake-modules plasma-wayland-protocols qt6-base-dev qt6-base-private-dev qt6-declarative-dev qt6-wayland-dev libkf6config-dev libkf6coreaddons-dev libkf6crash-dev libkf6dbusaddons-dev libkf6guiaddons-dev libkf6i18n-dev libkf6kcmutils-dev libkf6statusnotifieritem-dev libkpipewire-dev freerdp3-dev libwinpr3-dev libxkbcommon-dev libpam0g-dev qtkeychain-qt6-dev libei-dev" ;;
    *)
      say "cmake's message above names the missing package; it is that library's development package (-devel or -dev), plus extra-cmake-modules and plasma-wayland-protocols" ;;
  esac
}

# keys.openpgp.org serves only keys whose owner confirmed an address,
# which two of the four signers have not, and gpg exits 0 when it got
# any key at all; so the keyservers are tried in turn until the
# signature verifies, and the verification is what decides.
verify_tarball() {
  local status fpr server missing
  status=$(gpg --status-fd 1 --verify "$1.sig" "$1" 2>/dev/null || true)
  for server in hkps://keys.openpgp.org hkps://keyserver.ubuntu.com; do
    grep -q '^\[GNUPG:\] NO_PUBKEY' <<<"$status" || break
    say "fetching the Plasma release keys by fingerprint from ${server#hkps://}"
    gpg --keyserver "$server" --recv-keys "${release_keys[@]}" >/dev/null 2>&1 || true
    status=$(gpg --status-fd 1 --verify "$1.sig" "$1" 2>/dev/null || true)
  done
  missing=$(awk '/^\[GNUPG:\] NO_PUBKEY/ {print $3}' <<<"$status")
  [ -z "$missing" ] \
    || die "no keyserver had the key $missing that signed $(basename "$1"); import it yourself (gpg --recv-keys ${release_keys[*]}) or pass --no-verify"
  # VALIDSIG's last field is the primary key's fingerprint, whichever
  # subkey signed.
  fpr=$(awk '/^\[GNUPG:\] VALIDSIG/ {print $NF}' <<<"$status")
  [ -n "$fpr" ] || die "the signature on $(basename "$1") doesn't verify"
  for k in "${release_keys[@]}"; do
    [ "$k" = "$fpr" ] && { say "signature good, key $fpr"; return; }
  done
  die "$(basename "$1") is signed by $fpr, not one of the Plasma release keys this script knows"
}

# The pinned release is checked by its sum; any other by its signature.
check_tarball() {
  local v=$1 tarball=$2 sum
  if [ "$v" = "$known_good" ]; then
    command -v sha256sum >/dev/null || die "sha256sum is needed to check the pinned tarball"
    sum=$(sha256sum "$tarball" | awk '{print $1}')
    [ "$sum" = "$known_good_sha256" ] \
      || die "$(basename "$tarball") is not the tarball this script pins (sha256 $sum); remove it from $cache and install again"
    say "checksum good: the pinned krdp $v"
  elif [ "$verify" -eq 1 ]; then
    verify_tarball "$tarball"
  else
    say "not checking the signature (--no-verify)"
  fi
}

# Applies one patch to the source. A patch the release already has is
# skipped, which is how the fix ends once upstream ships it; one that
# fits neither way is rejected, and that returns 1.
apply_patch() {
  local src=$1 p=$2 v=$3
  if patch -d "$src" -p1 --forward --dry-run < "$here/$p" >/dev/null 2>&1; then
    say "applying $p"
    patch -d "$src" -p1 --forward < "$here/$p" || return 1
  elif patch -d "$src" -p1 --reverse --dry-run < "$here/$p" >/dev/null 2>&1; then
    say "krdp $v already has $p: skipped, and the patch can leave this script"
  else
    say "$p no longer applies to krdp $v: upstream moved the code, the patch needs refreshing"
    return 1
  fi
}

# Fetches, checks, patches and builds one release into the staging
# directory. Returns 1 when a patch is rejected or the build fails,
# which is what the pin is for; a failed download or check ends the
# script, since another release is no answer to those.
build_release() {
  local v=$1 tarball url f p gen
  mkdir -p "$cache"
  tarball=$cache/krdp-$v.tar.xz
  url=https://download.kde.org/stable/plasma/$v/krdp-$v.tar.xz
  for f in "$tarball" "$tarball.sig"; do
    [ -s "$f" ] && continue
    # The pinned release needs no signature file.
    [ "$f" = "$tarball.sig" ] && { [ "$v" = "$known_good" ] || [ "$verify" -eq 0 ]; } && continue
    say "downloading $(basename "$f")"
    curl -fsSL --retry 3 -o "$f.part" "$url${f##"$tarball"}" || die "download failed: $url${f##"$tarball"}"
    mv -f "$f.part" "$f"
  done
  check_tarball "$v" "$tarball"

  rm -rf "${cache:?}/src" "${cache:?}/build" "${cache:?}/stage"
  mkdir -p "$cache/src"
  tar -xJf "$tarball" -C "$cache/src" --strip-components=1 || die "could not unpack $tarball"
  # The fix first: the feature is made against the source with it.
  for p in krdp-pointer-cache-check.patch krdp-embed-cursor.patch; do
    apply_patch "$cache/src" "$p" "$v" || return 1
  done

  gen=()
  command -v ninja >/dev/null && gen=(-G Ninja)
  say "configuring krdp $v"
  if ! cmake -S "$cache/src" -B "$cache/build" "${gen[@]}" \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX="$prefix" \
      -DKDE_INSTALL_LIBDIR="lib/$name" \
      -DBUILD_TESTING=OFF \
      -DBUILD_EXAMPLES=OFF; then
    dependency_hint
    say "cmake could not configure krdp $v; see above for what is missing"
    return 1
  fi
  say "building (this takes a few minutes)"
  cmake --build "$cache/build" --parallel "$(nproc)" \
    || { say "krdp $v did not build"; return 1; }
  DESTDIR=$cache/stage cmake --install "$cache/build" >/dev/null \
    || { say "krdp $v did not install into the staging directory"; return 1; }
}

# Installs what build_release staged. With a second argument, the
# Plasma release the pinned krdp stands in for, which status reads.
install_built() {
  local v=$1 held=${2:-} staged
  # New files beside the old, then renamed over them, so a running
  # server keeps the inodes it has mapped until it is restarted.
  staged=$cache/stage$prefix
  mkdir -p "$bindir" "$prefix/lib"
  rm -rf "${libdir:?}.new"
  mkdir -p "$libdir.new"
  # the versioned library and its SONAME link, not the libKRdp.so link
  # for linking against
  cp -P "$staged/lib/$name"/libKRdp.so.6* "$libdir.new/"
  echo "$v" > "$libdir.new/version"
  [ -z "$held" ] || echo "$held" > "$libdir.new/held-for"
  rm -rf "${libdir:?}"
  mv "$libdir.new" "$libdir"
  install -m755 "$staged/bin/krdpserver" "$bindir/$name.new"
  mv -f "$bindir/$name.new" "$bindir/$name"
  say "installed $bindir/$name and $libdir"
}

do_install() {
  local installed explicit
  for tool in cmake curl tar patch; do
    command -v "$tool" >/dev/null || die "$tool is needed; install it first"
  done
  if [ "$verify" -eq 1 ]; then
    command -v gpg >/dev/null || die "gpg is needed to check the tarball's signature (or pass --no-verify)"
  fi
  explicit=$version
  [ -n "$version" ] || version=$(host_version) \
    || die "no krdpserver or plasmashell to read the Plasma version from; pass --version"
  case $version in
    6.[0-9]*.[0-9]*) ;;
    *) die "'$version' doesn't look like a Plasma 6 release" ;;
  esac

  installed=$(installed_version || true)
  if [ "$installed" = "$version" ] && [ -x "$bindir/$name" ] && [ "$force" -eq 0 ]; then
    say "$version is already built and installed (--force rebuilds)"
  elif [ -z "$explicit" ] && [ "$installed" = "$known_good" ] && [ -x "$bindir/$name" ] \
      && [ "$(held_for || true)" = "$version" ] && [ "$force" -eq 0 ]; then
    say "the pinned krdp $known_good is installed for Plasma $version, which the patches don't fit yet; refresh them, then install --force"
  else
    if [ -n "$installed" ]; then
      say "installed $installed, Plasma is $version: rebuilding"
    fi
    if build_release "$version"; then
      install_built "$version"
    elif [ -n "$explicit" ] || [ "$version" = "$known_good" ]; then
      die "krdp $version was not built; what is installed stays as it was"
    else
      say "falling back to the pinned krdp $known_good, the release the patches were made for, built against Plasma $version's libraries"
      build_release "$known_good" \
        || die "the pinned krdp $known_good does not build against Plasma $version either; what is installed stays as it was"
      install_built "$known_good" "$version"
      say "the patches need refreshing for krdp $version; until then this server is krdp $known_good"
    fi
  fi

  mkdir -p "$unit_dir"
  cat > "$unit" <<UNIT
# Written by curiousj-framekit's pc/krdpserver-embed-cursor script;
# install again rewrites this file (--port for another port). The
# second KRDP server, beside the distribution's on 3389; --plasma since
# a headset can't answer the desktop portal's prompt on the PC's screen.
[Unit]
Description=KRDP Server with the host's pointer in the stream
After=plasma-core.target

[Service]
Type=exec
ExecStart=$bindir/$name --plasma --port $port
Restart=on-abnormal

[Install]
WantedBy=plasma-workspace.target
UNIT

  if [ -e "/usr/lib/systemd/user/$name.service" ]; then
    say "a packaged copy is installed too (/usr/lib/systemd/user/$name.service); the unit in ~/.config overrides it, and the package can go (on Arch: sudo pacman -R $name)"
  fi

  local embed=false
  [ "$embed_all" -eq 1 ] && embed=true
  if command -v kwriteconfig6 >/dev/null; then
    kwriteconfig6 --file krdpserverrc --group General --key EmbedCursor --type bool "$embed"
  else
    say "kwriteconfig6 not found: put EmbedCursor=$embed under [General] in ~/.config/krdpserverrc yourself"
  fi

  do_start restart
}

case $command in
  install) do_install ;;
  start) do_start ;;
  stop) do_stop ;;
  firewall) do_firewall ;;
  status) do_status ;;
  uninstall) do_uninstall ;;
esac
