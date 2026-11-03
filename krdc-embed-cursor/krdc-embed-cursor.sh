#!/usr/bin/env bash
# krdc-embed-cursor: KDE's KRDC with a "Remote pointer: painted into the
# video by the server" option per host (krdc-embed-cursor.patch), built
# from a KRDC release and installed under ~/.local, on the PC and on the
# Frame alike. Any distribution with KDE Frameworks 6 and FreeRDP 3;
# SteamOS as it is: the two build dependencies it lacks, extra-cmake-
# modules and qtkeychain, are built here when the host has no copy.
#
# KRdp sends a viewer the pointer's shape to draw at its own pointer, so
# a viewer that only watches never sees where the host's mouse is. With
# the option on, KRDC advertises no pointer cache, and a KRdp built with
# pc/krdpserver-embed-cursor paints its own pointer into the video for
# that connection. Off, the client is upstream's exactly.
#
# The build lives in ~/.local/lib/krdc-embed-cursor, a prefix of its
# own: KRDC's RDP and VNC backends are Qt plugins that Qt finds only
# through QT_PLUGIN_PATH, so ~/.local/bin/krdc is a launcher that sets
# it and runs the build's binary. The launcher shadows a distribution's
# krdc on PATH, and ~/.local/share/applications/org.kde.krdc.desktop
# shadows the distribution's or the flatpak's menu entry, so KRDC from
# the menu is this one; uninstall puts both back. The build reads the
# same ~/.config/krdcrc and bookmarks as a distribution's krdc. A
# flatpak KRDC keeps its own under ~/.var/app/org.kde.krdc; install
# copies them over when there are none yet, once.
#
# The release built is the one below unless --version says otherwise,
# checked against the KDE Gear release keys; extra-cmake-modules
# against the Frameworks keys; qtkeychain by the commit its tag pointed
# at when this was written. A missing key is fetched by fingerprint.
#
# Usage: krdc-embed-cursor.sh COMMAND [options]
#   install [--version V] [--prefix DIR] [--force] [--no-verify]
#                 build KRDC with the patch, install under --prefix
#                 (default ~/.local), write the launcher and the menu
#                 entry; extra-cmake-modules and qtkeychain first when
#                 the host has neither
#   status        what is installed and what the menu and PATH run
#   uninstall     remove the build, the launcher, the menu entry and the
#                 build cache; krdcrc and the bookmarks stay
#   --version V   the KRDC release to build (default: 26.08.2)
#   --force       rebuild even when the installed version matches
#   --no-verify   skip the signature and commit checks
# CMAKE_PREFIX_PATH is passed through to cmake for a dependency that
# is installed somewhere cmake doesn't look.

set -euo pipefail

name=krdc-embed-cursor
here=$(cd "$(dirname "$0")" && pwd)
prefix=$HOME/.local
version=26.08.2
force=0
verify=1
cache=${XDG_CACHE_HOME:-$HOME/.cache}/$name
# KDE Gear release signers, as Arch's krdc PKGBUILD lists them.
gear_keys=(
  CA262C6C83DE4D2FB28A332A3A6A4DB839EAA6D7 # Albert Astals Cid
  F23275E4BF10AFC1DF6914A6DBD2CE893E2D1C87 # Christoph Feck
  D81C0CB38EB725EF6691C385BB463350D6EF31EF # Heiko Becker
)
# KDE Frameworks release signers, as Arch's extra-cmake-modules
# PKGBUILD lists them.
frameworks_keys=(
  53E6B47B45CEA3E0D5B7457758D0EE648A48B3BB # David Faure
  90A968ACA84537CC27B99EAF2C8DF587A6D4AAC1 # Nicolas Fella
)
# The last extra-cmake-modules that still takes CMake 3.16; from 6.24
# it wants 3.27 and from 6.31 3.30, where SteamOS 0.5.6 has 3.29.
ecm_version=6.20.0
qtkeychain_version=0.17.0
# The commit tag 0.17.0 pointed at on 2026-11-03.
qtkeychain_commit=875f77d9f61bd97fd84cca47ce3bc71186dfbd09

say() { printf '%s: %s\n' "$name" "$*"; }
die() { printf '%s: %s\n' "$name" "$*" >&2; exit 1; }
usage() { sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \{0,1\}//'; }

command=${1:-}
[ $# -gt 0 ] && shift
case $command in
  install|status|uninstall) ;;
  -h|--help|help|'') usage; [ -n "$command" ] && exit 0 || exit 1 ;;
  *) die "unknown command $command (see --help)" ;;
esac
while [ $# -gt 0 ]; do
  case $1 in
    --version) version=${2:?--version needs a release}; shift ;;
    --prefix) prefix=${2:?--prefix needs a directory}; shift ;;
    --force) force=1 ;;
    --no-verify) verify=0 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option $1 for $command (see --help)" ;;
  esac
  shift
done
[ "$(id -u)" -ne 0 ] || die "run as the user who will run KRDC, not root"
case $prefix in /*) ;; *) die "--prefix needs an absolute path" ;; esac

home=$prefix/lib/$name
launcher=$prefix/bin/krdc
desktop=$prefix/share/applications/org.kde.krdc.desktop
config_home=${XDG_CONFIG_HOME:-$HOME/.config}
data_home=${XDG_DATA_HOME:-$HOME/.local/share}
flatpak_app=$HOME/.var/app/org.kde.krdc

installed_version() { cat "$home/version" 2>/dev/null; }

# Whether cmake would find a package's config on this host, by where
# distributions put them; a build of our own under $home counts too.
have_cmake_config() {
  local f
  for f in /usr/lib/cmake/$1/$1Config.cmake /usr/lib64/cmake/$1/$1Config.cmake \
      /usr/lib/*/cmake/$1/$1Config.cmake /usr/local/lib/cmake/$1/$1Config.cmake \
      /usr/share/$1/cmake/$1Config.cmake /usr/share/cmake/$1/$1Config.cmake \
      "$home"/lib/cmake/$1/$1Config.cmake "$home"/lib64/cmake/$1/$1Config.cmake \
      "$home"/share/$1/cmake/$1Config.cmake; do
    [ -e "$f" ] && return 0
  done
  return 1
}

fetch() {
  [ -s "$2" ] && return 0
  say "downloading $(basename "$2")"
  curl -fsSL --retry 3 -o "$2.part" "$1" || die "download failed: $1"
  mv -f "$2.part" "$2"
}

# verify_tarball FILE KEY...: FILE.sig must be by one of the KEYs. A
# key not on keys.openpgp.org (Nicolas Fella's, for one) is tried on
# Ubuntu's keyserver next; gpg exits 0 when it got any key, so it is
# the verification that says whether the signer's came.
verify_tarball() {
  local file=$1 status fpr k server
  shift
  status=$(gpg --status-fd 1 --verify "$file.sig" "$file" 2>/dev/null || true)
  for server in hkps://keys.openpgp.org hkps://keyserver.ubuntu.com; do
    grep -q '^\[GNUPG:\] NO_PUBKEY' <<<"$status" || break
    say "fetching the release keys by fingerprint from ${server#hkps://}"
    gpg --keyserver "$server" --recv-keys "$@" >/dev/null 2>&1 || true
    status=$(gpg --status-fd 1 --verify "$file.sig" "$file" 2>/dev/null || true)
  done
  if grep -q '^\[GNUPG:\] NO_PUBKEY' <<<"$status"; then
    die "could not fetch the key that signed $(basename "$file"); import it yourself (gpg --recv-keys $*) or pass --no-verify"
  fi
  # VALIDSIG's last field is the primary key's fingerprint, whichever
  # subkey signed.
  fpr=$(awk '/^\[GNUPG:\] VALIDSIG/ {print $NF}' <<<"$status")
  [ -n "$fpr" ] || die "the signature on $(basename "$file") doesn't verify"
  for k in "$@"; do
    [ "$k" = "$fpr" ] && { say "signature good, key $fpr"; return; }
  done
  die "$(basename "$file") is signed by $fpr, not one of the release keys this script knows"
}

# What the build needs, by distribution family, for when cmake can't
# find one. Arch's list is its krdc PKGBUILD's; Debian's and Fedora's
# follow their naming and are not checked against a package index.
dependency_hint() {
  local id
  id=$(. /etc/os-release 2>/dev/null && echo "${ID:-} ${ID_LIKE:-}")
  case " $id " in
    *" steamos "*)
      say "on SteamOS the host has everything but extra-cmake-modules and qtkeychain, which this script builds; cmake's message above names what else is missing" ;;
    *" arch "*|*" cachyos "*|*" manjaro "*|*" endeavouros "*)
      say "on Arch: sudo pacman -S --needed base-devel cmake ninja extra-cmake-modules qt6-base qt6-tools qt6-wayland kbookmarks kcmutils kcompletion kconfig kconfigwidgets kcoreaddons kcrash kdnssd kguiaddons ki18n kio knotifyconfig kstatusnotifieritem kwidgetsaddons kxmlgui kwallet libssh freerdp qtkeychain-qt6 libvncserver" ;;
    *" fedora "*|*" rhel "*)
      say "on Fedora: sudo dnf install cmake ninja-build gcc-c++ gettext extra-cmake-modules qt6-qtbase-devel qt6-qtbase-private-devel qt6-qttools-devel qt6-qtwayland-devel kf6-kbookmarks-devel kf6-kcmutils-devel kf6-kcompletion-devel kf6-kconfig-devel kf6-kconfigwidgets-devel kf6-kcoreaddons-devel kf6-kcrash-devel kf6-kdnssd-devel kf6-kguiaddons-devel kf6-ki18n-devel kf6-kio-devel kf6-knotifyconfig-devel kf6-kstatusnotifieritem-devel kf6-kwidgetsaddons-devel kf6-kxmlgui-devel kf6-kwallet-devel libssh-devel freerdp-devel qtkeychain-qt6-devel libvncserver-devel" ;;
    *" debian "*|*" ubuntu "*|*" neon "*)
      say "on Debian or Ubuntu: sudo apt install build-essential cmake ninja-build gettext extra-cmake-modules qt6-base-dev qt6-base-private-dev qt6-tools-dev qt6-wayland-dev libkf6bookmarks-dev libkf6kcmutils-dev libkf6completion-dev libkf6config-dev libkf6configwidgets-dev libkf6coreaddons-dev libkf6crash-dev libkf6dnssd-dev libkf6guiaddons-dev libkf6i18n-dev libkf6kio-dev libkf6notifyconfig-dev libkf6statusnotifieritem-dev libkf6widgetsaddons-dev libkf6xmlgui-dev libkf6wallet-dev libssh-dev freerdp3-dev libwinpr3-dev qtkeychain-qt6-dev libvncserver-dev" ;;
    *)
      say "cmake's message above names the missing package; it is that library's development package (-devel or -dev)" ;;
  esac
}

cmake_generator() {
  command -v ninja >/dev/null && echo -G && echo Ninja
}

build_ecm() {
  local tarball url
  tarball=$cache/extra-cmake-modules-$ecm_version.tar.xz
  url=https://download.kde.org/stable/frameworks/${ecm_version%.*}/extra-cmake-modules-$ecm_version.tar.xz
  fetch "$url" "$tarball"
  fetch "$url.sig" "$tarball.sig"
  if [ "$verify" -eq 1 ]; then verify_tarball "$tarball" "${frameworks_keys[@]}"; else say "not checking the signature (--no-verify)"; fi
  rm -rf "${cache:?}/ecm"
  mkdir -p "$cache/ecm/src"
  tar -xJf "$tarball" -C "$cache/ecm/src" --strip-components=1
  say "installing extra-cmake-modules $ecm_version under $home (the host has none)"
  cmake -S "$cache/ecm/src" -B "$cache/ecm/build" $(cmake_generator) \
    -DCMAKE_INSTALL_PREFIX="$home" \
    -DBUILD_TESTING=OFF -DBUILD_HTML_DOCS=OFF -DBUILD_MAN_DOCS=OFF -DBUILD_QTHELP_DOCS=OFF >/dev/null
  cmake --install "$cache/ecm/build" >/dev/null
}

build_qtkeychain() {
  local src head secret
  src=$cache/qtkeychain
  command -v git >/dev/null || die "git is needed to fetch qtkeychain; install it first"
  if [ ! -d "$src/.git" ]; then
    say "cloning qtkeychain $qtkeychain_version"
    rm -rf "${src:?}"
    git clone -q --depth 1 --branch "$qtkeychain_version" https://github.com/frankosterfeld/qtkeychain.git "$src" 2>/dev/null \
      || die "could not clone qtkeychain $qtkeychain_version"
  fi
  head=$(git -C "$src" rev-parse HEAD)
  if [ "$verify" -eq 1 ]; then
    [ "$head" = "$qtkeychain_commit" ] \
      || die "qtkeychain's tag $qtkeychain_version is at $head, not the commit this script recorded ($qtkeychain_commit); the tag moved, or the clone is stale: rm -rf $src"
    say "qtkeychain at the recorded commit"
  fi
  secret=OFF
  pkg-config --exists libsecret-1 2>/dev/null && secret=ON
  say "building qtkeychain $qtkeychain_version under $home (the host has none)"
  cmake -S "$src" -B "$cache/qtkeychain-build" $(cmake_generator) \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$home" \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DBUILD_TEST_APPLICATION=OFF -DBUILD_TRANSLATIONS=OFF \
    -DLIBSECRET_SUPPORT=$secret >/dev/null
  cmake --build "$cache/qtkeychain-build" --parallel "$(nproc)" >/dev/null
  cmake --install "$cache/qtkeychain-build" >/dev/null
}

write_launcher() {
  mkdir -p "$prefix/bin"
  cat > "$launcher.new" <<LAUNCHER
#!/bin/sh
# Written by curiousj-framekit's krdc-embed-cursor script: the KRDC
# built under the directory below, whose RDP and VNC plugins Qt finds
# only through QT_PLUGIN_PATH. uninstall removes this file.
home=$home
export QT_PLUGIN_PATH="\$home/lib/plugins\${QT_PLUGIN_PATH:+:\$QT_PLUGIN_PATH}"
export XDG_DATA_DIRS="\$home/share:\${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
exec "\$home/bin/krdc" "\$@"
LAUNCHER
  chmod 755 "$launcher.new"
  mv -f "$launcher.new" "$launcher"
}

write_desktop_entry() {
  local built=$home/share/applications/org.kde.krdc.desktop
  [ -f "$built" ] || die "the build left no $built"
  mkdir -p "$(dirname "$desktop")"
  {
    echo "# Written by curiousj-framekit's krdc-embed-cursor script; it"
    echo "# shadows the distribution's or the flatpak's entry until uninstall."
    sed "s|^Exec=$home/bin/krdc|Exec=$launcher|" "$built"
  } > "$desktop.new"
  grep -q "^Exec=$launcher" "$desktop.new" || die "could not point $desktop at the launcher"
  mv -f "$desktop.new" "$desktop"
  command -v update-desktop-database >/dev/null && update-desktop-database -q "$(dirname "$desktop")" 2>/dev/null || true
}

# A flatpak KRDC's hosts and bookmarks, for a first install only; after
# that the two keep their own.
carry_flatpak_config() {
  local copied=0
  if [ ! -e "$config_home/krdcrc" ] && [ -s "$flatpak_app/config/krdcrc" ]; then
    mkdir -p "$config_home"
    cp "$flatpak_app/config/krdcrc" "$config_home/krdcrc"
    copied=1
  fi
  if [ ! -e "$data_home/krdc/bookmarks.xml" ] && [ -s "$flatpak_app/data/krdc/bookmarks.xml" ]; then
    mkdir -p "$data_home/krdc"
    cp "$flatpak_app/data/krdc/bookmarks.xml" "$data_home/krdc/bookmarks.xml"
    copied=1
  fi
  [ "$copied" -eq 1 ] && say "copied the flatpak KRDC's hosts and bookmarks to $config_home/krdcrc and $data_home/krdc (its passwords are in the wallet, which both use)"
  return 0
}

do_install() {
  local installed tarball url vnc tool
  for tool in cmake curl tar patch; do
    command -v "$tool" >/dev/null || die "$tool is needed; install it first"
  done
  if [ "$verify" -eq 1 ]; then
    command -v gpg >/dev/null || die "gpg is needed to check the tarball's signature (or pass --no-verify)"
  fi
  case $version in
    2[0-9].[0-9][0-9].[0-9]*) ;;
    *) die "'$version' doesn't look like a KDE Gear release (such as 26.08.2)" ;;
  esac

  installed=$(installed_version || true)
  if [ "$installed" = "$version" ] && [ -x "$home/bin/krdc" ] && [ "$force" -eq 0 ]; then
    say "$version is already built and installed (--force rebuilds)"
  else
    [ -n "$installed" ] && say "installed $installed, building $version"
    mkdir -p "$cache"
    tarball=$cache/krdc-$version.tar.xz
    url=https://download.kde.org/stable/release-service/$version/src/krdc-$version.tar.xz
    fetch "$url" "$tarball"
    fetch "$url.sig" "$tarball.sig"
    if [ "$verify" -eq 1 ]; then verify_tarball "$tarball" "${gear_keys[@]}"; else say "not checking the signature (--no-verify)"; fi

    rm -rf "${cache:?}/src" "${cache:?}/build"
    mkdir -p "$cache/src"
    tar -xJf "$tarball" -C "$cache/src" --strip-components=1
    say "applying krdc-embed-cursor.patch"
    patch -d "$cache/src" -p1 --forward < "$here/krdc-embed-cursor.patch" \
      || die "the patch no longer applies to krdc $version: upstream moved the code, the patch needs refreshing"

    # A prefix of its own, built up from nothing each time: the two
    # dependencies first when the host has no copy, then KRDC against
    # them, so its RUNPATH points here.
    rm -rf "${home:?}"
    mkdir -p "$home"
    have_cmake_config ECM || build_ecm
    have_cmake_config Qt6Keychain || build_qtkeychain

    vnc=OFF
    pkg-config --exists libvncclient 2>/dev/null && vnc=ON
    say "configuring krdc $version (VNC $vnc)"
    if ! cmake -S "$cache/src" -B "$cache/build" $(cmake_generator) \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$home" \
        -DCMAKE_PREFIX_PATH="$home${CMAKE_PREFIX_PATH:+;$CMAKE_PREFIX_PATH}" \
        -DKDE_INSTALL_USE_QT_SYS_PATHS=OFF \
        -DKDE_INSTALL_LIBDIR=lib \
        -DKDE_INSTALL_PLUGINDIR=lib/plugins \
        -DBUILD_TESTING=OFF \
        -DWITH_RDP=ON -DWITH_VNC=$vnc; then
      dependency_hint
      die "cmake could not configure krdc; see above for what is missing"
    fi
    say "building (a few minutes)"
    cmake --build "$cache/build" --parallel "$(nproc)"
    cmake --install "$cache/build" >/dev/null
    [ -e "$home/lib/plugins/krdc/krdc_rdpplugin.so" ] || die "the build left no RDP plugin under $home/lib/plugins/krdc"
    echo "$version" > "$home/version"
    say "installed krdc $version under $home"
  fi

  write_launcher
  write_desktop_entry
  carry_flatpak_config
  say "$launcher runs it; the menu's KRDC is now this one"
  say "for a host, in its settings: Remote pointer > Painted into the video by the server (and View > Show Local Cursor off, unless you want your own pointer over it)"
}

do_status() {
  local installed
  installed=$(installed_version || true)
  if [ -n "$installed" ] && [ -x "$home/bin/krdc" ]; then
    say "krdc $installed under $home"
  else
    say "not installed under $home"
  fi
  [ -x "$launcher" ] && say "launcher $launcher" || say "no launcher at $launcher"
  [ -f "$desktop" ] && say "menu entry $desktop" || say "no menu entry at $desktop"
  if command -v krdc >/dev/null; then
    say "krdc on PATH is $(command -v krdc)"
  else
    say "no krdc on PATH ($prefix/bin is not on it)"
  fi
  [ -d "$home/share/ECM" ] && say "extra-cmake-modules $ecm_version is the build's own"
  [ -e "$home/lib/cmake/Qt6Keychain" ] && say "qtkeychain $qtkeychain_version is the build's own"
  return 0
}

do_uninstall() {
  rm -f "${launcher:?}" "${desktop:?}"
  rm -rf "${home:?}" "${cache:?}"
  command -v update-desktop-database >/dev/null && update-desktop-database -q "$(dirname "$desktop")" 2>/dev/null || true
  say "removed; $config_home/krdcrc and the bookmarks stay, and the menu's KRDC is the distribution's or the flatpak's again"
}

case $command in
  install) do_install ;;
  status) do_status ;;
  uninstall) do_uninstall ;;
esac
