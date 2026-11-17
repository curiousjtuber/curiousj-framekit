# curiousj-framekit: the shell side of the kit, for bash and zsh. Written
# by `cjf init` to ~/.local/share/curiousj-framekit/init.sh and sourced
# from one marked line at the top of ~/.bashrc and ~/.zshrc, which the
# host and every distrobox share. Each part guards itself, so the file
# stays right as items are installed or removed; `cjf init` rewrites it
# (the completion at the end is generated). Edit the source in the kit,
# not this copy.

# --- Frametop terminals ------------------------------------------------
# Frametop's desktop gives its session XDG_CONFIG_HOME=~/.config/frametop
# and XDG_STATE_HOME=~/.local/state/frametop so that its Plasma never
# touches the stock desktop's; a terminal there inherits them. KDE tools
# run from it should see those, command-line tools their usual dirs:
# mise would take ~/.config/mise/config.toml for an untrusted project
# file. So mise is pointed at its usual dirs (ahead of its activation,
# since its prompt hook rereads its config), and `frametop-xdg off|on`
# switches the rest of the shell session.
if [[ ${XDG_CONFIG_HOME:-} == "$HOME/.config/frametop" ]]; then
    export MISE_CONFIG_DIR=$HOME/.config/mise
    export MISE_STATE_DIR=$HOME/.local/state/mise
    export FRAMETOP_XDG_CONFIG_HOME=$XDG_CONFIG_HOME
    export FRAMETOP_XDG_STATE_HOME=$XDG_STATE_HOME
fi
if [[ -n ${FRAMETOP_XDG_CONFIG_HOME:-} ]]; then
    function frametop-xdg {
        case ${1:-} in
            off) unset XDG_CONFIG_HOME XDG_STATE_HOME ;;
            on)
                export XDG_CONFIG_HOME=$FRAMETOP_XDG_CONFIG_HOME
                export XDG_STATE_HOME=$FRAMETOP_XDG_STATE_HOME
                ;;
            '') ;;
            *) echo "usage: frametop-xdg [off|on]" >&2; return 2 ;;
        esac
        echo "XDG_CONFIG_HOME=${XDG_CONFIG_HOME:-(unset: ~/.config)}"
        echo "XDG_STATE_HOME=${XDG_STATE_HOME:-(unset: ~/.local/state)}"
    }
fi

# --- Homebrew ------------------------------------------------------------
# On the host only: a distrobox doesn't see /home/linuxbrew. Ahead of the
# PATH additions below, so that those come first.
if [[ -x /home/linuxbrew/.linuxbrew/bin/brew && :$PATH: != *:/home/linuxbrew/.linuxbrew/bin:* ]]; then
    eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
fi

# --- PATH: the shims, then ~/.local/bin ------------------------------------
# The shims directory holds programs that must carry another program's
# name and come before /usr/bin: today only podman, which distrobox needs
# from the nested desktops. ~/.local/bin holds the kit's commands, uv's
# and mise's.
_cjf_shims=$HOME/.local/share/curiousj-framekit/shims
case :$PATH: in
    *:"$_cjf_shims":*) ;;
    *) export PATH="$_cjf_shims:$PATH" ;;
esac
case :$PATH: in
    *:"$HOME/.local/bin":*) ;;
    *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
unset _cjf_shims

# --- mise ------------------------------------------------------------------
# The tools mise manages on PATH in every shell: uv and fzf, which the
# kit needs, rust for a Rust package, and whatever else `mise use -g`
# added. Skipped when mise isn't installed or is active already.
if [[ -x $HOME/.local/bin/mise && -z ${MISE_SHELL:-} ]]; then
    if [[ -n ${ZSH_VERSION:-} ]]; then
        eval "$("$HOME/.local/bin/mise" activate zsh)"
    else
        eval "$("$HOME/.local/bin/mise" activate bash)"
    fi
fi

# --- waypipe from a Game Mode terminal ------------------------------------
# Game Mode is an X11 session: gamescope names its Wayland socket only in
# GAMESCOPE_WAYLAND_DISPLAY, so a waypipe client started there would fail
# with "WAYLAND_DISPLAY is not set". The shell itself doesn't export it,
# since Qt and GTK apps started from that terminal would then leave
# Xwayland for native Wayland.
function waypipe {
    if [[ -z $WAYLAND_DISPLAY && -n $GAMESCOPE_WAYLAND_DISPLAY ]]; then
        WAYLAND_DISPLAY=$GAMESCOPE_WAYLAND_DISPLAY command waypipe "$@"
    else
        command waypipe "$@"
    fi
}

# --- libfuse 2 for AppImages -------------------------------------------
# SteamOS 0.5.7 dropped fuse2, and an AppImage's runtime dlopens
# libfuse.so.2 to mount itself. With the kit's fuse2 package installed
# and none in the image, its directory goes on LD_LIBRARY_PATH, so an
# AppImage started from a shell runs as it is; the directory holds
# nothing but libfuse, so nothing else travels with it. On the host
# only: a distrobox has its own /usr and its own fuse2 to install. An
# image that ships fuse2 again turns this off by itself.
_cjf_fuse2=$HOME/.local/lib/fuse2
if [[ -e $_cjf_fuse2/libfuse.so.2 && ! -e /usr/lib/libfuse.so.2
      && -z ${CONTAINER_ID:-} && ! -e /run/.containerenv ]]; then
    case :${LD_LIBRARY_PATH:-}: in
        *:"$_cjf_fuse2":*) ;;
        *) export LD_LIBRARY_PATH="$_cjf_fuse2${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ;;
    esac
fi
unset _cjf_fuse2

# --- tailscale ---------------------------------------------------------
# The CLI lives on the persistent home partition, not on PATH; a
# distrobox sees neither it nor the daemon's socket, so there it runs on
# the host.
if [[ -x /home/.tailscale/bin/tailscale || -n ${CONTAINER_ID:-} || -e /run/.containerenv ]]; then
    if [[ -n ${CONTAINER_ID:-} || -e /run/.containerenv ]]; then
        alias tailscale='distrobox-host-exec /home/.tailscale/bin/tailscale'
    else
        alias tailscale=/home/.tailscale/bin/tailscale
    fi
fi

# --- cjf completion ----------------------------------------------------
# Generated by `cjf init` into one file per shell, beside this one: a
# shell parses a whole if-block before running it, so the other shell's
# script can't sit inline. zsh's needs compinit to have run (compdef),
# and this file is sourced from the top of ~/.zshrc, ahead of whatever
# runs compinit there (oh-my-zsh, say). So without compdef the script
# waits for the first prompt, when the rc file is done, and is dropped
# if there is still no compdef then.
if [[ -n ${ZSH_VERSION:-} ]]; then
    if [[ -r ~/.local/share/curiousj-framekit/completion.zsh ]]; then
        if command -v compdef >/dev/null 2>&1; then
            source ~/.local/share/curiousj-framekit/completion.zsh
        else
            function _cjf_completion_at_prompt {
                add-zsh-hook -d precmd _cjf_completion_at_prompt
                unfunction _cjf_completion_at_prompt
                if command -v compdef >/dev/null 2>&1; then
                    source ~/.local/share/curiousj-framekit/completion.zsh
                fi
            }
            autoload -Uz add-zsh-hook
            add-zsh-hook precmd _cjf_completion_at_prompt
        fi
    fi
elif [[ -n ${BASH_VERSION:-} && -r ~/.local/share/curiousj-framekit/completion.bash ]]; then
    source ~/.local/share/curiousj-framekit/completion.bash
fi
