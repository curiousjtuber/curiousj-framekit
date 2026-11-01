import unittest
from pathlib import Path

from curiousj_framekit import cmdline, where

FRAME = {"NAME": "SteamOS", "ID": "steamos", "ID_LIKE": "arch", "VARIANT_ID": "vr",
         "VERSION_ID": "0.5.6", "BUILD_ID": "20261022.6153909", "PRETTY_NAME": "SteamOS"}
DECK = dict(FRAME, VARIANT_ID="steamdeck")
CACHY = {"NAME": "CachyOS Linux", "ID": "cachyos", "PRETTY_NAME": "CachyOS Linux"}
NOWHERE = Path("/nonexistent/containerenv")


class OsRelease(unittest.TestCase):
    def test_parses_quotes_blanks_and_comments(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix="os-release", delete=False) as f:
            f.write('NAME="SteamOS"\n\n# a comment\nID=steamos\nVARIANT_ID="vr"\n'
                    "ANSI_COLOR=\"1;35\"\nBROKEN LINE\n")
        info = where.os_release(Path(f.name))
        self.assertEqual(info["NAME"], "SteamOS")
        self.assertEqual(info["ID"], "steamos")
        self.assertEqual(info["VARIANT_ID"], "vr")
        self.assertEqual(info["ANSI_COLOR"], "1;35")
        self.assertNotIn("BROKEN LINE", info)

    def test_missing_file_is_empty(self):
        self.assertEqual(where.os_release(Path("/nonexistent/os-release")), {})


class IsFrame(unittest.TestCase):
    def test_frame_deck_pc(self):
        self.assertTrue(where.is_frame(FRAME, {}))
        self.assertFalse(where.is_frame(DECK, {}))
        self.assertFalse(where.is_frame(CACHY, {}))
        self.assertFalse(where.is_frame({}, {}))

    def test_override_for_ci(self):
        self.assertTrue(where.is_frame(CACHY, {"CJF_ASSUME_FRAME": "1"}))
        self.assertFalse(where.is_frame(CACHY, {"CJF_ASSUME_FRAME": "0"}))


class Session(unittest.TestCase):
    def test_container(self):
        self.assertTrue(where.in_container({"CONTAINER_ID": "arch"}, NOWHERE))
        self.assertFalse(where.in_container({}, NOWHERE))
        self.assertFalse(where.in_container({"CONTAINER_ID": ""}, NOWHERE))

    def test_desktop_from_runtime_dir(self):
        self.assertEqual(where.desktop({"XDG_RUNTIME_DIR": "/run/user/1000/nested_plasma"}), "stock")
        self.assertEqual(where.desktop({"XDG_RUNTIME_DIR": "/run/user/1000/frametop/"}), "frametop")
        self.assertIsNone(where.desktop({"XDG_RUNTIME_DIR": "/run/user/1000"}))
        self.assertIsNone(where.desktop({}))

    def test_wayland_display(self):
        self.assertEqual(where.wayland_display({"WAYLAND_DISPLAY": "wayland-0"}), "wayland-0")
        self.assertEqual(where.wayland_display({"WAYLAND_DISPLAY": "",
                                                "GAMESCOPE_WAYLAND_DISPLAY": "gamescope-0"}),
                         "gamescope-0")
        self.assertIsNone(where.wayland_display({}))


class Describe(unittest.TestCase):
    def test_phrases(self):
        self.assertEqual(where.describe(FRAME, {}), "the Frame's host")
        self.assertEqual(where.describe(FRAME, {"XDG_RUNTIME_DIR": "/run/user/1000/nested_plasma"}),
                         "the Frame's host, in Desktop Mode")
        self.assertEqual(where.describe(FRAME, {"XDG_RUNTIME_DIR": "/run/user/1000/frametop"}),
                         "the Frame's host, in Frametop's desktop")
        self.assertEqual(where.describe(CACHY, {}), "a PC (CachyOS Linux)")

    def test_in_a_box(self):
        with unittest.mock.patch.object(where, "CONTAINER_MARK", NOWHERE):
            self.assertEqual(where.describe(FRAME, {"CONTAINER_ID": "arch"}), "a container")


class Requirements(unittest.TestCase):
    def test_require_frame_names_where_we_are(self):
        with unittest.mock.patch.object(where, "os_release", return_value=CACHY):
            with self.assertRaises(cmdline.Error) as cm:
                where.require_frame("status")
            self.assertEqual(str(cm.exception), "status runs on the Frame; this is a PC (CachyOS Linux)")

    def test_require_host_refuses_a_box_and_names_the_way_through(self):
        with unittest.mock.patch.object(where, "os_release", return_value=CACHY), \
             unittest.mock.patch.dict("os.environ", {"CONTAINER_ID": "arch"}):
            with self.assertRaises(cmdline.Error) as cm:
                where.require_host("status")
            self.assertEqual(str(cm.exception),
                             "status runs on the Frame's host, not in a container; "
                             "from a distrobox: distrobox-host-exec cjf status")

    def test_require_pc(self):
        with unittest.mock.patch.object(where, "os_release", return_value=FRAME), \
             unittest.mock.patch.dict("os.environ", {}, clear=False):
            with self.assertRaises(cmdline.Error):
                where.require_pc()


import unittest.mock  # noqa: E402  (used above through unittest.mock)
