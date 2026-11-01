import tempfile
import unittest
from pathlib import Path

from curiousj_framekit.frame import vr


class AaEstimate(unittest.TestCase):
    def test_ends_of_the_line(self):
        self.assertEqual(vr.aa_estimate(0.0), (1.13, 0))
        volts, nimh = vr.aa_estimate(1.0)
        self.assertAlmostEqual(volts, 1.48)
        self.assertEqual(nimh, 100)

    def test_middle_of_the_curve(self):
        level = (1.255 - 1.13) / (1.48 - 1.13)
        volts, nimh = vr.aa_estimate(level)
        self.assertAlmostEqual(volts, 1.255)
        self.assertEqual(nimh, 50)


def power_supply(root: Path, battery=True, charger=True):
    if battery:
        b = root / "max1720x_bat_7-36"
        b.mkdir()
        (b / "type").write_text("Battery\n")
        (b / "status").write_text("Not charging\n")
        (b / "capacity").write_text("98\n")
        (b / "voltage_now").write_text("8839218\n")
    if charger:
        c = root / "pm8550b-charger"
        c.mkdir()
        (c / "type").write_text("Unknown\n")
        (c / "status").write_text("Full\n")
        (c / "online").write_text("1\n")
        u = root / "tcpm-source-psy-c400000.spmi:pmic@7:typec@2b00"
        u.mkdir()
        (u / "type").write_text("USB\n")
        (u / "online").write_text("1\n")
        (u / "voltage_now").write_text("15000000\n")


class HeadsetPower(unittest.TestCase):
    def test_as_read_on_the_frame(self):
        with tempfile.TemporaryDirectory() as d:
            power_supply(Path(d))
            self.assertEqual(vr.headset_power(Path(d)), "98%, plugged in (15 V), not charging: full")

    def test_unplugged_discharging(self):
        with tempfile.TemporaryDirectory() as d:
            power_supply(Path(d), charger=False)
            (Path(d) / "max1720x_bat_7-36" / "status").write_text("Discharging\n")
            self.assertEqual(vr.headset_power(Path(d)), "98%, discharging")

    def test_no_battery(self):
        with tempfile.TemporaryDirectory() as d:
            power_supply(Path(d), battery=False)
            self.assertIsNone(vr.headset_power(Path(d)))
        self.assertIsNone(vr.headset_power(Path("/nonexistent")))


class Row(unittest.TestCase):
    def test_columns(self):
        self.assertEqual(vr.row("headset", "Steam Frame", "", "98%"),
                         "headset  Steam Frame                 98%")
        self.assertEqual(vr.row("left", "Roy_Left", "ABC", "on"),
                         "left     Roy_Left     ABC            on")
