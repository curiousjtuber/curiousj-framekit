#!/bin/sh
# Installs curiousj-framekit with uv, into ~/.local/bin, as `cjf` and
# `curiousj-framekit`:
#
#   curl -LsSf https://raw.githubusercontent.com/curiousjtuber/steam-frame-utils/main/install.sh | sh
#   wget -qO- https://raw.githubusercontent.com/curiousjtuber/steam-frame-utils/main/install.sh | sh
#
# uv is installed first from astral.sh when none is found, and uv
# fetches a Python 3.12+ when the system has none, so a bare Frame needs
# only curl or wget, and git. Nothing here needs root. Run it again to
# upgrade: an install already there, editable or not, is upgraded from
# the source it came from.
#
#   CURIOUSJ_FRAMEKIT_SOURCE  what to install, replacing any install
#                             already there: a git URL (default
#                             git+https://github.com/curiousjtuber/steam-frame-utils,
#                             '@TAG' pins one) or a checkout's directory
#   CURIOUSJ_FRAMEKIT_NO_UV   set: stop rather than install uv
#
# The whole script is one function, called on its last line, so a
# download cut short runs nothing. Taken from curiousj-tools' install.sh.

main() {
    set -eu
    default_source=git+https://github.com/curiousjtuber/steam-frame-utils

    uv=$(find_uv) || uv=
    if [ -z "$uv" ]; then
        [ -z "${CURIOUSJ_FRAMEKIT_NO_UV:-}" ] ||
            die "no uv found, and CURIOUSJ_FRAMEKIT_NO_UV is set: install uv (https://docs.astral.sh/uv/), then rerun"
        say "installing uv from astral.sh"
        tmp=$(mktemp)
        trap 'rm -f "$tmp"' EXIT
        fetch https://astral.sh/uv/install.sh > "$tmp" || die "could not download the uv installer"
        sh "$tmp" || die "the uv installer failed"
        uv=$(find_uv) || die "uv installed, but not found where its installer puts it"
    fi
    say "using $uv"

    if [ -n "${CURIOUSJ_FRAMEKIT_SOURCE:-}" ]; then
        install_from "$CURIOUSJ_FRAMEKIT_SOURCE"
    elif "$uv" tool list 2>/dev/null | grep -q '^curiousj-framekit '; then
        say "upgrading curiousj-framekit"
        "$uv" tool upgrade curiousj-framekit || die "\`uv tool upgrade curiousj-framekit\` failed"
    else
        install_from "$default_source"
    fi

    command -v fzf > /dev/null 2>&1 ||
        note "optional, not found: fzf (the menus fall back to numbered lists)"

    say "done. Run: cjf"
}

install_from() {  # install SOURCE: replaces any install already there
    case $1 in
        git+*) command -v git > /dev/null 2>&1 || die "installing from $1 needs git" ;;
    esac
    say "installing curiousj-framekit from $1"
    "$uv" tool install --force "$1" || die "\`uv tool install $1\` failed"
}

find_uv() {  # the uv on PATH, else one where its installer or mise puts it
    if command -v uv > /dev/null 2>&1; then
        command -v uv
        return
    fi
    for f in "${XDG_BIN_HOME:-$HOME/.local/bin}/uv" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" \
             "${MISE_DATA_DIR:-$HOME/.local/share/mise}/shims/uv"; do
        if [ -x "$f" ]; then
            echo "$f"
            return
        fi
    done
    return 1
}

fetch() {  # fetch URL: the body on stdout
    if command -v curl > /dev/null 2>&1; then
        curl -fsSL "$1"
    elif command -v wget > /dev/null 2>&1; then
        wget -qO- "$1"
    else
        die "neither curl nor wget found"
    fi
}

say()  { printf 'curiousj-framekit: %s\n' "$1"; }
note() { printf 'curiousj-framekit: note: %s\n' "$1" >&2; }
die()  { printf 'curiousj-framekit: error: %s\n' "$1" >&2; exit 1; }

main "$@"
