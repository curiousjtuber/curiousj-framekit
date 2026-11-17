import tempfile
import unittest
from pathlib import Path
from unittest import mock

from curiousj_framekit import cmdline
from curiousj_framekit.cmdline import Options
from curiousj_framekit.install import catalog
from curiousj_framekit.install.catalog import Check, Fresh, Item, State, Status
from curiousj_framekit.frame import pkg
from curiousj_framekit.beatsaber import manager
from curiousj_framekit.install.kinds import base, tailscale, uv_tool

class Base(unittest.TestCase):
    def test_sha256(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write(b"hello\n")
        digest = base.sha256_of(Path(f.name))
        self.assertEqual(digest, "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03")


class KrdcPkgbuild(unittest.TestCase):
    def test_patch_sum_matches_the_shared_patch(self):
        """The PKGBUILD's last b2sum is the patch beside it, a link to the
        PC script's; a changed patch needs the sum and a pkgrel bump.
        FreeRDP is a source, not a dependency: the package builds its
        own, with the V4L2 decoder patch; its sum and those of the
        Frame's three KRDC patches are the four before. LibVNCServer
        is a source as well, for the VNC plugin."""
        import hashlib
        import re
        from curiousj_framekit.frame import pkg
        directory = pkg.pkgbuilds_dir() / "krdc"
        patch = directory / "krdc-embed-cursor.patch"
        self.assertEqual(patch.resolve(), (pkg.pkgbuilds_dir().parent / "krdc-embed-cursor/krdc-embed-cursor.patch").resolve())
        sums = re.findall(r"'([0-9a-f]{128}|SKIP)'", (directory / "PKGBUILD").read_text())
        self.assertEqual(len(sums), 10)
        self.assertEqual(sums[-1], hashlib.blake2b(patch.read_bytes()).hexdigest())
        v4l2 = directory / "freerdp-h264-v4l2m2m.patch"
        self.assertEqual(sums[-5], hashlib.blake2b(v4l2.read_bytes()).hexdigest())
        bgrx = directory / "krdc-bgrx-buffer.patch"
        self.assertEqual(sums[-4], hashlib.blake2b(bgrx.read_bytes()).hexdigest())
        toolbar = directory / "krdc-fullscreen-toolbar.patch"
        self.assertEqual(sums[-3], hashlib.blake2b(toolbar.read_bytes()).hexdigest())
        clipboard = directory / "krdc-clipboard-thread.patch"
        self.assertEqual(sums[-2], hashlib.blake2b(clipboard.read_bytes()).hexdigest())
        name, ver, rel, deps = pkg.pkgbuild_info(directory)
        self.assertEqual((name, ver), ("krdc", "26.08.3"))
        self.assertNotIn("freerdp", deps)
        self.assertIn("ffmpeg", deps)


class KrdpserverPackage(unittest.TestCase):
    """The pacman-home server: its PKGBUILD reads, carries its patches,
    and asks for the KRdp Server menu entry."""

    def test_menu_entry(self):
        from curiousj_framekit.frame import rdp
        text = rdp.menu_entry_text()
        self.assertIn("Name=KRdp Server", text)
        self.assertIn(" rdp gui\n", text)

    def test_no_flatpak_item(self):
        self.assertNotIn("krdp", catalog.load())

    def test_item_and_pkgbuild(self):
        item = catalog.load()["krdpserver"]
        self.assertEqual(item.kind, "pacman-home")
        self.assertEqual(item.get("menu_entry"), "krdp")
        directory = pkg.pkgbuilds_dir() / item["pkgbuild"]
        name, ver, rel, deps = pkg.pkgbuild_info(directory)
        self.assertEqual(name, "krdpserver")
        self.assertEqual(ver, "6.4.5")
        self.assertIn("freerdp", deps)
        self.assertEqual(sorted(p.name for p in directory.glob("*.patch")),
                         ["kpipewire-cursor-bitmap-size.patch", "kpipewire-ffmpeg-profiles.patch",
                          "krdp-ext-security.patch", "krdp-plasma-stream.patch"])
        self.assertFalse(any(p.is_symlink() for p in directory.glob("*.patch")))


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


class Versions(unittest.TestCase):
    def test_version_tuple(self):
        self.assertEqual(base.version_tuple("v3.5.1"), (3, 5, 1))
        self.assertEqual(base.version_tuple("0.12.0-install-H62l1s"), (0, 12, 0))
        self.assertEqual(base.version_tuple("1.8.2.5"), (1, 8, 2, 5))
        self.assertEqual(base.version_tuple("main"), ())

    def test_newer(self):
        self.assertTrue(base.newer("1.104.5", "1.102.4"))
        self.assertFalse(base.newer("1.102.4", "1.104.5"))
        self.assertFalse(base.newer("v3.5.1", "v3.5.1"))
        self.assertTrue(base.newer("0.14.1", "0.12.0-install-H62l1s"))
        self.assertFalse(base.newer("0.12.0", "0.12.0-install-H62l1s"))
        self.assertTrue(base.newer("beta", "alpha"))
        self.assertFalse(base.newer("v1.0", "1.0"))


class Checks(unittest.TestCase):
    """The parsers over captured output, and the checks that need no
    network."""

    def test_uv_tool_origin(self):
        self.assertEqual(uv_tool.origin_of({"url": "file:///home/steamos/curiousj-tools",
                                            "dir_info": {"editable": True}}),
                         ("editable", "/home/steamos/curiousj-tools"))
        self.assertEqual(uv_tool.origin_of({"url": "https://github.com/x/y",
                                            "vcs_info": {"vcs": "git", "commit_id": "abc"}}),
                         ("git", "https://github.com/x/y"))
        self.assertIsNone(uv_tool.origin_of({}))
        self.assertIsNone(uv_tool.origin_of({"url": "https://files.pythonhosted.org/x.whl",
                                             "archive_info": {}}))

    def test_local_outdated_wins(self):
        """A missing part or a moved pin is outdated whatever upstream says."""
        from curiousj_framekit.install.kinds import config
        item = catalog.load()["cursor"]
        with mock.patch.object(config.Kind, "check", return_value=Check(Fresh.CURRENT, "1")):
            check = catalog.check_of(item, Options(), Status(State.OUTDATED, "missing wl-clipboard"))
        self.assertEqual(check.fresh, Fresh.OUTDATED)
        self.assertEqual(check.note, "missing wl-clipboard")
        with mock.patch.object(config.Kind, "check", side_effect=cmdline.Error("no network")):
            check = catalog.check_of(item, Options(), Status(State.OK, "1"))
        self.assertEqual(check.fresh, Fresh.UNKNOWN)
        self.assertIn("no network", check.note)

    def test_check_lines(self):
        from curiousj_framekit.install import update
        lines = update.check_lines({
            "tailscale": Check(Fresh.OUTDATED, "1.102.4", "1.104.5", "pkgs.tailscale.com stable"),
            "emacs": Check(Fresh.BEHIND, "31.1-1", "31.2", "Arch Linux ARM", "the PKGBUILD has 31.1: bump it"),
            "fuse2": Check(Fresh.CURRENT, "2.9.9-1", source="the kit's PKGBUILD"),
            "waypipe": Check(Fresh.UNKNOWN, "0.11.3-1", note="can't tell: no network"),
            "krdc": Check(Fresh.OUTDATED, "26.08.2-1", "26.08.2-1", "the kit's PKGBUILD",
                          "26.08.2-1 installed, but the host no longer has libxml2.so.2 (a SteamOS update): rebuild it"),
        })
        self.assertEqual(lines, [
            "outdated  tailscale  1.102.4 -> 1.104.5 (pkgs.tailscale.com stable)",
            "behind    emacs      31.1-1 -> 31.2 (Arch Linux ARM); the PKGBUILD has 31.1: bump it",
            "current   fuse2      2.9.9-1 (the kit's PKGBUILD)",
            "?         waypipe    0.11.3-1; can't tell: no network",
            "outdated  krdc       26.08.2-1 (the kit's PKGBUILD); 26.08.2-1 installed, but the host no longer has "
            "libxml2.so.2 (a SteamOS update): rebuild it",
        ])

    def test_every_kind_answers_check(self):
        """No kind falls through to Base's `no way to tell` by accident:
        each one defines check (the cursor's says current)."""
        from curiousj_framekit.install.kinds import MODULES
        for name in MODULES:
            module = __import__(f"curiousj_framekit.install.kinds.{MODULES[name]}", fromlist=["Kind"])
            self.assertIn("check", vars(module.Kind), name)


class PacmanHome(unittest.TestCase):
    def test_status_without_pacman_is_unknown_and_writes_nothing(self):
        from curiousj_framekit.frame import pkg
        from curiousj_framekit.install.kinds import pacman_home
        item = next(it for it in catalog.load().values() if it.kind == "pacman-home")
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict("os.environ", {"HOME": tmp}), \
                mock.patch.object(pkg, "HOST_PACMAN", str(Path(tmp) / "no-pacman")):
            status = pacman_home.Kind().status(item, Options())
            self.assertEqual(status.state, State.UNKNOWN)
            self.assertIn("no pacman here", status.detail)
            self.assertFalse((Path(tmp) / ".local/etc").exists())


class PacmanHomeBroken(unittest.TestCase):
    """A package whose program lost a library to a SteamOS update is
    outdated at the same version, and cjf update rebuilds it."""

    DETAIL = "31.1-1 installed, but the host no longer has libxml2.so.2 (a SteamOS update): rebuild it"

    def test_status_and_check(self):
        from curiousj_framekit.frame import pkg
        from curiousj_framekit.install.kinds import pacman_home
        item = catalog.load()["emacs"]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict("os.environ", {"HOME": tmp}), \
                mock.patch.object(pkg, "query_version", return_value="31.1-1"), \
                mock.patch.object(pkg, "pkgbuild_info", return_value=("emacs-wayland", "31.1", "1", [])), \
                mock.patch.object(pkg, "broken_libs", return_value=[("bin/emacs-31.1", "libxml2.so.2")]), \
                mock.patch.object(pkg, "upstream_version", return_value=None), \
                mock.patch.object(pacman_home, "synced_paths", return_value=pkg.Paths(Path(tmp))):
            status = pacman_home.Kind().status(item, Options())
            self.assertEqual(status.state, State.OUTDATED)
            self.assertEqual(status.detail, self.DETAIL)
            check = catalog.check_of(item, Options(), status)
        self.assertEqual(check, Check(Fresh.OUTDATED, "31.1-1", "31.1-1", "the kit's PKGBUILD", self.DETAIL))

    def test_broken_and_behind_is_a_rebuild_first(self):
        from curiousj_framekit.frame import pkg
        from curiousj_framekit.install.kinds import pacman_home
        item = catalog.load()["emacs"]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(pkg, "query_version", return_value="31.1-1"), \
                mock.patch.object(pkg, "pkgbuild_info", return_value=("emacs-wayland", "31.1", "1", [])), \
                mock.patch.object(pkg, "upstream_version", return_value=("31.2", "Arch Linux ARM")), \
                mock.patch.object(pkg, "vercmp", return_value=1), \
                mock.patch.object(pacman_home, "synced_paths", return_value=pkg.Paths(Path(tmp))):
            check = pacman_home.Kind().check(item, Options(), Status(State.OUTDATED, self.DETAIL))
        self.assertEqual(check.fresh, Fresh.OUTDATED)
        self.assertEqual(check.available, "31.1-1")
        self.assertEqual(check.note, self.DETAIL + "; and 31.2 is out (Arch Linux ARM): "
                                     "the PKGBUILD has 31.1: bump data/pkgbuilds/emacs/PKGBUILD")

    def test_a_bump_keeps_its_line(self):
        from curiousj_framekit.frame import pkg
        from curiousj_framekit.install.kinds import pacman_home
        item = catalog.load()["emacs"]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(pkg, "query_version", return_value="31.1-1"), \
                mock.patch.object(pkg, "pkgbuild_info", return_value=("emacs-wayland", "31.1", "2", [])), \
                mock.patch.object(pkg, "upstream_version", return_value=None), \
                mock.patch.object(pacman_home, "synced_paths", return_value=pkg.Paths(Path(tmp))):
            status = Status(State.OUTDATED, "31.1-1 installed, 31.1-2 in the PKGBUILD")
            check = pacman_home.Kind().check(item, Options(), status)
        self.assertEqual(check, Check(Fresh.OUTDATED, "31.1-1", "31.1-2", "the kit's PKGBUILD"))


class BSManagerFuse(unittest.TestCase):
    def test_env_puts_the_library_first(self):
        env = manager.appimage_env({"LD_LIBRARY_PATH": "/opt/lib", "HOME": "/h"})
        self.assertEqual(env["LD_LIBRARY_PATH"], f"{manager.FUSE2_LIB}:/opt/lib")
        self.assertEqual(manager.appimage_env({})["LD_LIBRARY_PATH"], str(manager.FUSE2_LIB))

    def test_fuse2_is_still_an_item(self):
        self.assertEqual(catalog.load()["fuse2"].kind, "pacman-home")
