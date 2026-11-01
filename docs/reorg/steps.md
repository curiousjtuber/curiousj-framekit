# From steam-frame-utils to curiousj-framekit: the steps

> **Closed 2026-11-01.** All seven stages are done. Kept as the record
> of how the move was staged and what deviated along the way,
> not updated after this date. What the kit does today is in the
> [README](../../README.md) and [docs/](../).

Implementation plan of 2026-10-31 for the decisions in
[plan.md](plan.md). Seven stages, each leaving the Frame
working and each ending with a check on the Frame itself. Old scripts
are deleted only after what replaces them has been run there, so at no
point is the checkout half-migrated in a way the Frame notices.

## Rules for the whole run

- **Work on `dev`, in small conventional commits**, as now: pushed to
  `dev`, pulled on the Frame, tested there, merged to `main` by you.
  Every commit keeps the old scripts working until the stage that
  deletes them; the package and the scripts share the checkout in the
  meantime.
- **The Frame's checkout stays at `~/steam-frame-utils`** until stage
  7, since the rc blocks, the autostart entry and the launch options
  name that path.
- **The package is installed on the Frame as an editable tool from
  that checkout** (`uv tool install --editable ~/steam-frame-utils`,
  uv from mise's shims), so a `git pull` is live, as curiousj-tools
  is. After the directory move in stage 7 it is reinstalled from the
  new path.
- **Port, don't rewrite.** Each tool's behaviour, flags and messages
  carry over as they are; the header comment becomes the module
  docstring and the `--help`. Improvements wait for after the port,
  except where the plan decided one (uniform flags, the config file).
- **A ported tool is verified on the Frame before its script goes**:
  the same invocations as the README documents, from a Desktop Mode
  terminal and over SSH, since the two environments differ. Report
  what was run; a green test suite is not a green tool.
- **Tests go in with each port**, for the pure logic only: parsers of
  command output and files, the rc-file and `kcminputrc` edits, the
  catalog, the PKGBUILD rewrite, the AA voltage estimate. Frame-only
  calls sit behind small functions that tests replace. The fake-`HOME`
  trick used for `setup.sh` carries over for anything that writes
  under the home directory, never with distrobox-host-exec paths.
- **Delete, don't deprecate.** When a script's replacement is verified,
  the script is removed in the same commit and the README entry with
  it. `migrate` (stage 3) is the compatibility layer, not leftover
  scripts.

## Stage 1: the skeleton

**Done 2026-10-31** (`7fb282a`, `2b1f375` and the refusal fix after
them). Verified on the Frame over SSH: `cjf status` prints what
`frame-versions` printed, line for line; the picker draws and quits;
the suite passes under both the system Python 3.12 and mise's 3.15,
which is what the tool venv runs on; inside the `dev` distrobox the
command runs and refuses, naming `distrobox-host-exec`. Not run from a
Desktop Mode terminal, since that needs the headset on: `cjf status`
there is the one check left to you.

Goal: `cjf --help` and `cjf status` run on the Frame from an editable
install, and the shared plumbing every later port uses is in place.

- `pyproject.toml` (hatchling, `src/curiousj_framekit`, `requires-python
  >= 3.12`, click), `uv.lock`, `tests/` with pytest, `.gitignore`
  additions. Entry points `curiousj-framekit` and `cjf`; the others
  come with their stages.
- `cmdline.py`: the click base from curiousj-tools (hand-laid help from
  the docstring, `-h`, exit statuses), plus what the Frame tools share
  and the shell scripts duplicate: `die`, a `--yes`/`--check` pair,
  "ask before changing", a diff-and-backup file writer
  (`<file>.bak-<timestamp>`), and a `run()` wrapper that logs commands
  under `-v`.
- `where.py`: Frame or PC from `/etc/os-release`; inside a container
  (`CONTAINER_ID`, `/run/.containerenv`); which desktop from
  `XDG_RUNTIME_DIR` (`nested_plasma`, `frametop`, neither); whether a
  Wayland display is reachable. One refusal message per condition.
  Also an override for CI (see stage 4, KRdp), so a build can run on a
  non-Frame runner.
- `cli.py`: the root group, and the bare-invocation picker (fzf when
  present, else a numbered menu; copy `pick-lines`' logic rather than
  depend on curiousj-tools).
- `install.sh`: curiousj-tools' script with the names changed. Not
  used on the Frame yet; it is what a fresh Frame will run in stage 7.
- First port, as the proof: `frame-versions` becomes the top of `cjf
  status`. It is 73 lines, reads files and one `pacman -Q`, and has
  nothing to break.

Done when: `uv tool install --editable ~/steam-frame-utils` on the
Frame puts `cjf` in `~/.local/bin`, `cjf` bare shows the picker with
`status` in it, `cjf status` prints what `frame-versions` prints, and
`pytest` passes on the PC. `bin/frame-versions` is deleted.

Watch: which Python uv picks on the Frame (mise's 3.15 today); the
package must run on both it and 3.12, so CI tests both.

## Stage 2: the tools

**Done 2026-11-01** (`2c7d212` the ports, `afffdbb` the deletions).
Verified on the Frame over SSH, each port beside its script: `wifi`,
`wifi --all`, `cursor size`, `controllers`, `rdp status`, `rdp status
--keys`, `beat-saber-recent` and `--all` gave identical output; `vr`
the same rows plus the headset's; `cursor software` the same state in
the new words. `beat-saber-recent --install-hook` recognized the hook
through the debug port, and the launch options, the two autostart
entries and the KRdp menu entry were switched to the new commands
before the scripts went. Not verified, since no desktop was running
and no controller was on: `vr off`, `controllers off`, `rdp start` and
`stop`, `cursor apply` from inside a desktop, `rdp gui`, and `bsmanager`
in a waypipe session. Those are the first things to try when you next
have the headset on.

One deliberate omission from the port: the scripts found a running
desktop's session bus by reading its plasmashell's environment, which
let `cursor-size` apply a change from SSH and `sw-cursor` report what
the running desktop was given. The ports do not read other processes'
environments. A running desktop is known by its Wayland socket; from
SSH a size change is saved and applies at the desktop's next start, or
at once from a terminal inside it, which is where the autostart entry
runs. If applying from SSH turns out to matter, it is a small addition
to `desktops.py`, and your call.

Goal: every `bin/` tool but the package managers is a `cjf` subcommand
or its own entry point, and `bin/` is empty of them.

In order of risk, lowest first, one commit each:

1. `wifi-known` → `cjf wifi` (parses `nmcli`; 62 lines).
2. `cursor-size` and `sw-cursor` → `cjf cursor size|theme|apply` and
   `cjf cursor software on|off|default`. The first write to
   `~/.config/curiousj-framekit/config.toml` (the software-cursor
   choice replaces the marker line in the `environment.d` file; the
   file itself stays what KWin reads). The autostart entry's `Exec`
   becomes `cjf cursor apply`, written by `software on` as today.
3. `steam-controller` → `cjf controllers` (already Python; moves in).
4. `vr-controllers` → `cjf vr` (already Python; moves in, with
   `notes/aa-voltage*` tracked under `docs/notes/` and the fit's test).
   Gains a headset row with the battery from
   `/sys/class/power_supply/max1720x_bat_7-36` and whether it is
   plugged in (D22), which also feeds `status`; the controllers' rows
   still need SteamVR, and `vr` says so when it isn't running.
5. `krdpd` → `cjf rdp start|stop|status|log|password` (208 lines of
   bash around flatpak run and a password file; the port that most
   wants the `run()` wrapper). `krdpd-gui` becomes
   `data/krdp-gui.py`, run by `/usr/bin/python3`, calling `cjf rdp`
   instead of `krdpd`; its `.desktop` entry is rewritten by
   `install-krdp.sh` for now and by the catalog item in stage 4.
6. `beat-saber-recent` and `bsmanager` → entry points of the same
   names from `curiousj_framekit.beatsaber`. `--install-hook` writes
   `~/.local/bin/beat-saber-recent --record`, the absolute path, since
   Steam's `PATH` has no `~/.local/bin`. `bsmanager` keeps only the
   Frame half: it refuses without `WAYLAND_DISPLAY`, and its header
   documents the PC one-liner with `sshtsf -w` or `waypipe ssh`.

`bin/podman` stays for stage 3. `pacman-home`, `makepkg-home` and
`homeify` stay for stage 5.

Done when: each tool has been run on the Frame as its README section
describes, from Desktop Mode and over SSH, and its script is gone.
For `cjf rdp`, a KRDC session from the PC to Frametop's desktop. For
Beat Saber, one launch of the game with the rewritten launch options
and a `beat-saber-recent` that lists it.

## Stage 3: the base, the shell side, and `migrate`

**Done 2026-11-01** (`c9f45b5`, `b48e26a`, `29010d7`). `cjf migrate`
ran on the Frame with `--yes` after a `--check` review: the old blocks
went from `~/.bashrc`, `~/.zshrc` and `~/.distroboxrc` (backed up), the
init block and `init.sh` came in, the song history moved. A login bash
afterwards starts clean, has `cjf`'s completion registered, the podman
shim first on `PATH`, the `waypipe` function and the `tailscale` alias;
`distrobox enter dev` sees the shims first. A second `migrate` finds
nothing to do. `install.sh` was run in a fake home on the PC with a
bare `PATH`: it listed mise, uv and the kit, installed all three, and
stopped before `cjf init` as told. Not verified: zsh on the Frame (its
host has no zsh), and the mise-first installer against a Frame with
nothing on it. Settled on the way: the rc line sources a static file,
as Q5 leaned; the completion scripts live in files of their own, one
per shell, since bash parses a whole `if` block before running it and
zsh's script is not bash. One bug found by the Frame, not the tests,
and now covered by them: the shell files are run through `bash -n` and
`zsh -n`.

Goal: the rc files, `~/.distroboxrc` and the autostart entry no longer
name the checkout; `setup.sh`'s always-on part is `cjf init`; a Frame
set up by the old `setup.sh` is moved over by `cjf migrate`.

- `shell/init.sh`: the six `shell-init/` files folded into one, each
  part guarding itself at source time as now (brew's shellenv if the
  binary exists, mise if installed and not active, the waypipe
  function, the tailscale alias with its host-exec branch, the
  Frametop XDG fix), plus click's completion for `cjf`, plus the shims
  directory first on `PATH`. Written by the base install to
  `~/.local/share/curiousj-framekit/init.sh`; the rc line is `source`
  of that file, guarded by `-r`. `cjf init bash|zsh` prints it, `cjf
  init --path` names it. Settle here, with the measured numbers in
  the plan's Q5, whether the rc line evals or sources; the plan leans
  to sourcing.
- `shell/shims/podman`: `bin/podman` moved, installed to the shims
  directory by the distrobox catalog item (stage 4); until then, by
  `cjf init`.
- `cjf init` (the command): `~/.local/bin` on `PATH` in `~/.bashrc`
  and `~/.profile` if missing; the rc line in `~/.bashrc` and
  `~/.zshrc`; the `~/.distroboxrc` block pointing at the shims
  directory; the autostart entry if the software cursor is on. Each
  change shown as a diff and asked about, backed up first, as
  `setup.sh` does. `--check` reports.
- `install.sh` reworked for the base as D9 now has it: find or install
  mise (mise.run), `mise use -g uv fzf` for what is missing, list what
  it is about to install and ask once on the tty, `uv tool install`,
  then run `cjf init`. The stage 1 version only installs the package.
  Tested with a fake `HOME` on the PC, where mise, uv and fzf are all
  absent from that home, and on the Frame, where all three are present
  and the list should be empty but the package.
- `cjf migrate`: finds and removes the `# >>> steam-frame-utils: …`
  blocks in `~/.bashrc`, `~/.zshrc`, `~/.profile` and `~/.distroboxrc`
  (both the two-block form and the older one-per-file form `setup.sh`
  already recognizes), replaces
  `~/.config/autostart/steam-frame-utils-cursor.desktop` and its
  Frametop twin with the new entry, rewrites Beat Saber's launch
  options through the Steam debug port where they name the old
  checkout, moves `~/.local/state/steam-frame-utils/` to
  `~/.local/state/curiousj-framekit/`, carries the software-cursor
  choice from the `environment.d` marker line into the config file,
  and then runs `cjf init`. Idempotent: a second run finds nothing.
  `pacman-home`'s files under `~/.local/etc` and `~/.local/var` are
  pacman's layout and don't move.

Done when: on the Frame, `cjf migrate` followed by a new login shell
in Desktop Mode, over SSH and in a distrobox gives the same `PATH`,
aliases and functions as before (diff `env` and `alias` output against
a capture taken first); the cursor size survives a desktop restart;
`distrobox enter` works from Desktop Mode. On the PC, the fake-`HOME`
run of `migrate` against rc files copied from the Frame. Then
`shell-init/`, `distrobox/`, `autostart/`, `environment.d/` and
`bin/podman` are deleted, and `setup.sh` loses its always-on part (its
options stay until stage 4).

Watch: `setup.sh`'s refusal of checkout paths with shell
metacharacters becomes moot once nothing names the checkout; and the
`-r` guard means a shell never fails on a missing init file, so a
broken `migrate` degrades rather than locks you out. Still, keep an
SSH session open across the first run.

## Stage 4: the catalog

**Done 2026-11-01** (`b6cc09c`, `82f2e72`, `4344ee5`, `fb9d124`). The
KRdp workflow run for `82f2e72` succeeded: the runner installed the kit
and `cjf install krdp --bundle` built the bundle from the manifest in
the package's data, with `CJF_ASSUME_FRAME=1`. Verified on the Frame
over SSH:
`cjf installed` reports all nineteen items with the versions the
scripts knew (Tailscale running on the tailnet, Homebrew 7.0.11, rust
1.99.1, Nerd Fonts v3.5.1, waypipe 0.11.2-1, emacs 31.1-1, pacman
7.1.0-1, distrobox 1.8.2.5, curiousj-tools, Frametop 0.2.2, the four
Flatpaks, KRdp's build, BSManager, Full Keyboard 0.12.0); `--check
install` of every item shows the step its script took and nothing else;
`cjf install nerd-fonts` against fonts at the latest release finds
nothing to do; `--check install --all` lists only what updates by
installing again, and found Full Keyboard 0.12.1 waiting. Not run on
the Frame, since each needs your password or a long download: a
Tailscale reinstall, a Homebrew install, a Frametop reinstall, a KRdp
build, and any actual Flatpak update. The KRdp workflow started on the
push that moved the manifest; its result decides whether the stage is
closed.

Two deviations from the plan, both deliberate. The KRdp manifest and
patches live in the package's data, `src/curiousj_framekit/data/krdp/`,
not in a `flatpak/krdp/` directory at the repo root, so that a kit
installed from git can build it; the workflow triggers on that path.
And the stamp that says whether the build matches the manifest now
ignores comment and blank lines, so a note added to the manifest does
not force a half-hour rebuild; the Frame's recorded stamp was refreshed
once by hand for the comment edit that moved the file. One fix the
Frame found: an error in one item (Full Keyboard was running) stopped
`install --all`; now it is reported and the run goes on, ending with 1.
And one lesson recorded: a `pytest | tail` chain committed on a red
suite once (`82f2e72`), since the pipeline's status was tail's; chains
run with `pipefail` since.

Goal: every optional install is a catalog entry, `cjf install` and
`cjf status` read the catalog, and `setup.sh`, the three top-level
`install-*.sh` and the eight `apps/*.sh` are gone.

- `install/catalog.toml`: one `[item.NAME]` per entry with `kind`,
  `description`, the kind's fields (flatpak id and remote; release
  repo, asset pattern and sums source; PKGBUILD directory; and so
  on), `needs_root`, and the checks that `TRUST.md` records today.
- One module per kind, in this order, each replacing scripts as it
  lands:
  1. `config`: the software cursor and cursor size as entries, so the
     catalog has an item before any download code exists.
  2. `flatpak`: Moonlight, KRDC, Deskflow, Stream Frame. The
     configurable scope (`user` default, `system` with sudo). Deletes
     four `apps/install-*.sh`.
  3. `upstream-installer`: BSManager, Full Keyboard, Frametop; fetch,
     check against the recorded or published sum, run the upstream
     installer with the entry's flags, `--uninstall`, `--version`.
     Frametop's entry carries the recorded sha256 and the `--yes`,
     `--no-eye-tracker`, `--bluetooth`, `--any-steamos`,
     `--unpack-only` pass-throughs. Deletes three scripts.
  4. `flatpak-build`: KRdp's server. `apps/krdp/` moves to
     `flatpak/krdp/`; the manifest and patches are unchanged. The
     workflow's `paths` and its build step change to install the
     package on the runner (`uv tool install .`) and run `cjf install
     krdp --bundle FILE`; `where.py` needs the CI override here, since
     the runner is not a Frame. The item also writes the GUI's
     `.desktop` entry. Deletes `apps/install-krdp.sh`.
  5. `system-service`: Tailscale, from `install-tailscale.sh`'s logic
     with its keep-list and firewalld handling; `--trust-tailnet` as
     an entry option. Deletes that script.
  6. `installer-script`: distrobox (then the shims entry and the
     `~/.distroboxrc` block); and the `mise` kind for `rust`. Deletes
     `setup.sh`'s `--mise` and distrobox parts.
  7. `brew`: Homebrew itself, zsh, wl-clipboard. Deletes `--brew` and
     `--zsh`.
  8. `fonts`: Nerd Fonts, from `install-nerd-fonts.sh`. Deletes it.
  9. `uv-tool`: curiousj-tools.
  10. `pacman-home` kind: entries for waypipe (relocate), emacs and
      pacman 7; the kind calls the still-shell `pacman-home` and
      `makepkg-home` until stage 5 ports them. Deletes
      `install-waypipe.sh` and `setup.sh`'s `--packages`, `--emacs`
      and `--waypipe`; with that, `setup.sh` is empty and goes.
- `cjf install [NAME…] | --check`, `cjf install` bare (the picker over
  the catalog, each item with its state), and `cjf installed`, the
  same list as a command; `cjf status --all` appends it (D23).
- Dependencies (D21): `needs = […]` in catalog entries, resolved into
  one up-front question and dependency order by `install`; and a
  `needs(item)` helper that commands call at their start (`rdp` →
  `krdp`, `bsmanager` → `bsmanager` and `waypipe`, `pkg build` of a
  Rust PKGBUILD → `rust`), refusing in one line with the `cjf install`
  to run. The stage 2 ports of `rdp` and `bsmanager` check for the
  flatpak and the AppImage directly until this lands, then switch to
  the helper.
- `TRUST.md` regenerated from the catalog, or a test that fails when
  the two disagree; `docs/TRUST.md` and `apps/TRUST.md` merge into it.

Done when: on the Frame, `cjf status` agrees with what is installed;
one item of each kind has been installed or updated through `cjf
install` (Flatpak: update one of the four; upstream: Full Keyboard,
which refuses an installed version harmlessly; system-service: a
Tailscale re-run that finds nothing to do; config: cursor); the krdp
workflow has produced a bundle from the moved manifest on a `dev`
push; and `setup.sh`, `install-*.sh` and `apps/` are gone.

Watch: `install-tailscale.sh` is also documented as runnable by hand
with `sudo bash` on a Frame without the checkout; the catalog item
replaces that with "install the package, then `cjf install
tailscale`", which the Tailscale section of the docs says.

## Stage 5: the package managers

**Done 2026-11-01** (`0b50086` and the deletion commit). Verified on
the Frame beside the old script: `pacman-home -Q`, `-Qo` and `check`
gave identical output; `keyring --check` found the keys; `-U` of the
cached waypipe package reinstalled it through fakeroot; `outdated`
synced Arch Linux ARM's databases and reported waypipe 0.11.3 newer
than the 0.11.2 installed; `cjf pkg homeify jq` fetched Arch's PKGBUILD
and produced the rewrite `docs/home-packages.md` describes for jq
(prefix, aarch64, `python` unlisted as mise's), parsing cleanly. Not
run: `cjf pkg build` (a real build; its code path is the kind's), and
`relocate` of a new package (a download; `fetch` and `relocate_pkg` are
the script's steps and `-U` of their result is what was run).

Goal: `pacman-home`, `makepkg-home` and `homeify` are Python, with
`pacman-home` keeping its name.

- `frame/pkg.py`: `pacman-home` (entry point of that name, pacman's
  flags passed through, `check`, `outdated`, `relocate`, `keyring`),
  `cjf pkg build NAME` (`makepkg-home`) and `cjf pkg homeify NAME`.
  The fakeroot arrangement, the two `pacman.conf` files under
  `~/.local/etc`, the pinned ALARM key fingerprint and the library
  check through `ldd` carry over as they are; the `relocate` tree
  rewrite and `homeify`'s PKGBUILD rewrite are the two pieces of
  logic that get real tests, against fixture PKGBUILDs (emacs, pacman,
  and the paru one from `docs/paru.md`).
- The `pacman-home` catalog kind (stage 4) switches from calling the
  scripts to calling these.

Done when: on the Frame, `pacman-home -Q` lists what it listed before;
`pacman-home outdated` runs; `cjf pkg build pacman` repackages
(`makepkg -R`, seconds) and installs; `homeify jq` gives the diff
`docs/home-packages.md` describes. Then the three scripts go and
`bin/` is deleted.

## Stage 6: documentation, the PC side, and the extras

**Done 2026-11-01** (`a95fafc`). `cjf after-update` ran on the Frame
twice: the first run recorded SteamOS 0.5.6 and found the Tailscale
unit in place, every pacman-home package's binaries resolving, the
cursor file matching the config, KRdp's build matching the manifest,
and noted that the Desktop launcher starts the `~/frametop` checkout
rather than the 0.2.2 release; the second compared against the record.
`pc/` holds the two PKGBUILDs and a README of the PC side. The README
is a map; the old sections are `docs/install.md`, `apps.md`,
`tailscale.md`, `shell-init.md`, `cursor.md` and `packages.md`, moved
with their links adjusted and a lead paragraph each saying the text is
the scripts' and the reasons hold. Every relative link in the docs
resolves (checked by a script, not by eye). What was not done: a real
rewrite of those pages in the kit's words; they read as history with
corrections, which stage 7's release can follow.

Goal: the README is a map again, the PC side has its directory, and
the two commands the plan added exist.

- `pc/pkgbuilds/krdpserver-embed-cursor/` and
  `pc/pkgbuilds/frame-control-bin/` (from `pkgbuilds/pc/`), with
  `pc/README.md` holding the PC-side instructions now in the README's
  Apps section (krdpserver with `--plasma`, the embed-cursor switch
  and the rebuild after a Plasma update, Frame Control). `pkgbuilds/`
  keeps the Frame's. `.gitignore` paths follow.
- `cjf after-update`: the checklist from the README run as checks:
  Tailscale unit present and enabled; every `pacman-home` package's
  binaries resolve (`ldd … not found`); the `environment.d` file and
  autostart entry match the config; the Frametop launcher's `Exec`
  points at the release the catalog knows; SteamOS version against the
  one recorded at the last run in
  `~/.local/state/curiousj-framekit/after-update.toml`, which each run
  rewrites (D24).
- `README.md` rewritten: what this is and whose, "formerly
  steam-frame-utils", the install one-liner, the command map, the
  catalog as a table, links. Each present section becomes a `docs/`
  page, trimmed where it described scripts that no longer exist; the
  memos stay as they are. The script-header URLs become docs links.
- `notes/` already moved in stage 2.

Done when: the README fits on a screen or two, every `docs/` link
resolves, and `cjf after-update` has been run on the Frame once.

## Stage 7: the rename

**Left to you, 2026-11-01.** Everything before it is on `dev`, pulled
and installed on the Frame. The rename is outward-facing (the GitHub
repository's name) and the merge to `main` is yours by the workflow, so
neither was done unasked. The steps below are exact; `cjf migrate` has
already run on the Frame, so step 3 is only the directory move and the
reinstall. After step 1, `install.sh`'s default source and the README's
install line still say `steam-frame-utils` and are covered by GitHub's
redirect; change them to the new name in the same commit as step 4.

Goal: the repo, the checkouts and the Frame carry the new name.

1. GitHub: Settings → rename to `curiousj-framekit`; never create a
   repo of the old name. Check that the krdp release assets and the
   workflow still run (one `workflow_dispatch`).
2. `git remote set-url origin
   git@github.com:curiousjtuber/curiousj-framekit.git` on the PC and
   the Frame.
3. On the Frame: `cjf migrate` has run in stage 3; now move the
   checkout, `mv ~/steam-frame-utils ~/curiousj-framekit`, and
   reinstall the tool from the new path, `uv tool install --force
   --editable ~/curiousj-framekit`. Nothing else names the directory
   by then; `cjf status` and a new shell confirm it.
4. The workflow's header comment and `gh attestation verify --repo`
   example, the README's "formerly" line, and the `.github` badges if
   any.
5. The install story for a fresh Frame, once, end to end: a fake-`HOME`
   on the PC for `install.sh` (it needs only uv and git), then on the
   Frame `cjf init` and `cjf install` from the picker for one item.
6. Merge `dev` to `main`; tag `v0.1.0`.

**Done 2026-11-01** (`9a1fdf3`, `c45f077`, `42712bc`). The GitHub
repository was renamed in place with `gh repo rename`; the old URLs
answer 301 to the new ones, the krdp release and the workflow came
along. Both remotes were set by hand (`gh` did not touch the ssh form).
On the Frame the checkout moved to `~/curiousj-framekit` and the tool
was reinstalled from it (`uv` is a mise shim there, so plain ssh needs
`~/.local/share/mise/shims` on PATH first); `cjf status` reports
`kit 0.1.0 curiousj-framekit, editable from ~/curiousj-framekit`, and
a login shell finds `cjf` in `~/.local/bin`. Two files under the home
still named the old directory: the software-cursor environment.d file
carried the old marker line, dropped by `cjf cursor software on` now
that the choice is in the config, and the emacs binary embeds its
configure-time lisp path as a fallback, which is harmless (its runpath
is `~/.local/lib`, `ldd` resolves everything). Step 5 was run from the
raw URL on `main` into a fake `HOME` on the PC: mise, uv through it,
the kit at `9a1fdf3`, with `CURIOUSJ_FRAMEKIT_NO_INIT` since `cjf
init` is the Frame's; the Frame's own init and picker were not run
again, it was set up in stage 3. The two workflow runs the rename
triggered failed in forty seconds: `cjf install` now takes every
item's status first, and the pacman-home kind ran `/usr/bin/pacman`,
which the runner lacks; `c45f077` guards that in `pkg.pacman`, and the
dispatched run after it built the bundle in eight minutes. The version
became 0.1.0 for the tag. Kept on purpose: the old name inside
`docs/install.md` and `docs/shell-init.md`, which quote the old scheme,
and the PC's checkout directory, still `~/steam-frame-utils` (this
session's working directory; renaming it is yours).

## Points to settle while implementing

Named in the plan, left to the stage that meets them:

- Stage 1: whether to pin the tool's Python (`uv tool install
  --python 3.12`) or support both 3.12 and 3.15; the plan supports
  both.
- Stage 3: `eval` versus `source` for the rc line (Q5's numbers).
- Stage 4: the CI override in `where.py`, and what the Tailscale docs
  say to a Frame without the package.
- Stage 5: whether `pacman-home`'s pacman pass-through stays `exec` of
  the real pacman with the config, or wraps every subcommand.

## Size, for pacing

What goes: about 4,900 lines of shell and 830 of Python across 30
files. What comes: one package whose modules each map to one of them,
smaller for the shared plumbing and the four-into-one installers.
Stages 1 to 3 are the risky ones, since they touch what every shell on
the Frame runs; 4 is the largest; 5 is the most intricate; 6 and 7
are housekeeping. Each stage is a few sessions, with the Frame check
at the end of each as the gate to the next.
