# curiousj-framekit: how it is used

> **Closed 2026-11-01.** Written before the implementation, to check
> the design against real days with the Frame. The scenarios were not
> re-verified against what shipped and are
> not updated after this date. What the kit does today is in the
> [README](../../README.md) and [docs/](../).

Usage scenarios of 2026-10-31, revision 3, for the design in
[plan.md](plan.md), written before stage 2 so that the
shape can be checked against real days with the Frame. Each is a
terminal session as it should look when all seven stages are done;
`$` is the prompt, the rest is what the kit prints. Output formats are
the ones the scripts have today unless the plan changed them. Where a
scenario shows a choice the plan did not settle, it says so.

## 1. A fresh Frame

Nothing on the Frame yet but SSH. From the PC, or a Konsole in Desktop
Mode. The installer says what it will put where and asks once; mise is
the first thing in, and uv and fzf come through it (plan D9):

```
$ curl -LsSf https://raw.githubusercontent.com/curiousjtuber/curiousj-framekit/main/install.sh | sh
curiousj-framekit will install, for steamos, with no root:
  mise                 ~/.local/bin/mise, from mise.run
  uv, fzf              through mise (mise use -g uv fzf)
  curiousj-framekit    as a uv tool: cjf and curiousj-framekit in ~/.local/bin
and then run `cjf init`, which asks before each change it makes.
continue? [Y/n]
install        mise 2026.10.3
install        uv 0.13.6, fzf 0.74.5
install        curiousj-framekit from git+https://github.com/curiousjtuber/curiousj-framekit
```

On a Frame that has some of these already (this one has mise with uv
and fzf), the list shows only what is missing. The installer then runs
`cjf init`, the base: `~/.local/bin` on `PATH`, the one rc line, mise's
activation inside it, the shims directory. It asks before each change
and shows the diff:

```
change         ~/.bashrc
--- ~/.bashrc
+++ ~/.bashrc
@@ -1,3 +1,5 @@
+export PATH=~/.local/bin:$PATH
+[[ -r ~/.local/share/curiousj-framekit/init.sh ]] && source ~/.local/share/curiousj-framekit/init.sh
 #
 # ~/.bashrc
 #
write ~/.bashrc? [Y/n]
backup         ~/.bashrc.bak-20261101-091500
change         ~/.profile
...
write ~/.profile? [Y/n]
create         ~/.distroboxrc
write ~/.distroboxrc? [Y/n]
create         ~/.local/share/curiousj-framekit/init.sh
create         ~/.local/share/curiousj-framekit/shims/podman
done: open a new shell, then run cjf
```

`cjf init` can be run again at any time; it finds nothing to do. A new
shell has `cjf`, mise's tools and the completion. From here on
everything is `cjf`, and `cjf` alone is the menu, in fzf:

```
$ cjf
cjf> _
  ENTER runs the command
  status        the versions of SteamOS, SteamVR and the Steam client, and what is installed
  install       install or update an optional item: apps, packages, services, fonts
  cursor        the mouse cursor in Desktop Mode and Frametop's desktop
  wifi          the saved Wi-Fi networks in range
  vr            the headset and VR controllers: battery, or turn controllers off
  controllers   the Steam Controllers paired over Bluetooth
  rdp           serve a Plasma desktop on the Frame over RDP
  pkg           build or relocate a package under ~/.local
  after-update  what to re-check after a SteamOS update
  migrate       move a Frame set up by steam-frame-utils to this kit
```

(The numbered menu stays as the fallback for a shell where fzf is
missing, as stage 1 showed it.) Picking `install` with no item opens
the catalog, every item with its state:

```
install> _
  TAB marks items, ENTER confirms
  ok        cursor         the software mouse cursor in Desktop Mode, and the cursor size
  missing   tailscale      Tailscale as a system service that survives updates (sudo)
  missing   homebrew       Homebrew in /home/linuxbrew, for zsh and wl-clipboard (sudo once)
  missing   zsh            zsh from Homebrew (needs homebrew)
  missing   rust           rust through mise, for a Rust package in pkgbuilds/
  missing   nerd-fonts     JetBrainsMono and NerdFontsSymbolsOnly in ~/.local/share/fonts
  missing   waypipe        waypipe for the host, Arch Linux ARM's package relocated under ~/.local
  missing   emacs          Emacs with PGTK, built here for ~/.local (about three minutes)
  missing   pacman         pacman 7 for ~/.local, with a current libalpm
  missing   distrobox      distrobox under ~/.local, working from Desktop Mode and Frametop
  missing   curiousj-tools sshtsf, xssh, pssh and the rest, as a uv tool
  missing   frametop       Frametop, the multi-screen Plasma desktop and 3D mouse
  missing   stream-frame   Stream Frame: watch, record and screenshot the headset (Flatpak)
  missing   moonlight      Moonlight game streaming client (Flatpak, Flathub)
  missing   krdc           KRDC, KDE's RDP and VNC client (Flatpak, Flathub)
  missing   deskflow       Deskflow, the PC's mouse and keyboard on the Frametop desktop (Flatpak)
  missing   krdp           KRdp's server, built here as a Flatpak (half an hour the first time)
  missing   bsmanager      BSManager, Beat Saber versions, mods and maps (upstream installer)
  missing   full-keyboard  Full Keyboard for the dashboard and local apps (upstream installer)
```

There is no "recommended" mark and no preselected set (plan D11): the
one-line descriptions are the recommendation. Marking `tailscale`,
`waypipe`, `nerd-fonts` and `moonlight` and confirming runs them in
catalog order, each item asking for what it needs and saying what it
does, in the `ok`/`install`/`note` columns the scripts use today:

```
install        tailscale
sudo: a password for steamos is needed once, for the system service.
[sudo] password for steamos:
install        /home/.tailscale/bin/tailscale 1.96.1
install        /etc/systemd/system/tailscaled.service
enable         tailscaled
note           log in with: sudo /home/.tailscale/bin/tailscale up --qr --operator=steamos --ssh
ok             tailscale alias (in init.sh)
install        waypipe
keyring        Arch Linux ARM's keys, checked against the pinned fingerprint
relocate       waypipe 0.11.2-1 under ~/.local
install        nerd-fonts
install        JetBrainsMono v3.4.0 -> ~/.local/share/fonts/NerdFonts/JetBrainsMono
install        NerdFontsSymbolsOnly v3.4.0
fc-cache       2 families added; restart Konsole and pick a "Nerd Font Mono" family
install        moonlight
add            remote flathub (user)
install        com.moonlight_stream.Moonlight, and org.kde.Platform 6.11 (about 400 MB)
proceed? [Y/n]
done: 4 installed; cjf status shows them
```

The same by name, scriptable, with `--yes` answering every question:

```
$ cjf --yes install tailscale waypipe nerd-fonts moonlight
```

### Items that need other items

An item declares what it needs (plan D21): `zsh` needs `homebrew`,
`rust` needs nothing beyond the base (mise is there), a Rust PKGBUILD
needs `rust`. Asking for one asks for its needs with it, up front, as
one question:

```
$ cjf install zsh
zsh needs homebrew, which isn't installed. Install both?
  homebrew    Homebrew in /home/linuxbrew (sudo once, to create the directory)
  zsh         zsh from Homebrew
continue? [Y/n]
install        homebrew
[sudo] password for steamos:
...
install        zsh
```

A command that depends on an item says which, and how to get it, in
the one-line form of the stage 1 refusals:

```
$ cjf rdp start
cjf: rdp needs the krdp item (KRdp's server): cjf install krdp
$ bsmanager
bsmanager: needs the bsmanager item and waypipe: cjf install bsmanager waypipe
```

## 2. An ordinary day

Two commands (plan D23): `status` is the live state of the Frame,
`installed` is the catalog's, and `status --all` is both:

```
$ cjf status
SteamOS       0.5.6       build 20261022.6153909, beta channel
SteamVR       2.18.2      build 1791331621 (2026-10-07 00:07 UTC)
Steam client  1792099137  built 2026-10-15 21:18 UTC, beta channel
kit           curiousj-framekit 0.3.0, editable from ~/curiousj-framekit

headset       98%, plugged in (15 V), not charging: full
cursor        software on, 32 px breeze_cursors (stock), 32 px (frametop)
tailscale     running, 100.84.3.21, key expires in 171 days
rdp           not running
$ cjf installed
ok        cursor         the software mouse cursor in Desktop Mode, and the cursor size
ok        tailscale      Tailscale as a system service that survives updates (sudo)
missing   homebrew       Homebrew in /home/linuxbrew, for zsh and wl-clipboard (sudo once)
...
outdated  waypipe        0.11.2-1 installed, 0.11.3-1 at Arch Linux ARM
```

The headset and the controllers, from a shell instead of putting the
headset on. The headset's battery comes from the kernel
(`/sys/class/power_supply/max1720x_bat_7-36`), so it shows with or
without SteamVR running; the controllers' comes from SteamVR, as today:

```
$ cjf vr
device   model               serial        on   battery
headset  Steam Frame                       yes  98%  plugged in, full
left     Steam Frame Ctrl L  2ABC...       yes  61%  ~1.33 V, NiMH about half
right    Steam Frame Ctrl R  2ABD...       yes  58%  ~1.32 V, NiMH about half
$ cjf vr off left
off            left  (a button turns it back on)
$ cjf controllers
Steam Controller (28de:1303)  on   battery 84%
$ cjf controllers off
off            Steam Controller
```

The desktop:

```
$ cjf cursor
software cursor  on (the next sessions); the running desktop got KWIN_FORCE_SW_CURSOR=1
size             32 px, breeze_cursors    (Desktop Mode, running)
$ cjf cursor size 24
set            24 px for the stock desktop (running); KWin told to reload
$ cjf cursor software off
change         ~/.config/curiousj-framekit/config.toml   (cursor.software = false)
remove         ~/.config/environment.d/90-kwin-software-cursor.conf
remove         ~/.config/autostart/curiousj-framekit-cursor.desktop
note           takes effect at the next login
$ cjf wifi
signal  *  SSID            connection
 84     *  home-5g
 61        home
 40        neighbour-guest
```

Plain words, no flags to remember: `cursor size`, `cursor software
on|off|default`, `cursor theme NAME`, `cursor apply` (what the
autostart entry runs). The old `--desktop frametop|stock` stays as an
option on `size` for use over SSH when both desktops run.

## 3. The desktop from the PC over RDP

On the Frame, with the `krdp` item installed and Frametop's desktop
running:

```
$ cjf rdp start
start          krdpserver (io.github.curiousjtuber.Krdp) on frametop's desktop, port 3391
note           connect to frame.local:3391 as steamos; password: cjf rdp password
$ cjf rdp status
running        pid 41023, frametop desktop, port 3391, 1 client (192.168.1.20)
```

On the PC, KRDC to `frame.local:3391`. Later:

```
$ cjf rdp password --generate
set            a new password in ~/.config/krdpd/password; the running server picks it up
$ cjf rdp stop
```

From the Frametop desktop itself, "KRdp Server" in the menu is the
same thing as a window, with the password and the log shown. It is a
standalone script run by the system Python (plan Q14), so it needs
nothing installed beyond the `krdp` item, whose install adds the menu
entry.

## 4. Beat Saber

Two commands of their own, since their names go into Steam (plan Q17):

```
$ beat-saber-recent
2026-10-30 21:14  launch
  21:16  Megalovania [Expert+]
  21:21  Ghost [Expert]
2026-10-31 19:02  launch
  19:04  Gangnam Style [Hard]
$ beat-saber-recent --install-hook
set            Beat Saber launch options, through the Steam client's debug port:
               ~/.local/bin/beat-saber-recent --record; %command%; ~/.local/bin/beat-saber-recent --record
```

The hook keeps the absolute path, since Steam's `PATH` has no
`~/.local/bin`. The install itself is a catalog item, `cjf install
bsmanager`. And BSManager in a window on the PC, through waypipe:

```
pc$ waypipe --remote-bin /home/steamos/.local/bin/waypipe ssh steamos@frame.local bsmanager
```

(sshtsf opens tmux first, so it is not a one-liner for this; a session
in its config with `waypipe = true` and `command = "bsmanager"` under
a `[hosts.frame]` entry does the same from `sshtsf frame bsmanager`, if
you want it there.) On the Frame, `bsmanager` refuses outside a
Wayland session with the one-liner above in the message, and without
its item or waypipe with the install command (scenario 1).

## 5. Something new to install, later

```
$ cjf install krdc
install        krdc
ok             remote flathub (user)
install        org.kde.krdc  (the KDE runtime 6.10 is there already, from stream-frame)
proceed? [Y/n]
done
$ cjf install --check frametop
would install  frametop 0.2.3 (release Frametop.zip, sha256 recorded here)
would ask      Frametop's own eye tracker (sudo), the Bluetooth fixes (sudo)
```

The scope of a Flatpak, per item or for all:

```
$ cjf install --system moonlight         # sudo flatpak --system
```

```toml
# ~/.config/curiousj-framekit/config.toml
[flatpak]
scope = "user"          # or "system"

[cursor]
software = true
size = 32
theme = "breeze_cursors"

[rdp]
port = 3391
```

Updating what is installed is the same command again: an installed item
is updated, as every script does on a re-run today. `cjf install` with
every item marked is "update everything this kit knows about".

## 6. After a SteamOS update

```
$ cjf after-update
SteamOS        0.5.6 -> 0.5.7 (build 20261118.6209911), since the last run
ok             tailscaled.service is still there and enabled
ok             ~/.local packages resolve their libraries (waypipe, emacs, pacman)
rebuild        emacs: libtree-sitter.so.0 not found  ->  cjf pkg build emacs
ok             ~/.config/environment.d/90-kwin-software-cursor.conf matches config
check          Frametop 0.2.2: the tested-SteamOS table doesn't list 0.5.7 yet
note           docs/desktop-cursor.md says how to re-check the cursor fixes on a new SteamOS
```

Then whatever it named: `cjf pkg build emacs`, or `cjf install
tailscale` if the unit were gone, which restores it and keeps the
login. The "since the last run" line compares against the SteamOS
version and build recorded in
`~/.local/state/curiousj-framekit/after-update.toml` at the end of
each run (plan D24); the first run says it has nothing to compare
with and records.

## 7. Packages under ~/.local

`pacman-home` keeps its name and pacman's flags:

```
$ pacman-home -Q
emacs-wayland 31.1-1
pacman 7.1.0-1
waypipe 0.11.2-1
$ pacman-home outdated
waypipe   0.11.2-1  ->  0.11.3-1   (Arch Linux ARM)
emacs     31.1-1    ok (pkgbuilds/emacs)
pacman    7.1.0-1   ok (pkgbuilds/pacman; git snapshot upstream)
$ cjf install waypipe                   # relocates 0.11.3
```

A new program, the three ways in from the plan's "Which way in":

```
$ pacman-home relocate jq               # 1: binary, if self-contained
$ cjf pkg homeify jq                    # 2: Arch's PKGBUILD rewritten for ~/.local, diff shown
$ cjf pkg build jq                      # makepkg -f, pacman-home -U, offer to clean up
$ cjf pkg build paru
cjf: paru's PKGBUILD needs cargo, from the rust item: cjf install rust
```

## 8. This Frame, moving over

Once, on the Frame set up by `setup.sh`:

```
$ cjf migrate
found          steam-frame-utils blocks in ~/.bashrc, ~/.zshrc, ~/.profile, ~/.distroboxrc
change         ~/.bashrc      (the two blocks removed; the init line added)
--- ~/.bashrc
+++ ~/.bashrc
@@ -1,9 +1,3 @@
-# >>> steam-frame-utils: top >>>
-# https://github.com/curiousjtuber/steam-frame-utils#shell-init
-for _sfu in brew frametop bin; do
-    _sfu="$HOME/steam-frame-utils/shell-init/$_sfu.sh"
-    [[ -r $_sfu ]] && source "$_sfu"
-done
-unset _sfu
-# <<< steam-frame-utils: top <<<
+[[ -r ~/.local/share/curiousj-framekit/init.sh ]] && source ~/.local/share/curiousj-framekit/init.sh
write ~/.bashrc? [Y/n]
backup         ~/.bashrc.bak-20261101-100012
...
replace        ~/.config/autostart/steam-frame-utils-cursor.desktop -> curiousj-framekit-cursor.desktop
replace        ~/.config/frametop/autostart/steam-frame-utils-cursor.desktop
move           ~/.local/state/steam-frame-utils -> ~/.local/state/curiousj-framekit
carry          cursor.software = true  (from the environment.d marker line)
set            Beat Saber launch options: ~/steam-frame-utils/bin/beat-saber-recent -> ~/.local/bin/beat-saber-recent
ok             pacman-home's database under ~/.local (pacman's layout, unchanged)
done: open a new shell; a second run finds nothing to do
```

Then, at stage 7, `mv ~/steam-frame-utils ~/curiousj-framekit` and
`uv tool install --force --editable ~/curiousj-framekit`; nothing else
names the directory by then.

## 9. From a distrobox, and from the PC

The home directory is shared with every box, so `cjf` is on `PATH`
there and runs (the tool venv's Python lives under `~/.local`). What
needs the host says so, as it did in stage 1:

```
box$ cjf status
cjf: status runs on the Frame's host, not in a container; from a distrobox: distrobox-host-exec cjf status
box$ distrobox-host-exec cjf status
SteamOS       0.5.6 ...
```

`distrobox enter` itself works from Desktop Mode because the podman
shim is first on `PATH` through `init.sh` and `~/.distroboxrc`, as
`bin/podman` is today.

On the PC there is no `cjf` (plan D20): the PC side is `pc/` with the
two PKGBUILDs and a README, installed with `makepkg -si` in their
directories. If a PC command comes, it is `curiousj-framekit-pc`, a
second package in the same repo.

## 10. The kit itself

On the Frame it is an editable install from the checkout, so updating
it is `git pull` in `~/curiousj-framekit`; after a change to
`pyproject.toml` (a new dependency or entry point), `uv tool install
--force --editable ~/curiousj-framekit` once. A Frame installed from
the one-liner updates with the same one-liner, or `uv tool upgrade
curiousj-framekit`. `cjf status` could show the kit's own version and
whether the checkout is behind `origin/dev`; that is not in the plan
and is a question for you.

## 11. Help, everywhere the same

```
$ cjf --help                 the map: one line per command
$ cjf install --help         the docstring as written: usage lines, then options
$ cjf -h cursor              -h works like --help, at either place
$ cjf --check install emacs  what would happen, nothing changed
$ cjf -v install emacs       every command run, printed as it runs
$ cjf cur<TAB>               completion, from init.sh
```

Every change to a file is shown as a diff and asked about, backed up
with a timestamp first; `--yes` answers, `--check` reports; without a
terminal a command asks nothing and takes the default, as `setup.sh`
does now.

## What this left open, and how it was settled

- `cjf status` versus the catalog's state: two commands, `status` for
  the live state and `installed` for the catalog, `status --all` for
  both (D23).
- `after-update` records the SteamOS version at each run, in a small
  state file (D24).
- The kit's own version: shown as a `kit` line in `status`, with where
  it is installed from; whether the checkout is behind `origin/dev` is
  not checked, since that needs the network and `git fetch` is the
  honest answer.
- The picker stays two levels deep, commands and then the catalog, as
  `ujust` is.

## Revision history

- **Rev 3, 2026-10-31.** From the second round of annotations: the
  `sshtsf -w` one-liner replaced by the waypipe command and a note on
  an sshtsf session; `status` and `installed` split (D23);
  `after-update` records (D24); the open points closed.
- **Rev 2, 2026-10-31.** From the first annotations: the installer is
  mise-first, lists what it will install and asks once, and runs `cjf
  init`; a section on items that need other items and commands that
  need items (plan D21); the headset's battery in `cjf vr` and
  `status`, from the kernel.
- **Rev 1, 2026-10-31.** First draft.
  
  add to todo
  
- The picker's two-level shape, a command menu and then a catalog
  menu, means two keystrokes to reach "install something"; `cjf
  install` typed is one. That matches `ujust`, which is also flat, but
  if you'd rather have the catalog items in the top menu too, that is
  easy to add and worth deciding before stage 4.

  no catalog items in the top menu for now

## Revision history

- **Rev 2, 2026-10-31.** From your annotations: the installer is
  mise-first, lists what it will install and asks once, and runs `cjf
  init`; a section on items that need other items and commands that
  need items (plan D21); the headset's battery in `cjf vr` and
  `status`, from the kernel.
- **Rev 1, 2026-10-31.** First draft.
