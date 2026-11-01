"""The `flatpak-build` kind: an app built here with flatpak-builder from
a manifest the kit ships. Today KRdp's server: SteamOS has no krdp,
Flathub only the client, and anything built against the image's Plasma
breaks at the next SteamOS update, so it is built on KDE's runtime with
its own FreeRDP, kpipewire and krdp, pinned and patched as the manifest
explains. It goes in the user installation, where flatpak-builder works
without root; the build needs the KDE SDK (about 1 GB to download, 4 GB
on disk) and org.flatpak.Builder, installed on first use, and takes
about half an hour on the Frame. Downloads and build state stay in
~/.cache/krdpd/flatpak, so a re-run after a manifest change rebuilds
only what changed, and a run with nothing changed does nothing.

    cjf install krdp [--bundle [FILE]]    also write the app as one .flatpak
                                          file for another aarch64 device
                                          (flatpak --user install FILE)

The CI workflow builds the same bundle on GitHub's arm64 runner with
CJF_ASSUME_FRAME=1."""

from __future__ import annotations

import hashlib
import os
from importlib import resources
from pathlib import Path

from ... import cmdline, where
from ...cmdline import Error, Options
from ..catalog import Item, State, Status
from .base import Base, require_commands

FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"
GUI_ID = "io.github.curiousjtuber.Krdpd"


def manifest_path(item: Item) -> Path:
    return Path(str(resources.files("curiousj_framekit") / "data" / item["manifest"]))


def state_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "krdpd/flatpak"


def stamp(item: Item) -> str:
    """The first 16 hex digits of the sha256 over the manifest's lines
    that build something (comment and blank lines left out, so a note
    added to the manifest doesn't force a half-hour rebuild) and the
    patches beside it."""
    manifest = manifest_path(item)
    h = hashlib.sha256()
    for line in manifest.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            h.update(line.encode() + b"\n")
    for patch in sorted(manifest.parent.glob("*.patch")):
        h.update(patch.read_bytes())
    return h.hexdigest()[:16]


def installed_stamp() -> str | None:
    try:
        return (state_dir() / "installed").read_text().strip()
    except OSError:
        return None


def menu_entry_path() -> Path:
    return Path.home() / ".local/share/applications" / f"{GUI_ID}.desktop"


def menu_entry_text() -> str:
    return ("[Desktop Entry]\nType=Application\nName=KRdp Server\n"
            "GenericName=Remote Desktop Server\n"
            "Comment=Serve this Plasma desktop over RDP: start, stop, where to connect, the password\n"
            f"Exec={cmdline.cjf_path()} rdp gui\nIcon=krfb\nTerminal=false\n"
            "Categories=Network;RemoteAccess;\nKeywords=rdp;remote;krdp;krdpd;\n")


def flatpak_user(opts: Options, *args: str, check: bool = True, capture: bool = True):
    env = dict(os.environ, XDG_RUNTIME_DIR=f"/run/user/{os.getuid()}")
    return cmdline.run(opts, ["flatpak", "--user", *args], check=check, capture=capture, env=env)


class Kind(Base):
    options = "[--bundle [FILE]]"

    def status(self, item: Item, opts: Options) -> Status:
        proc = flatpak_user(opts, "info", item["app"], check=False)
        if proc.returncode != 0:
            return Status(State.MISSING)
        commit = next((l.split(":", 1)[1].strip()[:12] for l in proc.stdout.splitlines()
                       if l.strip().startswith("Commit:")), "")
        if installed_stamp() != stamp(item):
            return Status(State.OUTDATED, f"{commit}; the manifest changed since the build")
        return Status(State.OK, commit)

    def install(self, item: Item, opts: Options, args: list[str]) -> bool:
        where.require_host(item.name)
        require_commands("flatpak")
        bundle = None
        if args:
            if args[0] != "--bundle" or len(args) > 2:
                raise Error(f"{item.name} takes --bundle [FILE]; got {' '.join(args)}")
            bundle = Path(args[1] if len(args) == 2 else f"{os.getcwd()}/{item['app']}.flatpak")
        manifest = manifest_path(item)
        if not manifest.is_file():
            raise Error(f"manifest not found: {manifest}")
        status = self.status(item, opts)
        changed = False
        if status.state == State.OK:
            cmdline.say("ok", f"{item['app']} ({status.detail}), up to date with the manifest")
        else:
            cmdline.say("would build" if opts.check else "build",
                        f"{item['app']} from {cmdline.tilde(manifest)} "
                        "(about half an hour the first time; the SDK is about 1 GB)")
            if opts.check:
                changed = True
            elif not cmdline.confirm(opts, "install the SDK if needed and build?"):
                return False
            else:
                flatpak_user(opts, "remote-add", "--if-not-exists", "flathub", FLATHUB)
                out = flatpak_user(opts, "install", "-y", "--noninteractive", "flathub", item["sdk"],
                                   *item.get("extras", []), check=False).stdout
                for line in out.splitlines():
                    if line.strip() and "is already installed" not in line:
                        print(line)
                state = state_dir()
                state.mkdir(parents=True, exist_ok=True)
                cmdline.run(opts, ["flatpak", "run", "org.flatpak.Builder", "--user", "--install",
                                   "--force-clean", "--install-deps-from=flathub",
                                   f"--state-dir={state / 'state'}", str(state / "build"), str(manifest)],
                            capture=False, env=dict(os.environ, XDG_RUNTIME_DIR=f"/run/user/{os.getuid()}"))
                (state / "installed").write_text(stamp(item) + "\n")
                cmdline.say("installed", f"{item['app']} ({self.status(item, opts).detail})")
                print("start it with: cjf rdp start   (see cjf rdp --help)")
                changed = True
        # The menu entry, in the home folder's applications, which both
        # desktops' menus read.
        changed |= cmdline.write_file(opts, menu_entry_path(), menu_entry_text())
        if bundle and not opts.check:
            # flatpak-builder exports each build to the ostree repo in its
            # state dir; the bundle comes from there, and names Flathub so
            # the installing side can fetch the runtime itself.
            cmdline.run(opts, ["flatpak", "build-bundle", f"--runtime-repo={FLATHUB}",
                               str(state_dir() / "state" / "cache"), str(bundle), item["app"], "master"],
                        capture=False)
            size = bundle.stat().st_size / 1_000_000
            print(f"wrote {bundle} ({size:.0f} MB); install it with: flatpak --user install {bundle}")
            changed = True
        elif bundle:
            cmdline.say("would write", str(bundle))
        return changed

    def uninstall(self, item: Item, opts: Options) -> bool:
        changed = False
        if flatpak_user(opts, "info", item["app"], check=False).returncode == 0:
            cmdline.say("would remove" if opts.check else "remove", item["app"])
            if not opts.check and cmdline.confirm(opts, f"remove {item['app']}?"):
                flatpak_user(opts, "uninstall", "-y", "--noninteractive", item["app"], capture=False)
            changed = True
        changed |= cmdline.remove_file(opts, menu_entry_path(), "the KRdp Server menu entry")
        if changed and not opts.check:
            cmdline.note(f"the build tools stay: flatpak --user uninstall {item['sdk']} org.flatpak.Builder")
        return changed
