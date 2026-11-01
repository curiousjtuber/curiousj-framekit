"""cjf controllers -- the Steam Controllers paired to the Frame over
Bluetooth: list the ones that are on, or turn them off from a shell, as
holding the Steam button does.

    cjf controllers
    cjf controllers off [NAME]

With no argument it lists each Steam Controller that is on, with its
battery when BlueZ reports it. `off` turns them all off, or only the
one whose name (as listed, or any part of it) is NAME. A press of the
Steam button turns one back on. This is Valve's own HID command, 0x9f
"off!", the one Steam itself sends; the kernel's hid-steam driver
doesn't take this controller (28de:1303) yet, so it is sent straight to
the hidraw node, which SteamOS lets the user write.

Checked on the Steam Controller over Bluetooth; a wired one, or the old
one through its dongle, takes the same command on feature report 0 and
is tried that way, untested.
"""

from __future__ import annotations

import fcntl
import glob
import os
import time
from dataclasses import dataclass

import click

from .. import cmdline, where
from ..cmdline import Options, pass_options

VALVE = 0x28DE
BUS_USB, BUS_BLUETOOTH = 0x03, 0x05
TURN_OFF = bytes([0x9F, 0x04]) + b"off!"      # ID_TURN_OFF_CONTROLLER, length, magic
REPORT_SIZE = 64                               # one feature report, ID byte included


@dataclass
class Controller:
    dev: str        # /dev/hidrawN
    name: str
    bus: int
    address: str    # the Bluetooth address, for BlueZ

    @property
    def link(self) -> str:
        return "bluetooth" if self.bus == BUS_BLUETOOTH else "usb"


def parse_uevent(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def controller_from(uevent_path: str, text: str) -> Controller | None:
    """The controller a hidraw uevent describes, if it is Valve's."""
    fields = parse_uevent(text)
    try:
        bus, vendor, _ = (int(x, 16) for x in fields.get("HID_ID", "0:0:0").split(":"))
    except ValueError:
        return None
    if vendor != VALVE:
        return None
    node = uevent_path.split("/")[4] if uevent_path.count("/") >= 4 else "?"
    return Controller("/dev/" + node, fields.get("HID_NAME", "?"), bus, fields.get("HID_UNIQ", ""))


def controllers() -> list[Controller]:
    found = []
    for uevent in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
        try:
            with open(uevent) as f:
                text = f.read()
        except OSError:
            continue
        c = controller_from(uevent, text)
        if c:
            found.append(c)
    return found


def battery_from(bluetoothctl_info: str) -> str:
    """`battery NN%` from `bluetoothctl info`'s output, or ""."""
    for line in bluetoothctl_info.splitlines():
        if line.strip().startswith("Battery Percentage:"):
            return "battery " + line.rsplit("(", 1)[-1].rstrip(")") + "%"
    return ""


def battery(opts: Options, ctrl: Controller) -> str:
    if ctrl.bus != BUS_BLUETOOTH or not ctrl.address:
        return ""
    info = cmdline.output(opts, ["bluetoothctl", "info", ctrl.address], default="")
    return battery_from(info or "")


def hidiocsfeature(size: int) -> int:
    # _IOC(_IOC_READ | _IOC_WRITE, 'H', 0x06, size), as linux/hidraw.h has it
    return (3 << 30) | (size << 16) | (ord("H") << 8) | 0x06


def turn_off(ctrl: Controller) -> bool:
    """Send the power-off report; True when the node went away."""
    # Over Bluetooth the controller's vendor commands go on feature
    # report 1; over USB on report 0, as hid-steam sends them.
    report_id = 1 if ctrl.bus == BUS_BLUETOOTH else 0
    buf = bytes([report_id]) + TURN_OFF
    buf += bytes(REPORT_SIZE - len(buf))
    try:
        fd = os.open(ctrl.dev, os.O_RDWR)
    except PermissionError:
        raise cmdline.Error(f"{ctrl.dev} isn't writable; is this the Frame's own user?") from None
    except OSError as e:
        raise cmdline.Error(f"{ctrl.dev}: {e.strerror}") from None
    try:
        fcntl.ioctl(fd, hidiocsfeature(len(buf)), buf)
    except OSError as e:
        raise cmdline.Error(f"{ctrl.name}: sending the command failed: {e.strerror}") from None
    finally:
        os.close(fd)
    deadline = time.monotonic() + 3
    while os.path.exists(ctrl.dev) and time.monotonic() < deadline:
        time.sleep(0.1)
    return not os.path.exists(ctrl.dev)


@click.command(cls=cmdline.Command, help=__doc__,
               short_help="the Steam Controllers paired over Bluetooth: list, or turn off")
@click.argument("action", required=False, type=click.Choice(["off"]))
@click.argument("name", required=False)
@pass_options
def controllers_cmd(opts: Options, action: str | None, name: str | None) -> int:
    where.require_host("controllers")
    if name and not action:
        raise click.UsageError("NAME goes with off")
    found = controllers()
    if not action:
        if not found:
            print("no Steam Controller is on")
            return 0
        for c in found:
            print(f"{c.name:<32} {c.link:<10} {battery(opts, c)}".rstrip())
        return 0
    if name:
        found = [c for c in found if name.lower() in c.name.lower()]
        if not found:
            raise cmdline.Error(f"no Steam Controller named {name} is on")
    elif not found:
        print("no Steam Controller is on")
        return 0
    failed = False
    for c in found:
        if turn_off(c):
            print(f"{c.name}: off")
        else:
            print(f"{c.name}: still on")
            failed = True
    return 1 if failed else 0
