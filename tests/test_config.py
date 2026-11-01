import io
import tempfile
import unittest
from pathlib import Path

from curiousj_framekit import cmdline, config
from curiousj_framekit.cmdline import Options


class Dumps(unittest.TestCase):
    def test_roundtrip(self):
        data = {"cursor": {"software": True, "size": 32, "theme": "breeze_cursors"},
                "flatpak": {"scope": "user"}, "rdp": {"port": 3391}}
        text = config.dumps(data)
        self.assertIn("[cursor]\nsoftware = true\nsize = 32\ntheme = \"breeze_cursors\"\n", text)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            p.write_text(text)
            self.assertEqual(config.load(p), data)

    def test_strings_are_escaped(self):
        text = config.dumps({"a": {"s": 'he said "hi"\\'}})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.toml"
            p.write_text(text)
            self.assertEqual(config.load(p)["a"]["s"], 'he said "hi"\\')

    def test_empty_section_is_skipped(self):
        self.assertNotIn("[x]", config.dumps({"x": {}}))


class Load(unittest.TestCase):
    def test_missing_is_empty(self):
        self.assertEqual(config.load(Path("/nonexistent/config.toml")), {})

    def test_bad_toml_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.toml"
            p.write_text("[cursor\n")
            with self.assertRaises(cmdline.Error):
                config.load(p)


class SetValue(unittest.TestCase):
    def test_set_and_remove(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            out = io.StringIO()
            self.assertTrue(config.set_value(Options(yes=True), "cursor", "software", True, p, out=out))
            self.assertEqual(config.get("cursor", "software", path=p), True)
            self.assertFalse(config.set_value(Options(yes=True), "cursor", "software", True, p, out=out))
            self.assertTrue(config.set_value(Options(yes=True), "cursor", "software", None, p, out=out))
            self.assertEqual(config.load(p), {})
            self.assertIsNone(config.get("cursor", "software", path=p))
