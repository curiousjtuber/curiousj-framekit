import tempfile
import unittest
from pathlib import Path
from unittest import mock

from curiousj_framekit import cmdline
from curiousj_framekit.cmdline import Options
from curiousj_framekit.install import catalog
from curiousj_framekit.install.catalog import Item, State
from curiousj_framekit.install.kinds import base, flatpak, flatpak_build, tailscale, upstream, uv_tool

SUMS = ("abc123  other.tar.gz\n"
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef  framekeyboard-1.2.3-aarch64.tar.gz\n"
        "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210 *Frametop.zip\n")


class Base(unittest.TestCase):
    def test_sum_for(self):
        self.assertEqual(base.sum_for(SUMS, "framekeyboard-1.2.3-aarch64.tar.gz"), "0123456789abcdef" * 4)
        self.assertEqual(base.sum_for(SUMS, "Frametop.zip"), "fedcba9876543210" * 4)
        self.assertIsNone(base.sum_for(SUMS, "other.tar.gz"))  # not a sha256
        self.assertIsNone(base.sum_for(SUMS, "missing"))

    def test_sha256_and_verify(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write(b"hello\n")
        digest = base.sha256_of(Path(f.name))
        self.assertEqual(digest, "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03")
        base.verify(Path(f.name), digest, "x")
        with self.assertRaises(cmdline.Error):
            base.verify(Path(f.name), "0" * 64, "x")


class Upstream(unittest.TestCase):
    def test_take_version(self):
        self.assertEqual(upstream.take_version(["--version", "v0.2.3", "--yes"], "x"), ("0.2.3", ["--yes"]))
        self.assertEqual(upstream.take_version(["--yes"], "x"), (None, ["--yes"]))
        with self.assertRaises(cmdline.Error):
            upstream.take_version(["--version", "latest"], "x")
        with self.assertRaises(cmdline.Error):
            upstream.take_version(["--version=0.2.3"], "x")

    def test_keyboard_archive_regex(self):
        m = upstream.KEYBOARD_ARCHIVE.search(SUMS)
        self.assertEqual(m.group(1), "1.2.3")

    def test_current_release(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertIsNone(upstream.current_release(root))
            (root / "releases" / "0.2.2").mkdir(parents=True)
            (root / "current").symlink_to("releases/0.2.2")
            self.assertEqual(upstream.current_release(root), "0.2.2")

    def test_frametop_status_against_catalog(self):
        item = catalog.load()["frametop"]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with mock.patch.object(upstream, "FRAMETOP_RELEASES", root):
                self.assertEqual(upstream.frametop_status(item, Options()).state, State.MISSING)
                (root / "releases" / item["version"]).mkdir(parents=True)
                (root / "current").symlink_to(f"releases/{item['version']}")
                self.assertEqual(upstream.frametop_status(item, Options()).state, State.OK)
                (root / "current").unlink()
                (root / "current").symlink_to("releases/0.1.0")
                self.assertEqual(upstream.frametop_status(item, Options()).state, State.OUTDATED)


class FlatpakBuild(unittest.TestCase):
    def test_stamp_covers_manifest_and_patches(self):
        item = catalog.load()["krdp"]
        path = flatpak_build.manifest_path(item)
        self.assertTrue(path.is_file(), path)
        self.assertEqual(len(list(path.parent.glob("*.patch"))), 2)
        self.assertEqual(len(flatpak_build.stamp(item)), 16)

    def test_menu_entry(self):
        text = flatpak_build.menu_entry_text()
        self.assertIn("Name=KRdp Server", text)
        self.assertIn(" rdp gui\n", text)


class Tailscale(unittest.TestCase):
    def test_unit_text(self):
        self.assertIn("ExecStart=/home/.tailscale/bin/tailscaled --statedir=/home/.tailscale/state", tailscale.UNIT_TEXT)
        self.assertIn("TS_DEBUG_FIREWALL_MODE=nftables", tailscale.UNIT_TEXT)

    def test_missing_parts_when_nothing_is_there(self):
        with mock.patch.object(tailscale, "BIN", Path("/nonexistent/bin")), \
             mock.patch.object(tailscale, "UNIT", Path("/nonexistent/unit")), \
             mock.patch.object(tailscale, "systemctl", return_value=False), \
             mock.patch.object(tailscale, "trusted", return_value=False):
            self.assertEqual(tailscale.missing_parts(Options(), True),
                             ["binaries", "unit", "enabled", "running", "trusted"])
            item = catalog.load()["tailscale"]
            with mock.patch("curiousj_framekit.where.in_container", return_value=False):
                self.assertEqual(tailscale.Kind().status(item, Options()).state, State.MISSING)


class UvTool(unittest.TestCase):
    def test_installed_version_parses_uv_tool_list(self):
        listing = "curiousj-tools v0.1.0\n- cjf\ncurious-other v2\n"
        with mock.patch.object(uv_tool, "uv_path", return_value="uv"), \
             mock.patch.object(cmdline, "run", return_value=mock.Mock(returncode=0, stdout=listing)):
            self.assertEqual(uv_tool.installed_version(Options(), "curiousj-tools"), "v0.1.0")
            self.assertIsNone(uv_tool.installed_version(Options(), "nothing"))


class Flatpak(unittest.TestCase):
    def test_scope(self):
        with mock.patch("curiousj_framekit.config.get", return_value="user"):
            self.assertEqual(flatpak.scope_of(Options(), []), "user")
            self.assertEqual(flatpak.scope_of(Options(), ["--system"]), "system")
        with mock.patch("curiousj_framekit.config.get", return_value="system"):
            self.assertEqual(flatpak.scope_of(Options(), []), "system")
        with mock.patch("curiousj_framekit.config.get", return_value="odd"):
            with self.assertRaises(cmdline.Error):
                flatpak.scope_of(Options(), [])


class StampIgnoresComments(unittest.TestCase):
    def test_comment_change_keeps_the_stamp(self):
        item = catalog.load()["krdp"]
        before = flatpak_build.stamp(item)
        path = flatpak_build.manifest_path(item)
        original = path.read_text()
        try:
            path.write_text("# a new note\n" + original.replace("\n#", "\n# changed", 1))
            self.assertEqual(flatpak_build.stamp(item), before)
            path.write_text(original.replace("--port", "--porx", 1))
            self.assertNotEqual(flatpak_build.stamp(item), before)
        finally:
            path.write_text(original)


class WantsUpdate(unittest.TestCase):
    def test_which_items_all_runs(self):
        from curiousj_framekit.install import commands
        from curiousj_framekit.install.catalog import Status
        items = catalog.load()
        ok = Status(State.OK, "x")
        self.assertTrue(commands.wants_update(items["moonlight"], ok))
        self.assertTrue(commands.wants_update(items["curiousj-tools"], ok))
        self.assertTrue(commands.wants_update(items["full-keyboard"], ok))
        self.assertFalse(commands.wants_update(items["frametop"], ok))
        self.assertFalse(commands.wants_update(items["bsmanager"], ok))
        self.assertFalse(commands.wants_update(items["krdp"], ok))
        self.assertFalse(commands.wants_update(items["cursor"], ok))
        self.assertTrue(commands.wants_update(items["krdp"], Status(State.OUTDATED, "x")))
        self.assertFalse(commands.wants_update(items["moonlight"], Status(State.MISSING)))
