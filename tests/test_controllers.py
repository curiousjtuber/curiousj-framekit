import unittest

from curiousj_framekit.frame import controllers

UEVENT = ("DRIVER=hid-generic\nHID_ID=0005:000028DE:00001303\nHID_NAME=Steam Controller\n"
          "HID_PHYS=aa:bb\nHID_UNIQ=11:22:33:44:55:66\nMODALIAS=hid:x\n")


class Parsing(unittest.TestCase):
    def test_valve_controller(self):
        c = controllers.controller_from("/sys/class/hidraw/hidraw3/device/uevent", UEVENT)
        self.assertEqual(c.dev, "/dev/hidraw3")
        self.assertEqual(c.name, "Steam Controller")
        self.assertEqual(c.bus, controllers.BUS_BLUETOOTH)
        self.assertEqual(c.address, "11:22:33:44:55:66")
        self.assertEqual(c.link, "bluetooth")

    def test_other_vendor_is_skipped(self):
        other = UEVENT.replace("000028DE", "0000046D")
        self.assertIsNone(controllers.controller_from("/sys/class/hidraw/hidraw1/device/uevent", other))

    def test_battery_line(self):
        info = "Device 11:22\n\tName: Steam Controller\n\tBattery Percentage: 0x54 (84)\n"
        self.assertEqual(controllers.battery_from(info), "battery 84%")
        self.assertEqual(controllers.battery_from("Device 11:22\n"), "")

    def test_ioctl_number(self):
        self.assertEqual(controllers.hidiocsfeature(64), (3 << 30) | (64 << 16) | (ord("H") << 8) | 6)
