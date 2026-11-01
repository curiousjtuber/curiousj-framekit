import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from curiousj_framekit import config
from curiousj_framekit.cmdline import Options
from curiousj_framekit.frame import cursor


class Targets(unittest.TestCase):
    def test_order_of_preference(self):
        self.assertEqual(cursor.targets("stock", "frametop", ["frametop"]), ["stock"])
        self.assertEqual(cursor.targets(None, "stock", ["frametop"]), ["stock"])
        self.assertEqual(cursor.targets(None, None, ["frametop", "stock"]), ["frametop"])
        self.assertEqual(cursor.targets(None, None, []), ["frametop", "stock"])


class ConfState(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(cursor.conf_state(None, None), ("", "none"))
        self.assertEqual(cursor.conf_state(cursor.ON_TEXT, None), ("on", "default"))
        self.assertEqual(cursor.conf_state(cursor.ON_TEXT, True), ("on", "chosen"))
        self.assertEqual(cursor.conf_state(cursor.OFF_TEXT, False), ("off", "chosen"))
        self.assertEqual(cursor.conf_state("# steam-frame-utils: sw-cursor off\nKWIN_FORCE_SW_CURSOR=0\n",
                                           None), ("off", "chosen"))
        self.assertEqual(cursor.conf_state("SOMETHING=1\n", None), ("", "other"))

    def test_entry_text_and_recognition(self):
        text = cursor.entry_text("/home/steamos/.local/bin/cjf")
        self.assertIn("Exec=/home/steamos/.local/bin/cjf cursor apply\n", text)
        self.assertTrue(cursor.is_our_entry(text))
        self.assertTrue(cursor.is_our_entry("[Desktop Entry]\nName=steam-frame-utils cursor size\n"))
        self.assertFalse(cursor.is_our_entry("[Desktop Entry]\nName=something else\n"))


class SoftwareCursor(unittest.TestCase):
    """set_software against a fake HOME, no desktop running."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.home = Path(self.dir.name)
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home)}, clear=False)
        self.env.start()
        for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME"):
            os.environ.pop(var, None)
        self.conf = self.home / ".config/environment.d" / cursor.CONF_NAME
        self.entry = self.home / ".config/autostart" / cursor.ENTRY_NAME
        self.out = io.StringIO()

    def tearDown(self):
        self.env.stop()
        self.dir.cleanup()

    def run_set(self, verb, **kw):
        with redirect_stdout(self.out):
            return cursor.set_software(Options(yes=True, **kw), verb)

    def test_on_off_default(self):
        self.run_set("on")
        self.assertEqual(self.conf.read_text(), cursor.ON_TEXT)
        self.assertIs(config.get("cursor", "software"), True)
        self.assertTrue(self.entry.is_file())
        self.assertIn("cursor apply", self.entry.read_text())

        self.run_set("off")
        self.assertEqual(self.conf.read_text(), cursor.OFF_TEXT)
        self.assertIs(config.get("cursor", "software"), False)
        self.assertFalse(self.entry.exists())

        self.run_set("default")
        self.assertEqual(self.conf.read_text(), cursor.ON_TEXT)
        self.assertIsNone(config.get("cursor", "software"))
        self.assertTrue(self.entry.is_file())

    def test_auto_installs_the_default_once(self):
        self.assertEqual(self.run_set("auto"), 100)
        self.assertEqual(self.conf.read_text(), cursor.ON_TEXT)
        self.assertEqual(self.run_set("auto"), 0)

    def test_auto_keeps_a_choice_and_carries_an_old_marker(self):
        self.conf.parent.mkdir(parents=True)
        self.conf.write_text("# steam-frame-utils: sw-cursor off\nKWIN_FORCE_SW_CURSOR=0\n")
        self.assertEqual(self.run_set("auto"), 0)
        self.assertEqual(self.conf.read_text(),
                         "# steam-frame-utils: sw-cursor off\nKWIN_FORCE_SW_CURSOR=0\n")
        self.assertIs(config.get("cursor", "software"), False)
        self.assertFalse(self.entry.exists())

    def test_old_entry_is_replaced(self):
        old = self.home / ".config/autostart" / cursor.OLD_ENTRY_NAME
        old.parent.mkdir(parents=True)
        old.write_text("[Desktop Entry]\nName=steam-frame-utils cursor size\nExec=x\n")
        self.run_set("on")
        self.assertFalse(old.exists())
        self.assertTrue(self.entry.is_file())

    def test_other_file_is_left_alone_by_auto(self):
        self.conf.parent.mkdir(parents=True)
        self.conf.write_text("KWIN_SOMETHING=2\n")
        self.assertEqual(self.run_set("auto"), 0)
        self.assertEqual(self.conf.read_text(), "KWIN_SOMETHING=2\n")
        self.assertIn("left alone", self.out.getvalue())

    def test_check_changes_nothing(self):
        self.run_set("on", check=True)
        self.assertFalse(self.conf.exists())
        self.assertFalse(self.entry.exists())
        self.assertIn("would create", self.out.getvalue())
