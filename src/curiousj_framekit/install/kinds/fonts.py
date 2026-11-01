"""The `fonts` kind: Nerd Fonts in ~/.local/share/fonts/NerdFonts, one
directory per font with a .version file, as install-nerd-fonts.sh did.
fontconfig reads that directory under Wayland and X11 alike, Flatpak
apps see it too, and /home survives SteamOS updates. A re-run replaces
only fonts older than the latest release; archives are checked against
the release's SHA-256.txt. NerdFontsSymbolsOnly brings a fontconfig
rule that makes every font fall back to it for the icons.

    cjf install nerd-fonts [NAME...]    the catalog's two, or the names given
                                        (release archives without .tar.xz)"""

from __future__ import annotations

import os
import shutil
import tarfile
from pathlib import Path

from ... import cmdline
from ...cmdline import Error, Options
from ..catalog import Item, State, Status
from .base import Base, TempDir, fetch, fetch_text, final_url, require_commands, require_user, sum_for, verify

REPO = "https://github.com/ryanoasis/nerd-fonts"


def fonts_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "fonts/NerdFonts"


def confd() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base and not base.rstrip("/").endswith("/frametop"):
        return Path(base) / "fontconfig/conf.d"
    return Path.home() / ".config/fontconfig/conf.d"


def installed_version(name: str) -> str | None:
    try:
        return (fonts_dir() / name / ".version").read_text().strip()
    except OSError:
        return None


class Kind(Base):
    options = "[NAME...]  (fonts other than the catalog's two: FiraCode, Hack, Meslo, ...)"

    def status(self, item: Item, opts: Options) -> Status:
        names = item["fonts"]
        have = {n: installed_version(n) for n in names}
        missing = [n for n, v in have.items() if not v]
        if len(missing) == len(names):
            return Status(State.MISSING)
        if missing:
            return Status(State.OUTDATED, f"missing {' '.join(missing)}")
        versions = sorted(set(have.values()))
        return Status(State.OK, versions[0] if len(versions) == 1 else " ".join(versions))

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        require_user()
        require_commands("fc-cache", "fc-scan")
        names = [a.removesuffix(".tar.xz") for a in args] or list(item["fonts"])
        for name in names:
            if name.startswith("-"):
                raise Error(f"nerd-fonts takes font names; got {name}")
        # releases/latest redirects to .../releases/tag/<tag>; resolving
        # it once keeps the checksums and every archive from one release.
        tag = final_url(f"{REPO}/releases/latest").rstrip("/").rsplit("/", 1)[-1]
        if not tag.startswith("v"):
            raise Error(f"unexpected latest release: {tag}")
        todo = [n for n in names if installed_version(n) != tag]
        for n in names:
            if n not in todo:
                cmdline.say("ok", f"{n} {tag}")
        if not todo:
            return False
        for n in todo:
            cmdline.say("would install" if opts.check else "install", f"{n} {tag} -> {cmdline.tilde(fonts_dir() / n)}")
        if opts.check:
            return True
        if not cmdline.confirm(opts, f"download {len(todo)} font archive{'s' if len(todo) > 1 else ''}?"):
            return False
        sums = fetch_text(f"{REPO}/releases/download/{tag}/SHA-256.txt")
        installed = []
        with TempDir() as tmp:
            for n in todo:
                expected = sum_for(sums, f"{n}.tar.xz")
                if not expected:
                    raise Error(f"no {n} in the {tag} release; see {REPO}/releases/latest for the names")
                archive = tmp / f"{n}.tar.xz"
                cmdline.say("download", f"{n} {tag}")
                fetch(opts, f"{REPO}/releases/download/{tag}/{n}.tar.xz", archive)
                verify(archive, expected, f"{n}.tar.xz")
                unpacked = tmp / n
                unpacked.mkdir()
                with tarfile.open(archive) as tar:
                    tar.extractall(unpacked, filter="data")
                (unpacked / ".version").write_text(tag + "\n")
                dest = fonts_dir() / n
                fonts_dir().mkdir(parents=True, exist_ok=True)
                shutil.rmtree(dest, ignore_errors=True)
                shutil.move(str(unpacked), str(dest))
                cmdline.say("install", cmdline.tilde(dest))
                for conf in sorted(dest.glob("*.conf")):
                    confd().mkdir(parents=True, exist_ok=True)
                    shutil.copy(conf, confd() / conf.name)
                    cmdline.say("copy", cmdline.tilde(confd() / conf.name))
                installed.append(dest)
        cmdline.run(opts, ["fc-cache", "-f", str(fonts_dir())])
        families = cmdline.run(opts, ["fc-scan", "--format", "%{family[0]}\n", *map(str, installed)],
                               capture=True, check=False).stdout
        print("restart running apps to see the new fonts. Families:")
        for fam in sorted(set(f for f in families.splitlines() if f)):
            print(f"  {fam}")
        return True

    def uninstall(self, item: Item, opts: Options) -> bool:
        changed = False
        for n in item["fonts"]:
            d = fonts_dir() / n
            if not d.exists():
                continue
            cmdline.say("would remove" if opts.check else "remove", cmdline.tilde(d))
            if opts.check or not cmdline.confirm(opts, f"remove {n}?"):
                changed = changed or opts.check
                continue
            for conf in d.glob("*.conf"):
                (confd() / conf.name).unlink(missing_ok=True)
            shutil.rmtree(d)
            changed = True
        if changed and not opts.check:
            cmdline.run(opts, ["fc-cache", "-f"], check=False)
        return changed
