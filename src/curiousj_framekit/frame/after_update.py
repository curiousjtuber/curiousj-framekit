"""cjf after-update -- what to re-check after a SteamOS update, run as
one command: the checks the docs used to list, each ending in ok or in
the command that fixes it.

    cjf after-update

  SteamOS     the version and build now against what the last run
              recorded in ~/.local/state/curiousj-framekit/after-update.toml
              (recorded again at the end; the first run has nothing to
              compare with)
  tailscale   the unit is there and enabled, the daemon runs; an update
              can drop the unit (the keep list covers *.service, but a
              build has lost it before)
  packages    every program and library pacman-home installed under
              ~/.local still resolves its libraries (ldd ... not found);
              a host library moved from under a build means a rebuild
  cursor      the environment.d file matches the choice in the config,
              and the size entry is where the software cursor is
  frametop    which Frametop the Desktop launcher starts, the release
              the catalog knows or a checkout, and whether the release is
              current
  krdp        whether the built server still matches the kit's manifest

Then docs/desktop-cursor.md says how to re-check the cursor fixes on a
new SteamOS, which only a person with the headset on can do.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import click

from .. import cmdline, config, where
from ..cmdline import Options, pass_options
from . import cursor, pkg

RECORD_KEYS = ("VERSION_ID", "BUILD_ID")
LAUNCHER = ".local/share/applications/deckard-nested-desktop.desktop"


def state_path() -> Path:
    return config.state_dir() / "after-update.toml"


def read_record(path: Path | None = None) -> dict[str, str]:
    path = path or state_path()
    try:
        import tomllib
        with path.open("rb") as f:
            return {k: str(v) for k, v in tomllib.load(f).get("steamos", {}).items()}
    except (OSError, ValueError):
        return {}


def write_record(info: dict[str, str], path: Path | None = None, now: float | None = None) -> None:
    path = path or state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
    path.write_text(config.dumps({"steamos": {k: info.get(k, "?") for k in RECORD_KEYS} | {"seen": seen}}))


def steamos_line(info: dict[str, str], recorded: dict[str, str]) -> str:
    now = f"{info.get('VERSION_ID', '?')} (build {info.get('BUILD_ID', '?')})"
    if not recorded:
        return f"{'SteamOS':<14} {now}; nothing recorded before, recorded now"
    if all(recorded.get(k) == info.get(k) for k in RECORD_KEYS):
        return f"{'ok':<14} SteamOS {now}, as at the last run ({recorded.get('seen', '?')})"
    return (f"{'SteamOS':<14} {recorded.get('VERSION_ID', '?')} (build {recorded.get('BUILD_ID', '?')}) "
            f"-> {now}, since the last run ({recorded.get('seen', '?')})")


def is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def unresolved(path: Path) -> list[str]:
    """The libraries ldd says are not found for one file."""
    proc = subprocess.run(["ldd", str(path)], text=True, capture_output=True)
    return sorted({line.split()[0] for line in (proc.stdout + proc.stderr).splitlines()
                   if "not found" in line and line.split()})


def package_files(paths: pkg.Paths, name: str) -> list[Path]:
    out = pkg.pacman(paths, paths.conf, "-Ql", name, check=False).stdout
    files = []
    for line in out.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            p = Path(parts[1])
            if p.is_file() and not p.is_symlink() and ("/bin/" in str(p) or "/lib/" in str(p)):
                files.append(p)
    return files


def check_packages(opts: Options, items: dict) -> list[str]:
    lines = []
    try:
        paths = pkg.Paths()
        paths.write_confs()
        installed = pkg.pacman(paths, paths.conf, "-Q", check=False).stdout.split("\n")
    except Exception as e:  # noqa: BLE001
        return [f"{'skip':<14} packages: {e}"]
    names = [l.split()[0] for l in installed if l.strip()]
    if not names:
        return [f"{'ok':<14} no packages under ~/.local"]
    for name in names:
        missing: dict[str, list[str]] = {}
        for f in package_files(paths, name):
            if is_elf(f):
                libs = unresolved(f)
                if libs:
                    missing[f.name] = libs
        if not missing:
            lines.append(f"{'ok':<14} {name}: its programs and libraries resolve")
            continue
        detail = "; ".join(f"{f}: {' '.join(libs)}" for f, libs in missing.items())
        item = next((it for it in items.values() if it.get("package") == name), None)
        fix = (f"cjf install {item.name}" if item and item.get("relocate")
               else f"cjf pkg build {item['pkgbuild']}" if item else f"rebuild {name}")
        lines.append(f"{'rebuild':<14} {name}: not found: {detail}  ->  {fix}")
    return lines


def check_tailscale(opts: Options) -> str:
    from ..install.kinds import tailscale as ts
    parts = ts.missing_parts(opts, False)
    if "binaries" in parts and "unit" in parts:
        return f"{'ok':<14} tailscale: not installed"
    if parts:
        return f"{'fix':<14} tailscaled: missing {' '.join(parts)}  ->  cjf install tailscale"
    return f"{'ok':<14} tailscaled.service is there, enabled and running"


def check_cursor() -> list[str]:
    lines = []
    value, kind = cursor.conf_state(cursor.read_text(cursor.conf_path()), config.get("cursor", "software"))
    choice = config.get("cursor", "software")
    if kind == "none":
        lines.append(f"{'fix':<14} {cmdline.tilde(cursor.conf_path())} is gone  ->  cjf cursor software auto")
    elif kind == "other":
        lines.append(f"{'check':<14} {cmdline.tilde(cursor.conf_path())} isn't the kit's; left alone")
    elif choice is not None and value != ("on" if choice else "off"):
        lines.append(f"{'fix':<14} the environment.d file says {value}, the config {'on' if choice else 'off'}"
                     f"  ->  cjf cursor software {'on' if choice else 'off'}")
    else:
        lines.append(f"{'ok':<14} {cmdline.tilde(cursor.conf_path())} matches the config ({value})")
    if value == "on":
        for base, present in cursor.autostart_dirs():
            if present and not (base / "autostart" / cursor.ENTRY_NAME).is_file():
                lines.append(f"{'fix':<14} no cursor size entry in {cmdline.tilde(base / 'autostart')}"
                             "  ->  cjf cursor software auto")
    return lines


def check_frametop(items: dict, statuses: dict) -> list[str]:
    lines = []
    launcher = Path.home() / LAUNCHER
    exec_line = ""
    if launcher.is_file():
        for line in launcher.read_text().splitlines():
            if line.startswith("Exec="):
                exec_line = line[5:]
    releases = Path.home() / ".local/share/frametop/releases"
    if not exec_line:
        lines.append(f"{'ok':<14} Frametop: no Desktop launcher (not installed)")
        return lines
    if str(releases) in exec_line:
        lines.append(f"{'ok':<14} the Desktop launcher starts the Frametop release ({exec_line})")
    else:
        lines.append(f"{'note':<14} the Desktop launcher starts {exec_line.split()[0]}, a checkout, not the "
                     "release; that checkout's install.sh switched it")
    status = statuses.get("frametop")
    if status is not None:
        from ..install.catalog import State
        if status.state == State.OUTDATED:
            lines.append(f"{'check':<14} Frametop {status.detail}  ->  cjf install frametop")
        elif status.state == State.OK:
            lines.append(f"{'ok':<14} Frametop {status.detail} is the release the catalog knows")
    return lines


def check_krdp(statuses: dict) -> str:
    from ..install.catalog import State
    status = statuses.get("krdp")
    if status is None or status.state == State.MISSING:
        return f"{'ok':<14} krdp: not installed"
    if status.state == State.OUTDATED:
        return f"{'rebuild':<14} krdp: {status.detail}  ->  cjf install krdp"
    return f"{'ok':<14} krdp's build matches the kit's manifest"


@click.command(cls=cmdline.Command, help=__doc__, name="after-update",
               short_help="what to re-check after a SteamOS update, as one command")
@pass_options
def after_update(opts: Options) -> int:
    where.require_host("after-update")
    from ..install import catalog
    items = catalog.load()
    statuses = {n: catalog.status_of(items[n], opts) for n in ("frametop", "krdp") if n in items}
    info = where.os_release()
    recorded = read_record()
    print(steamos_line(info, recorded))
    print(check_tailscale(opts))
    for line in check_packages(opts, items):
        print(line)
    for line in check_cursor():
        print(line)
    for line in check_frametop(items, statuses):
        print(line)
    print(check_krdp(statuses))
    if recorded and any(recorded.get(k) != info.get(k) for k in RECORD_KEYS):
        print(f"{'note':<14} docs/desktop-cursor.md says how to re-check the cursor fixes on a new SteamOS")
    if not opts.check:
        write_record(info)
    return 0
