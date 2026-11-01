#!/bin/sh
# Installs curiousj-framekit on a Steam Frame: mise first, uv and fzf
# through it, then the kit as a uv tool (cjf and curiousj-framekit in
# ~/.local/bin), and finally `cjf init` for the base.
#
#   curl -LsSf https://raw.githubusercontent.com/curiousjtuber/curiousj-framekit/main/install.sh | sh
#   wget -qO- https://raw.githubusercontent.com/curiousjtuber/curiousj-framekit/main/install.sh | sh
#
# It says what it is about to install, only what is missing, and asks
# once on the terminal before doing anything; `cjf init` then asks
# before each file it changes. Nothing here needs root. Run it again to
# upgrade: an install already there, editable or not, is upgraded from
# the source it came from.
#
#   CURIOUSJ_FRAMEKIT_SOURCE  what to install, replacing any install
#                             already there: a git URL (default
#                             git+https://github.com/curiousjtuber/curiousj-framekit,
#                             '@TAG' pins one) or a checkout's directory
#   CURIOUSJ_FRAMEKIT_YES     set: don't ask (as when there is no
#                             terminal to ask on)
#   CURIOUSJ_FRAMEKIT_NO_INIT set: stop before `cjf init`
#
# The whole script is one function, called on its last line, so a
# download cut short runs nothing. After curiousj-tools' install.sh.

main() {
    set -eu
    default_source=git+https://github.com/curiousjtuber/curiousj-framekit
    bin=${XDG_BIN_HOME:-$HOME/.local/bin}
    shims=${MISE_DATA_DIR:-$HOME/.local/share/mise}/shims
    PATH=$bin:$shims:$PATH

    mise=$(find_tool mise) || mise=
    uv=$(find_tool uv) || uv=
    fzf=$(find_tool fzf) || fzf=

    echo "curiousj-framekit will install, for $(id -un), with no root:"
    [ -n "$mise" ] || echo "  mise                 $bin/mise, from mise.run"
    missing=
    [ -n "$uv" ] || missing="$missing uv"
    [ -n "$fzf" ] || missing="$missing fzf"
    [ -z "$missing" ] || echo "  $(echo $missing | tr ' ' ',')  through mise (mise use -g$missing)"
    if "${uv:-false}" tool list 2>/dev/null | grep -q '^curiousj-framekit '; then
        echo "  curiousj-framekit    upgraded, from where it was installed"
    else
        echo "  curiousj-framekit    as a uv tool: cjf and curiousj-framekit in $bin, from ${CURIOUSJ_FRAMEKIT_SOURCE:-$default_source}"
    fi
    [ -n "${CURIOUSJ_FRAMEKIT_NO_INIT:-}" ] || echo "and then run \`cjf init\`, which asks before each change it makes."
    confirm "continue?"

    if [ -z "$mise" ]; then
        say "installing mise from mise.run"
        tmp=$(mktemp)
        trap 'rm -f "$tmp"' EXIT
        fetch https://mise.run > "$tmp" || die "could not download the mise installer"
        MISE_INSTALL_PATH=$bin/mise sh "$tmp" || die "the mise installer failed"
        mise=$(find_tool mise) || die "mise installed, but not found in $bin"
    fi
    if [ -n "$missing" ]; then
        say "installing$missing through mise"
        # shellcheck disable=SC2086  # the tool names are meant to split
        "$mise" use -g $missing || die "\`mise use -g$missing\` failed"
        uv=$(find_tool uv) || uv=$("$mise" which uv) || die "uv installed through mise, but not found"
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
    [ -x "$bin/cjf" ] || die "installed, but $bin/cjf is missing"

    if [ -n "${CURIOUSJ_FRAMEKIT_NO_INIT:-}" ]; then
        say "done. Next: cjf init"
        return
    fi
    say "running cjf init"
    if [ -n "${CURIOUSJ_FRAMEKIT_YES:-}" ]; then
        "$bin/cjf" --yes init
    else
        "$bin/cjf" init < /dev/tty
    fi
}

confirm() {  # ask on the terminal; yes without one, or with CURIOUSJ_FRAMEKIT_YES
    [ -z "${CURIOUSJ_FRAMEKIT_YES:-}" ] || return 0
    [ -r /dev/tty ] || return 0
    printf '%s [Y/n] ' "$1" > /dev/tty
    read -r reply < /dev/tty || die "no answer; stopping"
    case $reply in
        ''|y|Y|yes|YES|Yes) ;;
        *) echo "curiousj-framekit: stopped; nothing was installed"; exit 1 ;;
    esac
}

install_from() {  # install SOURCE: replaces any install already there
    case $1 in
        git+*) command -v git > /dev/null 2>&1 || die "installing from $1 needs git" ;;
    esac
    say "installing curiousj-framekit from $1"
    "$uv" tool install --force "$1" || die "\`uv tool install $1\` failed"
}

find_tool() {  # NAME on PATH, else where its installer or mise puts it
    if command -v "$1" > /dev/null 2>&1; then
        command -v "$1"
        return
    fi
    for f in "$bin/$1" "$HOME/.cargo/bin/$1" "$shims/$1"; do
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
die()  { printf 'curiousj-framekit: error: %s\n' "$1" >&2; exit 1; }

main "$@"
