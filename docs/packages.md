## Packages for the host

The Frame's image carries makepkg, gcc, meson, cmake and the headers of
its libraries, so a package can be built on the host itself, against the
exact libraries it will run with, with no distrobox and no cross
toolchain. The kit ships its PKGBUILDs inside the package,
`src/curiousj_framekit/data/pkgbuilds/`, one directory each, so an
install from git has them as a checkout does. They are configured with
`--prefix=$HOME/.local`, so the result finds its data under `~/.local`
instead of the read-only `/usr`. `emacs/` is Emacs with PGTK, a host
build that sees the Frame's own `/usr`, D-Bus and processes, which the
distrobox one did not; `cjf install emacs` builds and installs it.
`krdc/` is KRDC with the kit's "Remote pointer" patch, in place of the
Flathub flatpak; it carries the two build dependencies the host lacks
([krdc-embed-cursor.md](krdc-embed-cursor.md)). `fuse2/` is libfuse 2,
the `libfuse.so.2` that every AppImage's runtime loads to mount itself
and that SteamOS 0.5.7 dropped from the image; `cjf install bsmanager`
brings it, and runs the AppImage with its directory on
`LD_LIBRARY_PATH` (the library's own directory, `~/.local/lib/fuse2`,
so nothing else travels with it). The header of each PKGBUILD says
what it leaves out and why. By hand, from a checkout:

```bash
cd ~/curiousj-framekit/src/curiousj_framekit/data/pkgbuilds/emacs && makepkg -f
```

```bash
pacman-home -U emacs-wayland-*.pkg.tar.zst
```

`cjf pkg build emacs` is those two commands, from any directory, run in
`~/.cache/curiousj-framekit/build/emacs/`, a copy of the PKGBUILD's
directory, so that nothing lands inside the package. `cjf pkg build
DIR` builds a directory of yours in place. Either way it ends with an
offer to delete what the build left: `src/`, `pkg/`, the package and
the downloaded sources, about half a gigabyte for emacs, listed with
their size before the question (`--clean` deletes unasked, `--keep` asks
nothing; homeify's `PKGBUILD.upstream` is kept either way). Keep them
while a PKGBUILD is being adjusted, since `makepkg -R` repackages from
them in seconds. `cjf install emacs`, `krdc`, `fuse2` and `krdpserver`
build when `pacman-home` doesn't have the PKGBUILD's version, or when a
program or library of the installed package can no longer load (`ldd`
names a library the host lost: SteamOS 0.5.7 took libxml2's soname from
under emacs), so `cjf update` rebuilds after a SteamOS update with no
bump.
`pc/pkgbuilds/frame-control-bin` is the other kind, an ordinary `/usr`
package for an Arch PC, which nothing here builds or offers; the PC's
`krdpserver-embed-cursor` is a `~/.local` build by script (see [the PC
side](../pc/README.md)).

Any package whose build takes a prefix can be set up the same way.
`cjf pkg homeify NAME` fetches Arch's PKGBUILD for NAME, or the
AUR's when Arch has none, writes `NAME/PKGBUILD` under the current
directory (`--into DIR` for another), rewrites it for the prefix (the configure,
cmake, meson and make prefix flags, `/usr` under `$pkgdir`, `aarch64` in
`arch`, the rpath and pkg-config path for `~/.local/lib`, and for a Rust
package the rpath in `RUSTFLAGS` too), unlists the `makedepends` that
mise provides, such as cargo, since makepkg checks them against the
host's packages, prints the diff, and says which `makedepends` the host
lacks. Review it, then `makepkg -f` and `pacman-home -U`; paru's
PKGBUILD was homeify's output with no hand edit, while it was here
([docs/paru.md](paru.md)). The rewrite is the mechanical part: a
build system that hardcodes `/usr` shows up afterwards as a file outside
`~/.local`, which `pacman-home check PKG` lists and `pacman-home -U`
refuses, and is fixed in the PKGBUILD by hand, as the kit's `emacs` was, for
features the host lacks and a layout that keeps out of the host's way.

A program that needs no file outside its own tree, such as waypipe,
needn't be built at all. `pacman-home relocate NAME` fetches Arch Linux
ARM's binary package through pacman's own repository machinery, against
one mirror (`ALARM_MIRROR` overrides it), takes it only with a valid
signature from Arch Linux ARM's keys, moves its `/usr` tree under
`~/.local`, points its absolute symlinks there, drops its install
scriptlet, and installs the result; `relocate FILE` does the same to a
package you have. It refuses a package with files under `/etc` or
`/var`, or under the parts of `/usr` that only work from there (systemd
and udev directories, polkit, system D-Bus services), and one whose
libraries the host cannot supply, a glibc or Qt newer than the host's
included, since the loader names the symbol version it lacks;
`--allow-missing-libs` installs anyway. What it cannot see is a program
that looks for its data under `/usr` at run time; that one needs a
build.

### Which way in

For a new program, in this order:

The keys come from Arch Linux ARM's `archlinuxarm-keyring` package,
which `pacman-home keyring` (run by `relocate NAME` the first time, and
by `setup.sh --waypipe=host` for a waypipe from before) fetches once
with signatures off, since there is nothing to check it with yet, and
holds to the key fingerprint recorded in `pacman-home` instead, checked
against archlinuxarm.org: a keyring that trusts other keys is refused.
`pacman-key` then populates `pacman-home`'s own keyring under
`~/.local/etc/pacman.d/gnupg`, under fakeroot like pacman. `pacman-home
keyring --check` says whether the keys are there. Arch Linux ARM doesn't
sign its databases, so those are taken on the mirror's word, as every
pacman does.

1. **`pacman-home relocate NAME`, and run the program.** It is the whole
   job when the program needs nothing outside its own tree. Relocate
   refuses a package with files outside `/usr` or in the parts of `/usr`
   that only work from there, drops an install scriptlet, and refuses
   one whose libraries the host lacks; what it cannot see is a program
   that looks for its data under `/usr` at run time, which installs
   cleanly and then fails or falls back to defaults. So the test is
   both: relocate accepts it, and the program works. waypipe passed;
   anything with data files, plugins, schemas or Python modules is
   likely to fail the second part.
2. **`cjf pkg homeify NAME`, then `cjf pkg build NAME`.** Often the whole job too: jq and paru (while it was here) built
   from homeify's output as it came.
3. **Edit the PKGBUILD where two signals say so.** homeify's closing
   list of `makedepends` the host lacks is where emacs's libgccjit and
   tree-sitter showed up, and became features turned off. `pacman-home
   -U` refusing a file outside `~/.local` after the build is where
   pacman's bash completions showed up, and became a move in
   `package()`. Beyond those, a layout may need deciding, as pacman's
   did to keep off `PATH`, and a quirk may show only when the installed
   program runs, as emacs's launcher did. Record each decision in the
   PKGBUILD's header; it is what the next SteamOS update will make you
   re-read.

[docs/home-packages.md](home-packages.md) records which way each
package so far went in, and what it took.

`pacman-home` is pacman with a configuration written to
`~/.local/etc/pacman.conf` that keeps the database, cache and log under
`~/.local`; `relocate` uses a second one beside it that adds Arch Linux
ARM's repositories, which the plain one lacks so that `-U` never pulls a
`/usr` package from them to satisfy a dependency. pacman refuses to
install or remove unless it runs as root, whatever paths it is given, so
`pacman-home` runs those operations under fakeroot, the same arrangement
makepkg uses to package: pacman is told it is root, writes the files as
you, and the ownership it sets is faked, so the files are yours. Its
database knows only what it installed, so a package's dependencies are
checked against the host's database and passed as `--assume-installed`;
a dependency the host lacks is an error. `pacman-home -Q`, `-Ql`, `-Qo`
and `-R` work as usual within that database.

`pacman-home outdated` compares every installed package, by version,
with Arch Linux ARM's repositories, with the AUR for one they lack, and
with the kit's PKGBUILD for it, so a bump upstream shows up
without a build. The release number after the dash is this repo's own
and isn't compared; a packaging that tracks git, as Arch's pacman does,
is marked as a snapshot. `cjf outdated` makes the same comparison for
the catalog's packages among everything else it checks: a relocated
package with a newer one upstream is `outdated`, and `cjf update`
relocates the new one; a built package whose upstream moved past its
PKGBUILD is `behind`, which is a bump in the PKGBUILD, here.

The pacman it runs is the host's: pacman 7.1 with libalpm 16 since
SteamOS 0.5.7. Until then the host had 6.1 with libalpm 14, and the kit
carried a pacman 7 of its own under `~/.local/lib/pacman/bin`, for its
libalpm and for compiled-in paths; it went on 2026-11-06, once the host
caught up ([home-packages.md](home-packages.md)). The ldconfig run the
host's pacman attempts after every transaction fails on the read-only
root and says so (`error: command failed to execute correctly`); the
transaction is done by then.

After a SteamOS update, `cjf installed` says which package lost a host
library, by `ldd` over its programs and libraries, and `cjf update`
rebuilds it.
