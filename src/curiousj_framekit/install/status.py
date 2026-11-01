"""cjf status -- what this Frame runs: the versions of SteamOS, SteamVR
and the Steam client, as Valve's patch notes number them, with each
one's build and update channel.

    cjf status

Runs on the Frame's host; a distrobox sees its own /etc/os-release, so
from one run `distrobox-host-exec cjf status`. More rows come as the
catalog does.
"""

from __future__ import annotations

import click

from .. import cmdline, where
from ..cmdline import Options, pass_options
from ..frame import versions


@click.command(cls=cmdline.Command, help=__doc__,
               short_help="the versions of SteamOS, SteamVR and the Steam client")
@pass_options
def status(opts: Options) -> int:
    where.require_host("status")
    print(versions.format_rows(versions.rows(opts, where.os_release())))
    return 0
