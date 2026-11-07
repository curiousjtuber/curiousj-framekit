import os
import tempfile
import unittest
from pathlib import Path

from curiousj_framekit.frame import rdp


class Parsing(unittest.TestCase):
    def test_flatpak_ps(self):
        text = ("Application                     Child PID\n"
                "org.kde.krdc                    1234\n"
                "io.github.curiousjtuber.Krdp    41023\n")
        self.assertEqual(rdp.parse_ps(text), "41023")
        self.assertIsNone(rdp.parse_ps("Application  Child PID\n"))

    def test_info(self):
        self.assertEqual(rdp.parse_info("desktop=/run/user/1000/frametop\nport=3391\n"),
                         {"desktop": "/run/user/1000/frametop", "port": "3391"})
        self.assertEqual(rdp.parse_info("server=home\npid=4242\n"), {"server": "home", "pid": "4242"})


class HomeServer(unittest.TestCase):
    """The ~/.local server is running when the pid start recorded still
    runs the package's binary, read from /proc."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proc = Path(self.tmp.name)
        self.binary = Path("/home/steamos/.local/lib/krdpserver/bin/krdpserver")

    def tearDown(self):
        self.tmp.cleanup()

    def cmdline(self, pid: str, argv: list[str]) -> None:
        (self.proc / pid).mkdir()
        (self.proc / pid / "cmdline").write_bytes(b"\0".join(os.fsencode(a) for a in argv) + b"\0")

    def test_the_recorded_pid_runs_the_binary(self):
        self.cmdline("4242", [str(self.binary), "--plasma", "--port", "3391"])
        info = {"server": "home", "pid": "4242"}
        self.assertEqual(rdp.home_pid(info, self.proc, self.binary), "4242")

    def test_gone_or_reused_pid(self):
        info = {"server": "home", "pid": "4242"}
        self.assertIsNone(rdp.home_pid(info, self.proc, self.binary))
        self.cmdline("4242", ["/usr/bin/sleep", "60"])
        self.assertIsNone(rdp.home_pid(info, self.proc, self.binary))

    def test_the_flatpak_is_not_this(self):
        self.cmdline("4242", [str(self.binary)])
        self.assertIsNone(rdp.home_pid({"server": "flatpak", "pid": "4242"}, self.proc, self.binary))
        self.assertIsNone(rdp.home_pid({"server": "home"}, self.proc, self.binary))

    def test_labels(self):
        self.assertEqual(rdp.server_label("home"), "the ~/.local build")
        self.assertEqual(rdp.server_label("flatpak"), "the flatpak")

    def test_desktop_label(self):
        self.assertEqual(rdp.desktop_label("/run/user/1000/nested_plasma"), "the stock desktop")
        self.assertEqual(rdp.desktop_label("/run/user/1000/frametop/"), "Frametop")
        self.assertEqual(rdp.desktop_label("/tmp/other"), "other")


class Addresses(unittest.TestCase):
    def test_every_address(self):
        self.assertEqual(rdp.addresses("3391", "0.0.0.0", "frame", "192.168.1.5", "100.84.3.21"),
                         "frame.local:3391  192.168.1.5:3391  100.84.3.21:3391 (tailnet)")
        self.assertEqual(rdp.addresses("3391", "", "frame", "", ""), "frame.local:3391")

    def test_one_address(self):
        self.assertEqual(rdp.addresses("3391", "100.84.3.21", "frame", "x", "y"), "100.84.3.21:3391")


class Password(unittest.TestCase):
    def test_shape(self):
        pw = rdp.make_password()
        self.assertEqual(len(pw), 20)
        self.assertTrue(pw.isalnum())
