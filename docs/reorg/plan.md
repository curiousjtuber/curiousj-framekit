# Reorganizing steam-frame-utils: requirements and UX

> **Closed 2026-11-01.** The reorganization this planned is done: all
> seven stages of [steps.md](steps.md) ran, and the repository is
> `curiousj-framekit`. Kept as the record of the decisions and why,
> not updated after this date. What the kit does today is in the
> [README](../../README.md) and [docs/](../).

Draft of 2026-10-31, revision 10, written from the rough notes at the
end of this file and a read of the whole repo, curiousj-tools and the
Frame (SteamOS 0.5.6, Python 3.12). Every question is now decided and
says so; section 0 lists the decisions. Numbers stay fixed across
revisions.

## 0. Decisions

- **D1. No setup/install/apps tiers.** The split between `setup.sh`'s
  parts, the top-level `install-*.sh` and `apps/` is historical, not
  a difference in kind: Homebrew, zsh, emacs, Nerd Fonts and Tailscale
  are as optional as any app. The new shape is a small *base* that
  everything assumes, and one *catalog* of optional items.
- **D2. The four install groups were a first cut, not a requirement.**
  Kinds come from what the install code has to do for an item (Q15).
- **D3. The per-app Flatpak scripts go away**, replaced by a `flatpak`
  kind in the catalog with a configurable installation scope (Q6).
- **D4. Distrobox stays as an optional app**; what goes is the `arch`
  box as a route for emacs and waypipe (Q18, goal 3).
- **D5. The name is `curiousj-framekit`** (Q1): repo, package, PyPI
  name, umbrella command, config and state directories; `cjf` is the
  short entry point for typing.
- **D6. One root command, `curiousj-framekit` (`cjf`), plus the Beat
  Saber tools as commands of their own** (Q2), under their current
  names (Q17).
- **D7. Of the thirteen current names three survive**: `pacman-home`
  (Q3), `beat-saber-recent` and `bsmanager` (Q17).
- **D8. A picker, not a TUI** (Q4).
- **D9. The base is mise, with uv and fzf through it, the package,
  `~/.local/bin` on `PATH`, and one rc line** (Q5). `install.sh` puts
  the first three in place, says what it will install and asks once,
  then runs `cjf init` for the rest.
- **D10. Every kind in the Q15 table is code or a doc line as its
  lean says**, decided per item when the catalog is written out.
- **D11. No recommended set** (Q16). No flag, no "fresh Frame"
  one-liner; the picker and `install NAME` are the only ways in.
- **D12. The trust posture stays and moves into the catalog** (Q7).
- **D13. The Frame is detected positively from `/etc/os-release`**;
  everything else is a PC (Q8).
- **D14. `bsmanager` keeps only its Frame half** (Q10), and
  curiousj-tools becomes a catalog item.
- **D15. Beat Saber is `beat-saber-recent` (with `--record` and
  `--install-hook`) and `bsmanager`**, with room to grow (Q11).
- **D16. Everything is ported to Python, `pacman-home` and `homeify`
  included** (Q12).
- **D17. A `cjf migrate` command handles the rename** (Q13).
- **D18. Python 3.12 or later; the RDP server's GUI is a standalone
  stdlib-plus-`gi` script run by the system Python** (Q14).
- **D19. Every suggestion in section 4 is accepted.**
- **D20. The PC side is `pc/` in this repo, PKGBUILDs and docs, no code
  yet**; when the first PC command is written, `pc/` becomes a uv
  workspace member, `curiousj-framekit-pc`, without moving anything
  (Q9).
- **D21. Dependencies are declared and named, never silent** (Q19): a
  catalog item lists the items it needs and `install` asks for them
  with it, up front; a command that needs an item refuses in one line
  that gives the `cjf install` to run.
- **D22. The headset's battery shows in `cjf vr` and `cjf status`**,
  read from the kernel, so it needs no SteamVR.
- **D23. `cjf status` is the Frame's live state, `cjf installed` the
  catalog's, and `status --all` both.** `status` also shows the kit's
  own version and where it is installed from.
- **D24. `cjf after-update` records the SteamOS version and build at
  each run**, in `~/.local/state/curiousj-framekit/after-update.toml`,
  and reports the change since.

Nothing is open. The implementation plan is
[steps.md](steps.md); the usage scenarios it should end in
are [scenarios.md](scenarios.md).

## 1. What is wrong today

**The name says nothing.** "steam-frame-utils" could be any grab bag,
and the GitHub namespace already has Frametop, Frame Control and
others whose names say what they do.

**Unlike things sit side by side with nothing saying what runs where.**
The top level has a 1,200-line interactive installer (`setup.sh`),
three loose `install-*.sh`, eight more under `apps/`, thirteen tools in
`bin/` (nine bash, three Python, one `sh`), rc fragments in
`shell-init/`, three single-file config directories (`autostart/`,
`environment.d/`, `distrobox/`), PKGBUILDs for two different machines,
and an 885-line README that is the only map. The Frame parts and the PC
parts are interleaved: `bin/bsmanager` runs on either machine and
ssh-es from the PC into the Frame, `pkgbuilds/pc/` is PC-only, and
everything else is Frame-only, but only the README says so.

**Three tiers of installer that don't mean anything.** `setup.sh`
installs some optional things through options (`--brew`, `--emacs`,
`--tailscale`, `--nerd-fonts`), delegates two of them to top-level
`install-*.sh` scripts that can also be run alone, and leaves `apps/`
to be run by hand. Which tier a thing landed in says when it was
written, not whether it is needed, who it is for, or how it installs.
The README's "fresh Frame" one-liner exists to paper over this.

**The same shell boilerplate is pasted into every script.**

| Fragment | Copies |
|---|---|
| "am I in a distrobox" check (`CONTAINER_ID`, `/run/.containerenv`) | 17 files |
| `die()` | 21 files |
| `usage()` printing the header comment through `sed` | 11 files |
| flatpak: add remote, confirm the runtime download, user install, report a system copy | 4 installers, identical but for two variables |
| `--yes` handling and the ask-before-download prompt | 5 installers |
| fetch a GitHub release and check a SHA-256 | 4 scripts, each its own way |

That is about 4,900 lines of shell in all, and the duplicated parts are
also where the bugs recur (a fix to one flatpak installer has to be
made four times). The bloat of the install scripts is one of the
motivations for this reorganization, so the replacement has to be
smaller, not a port.

**The `arch` distrobox is a second route that no longer earns its
place.** It exists for emacs and waypipe, both of which now build or
relocate natively through `pacman-home`. Supporting the second route
costs the two-route logic in `setup.sh` (`--emacs=host|box`,
`--waypipe=host|box`, switching with backups), the box's creation with
its pacman sandbox workaround, and a doc on arm64 Arch images.
Distrobox itself, and what makes it work from the nested desktops
(`bin/podman`, the `~/.distroboxrc` block), is a different matter: see
D4.

## 2. Goals, restated

1. **Rename** the repository, and give the package, the command and
   the config directory the same name: `curiousj-framekit`, a sibling
   of `curiousj-tools`.
2. **One Python project** replaces the shell scripts: a `src/` layout
   package built with hatchling and installed with `uv tool`, as
   curiousj-tools already is on both machines. `curiousj-framekit`,
   typed as `cjf`, has subcommands for general Frame operations and
   for installing (one catalog of optional items, see section 3); the
   Beat Saber tools are commands of their own. Run bare, a command
   offers its operations in a picker, the way Bazzite's `ujust` does.
3. **No `arch` box, and no second route for anything.** Emacs and
   waypipe come through `pacman-home` only. Distrobox remains an
   optional app, with the pieces that make it work from Desktop Mode
   and Frametop's desktop (the podman shim, the `~/.distroboxrc` block,
   the host-exec branch of the tailscale alias), since the home
   directory is shared with every box.
4. **No code that ssh-es from the PC into the Frame.** Each command is
   a Frame command or a PC command, and says so. On the PC, an Arch
   family distro (CachyOS) installs its parts through PKGBUILDs.
5. **Installs are declared, not scripted.** Each optional item is an
   entry in one catalog (what it is, how it installs, what is
   checked), and a few generic routines, one per kind, do the work.
   Where an item needs no code beyond one upstream command, the entry
   is documentation and nothing else.

## 3. Questions

### Naming and shape

**Q1. The name.** Decided: `curiousj-framekit`, for the repo, the
package, the PyPI name, the umbrella command,
`~/.config/curiousj-framekit/` and `~/.local/state/curiousj-framekit/`;
the import name is `curiousj_framekit`, and `cjf` is a second entry
point onto the same command, for typing. Two reasons for the prefix,
after `framekit` was the first choice:

- **The contents are personal.** The catalog is one person's list of
  what goes on a Frame, the Beat Saber tools one person's habits, the
  emacs build one person's editor. A neutral name promises a general
  toolkit the repo is not; the prefix says whose it is, as
  `curiousj-tools` does, and the two read as siblings.
- **`framekit` is taken on PyPI**, by a package with no summary or
  home page, so `uv tool install framekit` would have fetched a
  stranger's package. `curiousj-framekit` is free there (checked
  2026-10-31), as are `cjf` and `curiousj-framekit` as command names
  on both machines and `curiousjtuber/curiousj-framekit` on GitHub.

`curiousj-frame` was considered and dropped: bare "frame" names the
headset, so it reads as "curiousj's Frame", not tools for it; the
suffix says what the repo holds, the prefix whose. `framectl` was
avoided because of saphid's Frame Control.

On GitHub the repo is renamed in place, not recreated: history,
stars, issues, releases and the krdp release assets stay, and GitHub
redirects the old name for the web and for git over HTTPS and SSH
until a repo of the old name is created, so none ever is. The README
says "formerly steam-frame-utils" for a release or two, every checkout
gets `git remote set-url`, and the URLs in script headers and the
workflow comment are updated. The rename happens when the Python
package lands on `dev`, so the old name and the shell scripts go
together; the Frame's checkout stays at `~/steam-frame-utils` until
`migrate` exists, since the rc blocks there name that path.

**Q2. One root command or one per area?** Decided: one root,
`curiousj-framekit`, with groups (`cjf cursor size 32`, `cjf vr off
left`, `cjf install moonlight`; `cjf` is the short entry point, and
the examples below use it), plus the Beat Saber tools as commands of
their own, since their names go into Steam's launch options and are
typed on their own. Their names are Q17.

**Q17. The Beat Saber command's name.** Decided: there is no single Beat
Saber command; the two tools keep their current names,
`beat-saber-recent` and `bsmanager`, as entry points onto
`curiousj_framekit.beatsaber`. A bare `beatsaber` would read as the
command that starts the game, so any umbrella would have needed a prefix
or suffix (`beatsaber-tools`), and the two tools have unrelated jobs
anyway: one reads Unity's logs and the recorded songs, the other is a
thin launcher with a few checks. Keeping the names also means the launch
options already set in Steam keep their form, and `bsmanager` collides
with nothing: the upstream installer puts only the AppImage in
`~/Applications` and a `bs-manager.desktop` entry, no command on `PATH`.
`bsaber`, `bsr` and `saber` were considered and dropped with the
umbrella.

**Q3. Do the thirteen current names survive?** Decided: no, except
`pacman-home`, which is a drop-in for pacman with pacman's flags and
stays a name on `PATH` (as a second entry point onto the same code),
and the two Beat Saber names (Q17).

**Q4. Picker or TUI?** Decided: the picker. fzf when present, else a
numbered menu, as curiousj-tools' `pick-lines` does; reuse or copy
that. The GTK window for the RDP server (`krdpd-gui`) stays a GTK
window.

### Base and catalog

The shape after D1: a **base** that the package itself needs and that
every item assumes, and a **catalog** of optional items, each one
installed on its own (`cjf install NAME`) or from the picker
(`cjf install` bare). `cjf status` shows every item as
installed, missing or out of date, which is what `setup.sh --check`
and the "ok / missing" lines do today.

**Q5. What is in the base?** Decided (revised 2026-10-31 from the
scenario review): mise, and through it uv and fzf, since every
install needs uv and every menu wants fzf; the package itself;
`~/.local/bin` on `PATH`; and one rc line that brings in the shell
side (mise's activation, brew's shellenv, the waypipe function, the
tailscale alias, the Frametop XDG fix), each part guarding itself at
source time
as the `shell-init/` files do now, so the emitted file never has to be
regenerated when an item is added or removed. `install.sh` installs
mise from mise.run when it is missing, runs `mise use -g uv fzf` for
what is missing of those two, lists all it is about to install and
asks once, installs the package as a uv tool, and ends by running `cjf
init`, which asks per file as before and finds nothing to do on a
re-run. Rust stays an item (`rust`, through mise), since only a Rust
PKGBUILD needs it. The Desktop Mode cursor fix is a choice and so a
catalog item.

One point to settle while implementing, not a decision to take now: the
rc files are shared with every distrobox, and inside a box the `uv tool`
venv's Python may not run when it is the host's `/usr/bin/python3`; when
it is mise's, which lives under `~/.local` and is what uv picks on the
Frame today (Q14), it does. Measured on the Frame, 2026-10-31: a click
command such as `curiousj-tools init bash` takes 46 to 64 ms to start, a
bare `/usr/bin/python3` 18 ms, and sourcing today's six `shell-init/`
files 54 ms. So `eval "$(curiousj-framekit init bash)"` roughly doubles
the shell-init cost. Lean, still: the rc line sources a static file the
base install writes (`~/.local/share/curiousj-framekit/init.sh`,
`curiousj-framekit init --path` finds it), which costs nothing in Python
at shell start and works in every box; `curiousj-framekit init bash`
exists for the curiousj-tools-style one-liner where that is fine.

**Q6. Flatpaks: a list file, or an install feature?** Decided: (b), a
`flatpak` kind in the catalog, one routine of about thirty lines doing
what the four scripts do (add the remote if missing, install or update,
make sure the runtime is in the same installation, note a copy in the
other installation). The four scripts are the same script with two
variables, so each app is one entry: id, remote, remote URL, one line
of description.

Added: the **installation scope is configurable**, `user` (the default,
as today: no root, no polkit, works over SSH, survives updates in
`/home`) or `system` (`sudo flatpak --system …`; over SSH sudo asks once
rather than polkit per ref, as curiousj-tools' `flatpak-update`
operation notes). Per entry in the catalog, overridden by `[flatpak]
scope = …` in `~/.config/curiousj-framekit/config.toml` or a `--system`
flag. With `system`, the "a system copy exists too" note becomes the
other way round, and the runtime check applies to that installation.

**Q15. Which kinds does the catalog need, and which items are
documentation only?** Decided: the table below is the list, and the
lean under it is how each is decided when the catalog is written out.

| Kind | Items | What the code does beyond one upstream command |
|---|---|---|
| `flatpak` | Moonlight, KRDC, Deskflow (Flathub); Stream Frame (own remote) | see Q6 |
| `flatpak-build` | KRdp's server | flatpak-builder from our manifest and patches; `--bundle`; CI |
| `upstream-installer` | BSManager, Full Keyboard, Frametop | fetch the release, check a sum (recorded, or the release's `SHA256SUMS`), run the upstream installer with the right flags, handle `--uninstall` |
| `pacman-home` | waypipe (relocate), emacs, pacman 7 | build or relocate, dependency order, version check against the PKGBUILD |
| `brew` | Homebrew itself, zsh, wl-clipboard | create `/home/linuxbrew` with sudo once, run the installer, `brew install` |
| `mise` | rust (for a Rust PKGBUILD) | `mise use -g NAME`; mise itself is base (Q5) |
| `installer-script` | distrobox (`--prefix ~/.local`) | `curl \| sh` into `~/.local/bin`, then the podman shim and `~/.distroboxrc` block |
| `uv-tool` | curiousj-tools | `uv tool install git+…` (uv is there after the bootstrap); upgrade with `uv tool upgrade` |
| `system-service` | Tailscale | tarball to `/home/.tailscale`, unit, firewalld zone, all as root |
| `fonts` | Nerd Fonts | per-font release check, sum, fontconfig rule |
| `config` | software cursor + autostart entry, cursor size | write a file, back up what was there, say what needs a reboot |

Each kind is one routine; each item is one entry. Implement
`flatpak`, `upstream-installer`, `pacman-home`, `config`,
`system-service` and `installer-script` as code, since each has
checks, ordering or follow-up steps worth keeping; `brew`, `mise`,
`uv-tool` and `fonts` are code only if the entry's checks (sums,
versions) justify it, else a doc line. A doc-line item still has a
catalog entry so that `status` can report it.

**Q19 (new). How are dependencies handled?** Decided (D21). Two kinds
of dependency exist, and each is declared where it belongs:

- *An item needs an item.* The catalog entry says so (`needs =
  ["homebrew"]` on `zsh` and `wl-clipboard`; a Rust PKGBUILD's entry
  needs `rust`). `cjf install zsh` resolves the needs, lists what will
  be installed as one question up front, and installs in dependency
  order; `--check` lists the same. The picker shows "(needs X)" in the
  description. Nothing is installed silently as a side effect.
- *A command needs an item.* `cjf rdp` needs `krdp`; `bsmanager` needs
  `bsmanager` and `waypipe`; `cjf pkg build` of a Rust PKGBUILD needs
  `rust`; `cjf vr off` needs SteamVR running (a state, not an item,
  but the same one-line shape). Each checks at its start and refuses
  in one line that names the item and the `cjf install …` to run, the
  way `where.py`'s refusals name the host. One helper, `needs(item)`,
  reads the catalog's state so that command and `status` agree.

Not a dependency: a Flatpak's runtime, which `flatpak install`
resolves itself, and the host's own libraries, which `pacman-home`
checks at build time; both stay inside their kinds.

**Q16. Is there a recommended set?** Decided: no. No flag, and the
"fresh Frame" one-liner goes. A first run opens the picker over the
whole catalog, with each item's one-line description and state, and
that is the recommendation.

**Q7. How much of the trust posture stays?** Decided: all of it. The
checks that exist (recorded SHA-256 for Frametop, release sums for
Full Keyboard and Nerd Fonts, PGP for ALARM packages, the pinned
keyring fingerprint) move into the catalog entries (expected sum, sums
file, signature), and one `TRUST.md` is generated from or checked
against the catalog. Where an item becomes a doc line, TRUST.md says
the check went with it.

**Q18 (new). What of distrobox stays, and where?** From the feedback:
the `arch` box and the box routes go; distrobox is an optional app.
Its catalog entry installs distrobox under `~/.local` and the two
things that make it work from the nested desktops:

- the **podman shim**, today `bin/podman`, which switches podman to
  the real runtime dir and user bus under a nested `XDG_RUNTIME_DIR`.
  It has to be named `podman` and sit ahead of `/usr/bin` on `PATH`,
  but only for shells and for distrobox, never for Frametop's own
  podman use; so it lives in a shims directory
  (`~/.local/share/curiousj-framekit/shims/`) that the rc init and the
  `~/.distroboxrc` block put first, as the checkout's `bin/` is today.
  It stays a few lines of `sh`: distrobox runs podman many times per
  command, and a Python start each time would show.
- the **`~/.distroboxrc` block**, which puts that directory first for
  a distrobox export started outside any shell.

The tailscale alias keeps its `distrobox-host-exec` branch, and the
"where am I" module keeps a "inside a container" answer, since the
shared home means `curiousj-framekit` can be invoked from a box:
host-only operations refuse there with one line, as the scripts do now.
What is deleted: `--arch`, `--emacs=box`, `--waypipe=box`, the route
detection and switching, `IN_BOX_RUN`, and
`docs/arch-distrobox-images.md` (kept in git history).

### Frame versus PC

**Q8. The truncated "other: assume on …".** Decided: detect the Frame
positively from `/etc/os-release` (SteamOS, and the Frame's build id),
and treat every other machine as a PC. A PC command refuses on the
Frame and the other way round, with a one-line message.

**Q9. How is the PC side organized?** Decided: option 1 now, option 2
when needed. `pc/pkgbuilds/` and `pc/README.md` hold the two PKGBUILDs
(`krdpserver-embed-cursor`, `frame-control-bin`) and the PC-side
instructions, with no code. When the first PC command is written, `pc/`
gains a `pyproject.toml` and `src/curiousj_framekit_pc/` and the root
`pyproject.toml` lists it under `[tool.uv.workspace] members`; the
command installs with `uv tool install --editable ./pc` from a checkout
or `uv tool install "git+https://…/curiousj-framekit#subdirectory=pc"`
from GitHub, and the root package still installs alone. Checked on the
PC, 2026-10-31, with a throwaway workspace: all three installs work and
`uv lock` locks both packages in one `uv.lock`. `curiousj-framekit`
holds Frame code only, by construction. Your `~/pkgbuilds` on the PC is
not a git repository (it holds one AUR checkout), so there is no
collection to move the PKGBUILDs to; option 4 fell away.

The steer behind this: `curiousj-framekit` should hold only code that
runs on the Frame, but a Python command for the PC side of Frame
scenarios would be useful, and the two PKGBUILDs are Frame related, the
first specifically for the Frame + Deskflow + Frametop + RDP-client
scenario. For the record, what a PC command would do and the options
that were weighed:

What it would do, from what the README and the PKGBUILD headers ask of
the PC today:

- build and install `krdpserver-embed-cursor`, and **rebuild it after
  a Plasma update**, since the package pins against krdp's version
  and blocks `pacman -Syu` until rebuilt;
- **switch** krdpserver between upstream and the embed-cursor build:
  the systemd drop-in's `ExecStart`, and `EmbedCursor=true` in
  `~/.config/krdpserverrc`;
- make sure krdpserver runs with `--plasma` (the drop-in for
  `app-org.kde.krdpserver.service`), and start, stop and show it;
- build `frame-control-bin` from the release `.deb`, and update it
  when a new release appears;
- possibly the Deskflow server side, and the PC half of "BSManager in
  a window" as a documented `sshtsf -w` or `waypipe ssh` one-liner,
  not code.

That is a coherent set, all Arch-PC specific, and all about keeping
two packages current and switching one of them. Options for where it
lives:

1. **`pc/` in this repo, PKGBUILDs and docs, no code.** What exists
   today, tidied. Enough until a command is wanted; `makepkg -si` in
   the directory is the install. The rebuild-after-Plasma-update and
   the switch stay as commands in the PKGBUILD header.
2. **A second package in this repo, as a uv workspace.** `pc/` gets its
   own `pyproject.toml` (`curiousj-framekit-pc`, command name to pick,
   `framepc` say), installed with `uv tool install ./pc` or from
   `git+…#subdirectory=pc`. Hatchling and uv both support this; the root
   `pyproject.toml` lists the workspace members. One repo, one history,
   the PKGBUILDs beside the code that builds and switches them, and
   `curiousj-framekit` stays Frame-only by construction, not by a
   runtime check. Cost: two packages' metadata and tests in one repo,
   and the install one-liner differs per machine.
3. **A separate repo** (`curiousj-framekit-pc`). The cleanest boundary
   and the simplest install story per machine; the cost is two repos to
   keep in step for one scenario (the krdp embed-cursor change spans the
   Frame flatpak and the PC package).
4. **PC commands inside `curiousj-framekit`, gated by where.py.**
   Rejected by your steer: `curiousj-framekit` holds Frame code only.
5. **PC commands in curiousj-tools.** It is already the PC-side
   cross-machine toolkit (`sshtsf -w`), but krdpserver and Frame
   Control are Frame-specific, not ssh/tmux tooling; a poor fit.

Option 2 was preferred over 3 because the one scenario that needs
both sides, the embedded cursor, is easier to change in one commit
when both sides are in one repo.

**Q10. `bsmanager`'s PC side.** Decided: only the Frame half stays,
as `bsmanager` itself, which needs a Wayland display and refuses
otherwise. The PC side becomes a documented
one-liner with `sshtsf -w` (curiousj-tools) or plain `waypipe ssh`.
curiousj-tools itself joins the catalog (Q15, `uv-tool`).

### Scope of the groups

**Q11. What else is coming for Beat Saber?** Decided: what exists,
`beat-saber-recent` with `--record` and `--install-hook`, and
`bsmanager`, with room to grow; a new tool gets a new `beat-saber-`
name or a flag on one of these, whichever reads better.

**Q12. Does everything get ported, including `pacman-home`?**
Decided: yes, `pacman-home` (460 lines: pacman under fakeroot,
`relocate`, `outdated`, the keyring) and `homeify` (200 lines of
PKGBUILD rewriting) included. They are ported last, since they work
and have the least duplication, but nothing ships as shell inside the
package; `pacman-home` keeps its name as an entry point.

### Migration

**Q13. Who else uses this?** Decided: assume other Frame owners, and
provide `cjf migrate`: it removes the old rc blocks and the
`~/.distroboxrc` block, replaces the autostart entry whose `Exec`
names the old checkout, rewrites the Beat Saber launch options, moves
`~/.local/state/steam-frame-utils` and the `pacman-home` configuration
under `~/.local/etc` where paths change, and backs up what it edits.
Kept for a few releases. The old GitHub name redirects on its own.

**Q14. Does the Python on the Frame have to be the system one?**
Decided: no. `requires-python >= 3.12` (the Frame's system Python),
and the package runs in whatever interpreter `uv tool` picks. Checked
on the Frame, 2026-10-31, uv 0.13.6:

- `uv tool install` has no `--system-site-packages` option; `uv venv`
  does, and a venv made that way from `/usr/bin/python3` imports `gi`,
  Gtk 4 and Adw. Editing the tool venv's `pyvenv.cfg` by hand would
  work until the next `uv tool install --force` or upgrade recreates
  it, so it is not a mechanism to build on.
- With mise on `PATH`, `uv tool` picks mise's Python (3.15.2 on the
  Frame today), not the system 3.12; curiousj-tools' venv runs on it.
  So the package should assume nothing about which interpreter it is
  in, and `gi` is never importable from inside it.

So the RDP server's GUI (`krdpd-gui` today) becomes a **standalone
script**, stdlib and `gi` only, shipped in the package's data and run
by `/usr/bin/python3`; it drives the server through `cjf rdp …`
subprocesses, as it already drives `krdpd` today, so it imports
nothing from the package. The `.desktop` entry's `Exec` names the
script's installed path, written when the KRdp catalog item is
installed. Rejected: `--with pygobject` from PyPI, which would build
against the host's girepository and duplicate a library the system
already has.

## 4. Accepted suggestions

All of these are decided (D19).

### UX

- **`cjf` bare opens the picker**; `cjf --help` lists groups with one
  line each; every operation is also a plain subcommand, so
  the picker is a convenience, never the only way. In the install
  picker each catalog item shows its installed state, as `ujust`
  shows a recipe's description.
- **`cjf status`**: the SteamOS, SteamVR and client versions, the
  kit's own version, the headset's battery and charging state, the
  cursor settings in effect, Tailscale's state, and whether the RDP
  server runs. **`cjf installed`**: every catalog item's state, as the
  install picker shows it. `status --all` is both (D23). Together they
  replace `setup.sh --check` and `frame-versions`.
- **The headset's battery** (D22) in `cjf vr` beside the controllers',
  and in `status`, from `/sys/class/power_supply/max1720x_bat_7-36`
  (capacity, status, voltage); the charger and USB-C source there say
  whether it is plugged in. No SteamVR needed, unlike the controllers'
  percentage.
- **`cjf after-update`**: the checklist that is scattered through
  the README today, run as one command after a SteamOS update: is the
  Tailscale unit still there, do the `~/.local` packages still resolve
  their libraries (`ldd … not found`), is the cursor file in place,
  does the Frametop launcher still point at the right release.
- **One "where am I" module**, used everywhere: Frame or PC; inside a
  container or not; which desktop (Game Mode, Desktop Mode, Frametop)
  from the runtime directory; whether a Wayland display is reachable.
  Every refusal is one sentence that names what was expected.
- **Uniform flags** from one shared click base (curiousj-tools'
  `cmdline.py` is the model): `-h`, `--yes`, `--dry-run`/`--check`,
  `-v`. Every change to a file is shown as a diff and asked about, and
  the file is backed up with a timestamp, as setup.sh does now; that
  norm is kept word for word.
- **Choices in a config file**,
  `~/.config/curiousj-framekit/config.toml` (software cursor on or off,
  cursor size, RDP port, default fonts, Flatpak scope), instead of
  marker lines inside `environment.d` files.
- **Shell completion** from click, part of what the rc init brings in.
- **Beat Saber launch hook**: the launch option stays
  `beat-saber-recent --record; %command%; beat-saber-recent --record`
  in form, with the command in `~/.local/bin` instead of the checkout.
  Checked on the Frame, 2026-10-31: the Steam client's `PATH` is
  `/usr/local/bin:/usr/bin` and a game's is the same plus
  `/usr/local/sbin`, so `--install-hook` keeps writing the absolute
  path, `~/.local/bin/beat-saber-recent`, and `migrate` rewrites the
  old checkout path to it.

### Organization

```
curiousj-framekit/
  README.md  LICENSE  pyproject.toml  uv.lock  install.sh
  src/curiousj_framekit/
    cli.py          root group, picker
    where.py        Frame/PC, container, desktop, display detection
    cmdline.py      shared click base, prompts, diffs, backups
    frame/          cursor.py  wifi.py  versions.py  controllers.py
                    vr.py  rdp.py (krdpd)  pkg.py (pacman-home,
                    makepkg-home, homeify)
    beatsaber/      recent.py, manager.py: the beat-saber-recent and
                    bsmanager entry points
    install/        catalog.toml, one module per kind (flatpak.py,
                    upstream.py, pacman_home.py, config.py,
                    service.py, script.py, …), status.py, init.py,
                    migrate.py
    shell/          init.sh (what the rc line sources), shims/podman
    data/           autostart .desktop, environment.d conf,
                    tailscaled.service, krdp-gui.py (stdlib + gi,
                    run by /usr/bin/python3; see Q14)
  pkgbuilds/        the Frame's PKGBUILDs (emacs, pacman) and homeify's
                    templates
  flatpak/krdp/     manifest, patches, and the CI workflow's inputs
  pc/               pkgbuilds/, README.md; later pyproject.toml and
                    src/curiousj_framekit_pc/ as a uv workspace member (Q9)
  docs/             the README split by topic; the memos stay
  tests/
```

- `setup/` and `apps/install.py` from revision 1 collapse into
  `install/` with the catalog, per D1.
- The README shrinks to: what this is, the install one-liner, the
  command map, the catalog as a table, and links. Each topic section
  becomes a `docs/` page.
- The header comment of each script becomes the module docstring,
  which is the `--help` text, as in curiousj-tools; one source for
  both.
- `notes/` (untracked: AA calibration data and fit) goes to
  `docs/notes/` under git; it is referenced by `vr-controllers`'
  comments.

### Norms

- Python 3.12 or later (the Frame's), click, hatchling, `src/` layout,
  pytest, installed with `uv tool install --editable` on the Frame and
  from git elsewhere, exactly as curiousj-tools.
- Shell exists in four places only: `install.sh` (bootstrap),
  `shell/init.sh` (what the rc line sources), `shell/shims/` (programs
  that must carry another program's name and start fast, today only
  `podman`), and PKGBUILDs.
- Python outside the package's venv exists in one place: the RDP GUI
  script in `data/`, run by the system interpreter for PyGObject, which
  imports nothing from the package (Q14).
- Tests for the pure logic (parsers, the kcminputrc edit, the rc-file
  edit, the catalog, the PKGBUILD rewrite, the AA voltage estimate),
  with the Frame-only parts behind small interfaces that tests fake.
  The fake-HOME trick used for setup.sh carries over.
- Conventional commits and 72-column prose, as now; a `TRUST.md` kept
  in step with the catalog.
- The krdp release tags (`krdp-<ver>-<n>`) and the workflow's
  `--repo` reference move with the rename; the Flatpak app id
  `io.github.curiousjtuber.Krdp` does not need to change.

## Revision history

- **Rev 11, 2026-11-01.** Stages 1 to 6 of `steps.md` are done
  and on `dev`; stage 7, the rename, is left to you. Three deviations
  taken while implementing, each recorded in the steps: the KRdp
  manifest lives in the package's data rather than `flatpak/krdp/`;
  the ports do not read other processes' environments to find a nested
  desktop's session bus (a size change from SSH is saved, not applied);
  the completion scripts are files of their own, one per shell.
- **Rev 10, 2026-10-31.** From the second scenario review: `status`
  and `installed` (D23), `after-update`'s state file (D24).
- **Rev 9, 2026-10-31.** From the scenario review: the base grows to
  mise, uv and fzf, and `install.sh` asks once and runs `cjf init`
  (D9, Q5); dependencies between items and from commands to items are
  declared and named (D21, Q19); the headset's battery from the kernel
  (D22). The `mise` kind replaces the mise item in Q15.
- **Rev 8, 2026-10-31.** Section 0 points at `steps.md`, the
  staged implementation plan.
- **Rev 7, 2026-10-31.** The name becomes `curiousj-framekit`, with
  `cjf` as the short command; Q1 records why (personal contents, the
  PyPI collision, bare "frame" naming the device) and how the GitHub
  rename is done. D5, D6, the goals and every path and example follow.
- **Rev 6, 2026-10-31.** Q9 decided: `pc/` with PKGBUILDs and docs now,
  a `curiousj-framekit-pc` uv workspace member later, after checking the
  workspace installs work. D20 added; no question remains open.
- **Rev 5, 2026-10-31.** Q14 decided after checks on the Frame: the
  RDP GUI becomes a standalone stdlib-plus-`gi` script run by the
  system Python. Measured shell start-up costs added to Q5's note, and
  Steam's `PATH` to the launch-hook note. D18, the layout and the
  norms follow.
- **Rev 4, 2026-10-31.** Q17 decided: no umbrella Beat Saber command;
  `beat-saber-recent` and `bsmanager` keep their names. D6, D7, D15,
  Q2, Q3, Q10, Q11, the launch-hook note and the layout follow.
- **Rev 3, 2026-10-31.** Answers to Q1 to Q16 folded in as D4 to D19;
  section 0 now lists decisions and what is open. Distrobox stays as
  an optional app (goal 3 and the "what is wrong" paragraph rewritten,
  Q18 added for what of it stays). Q2 gained a separate Beat Saber
  command and Q17 for its name. Q6 gained the configurable Flatpak
  scope. Q9 narrowed with a fuller list of what a PC command would do
  and five options for where it lives. Q12 now ports `pacman-home` and
  `homeify` too. curiousj-tools added to the catalog (`uv-tool` kind).
  Q5 gained the note on sourcing a static init file because rc files
  are shared with the boxes. Section 4 renamed to accepted suggestions.
- **Rev 2, 2026-10-31.** Feedback on setup and installs folded in:
  the three tiers dissolved into base and catalog (D1), the four
  groups demoted to a first cut (D2), the Flatpak scripts to go (D3).
  Q5 and Q6 rewritten, Q15 and Q16 added, the install layout and the
  "what is wrong" section updated.
- **Rev 1, 2026-10-31.** First draft from the notes below.

## Appendix: the original notes

```
issues
- too generic repo name
- gatherings of different things unorganized
  - installs
  - bins
  - rc files
  - pc and frame parts
- duplicated shell script code fragments

wants to dos
- rename the repo
- python project
  - python bins instead of shell scripts
  - umbrella python commands
    - for all general frame operations
    - for specific apps (beat saber)
    - for setup and installs (not firmly decided yet)
    - sub commands or interactive tui (similar to bazzite ujust)
- get rid of distrobox dependency
- no ssh from pc to frame codes
  - distinguish commands for pc and frame
    - cachyos (or arch): install through pkgbuilds
    - other: assume on
- simplify apps and other install-*
  - group: flatpak from flathub
  - group: flatpak app own repo
  - group: follow app page instructions
  - group: pacman-home
```
