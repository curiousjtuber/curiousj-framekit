"""The versions of SteamOS, SteamVR and the Steam client on the Frame,
the numbers Valve's patch notes give, with each one's build and update
channel: the top of `cjf status`.

SteamVR comes with the OS image, under /opt/steamvr, and changes only
with a SteamOS update; vrcmd prints its version without SteamVR
running, and vrserver's log says it at each start, as the fallback. The
Steam client updates itself into ~/.local/share/Steam, so its version
is read from there, not from the deckard-steam-rel package, which keeps
the client the image shipped with: package/beta names the channel when
it isn't the default one, the manifest is named after it, and the
manifest's "version" is the one Settings > About shows. The client's
version and SteamVR's build are Unix times, shown with their date.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from ..cmdline import Options, output

STEAMVR = Path("/opt/steamvr")


@dataclass
class Row:
    name: str
    version: str
    detail: str


def format_rows(rows: list[Row]) -> str:
    return "\n".join(f"{r.name:<13} {r.version:<11} {r.detail}" for r in rows)


def when(unix_time: str | int) -> str:
    """`2026-10-07 00:07 UTC` for a Unix time, `?` for anything else."""
    try:
        return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(int(unix_time)))
    except (ValueError, OverflowError, OSError):
        return "?"


# --- SteamOS ----------------------------------------------------------

def steamos_row(info: dict[str, str], branch: str | None) -> Row:
    return Row("SteamOS", info.get("VERSION_ID", "?"),
               f"build {info.get('BUILD_ID', '?')}, {branch or '?'} channel")


# --- SteamVR ----------------------------------------------------------

def vrserver_log_version(log: str) -> str | None:
    """The version from the last `vrserver X.Y.Z startup` line of
    vrserver.txt."""
    found = re.findall(r" vrserver ([0-9.]+) startup ", log)
    return found[-1] if found else None


def steamvr_row(version: str | None, version_txt: str | None,
                vr_dir: Path = STEAMVR) -> Row:
    """version_txt is the content of bin/version.txt, which ends in CRLF;
    only its digits are the build."""
    build = re.sub(r"\D", "", version_txt or "")
    if build:
        detail = f"build {build} ({when(build)})"
    else:
        detail = f"no {vr_dir}/bin/version.txt"
    return Row("SteamVR", version or "?", detail)


# --- Steam client -----------------------------------------------------

def channel_of(beta: str) -> str:
    """`linux_arm64_beta_861407927dc8efb407da7cf` is the beta channel; an
    empty beta file, or none, is stable."""
    name = re.sub(r"^linux_arm64_", "", beta.strip())
    name = re.sub(r"_[0-9a-f]{16,}$", "", name)
    return name or "stable"


def manifest_version(text: str) -> str | None:
    """The "version" of a steam_client_*.manifest, a Unix time."""
    m = re.search(r'^\t"version"\t*"(\d+)"$', text, re.M)
    return m.group(1) if m else None


def client_manifest(package: Path) -> tuple[Path | None, str]:
    """The manifest for the channel package/beta names, else the newest
    manifest there, else None; and the beta file's content."""
    try:
        beta = (package / "beta").read_text().strip()
    except OSError:
        beta = ""
    named = package / f"steam_client_{beta + '_' if beta else ''}linuxarm64.manifest"
    if named.is_file():
        return named, beta
    found = sorted(package.glob("steam_client_*.manifest"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return (found[0] if found else None), beta


def steam_client_row(package: Path) -> Row:
    manifest, beta = client_manifest(package)
    version = manifest_version(manifest.read_text()) if manifest else None
    if version:
        return Row("Steam client", version,
                   f"built {when(version)}, {channel_of(beta)} channel")
    return Row("Steam client", "?", f"no client manifest under {package}")


def steam_package_dir(home: Path | None = None) -> Path:
    """~/.steam/steam resolved, else ~/.local/share/Steam; then package/."""
    home = home or Path.home()
    link = home / ".steam" / "steam"
    steam = link.resolve() if link.exists() else home / ".local/share/Steam"
    return steam / "package"


# --- all three ----------------------------------------------------------

def rows(opts: Options, info: dict[str, str], home: Path | None = None,
         vr_dir: Path = STEAMVR) -> list[Row]:
    """The three rows, probing the Frame; a missing tool or file is a `?`,
    never an error."""
    home = home or Path.home()
    branch = output(opts, ["steamos-select-branch", "-c"])

    version = output(opts, [str(vr_dir / "bin/linuxarm64/vrcmd"), "--version"])
    if not version:
        try:
            log = (home / ".local/share/Steam/logs/vrserver.txt").read_text(errors="replace")
        except OSError:
            log = ""
        version = vrserver_log_version(log)
    try:
        version_txt = (vr_dir / "bin/version.txt").read_text()
    except OSError:
        version_txt = None

    return [steamos_row(info, branch),
            steamvr_row(version, version_txt, vr_dir),
            steam_client_row(steam_package_dir(home))]
