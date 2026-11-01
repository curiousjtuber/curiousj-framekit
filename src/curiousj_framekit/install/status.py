"""cjf status -- what this Frame runs: the versions of SteamOS, SteamVR
and the Steam client, as Valve's patch notes number them, with each
one's build and update channel; the kit's own version; the headset's
battery; the cursor; Tailscale; the RDP server.

    cjf status [--all]

--all adds every catalog item's state, what `cjf installed` prints.
Runs on the Frame's host; a distrobox sees its own /etc/os-release, so
from one run `distrobox-host-exec cjf status`, which the refusal says.
"""

from __future__ import annotations

import json
from importlib import metadata

import click

from .. import cmdline, config, where
from ..cmdline import Options, pass_options
from ..frame import cursor, rdp, versions, vr


def kit_line() -> str:
    try:
        version = metadata.version("curiousj-framekit")
    except metadata.PackageNotFoundError:
        version = "?"
    where_from = ""
    try:
        direct = json.loads(metadata.distribution("curiousj-framekit").read_text("direct_url.json") or "{}")
        if direct.get("dir_info", {}).get("editable"):
            where_from = ", editable from " + cmdline.tilde(direct.get("url", "").removeprefix("file://"))
        elif direct.get("url"):
            where_from = ", from " + direct["url"]
    except (ValueError, metadata.PackageNotFoundError):
        pass
    return f"{'kit':<13} {version:<11} curiousj-framekit{where_from}"


def live_lines(opts: Options) -> list[str]:
    lines = []
    power = vr.headset_power()
    if power:
        lines.append(f"{'headset':<13} {power}")
    value, kind = cursor.conf_state(cursor.read_text(cursor.conf_path()),
                                    config.get("cursor", "software"))
    lines.append(f"{'cursor':<13} software {cursor.describe_state(value, kind)}")
    if not where.in_container():
        from .kinds import tailscale as ts
        from . import catalog
        status = ts.Kind().status(catalog.load()["tailscale"], opts)
        lines.append(f"{'tailscale':<13} {status.detail or status.state.value}")
        pid = rdp.instance_pid(opts)
        info = rdp.read_info() if pid else {}
        lines.append(f"{'rdp':<13} " + (f"running (pid {pid}), port {info.get('port', '?')}"
                                         if pid else "not running"))
    return lines


@click.command(cls=cmdline.Command, help=__doc__,
               short_help="the versions of SteamOS, SteamVR and the Steam client, and the live state")
@click.option("--all", "all_", is_flag=True, help="Also every catalog item's state.")
@pass_options
def status(opts: Options, all_: bool) -> int:
    where.require_host("status")
    print(versions.format_rows(versions.rows(opts, where.os_release())))
    print(kit_line())
    print()
    print("\n".join(live_lines(opts)))
    if all_:
        from . import catalog, commands
        items = catalog.load()
        print()
        print("\n".join(commands.state_lines(items, catalog.all_status(items, opts))))
    return 0
