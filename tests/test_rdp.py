import unittest

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
