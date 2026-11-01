import socket
import tempfile
import unittest
from pathlib import Path

from curiousj_framekit.frame import desktops


class Here(unittest.TestCase):
    def test_inside_each_desktop(self):
        home, run = Path("/home/x"), Path("/run/user/1000")
        self.assertEqual(desktops.here({"KDE_FULL_SESSION": "true",
                                        "XDG_RUNTIME_DIR": "/run/user/1000/frametop"}, home, run),
                         "frametop")
        self.assertEqual(desktops.here({"KDE_FULL_SESSION": "true",
                                        "XDG_RUNTIME_DIR": "/run/user/1000/nested_plasma/"}, home, run),
                         "stock")

    def test_not_a_kde_session_or_game_mode(self):
        home, run = Path("/home/x"), Path("/run/user/1000")
        self.assertIsNone(desktops.here({"XDG_RUNTIME_DIR": "/run/user/1000/frametop"}, home, run))
        self.assertIsNone(desktops.here({"KDE_FULL_SESSION": "true",
                                         "XDG_RUNTIME_DIR": "/run/user/1000"}, home, run))


class Running(unittest.TestCase):
    def test_socket_means_running(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "frametop").mkdir()
            (run / "nested_plasma").mkdir()
            s = socket.socket(socket.AF_UNIX)
            s.bind(str(run / "nested_plasma" / "wayland-0"))
            try:
                ds = desktops.desktops(Path("/home/x"), run)
                self.assertFalse(ds["frametop"].running())
                self.assertTrue(ds["stock"].running())
                self.assertEqual(desktops.running_names(Path("/home/x"), run), ["stock"])
            finally:
                s.close()

    def test_plain_file_is_not_a_socket(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "frametop").mkdir()
            (run / "frametop" / "wayland-0").write_text("")
            self.assertFalse(desktops.desktops(Path("/home/x"), run)["frametop"].running())
