"""bsmanager -- BSManager on the Frame, in a window on a Linux PC's
Wayland desktop, through waypipe. Run it on the Frame inside a `waypipe
ssh` session opened from the PC; in the headset, start BSManager from
Steam instead.

    bsmanager [--no-gpu] [-- BSMANAGER-ARGS...]

From the PC, the session and the command in one line:

    waypipe --remote-bin /home/steamos/.local/bin/waypipe ssh steamos@frame.local bsmanager

--no-gpu turns off BSManager's GPU rendering, for a blank or crashing
window; pass waypipe -n on the PC as well, so the window travels as
plain pixels instead of GPU buffers. The Frame needs waypipe (`cjf
install waypipe`) and BSManager (`cjf install bsmanager`), which brings
fuse2, the libfuse.so.2 the AppImage's runtime loads and SteamOS 0.5.7
dropped; it runs the AppImage with that library's directory on
LD_LIBRARY_PATH, as BSManager's menu entry does.

BSManager allows one instance: a second hands off to the first and
exits, with no new window, so this refuses while one runs. Its Electron
picks X11 by default, and a waypipe session has only Wayland, so it is
started with --ozone-platform=wayland.
"""

from __future__ import annotations

import os
import subprocess
import sys

import click

from .. import cmdline, where
from ..cmdline import Options, pass_options

APPIMAGE = "/home/steamos/Applications/BSManager.AppImage"
RUNNING = r"^/tmp/[.]mount_BSMan[^/]*/bs-manager"


def is_running(opts: Options) -> bool:
    return cmdline.run(opts, ["pgrep", "-f", RUNNING], check=False, capture=True).returncode == 0


@click.command(cls=cmdline.Command, help=__doc__,
               context_settings={"ignore_unknown_options": True})
@click.option("-n", "--no-gpu", is_flag=True, help="No GPU rendering, for a blank or crashing window.")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@pass_options
def cli(opts: Options, no_gpu: bool, args: tuple[str, ...]) -> int:
    if where.in_container():
        # AppImages mount themselves with FUSE, which a distrobox may
        # lack, so hand over to the host; distrobox-host-exec drops
        # WAYLAND_DISPLAY, which points at the waypipe session, so it is
        # passed along.
        display = os.environ.get("WAYLAND_DISPLAY", "")
        argv = ["distrobox-host-exec", "env", f"WAYLAND_DISPLAY={display}", "bsmanager"]
        argv += ["--no-gpu"] if no_gpu else []
        argv += ["--", *args] if args else []
        os.execvp(argv[0], argv)
    where.require_host("bsmanager")
    if not os.environ.get("WAYLAND_DISPLAY"):
        raise cmdline.Error("WAYLAND_DISPLAY is not set; run it in a waypipe ssh session from "
                            "the PC: waypipe --remote-bin /home/steamos/.local/bin/waypipe "
                            "ssh steamos@frame.local bsmanager")
    from ..install import catalog
    from ..install.kinds import upstream
    if not os.access(APPIMAGE, os.X_OK):
        catalog.needs("bsmanager", "bsmanager", opts)
    if not (upstream.FUSE2_LIB / "libfuse.so.2").exists():
        catalog.needs("fuse2", "bsmanager", opts)
    if is_running(opts):
        raise cmdline.Error("BSManager is already running, in the window it was started in; "
                            "quit it first")
    argv = [APPIMAGE, "--ozone-platform=wayland", "--no-sandbox"]
    if no_gpu:
        argv.append("--disable-gpu")
    argv += list(args)
    cmdline.log(opts, "+ " + " ".join(argv))
    os.execve(APPIMAGE, argv, upstream.appimage_env())


def main(argv: list[str] | None = None) -> int:
    return cmdline.run_main(cli, argv, "bsmanager")


if __name__ == "__main__":
    sys.exit(main())
