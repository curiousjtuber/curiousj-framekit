import tempfile
import unittest
from unittest import mock
from pathlib import Path

from curiousj_framekit.frame import after_update

INFO = {"VERSION_ID": "0.5.6", "BUILD_ID": "20261022.6153909"}


class Record(unittest.TestCase):
    def test_roundtrip_and_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state" / "after-update.toml"
            self.assertEqual(after_update.read_record(p), {})
            self.assertIn("nothing recorded before", after_update.steamos_line(INFO, {}))
            after_update.write_record(INFO, p, now=0)
            rec = after_update.read_record(p)
            self.assertEqual(rec["VERSION_ID"], "0.5.6")
            self.assertEqual(rec["BUILD_ID"], "20261022.6153909")
            self.assertIn("seen", rec)
            self.assertTrue(after_update.steamos_line(INFO, rec).startswith("ok"))
            newer = {"VERSION_ID": "0.5.7", "BUILD_ID": "20261118.6209911"}
            line = after_update.steamos_line(newer, rec)
            self.assertIn("0.5.6 (build 20261022.6153909) -> 0.5.7 (build 20261118.6209911)", line)


class Elf(unittest.TestCase):
    def test_is_elf(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write(b"\x7fELFrest")
        self.assertTrue(after_update.is_elf(Path(f.name)))
        with tempfile.NamedTemporaryFile("w", delete=False) as g:
            g.write("#!/bin/sh\n")
        self.assertFalse(after_update.is_elf(Path(g.name)))
        self.assertFalse(after_update.is_elf(Path("/nonexistent")))

    def test_unresolved_on_a_resolving_binary(self):
        self.assertEqual(after_update.unresolved(Path("/bin/sh").resolve()), [])


class Frametop(unittest.TestCase):
    def lines(self, home: Path) -> list[str]:
        with mock.patch.object(Path, "home", return_value=home):
            return after_update.check_frametop()

    def test_no_launcher_a_release_and_a_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            self.assertIn("not installed", self.lines(home)[0])
            releases = home / ".local/share/frametop/releases"
            (releases / "0.2.2").mkdir(parents=True)
            (releases / "current").symlink_to("0.2.2")
            launcher = home / after_update.LAUNCHER
            launcher.parent.mkdir(parents=True)
            launcher.write_text(f"[Desktop Entry]\nExec={releases}/current/bin/desktop\n")
            (line,) = self.lines(home)
            self.assertTrue(line.startswith("ok"))
            self.assertIn("the Frametop release, 0.2.2 (", line)
            launcher.write_text(f"[Desktop Entry]\nExec={home}/frametop/desktops.sh start\n")
            (line,) = self.lines(home)
            self.assertTrue(line.startswith("note"))
            self.assertIn("a checkout", line)
