## Shell init

Since stage 3 of the reorganization this is `cjf init`'s: it writes
`~/.local/share/curiousj-framekit/init.sh`, one file for bash and zsh
whose parts each guard themselves (Frametop terminals, Homebrew, the
shims and `~/.local/bin` on `PATH`, mise, the `waypipe` function, the
`tailscale` alias, and `cjf`'s completion from files beside it), and
one marked block at the top of `~/.bashrc` and `~/.zshrc` that sources
it. The text below describes the `shell-init/` scheme it replaced, kept
for the reasons behind each part until the docs are rewritten.

`shell-init/` holds one file per feature. `setup.sh` puts two marked
blocks into `~/.bashrc`, and into `~/.zshrc` if that exists, each a
short loop that sources the chosen files from this checkout:

```sh
# >>> steam-frame-utils: top >>>
# https://github.com/curiousjtuber/steam-frame-utils#shell-init
for _sfu in brew frametop bin; do
    _sfu="$HOME/steam-frame-utils/shell-init/$_sfu.sh"
    [[ -r $_sfu ]] && source "$_sfu"
done
unset _sfu
# <<< steam-frame-utils: top <<<
```

The files are read live, so a `git pull` changes the next shell without
a `setup.sh` re-run. The path is filled in from where `setup.sh` runs,
so the checkout can be anywhere; after moving it, run `setup.sh` again,
and until then the `-r` test just skips the files, rather than failing
every shell start. `setup.sh` refuses a path with `"`, `$`, `` ` ``,
`\`, `|` or `&` in it.

| Block | Files |
|---|---|
| `top`, at the start of the file | `brew.sh` with `--brew` (see [Homebrew](install.md#homebrew)), and `frametop.sh` and `bin.sh` always |
| `end`, at the end of the file | `waypipe.sh` with `--waypipe`, `tailscale.sh` with `--tailscale`, and `mise.sh` with `--mise` (see [mise](shell-init.md#mise)) |

`bin.sh` puts this checkout's `bin/` on `PATH`, ahead of Homebrew and
behind `~/.local/bin`, which the rc file puts first further down. It
finds the checkout from its own path (`BASH_SOURCE` in bash, `%x` in
zsh), so nothing but the blocks names it. distrobox puts `bin/` first
too, through [`~/.distroboxrc`](shell-init.md#distroboxrc).

A file stays in once it's there, so a run without its option keeps it.
An rc file with blocks of earlier versions, one per file or with the
files' text inline, gets them replaced by these two.

The bare host and its distroboxes share one home directory, so the same
blocks run in all of them. The containers read the same `~/.bashrc`, so
any host-only line added there outside these blocks runs inside every
distrobox too. Put such checks in a `shell-init/` file instead.

### mise

`shell-init/mise.sh` runs `mise activate` for the running shell, bash or
zsh, so the tools mise manages are on `PATH` in every shell: rust, for a
Rust package in `pkgbuilds/frame/`, and whatever else `mise use -g`
added. It skips itself when `~/.local/bin/mise` is missing, or when mise
is active already (`MISE_SHELL` is set), and `setup.sh` leaves an rc
file alone that activates mise on a line of its own. `setup.sh --mise`
installs mise with its own installer, one binary in `~/.local/bin`, and
`mise use -g rust` when cargo doesn't resolve; the version is mise's
business (`latest`), and `mise upgrade` keeps it current. The tools live
under `~/.local/share/mise`, so SteamOS updates keep them.

### The tailscale alias

`tailscale.sh` checks where it is running, using `$CONTAINER_ID` or
`/run/.containerenv`:

| Where | `tailscale` alias |
|---|---|
| Bare host (bash) | `/home/.tailscale/bin/tailscale` |
| A distrobox (bash or zsh) | `distrobox-host-exec /home/.tailscale/bin/tailscale` |

A distrobox sees neither `/home/.tailscale` nor the daemon's socket in
the host's `/run`, so the CLI has to run on the host.

### The waypipe function

SteamOS has no waypipe, and Valve's package repos for the Frame don't
carry it, so `--waypipe` installs [Arch Linux
ARM](https://archlinuxarm.org)'s aarch64 package under `~/.local`
through `install-waypipe.sh`, when `pacman-home` doesn't have it yet;
re-run `install-waypipe.sh` to update. The package needs only libc,
libgcc, lz4 and zstd, which SteamOS has, and no file outside its binary
and man page, so it runs on the host as it is (see [Packages for the
host](packages.md#packages-for-the-host)). `install-waypipe.sh` runs `pacman-home
relocate waypipe`: pacman syncs Arch Linux ARM's package databases from
one mirror, downloads the package when the installed version differs,
takes it only with a valid signature from Arch Linux ARM's keys (see
below), and the package's `/usr` tree is moved under `~/.local` and
installed into `pacman-home`'s database, so `pacman-home -Q waypipe`
knows it and `pacman-home -R waypipe` removes it. A library the host
lacks, a newer glibc among them, is reported before the install. A
waypipe from before `pacman-home`, a bare binary in `~/.local/bin`, is
backed up to `waypipe.bak-<timestamp>` first. `--waypipe=box` takes the
other source: a copy of the `arch` box's `/usr/bin/waypipe`, the same
package, which pacman in the box keeps current and a re-run of `setup.sh
--waypipe` refreshes. `pacman-home -Qo ~/.local/bin/waypipe` says which
is in place, and switching asks (see [emacs and waypipe: host or
box](install.md#emacs-and-waypipe-host-or-box)).

`shell-init/waypipe.sh` wraps `waypipe` in a function. Game Mode is an
X11 session: gamescope names its Wayland socket only in
`GAMESCOPE_WAYLAND_DISPLAY` (`gamescope-0`), so a `waypipe` client
started from a terminal there fails with `WAYLAND_DISPLAY is not set`.
When `WAYLAND_DISPLAY` is empty, the function fills it in from
`GAMESCOPE_WAYLAND_DISPLAY` for that one command. With that, `waypipe
ssh <host> <app>` from a Game Mode Konsole shows a remote app on the
Frame. The shell itself doesn't export it, because Qt and GTK apps
started from that terminal would then leave Xwayland for native Wayland.

### Frametop terminals

[Frametop](https://github.com/DeeJanuz/frametop)'s desktop gives Plasma
config and state dirs of its own (`XDG_CONFIG_HOME=~/.config/frametop`,
`XDG_STATE_HOME=~/.local/state/frametop`), so its panels and layout
never touch the stock desktop's. A terminal in that desktop inherits
them. That suits KDE tools run from it, which then change the Frametop
desktop's settings, but command-line tools miss their config: mise takes
`~/.config/mise/config.toml` for an untrusted project file and asks for
`mise trust`.

In such a shell, `frametop.sh` points mise at its usual dirs with
`MISE_CONFIG_DIR` and `MISE_STATE_DIR`, and leaves the XDG ones alone.
They're exported ahead of `mise activate`, hence the top of the rc file,
since mise's prompt hook reads its config again before every prompt;
after it, mise still works but warns once in every new shell. For other
tools, `frametop-xdg off` switches the rest of the shell session to the
usual XDG dirs, `frametop-xdg on` brings the desktop's back, and
`frametop-xdg` shows which are in use. Outside a Frametop desktop the
file does nothing. Inside a distrobox it isn't needed: `distrobox enter`
resets the XDG dirs to the usual ones itself.

## Distrobox in Desktop Mode

Desktop Mode on the Frame is Plasma nested inside gamescope, with its
own session environment (Frametop's desktop has the same, with
`/run/user/1000/frametop`):

- `XDG_RUNTIME_DIR=/run/user/1000/nested_plasma` rather than
  `/run/user/1000`
- `DBUS_SESSION_BUS_ADDRESS` is a private bus under `/tmp` with no
  `systemd --user` behind it

Rootless podman breaks on both. crun asks `org.freedesktop.systemd1` on
the session bus for the container's cgroup, so `distrobox enter` fails
with `crun: sd-bus call: Process org.freedesktop.systemd1 exited with
status 1`. And podman keeps its runtime state under `$XDG_RUNTIME_DIR`,
so a container started from SSH or Game Mode looks unset-up from Desktop
Mode: `unable to find user steamos: no matching entries in passwd file`.

`bin/podman` switches podman alone to the real runtime dir and user bus
when it runs under a runtime dir nested in `/run/user/<uid>`, such as
`nested_plasma` or Frametop's `frametop`, and passes through untouched
everywhere else. Without it, from Frametop's desktop `distrobox enter`
fails with `crun: error opening file
/run/user/1000/frametop/crun/<id>/status`. distrobox still forwards the
Desktop Mode environment into the container, so GUI apps there reach the
nested Plasma's `wayland-0`, X display and session bus. It is found from
this checkout, whose `bin/` comes before `/usr/bin` in `PATH`. Inside a
distrobox, which has the same `PATH` but no podman of its own, it hands
over to the host's podman through `distrobox-host-exec`, so `podman ps`
works there too.

### `~/.distroboxrc`

Since stage 3 `cjf init` puts a marked block here that moves
`~/.local/share/curiousj-framekit/shims` to the front of `PATH`, where
the podman shim lives; the text below has the reason.

The checkout's `bin/` is on `PATH` once an rc file has run, but not for
a distrobox export started without one, such as one started from a
launcher. The export runs `distrobox-enter` by its full path, which then
finds `/usr/bin/podman` and fails with the crun error above. distrobox
sources `~/.distroboxrc` before it looks for podman, so `setup.sh` puts
a block there (`distrobox/distroboxrc`) that moves `bin/` to the front
of `PATH` for distrobox alone. An earlier version copied `bin/podman` to
`~/.local/bin` instead, and `setup.sh` backs up that copy out of the
way.
