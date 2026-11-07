import unittest
from pathlib import Path

from curiousj_framekit import cmdline
from curiousj_framekit.frame import panel


class Sizes(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(panel.parse_size("3840x1080"), (3840, 1080))
        self.assertEqual(panel.parse_size(" 2560 X 1440 "), (2560, 1440))
        for bad in ("1920", "0x1080", "wide", "1920x"):
            with self.assertRaises(cmdline.Error):
                panel.parse_size(bad)

    def test_default_width_keeps_the_panel_a_metre_and_a_half_tall(self):
        self.assertEqual(panel.default_width(1920, 1080), 2.67)
        self.assertEqual(panel.default_width(3840, 1080), 5.33)
        self.assertEqual(panel.default_width(1080, 1920), 0.84)


class Units(unittest.TestCase):
    def test_unit_name_is_safe_and_idempotent(self):
        self.assertEqual(panel.unit_name("krdc"), "cjf-panel-krdc")
        self.assertEqual(panel.unit_name("my pc/two screens"), "cjf-panel-my-pc-two-screens")
        self.assertEqual(panel.unit_name(panel.panel_name(panel.unit_name("a b"))), panel.unit_name("a b"))
        self.assertEqual(panel.unit_name("///"), "cjf-panel-panel")

    def test_parse_units(self):
        text = ("cjf-panel-krdc.service loaded active running cjf panel krdc\n"
                "cjf-panel-moonlight.service loaded inactive dead cjf panel moonlight\n"
                "other.service loaded active running something else\n")
        self.assertEqual(panel.parse_units(text), [("krdc", "running"), ("moonlight", "dead")])
        self.assertEqual(panel.parse_units(""), [])


class Argv(unittest.TestCase):
    def test_gamescope_argv(self):
        argv = panel.gamescope_argv(Path("/home/u/.local/lib/gamescope-panel/bin/gamescope"), (3840, 1080), 5.33,
                                    "krdc", True, False, ["/home/u/.local/bin/krdc", "--fullscreen", "rdp://pc"])
        self.assertEqual(argv[:3], ["/home/u/.local/lib/gamescope-panel/bin/gamescope", "--backend", "openvr"])
        for flag, value in (("-W", "3840"), ("-H", "1080"), ("-w", "3840"), ("-h", "1080"),
                            ("--vr-overlay-key", "cjf.panel.krdc"), ("--vr-overlay-physical-width", "5.33")):
            self.assertEqual(argv[argv.index(flag) + 1], value, flag)
        self.assertIn("--force-windows-fullscreen", argv)
        self.assertNotIn("--expose-wayland", argv)
        self.assertEqual(argv[argv.index("--"):], ["--", "/home/u/.local/bin/krdc", "--fullscreen", "rdp://pc"])

    def test_wayland_and_no_fullscreen(self):
        argv = panel.gamescope_argv(Path("g"), (1920, 1080), 2.67, "app", False, True, ["app"])
        self.assertIn("--expose-wayland", argv)
        self.assertNotIn("--force-windows-fullscreen", argv)

    def test_environment(self):
        self.assertEqual(panel.environment(False, []), {"QT_QPA_PLATFORM": "xcb", "XCURSOR_SIZE": "32"})
        self.assertEqual(panel.environment(True, ["XCURSOR_SIZE=64", "FOO=a=b"]),
                         {"XCURSOR_SIZE": "64", "FOO": "a=b"})
        with self.assertRaises(cmdline.Error):
            panel.environment(False, ["NOVALUE"])

    def test_run_argv(self):
        argv = panel.run_argv("cjf-panel-krdc", {"QT_QPA_PLATFORM": "xcb"}, ["gamescope", "--", "krdc"])
        self.assertEqual(argv[:6], ["systemd-run", "--user", "--collect", "--quiet", "--unit", "cjf-panel-krdc"])
        self.assertIn("--setenv=QT_QPA_PLATFORM=xcb", argv)
        self.assertEqual(argv[argv.index("--"):], ["--", "gamescope", "--", "krdc"])
        self.assertEqual(argv[argv.index("--description") + 1], "cjf panel krdc")
        self.assertEqual(argv[argv.index("--property") + 1], "TimeoutStopSec=3")

    def test_the_app_is_wrapped_so_that_its_exit_ends_the_unit(self):
        argv = panel.wrapped("cjf-panel-krdc", ["/home/u/.local/bin/krdc", "--fullscreen", "rdp://pc"])
        self.assertEqual(argv[:2], ["/bin/sh", "-c"])
        self.assertIn('"$@"; systemctl --user stop --no-block "$0"', argv[2])
        self.assertEqual(argv[3:], ["cjf-panel-krdc.service", "/home/u/.local/bin/krdc", "--fullscreen", "rdp://pc"])
