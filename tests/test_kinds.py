import tempfile
import unittest
from pathlib import Path
from unittest import mock

from curiousj_framekit import cmdline
from curiousj_framekit.cmdline import Options
from curiousj_framekit.install import catalog
from curiousj_framekit.install.catalog import Check, Fresh, Item, State, Status
from curiousj_framekit.frame import pkg
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


class KrdcPkgbuild(unittest.TestCase):
    def test_patch_sum_matches_the_shared_patch(self):
        """The PKGBUILD's last b2sum is the patch beside it, a link to the
        PC script's; a changed patch needs the sum and a pkgrel bump."""
        import hashlib
        import re
        from curiousj_framekit.frame import pkg
        directory = pkg.pkgbuilds_dir() / "krdc"
        patch = directory / "krdc-embed-cursor.patch"
        self.assertEqual(patch.resolve(), (pkg.pkgbuilds_dir().parent / "krdc-embed-cursor/krdc-embed-cursor.patch").resolve())
        sums = re.findall(r"'([0-9a-f]{128}|SKIP)'", (directory / "PKGBUILD").read_text())
        self.assertEqual(len(sums), 4)
        self.assertEqual(sums[-1], hashlib.blake2b(patch.read_bytes()).hexdigest())
        name, ver, rel, deps = pkg.pkgbuild_info(directory)
        self.assertEqual((name, ver), ("krdc", "26.08.2"))
        self.assertIn("freerdp", deps)


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


class KrdpserverPackage(unittest.TestCase):
    """The pacman-home server: its PKGBUILD reads, carries its patches,
    and asks for the same menu entry as the flatpak."""

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
        # The cursor patch is the flatpak's, by symlink, so the two can't drift.
        link = directory / "kpipewire-cursor-bitmap-size.patch"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (pkg.pkgbuilds_dir().parent / "krdp" / link.name).resolve())


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


class PatchBody(unittest.TestCase):
    """A patch's prose header is not part of the build, so a note there
    keeps the flatpak's stamp; the diff after it is the build."""

    def test_prose_before_the_diff_is_dropped(self):
        diff = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
        self.assertEqual(flatpak_build.patch_body("why this patch\n\n" + diff), diff)
        self.assertEqual(flatpak_build.patch_body("a note\nFrom 1234 Mon Sep 17 00:00:00 2001\n" + diff),
                         "From 1234 Mon Sep 17 00:00:00 2001\n" + diff)
        self.assertEqual(flatpak_build.patch_body(diff), diff)
        self.assertEqual(flatpak_build.patch_body("no diff at all\n"), "no diff at all\n")

    def test_the_kits_patches_have_bodies(self):
        item = catalog.load()["krdp"]
        for patch in flatpak_build.manifest_path(item).parent.glob("*.patch"):
            body = flatpak_build.patch_body(patch.read_text())
            self.assertTrue(body.startswith(("From ", "diff ", "--- ")), patch.name)
            self.assertLess(len(body), len(patch.read_text()), f"{patch.name} has no prose header")


class StampIgnoresComments(unittest.TestCase):
    def test_comment_change_keeps_the_stamp(self):
        item = catalog.load()["krdp"]
        before = flatpak_build.stamp(item)
        path = flatpak_build.manifest_path(item)
        original = path.read_text()
        try:
            path.write_text("# a new note\n" + original.replace("\n#", "\n# changed", 1))
            self.assertEqual(flatpak_build.stamp(item), before)
            self.assertIn("runtime-version: '6.11'", original)
            path.write_text(original.replace("runtime-version: '6.11'", "runtime-version: '6.12'", 1))
            self.assertNotEqual(flatpak_build.stamp(item), before)
        finally:
            path.write_text(original)


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

    def test_flatpak_updates(self):
        found = flatpak.parse_updates("org.deskflow.deskflow\t1.27.0\tflathub\n")
        self.assertEqual(found, {"org.deskflow.deskflow": ("1.27.0", "flathub")})
        self.assertEqual(flatpak.parse_updates(""), {})

    def test_brew_outdated(self):
        from curiousj_framekit.install.kinds import brew
        text = '{"formulae":[{"name":"zsh","installed_versions":["5.9"],"current_version":"5.9.1"}],"casks":[]}'
        self.assertEqual(brew.parse_outdated(text), {"zsh": ("5.9", "5.9.1")})
        self.assertEqual(brew.parse_outdated('{"formulae":[],"casks":[]}'), {})
        with self.assertRaises(cmdline.Error):
            brew.parse_outdated("==> not json")

    def test_mise_outdated(self):
        from curiousj_framekit.install.kinds import mise
        text = '{"rust": {"name": "rust", "requested": "latest", "current": "1.91.0", "latest": "1.92.0"}}'
        self.assertEqual(mise.parse_outdated(text, "rust"), ("1.91.0", "1.92.0"))
        self.assertIsNone(mise.parse_outdated("{}", "rust"))
        self.assertIsNone(mise.parse_outdated("", "rust"))

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

    def test_frametop_check_against_catalog(self):
        item = catalog.load()["frametop"]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "releases" / "0.2.1").mkdir(parents=True)
            (root / "current").symlink_to("releases/0.2.1")
            with mock.patch.object(upstream, "FRAMETOP_RELEASES", root), \
                    mock.patch.object(upstream, "latest_tag", return_value=f"v{item['version']}"):
                check = upstream.frametop_check(item, Options(), Status(State.OUTDATED, "x"))
            self.assertEqual((check.fresh, check.installed, check.available), (Fresh.OUTDATED, "0.2.1", item["version"]))
            with mock.patch.object(upstream, "FRAMETOP_RELEASES", root), \
                    mock.patch.object(upstream, "latest_tag", return_value="v9.0.0"):
                check = upstream.frametop_check(item, Options(), Status(State.OUTDATED, "x"))
            self.assertEqual(check.fresh, Fresh.BEHIND)
            self.assertIn("bump version and sha256", check.note)

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
            "frametop": Check(Fresh.CURRENT, "0.2.2", source="GitHub release"),
            "bsmanager": Check(Fresh.UNKNOWN, "AppImage", note="updates itself"),
            "krdc": Check(Fresh.OUTDATED, "26.08.2-1", "26.08.2-1", "the kit's PKGBUILD",
                          "26.08.2-1 installed, but the host no longer has libxml2.so.2 (a SteamOS update): rebuild it"),
        })
        self.assertEqual(lines, [
            "outdated  tailscale  1.102.4 -> 1.104.5 (pkgs.tailscale.com stable)",
            "behind    emacs      31.1-1 -> 31.2 (Arch Linux ARM); the PKGBUILD has 31.1: bump it",
            "current   frametop   0.2.2 (GitHub release)",
            "?         bsmanager  AppImage; updates itself",
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
    def test_exec_line_gets_the_library_path_once(self):
        from curiousj_framekit.install.kinds import upstream
        line = 'Exec="/home/steamos/Applications/BSManager.AppImage" --no-sandbox %U'
        fixed = upstream.fuse_exec(line)
        self.assertEqual(fixed, f"Exec=env LD_LIBRARY_PATH={upstream.FUSE2_LIB} "
                                '"/home/steamos/Applications/BSManager.AppImage" --no-sandbox %U')
        self.assertEqual(upstream.fuse_exec(fixed), fixed)
        self.assertFalse(upstream.menu_entry_has_fuse(f"[Desktop Entry]\n{line}\nName=BSManager\n"))
        self.assertTrue(upstream.menu_entry_has_fuse(f"[Desktop Entry]\n{fixed}\nName=BSManager\n"))

    def test_fix_menu_entry_rewrites_exec_only(self):
        from curiousj_framekit.install.kinds import upstream
        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp) / "bs-manager.desktop"
            desktop.write_text('[Desktop Entry]\nName=BSManager\nExec="/x/BSManager.AppImage" --no-sandbox %U\n'
                               "Icon=/y/bs-manager.png\n")
            with mock.patch.object(upstream, "BSM_DESKTOP", desktop):
                self.assertTrue(upstream.fix_menu_entry())
                self.assertFalse(upstream.fix_menu_entry())
            self.assertEqual(desktop.read_text(), f"[Desktop Entry]\nName=BSManager\nExec=env LD_LIBRARY_PATH="
                             f'{upstream.FUSE2_LIB} "/x/BSManager.AppImage" --no-sandbox %U\nIcon=/y/bs-manager.png\n')

    def test_env_puts_the_library_first(self):
        from curiousj_framekit.install.kinds import upstream
        env = upstream.appimage_env({"LD_LIBRARY_PATH": "/opt/lib", "HOME": "/h"})
        self.assertEqual(env["LD_LIBRARY_PATH"], f"{upstream.FUSE2_LIB}:/opt/lib")
        self.assertEqual(upstream.appimage_env({})["LD_LIBRARY_PATH"], str(upstream.FUSE2_LIB))

    def test_bsmanager_needs_fuse2(self):
        items = catalog.load()
        self.assertIn("fuse2", items["bsmanager"].needs)
        self.assertEqual(items["fuse2"].kind, "pacman-home")
