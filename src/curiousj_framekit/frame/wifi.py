"""cjf wifi -- the Wi-Fi networks NetworkManager has saved, from Desktop
Mode, where the Frame has no Plasma network applet: by default only the
ones in range now, strongest first.

    cjf wifi [--all]

Columns: signal (0-100, blank when out of range), * for the network in
use, the SSID, and the connection's name when it differs from the SSID.
--all lists every saved network, in range or not. Saved networks are
matched by SSID, not by connection name, so a renamed one still shows.
Connect with `nmcli connection up NAME`.
"""

from __future__ import annotations

import click

from .. import cmdline, where
from ..cmdline import Options, pass_options


def unescape(ssid: str) -> str:
    """nmcli's terse output escapes a colon as \\: and a backslash as \\\\."""
    return ssid.replace("\\:", ":").replace("\\\\", "\\")


def wireless_uuids(terse: str) -> list[str]:
    """From `nmcli -t -f UUID,TYPE connection show`: the UUIDs of the
    Wi-Fi connections."""
    found = []
    for line in terse.splitlines():
        uuid, sep, kind = line.rpartition(":")
        if sep and kind == "802-11-wireless":
            found.append(uuid)
    return found


def sightings(terse: str) -> tuple[dict[str, int], set[str]]:
    """From `nmcli -t -f IN-USE,SIGNAL,SSID device wifi list`: the
    strongest signal per SSID, and the SSIDs in use. SSID is last in the
    field order so that only its own colons are escaped."""
    signal: dict[str, int] = {}
    inuse: set[str] = set()
    for line in terse.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        in_use, sig, ssid = parts
        ssid = unescape(ssid)
        if not ssid:
            continue
        try:
            strength = int(sig)
        except ValueError:
            continue
        if strength > signal.get(ssid, -1):
            signal[ssid] = strength
        if in_use == "*":
            inuse.add(ssid)
    return signal, inuse


def rows(saved: dict[str, str], signal: dict[str, int], inuse: set[str],
         all_: bool) -> list[str]:
    """The lines to print: in range first, strongest first; out of range
    last, with --all."""
    out = []
    for ssid, name in saved.items():
        if not all_ and ssid not in signal:
            continue
        sig = signal.get(ssid)
        suffix = "" if name == ssid else f"  ({name})"
        out.append((sig if sig is not None else -1,
                    f"{'' if sig is None else sig:>3} {'*' if ssid in inuse else ' '} {ssid}{suffix}"))
    out.sort(key=lambda t: -t[0])
    return [line for _, line in out]


def saved_networks(opts: Options) -> dict[str, str]:
    """SSID -> connection name, for every saved Wi-Fi connection."""
    listed = cmdline.run(opts, ["nmcli", "-t", "-f", "UUID,TYPE", "connection", "show"],
                         capture=True).stdout
    saved = {}
    for uuid in wireless_uuids(listed):
        ssid = cmdline.run(opts, ["nmcli", "-e", "no", "-g", "802-11-wireless.ssid",
                                  "connection", "show", uuid], capture=True).stdout.strip()
        if ssid:
            saved[ssid] = cmdline.run(opts, ["nmcli", "-e", "no", "-g", "connection.id",
                                             "connection", "show", uuid],
                                      capture=True).stdout.strip()
    return saved


@click.command(cls=cmdline.Command, help=__doc__,
               short_help="the saved Wi-Fi networks in range, strongest first")
@click.option("--all", "all_", is_flag=True, help="Every saved network, in range or not.")
@pass_options
def wifi(opts: Options, all_: bool) -> int:
    where.require_host("wifi")
    saved = saved_networks(opts)
    if not saved:
        raise cmdline.Error("no saved Wi-Fi networks")
    seen = cmdline.run(opts, ["nmcli", "-t", "-f", "IN-USE,SIGNAL,SSID", "device", "wifi", "list"],
                       capture=True).stdout
    signal, inuse = sightings(seen)
    for line in rows(saved, signal, inuse, all_):
        print(line)
    return 0
