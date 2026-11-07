"""cjf vr -- the headset and the Frame's VR controllers from a shell:
their batteries, or the controllers turned off as the SteamVR
dashboard's power menu does, without putting the headset on.

    cjf vr
    cjf vr off [left|right]

With no argument it lists the headset, with its battery and whether it
is plugged in, read from the kernel (so it shows with or without
SteamVR), then SteamVR's controllers: hand, model, serial, whether each
is on, and its battery. `off` turns off every controller that is on, or
only the hand named; a button turns it back on. The headset is never
touched. For the controllers SteamVR has to be running, as it is in
Game Mode.

The Frame's controllers run on one AA each, and their firmware reports
a percentage made for alkaline cells, which reads a full NiMH cell as
about 79%. So beside it the list gives the cell's voltage under load
worked back from that percentage, and the charge a NiMH cell has left at
that voltage. Both are estimates fitted to one pair of NiMH cells read
with a multimeter while the controllers ran (docs/notes/aa-voltage.csv,
with the fit in aa-voltage-fit.py); SteamVR never reports a voltage.

SteamVR has no public call for turning a controller off. The
dashboard's "Turn off controller" goes through the private
IVRControlPanel_006 interface, whose PowerOffTrackedDevice is the 13th
method (slot 12). That layout is read off the Android build SteamVR
ships beside the Linux one, which keeps its symbols: CHmdSystemLatest's
vtable in /opt/steamvr/bin/androidarm64/vrclient.so. A SteamVR update
that renames the interface makes this refuse rather than call the wrong
slot.
"""

from __future__ import annotations

import ctypes as C
import json
import os
import time
from pathlib import Path

import click

from .. import cmdline, where
from ..cmdline import Options, pass_options

POWER_OFF_SLOT = 12            # IVRControlPanel_006::PowerOffTrackedDevice(uint32_t)

MAX_DEVICES = 64               # k_unMaxTrackedDeviceCount
CLASS_CONTROLLER = 2           # ETrackedDeviceClass
ROLES = {1: "left", 2: "right"}    # ETrackedControllerRole: LeftHand, RightHand
PROP_MODEL = 1001              # Prop_ModelNumber_String
PROP_SERIAL = 1002             # Prop_SerialNumber_String
PROP_CHARGING = 1011           # Prop_DeviceIsCharging_Bool
PROP_BATTERY = 1012            # Prop_DeviceBatteryPercentage_Float
PROP_HAS_BATTERY = 1026        # Prop_DeviceProvidesBatteryStatus_Bool
FRAME_MODEL = "roy_"           # Roy_Left, Roy_Right: the Frame's AA controllers

# The firmware's percentage is linear in the cell's voltage under load,
# the voltage a meter reads on the running controller: 0% at 1.09 V and
# 100% at 1.48 V, a line fitted to 76 readings between 10% and 61%
# (3.6 mV rms, 18 mV at worst), so above 61% it is extrapolated. The
# voltage after a rest runs 15 to 50 mV higher, more so as the cell
# empties.
AA_EMPTY_V, AA_FULL_V = 1.09, 1.48
# A NiMH cell's charge against that voltage under load, from one pair of
# cells played from fresh off the charger (79%, 1.40 V) to one of them
# at 10% (1.13 V), charge taken as the play time left: about 21 hours
# in all. Half the sessions were timed, the rest assumed at 40 minutes,
# so the middle is good to seven points or so, and the estimate is
# rounded to 5. The bottom, below where the cells went, follows a fresh
# Eneloop's 0.1 A curve down to its 1.0 V cutoff (the curve is in
# docs/notes/eneloop-0.1A.csv); the rest of that curve does not fit
# these cells, which slope through the middle where a fresh cell stays
# flat.
NIMH_CURVE = [(1.00, 0), (1.10, 2), (1.13, 5), (1.15, 9), (1.17, 18), (1.19, 28), (1.21, 34),
              (1.23, 42), (1.25, 53), (1.27, 64), (1.29, 75), (1.32, 85), (1.36, 95), (1.40, 100)]
APP_BACKGROUND = 3            # VRApplication_Background: fails unless SteamVR already runs
ERR_NO_SERVER = 121            # VRInitError_Init_NoServerForBackgroundApp

POWER_SUPPLY = Path("/sys/class/power_supply")


# --- the headset, from the kernel -----------------------------------------

def read_attr(dev: Path, name: str) -> str | None:
    try:
        return (dev / name).read_text().strip()
    except OSError:
        return None


def headset_power(root: Path = POWER_SUPPLY) -> str | None:
    """One phrase: `98%, plugged in (15 V), not charging: full`; None when
    the kernel shows no battery (a PC, say)."""
    battery = None
    plugged = []
    try:
        devices = sorted(root.iterdir())
    except OSError:
        return None
    for dev in devices:
        kind = read_attr(dev, "type")
        if kind == "Battery" and battery is None:
            battery = dev
        elif read_attr(dev, "online") == "1" and kind != "Battery":
            volts = read_attr(dev, "voltage_now")
            if volts and volts.isdigit() and int(volts) > 0:
                plugged.append(f"{int(volts) / 1_000_000:g} V")
            else:
                plugged.append("")
    if battery is None:
        return None
    capacity = read_attr(battery, "capacity")
    status = (read_attr(battery, "status") or "").lower()
    parts = [f"{capacity}%" if capacity else "battery ?"]
    if plugged:
        detail = next((p for p in plugged if p), "")
        parts.append(f"plugged in ({detail})" if detail else "plugged in")
    if status == "full" or (status == "not charging" and plugged):
        parts.append("not charging: full" if status == "not charging" else "full")
    elif status:
        parts.append(status)
    return ", ".join(parts)


# --- the controllers, through SteamVR -------------------------------------

def runtime_dir() -> str:
    # Where SteamVR runs from, as `steamvr path` would say; vrpathreg
    # keeps it here.
    path = os.path.expanduser("~/.config/openvr/openvrpaths.vrpath")
    try:
        with open(path) as f:
            return json.load(f)["runtime"][0]
    except (OSError, KeyError, IndexError, ValueError):
        return "/opt/steamvr"


class NotRunning(cmdline.Error):
    """SteamVR isn't running."""


class OpenVR:
    def __init__(self):
        lib = os.path.join(runtime_dir(), "bin/linuxarm64/libopenvr_api.so")
        try:
            self.api = api = C.CDLL(lib)
        except OSError:
            raise cmdline.Error(f"{lib} not found: is SteamVR installed?") from None
        api.VR_InitInternal2.restype = C.c_void_p
        api.VR_InitInternal2.argtypes = [C.POINTER(C.c_int), C.c_int, C.c_char_p]
        api.VR_GetGenericInterface.restype = C.c_void_p
        api.VR_GetGenericInterface.argtypes = [C.c_char_p, C.POINTER(C.c_int)]
        api.VR_IsInterfaceVersionValid.restype = C.c_bool
        api.VR_IsInterfaceVersionValid.argtypes = [C.c_char_p]
        api.VR_GetVRInitErrorAsEnglishDescription.restype = C.c_char_p
        api.VR_GetVRInitErrorAsEnglishDescription.argtypes = [C.c_int]

        err = C.c_int(0)
        api.VR_InitInternal2(C.byref(err), APP_BACKGROUND, b"")
        if err.value == ERR_NO_SERVER:
            raise NotRunning("SteamVR isn't running")
        if err.value:
            why = api.VR_GetVRInitErrorAsEnglishDescription(err.value).decode()
            raise cmdline.Error(f"SteamVR refused: {why}")

        # IVRSystem through its C function table, in openvr_capi.h's order.
        for version in (b"IVRSystem_026", b"IVRControlPanel_006"):
            if not api.VR_IsInterfaceVersionValid(version):
                raise cmdline.Error(f"this SteamVR has no {version.decode()}; "
                                    "the tool needs updating for it")
        table = api.VR_GetGenericInterface(b"FnTable:IVRSystem_026", C.byref(err))
        if err.value or not table:
            raise cmdline.Error("SteamVR gave no IVRSystem")
        fns = C.cast(table, C.POINTER(C.c_void_p * 64)).contents

        def fn(slot, restype, *argtypes):
            return C.CFUNCTYPE(restype, *argtypes)(fns[slot])
        self.role = fn(19, C.c_int, C.c_uint32)
        self.device_class = fn(20, C.c_int, C.c_uint32)
        self.connected = fn(21, C.c_bool, C.c_uint32)
        self._bool = fn(22, C.c_bool, C.c_uint32, C.c_int, C.POINTER(C.c_int))
        self._float = fn(23, C.c_float, C.c_uint32, C.c_int, C.POINTER(C.c_int))
        self._string = fn(28, C.c_uint32, C.c_uint32, C.c_int, C.c_char_p, C.c_uint32,
                          C.POINTER(C.c_int))

        # IVRControlPanel is a C++ interface: a pointer to an object whose
        # first word is its vtable.
        panel = api.VR_GetGenericInterface(b"IVRControlPanel_006", C.byref(err))
        if err.value or not panel:
            raise cmdline.Error("SteamVR gave no IVRControlPanel")
        vtable = C.cast(C.c_void_p(panel), C.POINTER(C.POINTER(C.c_void_p * 32))).contents.contents
        self._panel = panel
        self._power_off = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32)(vtable[POWER_OFF_SLOT])

    def close(self):
        self.api.VR_ShutdownInternal()

    def string(self, index, prop):
        buf = C.create_string_buffer(256)
        err = C.c_int(0)
        self._string(index, prop, buf, len(buf), C.byref(err))
        return "" if err.value else buf.value.decode(errors="replace")

    def boolean(self, index, prop):
        err = C.c_int(0)
        value = self._bool(index, prop, C.byref(err))
        return None if err.value else value

    def battery(self, index):
        err = C.c_int(0)
        value = self._float(index, PROP_BATTERY, C.byref(err))
        return None if err.value else value

    def power_off(self, index):
        self._power_off(self._panel, index)

    def controllers(self):
        return [i for i in range(MAX_DEVICES) if self.device_class(i) == CLASS_CONTROLLER]


def describe(vr, index):
    model = vr.string(index, PROP_MODEL) or "?"
    serial = vr.string(index, PROP_SERIAL) or "?"
    # SteamVR forgets a controller's hand the moment it is off; the
    # Frame's controllers carry it in the model name (Roy_Left, Roy_Right).
    hand = ROLES.get(vr.role(index))
    if hand is None:
        hand = next((h for h in ROLES.values() if model.lower().endswith("_" + h)), "-")
    return hand, model, serial


def aa_estimate(level: float) -> tuple[float, int]:
    """The AA's voltage under load from the firmware's 0-1 level, and the
    NiMH charge left at that voltage, to the nearest 5%."""
    volts = AA_EMPTY_V + level * (AA_FULL_V - AA_EMPTY_V)
    if volts <= NIMH_CURVE[0][0]:
        return volts, 0
    for (v0, p0), (v1, p1) in zip(NIMH_CURVE, NIMH_CURVE[1:]):
        if volts <= v1:
            return volts, 5 * round((p0 + (volts - v0) / (v1 - v0) * (p1 - p0)) / 5)
    return volts, 100


def controller_state(vr, index) -> str:
    if not vr.connected(index):
        return "off"
    state = "on"
    model = vr.string(index, PROP_MODEL)
    if vr.boolean(index, PROP_HAS_BATTERY) and (level := vr.battery(index)) is not None:
        state += f", battery {round(level * 100)}%"
        if model.lower().startswith(FRAME_MODEL):
            volts, nimh = aa_estimate(level)
            state += f" (~{volts:.2f} V, NiMH ~{nimh}%)"
        if vr.boolean(index, PROP_CHARGING):
            state += " charging"
    return state


def row(hand: str, model: str, serial: str, state: str) -> str:
    return f"{hand:<8} {model:<12} {serial:<14} {state}"


def list_devices(vr) -> None:
    found = vr.controllers()
    if not found:
        print("no controllers known to SteamVR")
        return
    for i in found:
        hand, model, serial = describe(vr, i)
        print(row(hand, model, serial, controller_state(vr, i)))


def turn_off(vr, hand: str | None) -> int:
    targets = [i for i in vr.controllers()
               if vr.connected(i) and (hand is None or ROLES.get(vr.role(i)) == hand)]
    if not targets:
        if hand:
            raise cmdline.Error(f"the {hand} controller isn't on")
        print("no controller is on")
        return 0
    names = {i: describe(vr, i) for i in targets}
    for i in targets:
        vr.power_off(i)
    failed = False
    for i in targets:
        deadline = time.monotonic() + 3
        while vr.connected(i) and time.monotonic() < deadline:
            time.sleep(0.1)
        hand, model, serial = names[i]
        if vr.connected(i):
            print(f"{hand} {model} {serial}: still on")
            failed = True
        else:
            print(f"{hand} {model} {serial}: off")
    return 1 if failed else 0


@click.command(cls=cmdline.Command, help=__doc__,
               short_help="the headset and VR controllers: battery, or turn controllers off",
               menu=[cmdline.Entry("status", (), "the headset's battery, then each controller's"),
                     cmdline.Entry("off", ("off",), "turn off every controller that is on"),
                     cmdline.Entry("off left", ("off", "left"), "turn off the left controller"),
                     cmdline.Entry("off right", ("off", "right"), "turn off the right controller")])
@click.argument("action", required=False, type=click.Choice(["off"]))
@click.argument("hand", required=False, type=click.Choice(["left", "right"]))
@pass_options
def vr_cmd(opts: Options, action: str | None, hand: str | None) -> int:
    where.require_host("vr")
    if hand and not action:
        raise click.UsageError("left or right goes with off")
    if not action:
        power = headset_power()
        print(row("headset", "Steam Frame", "", power or "no battery seen by the kernel"))
        try:
            vr = OpenVR()
        except NotRunning:
            print("controllers: SteamVR isn't running")
            return 0
        try:
            list_devices(vr)
        finally:
            vr.close()
        return 0
    vr = OpenVR()
    try:
        return turn_off(vr, hand)
    finally:
        vr.close()
