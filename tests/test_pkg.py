import tempfile
import unittest
from pathlib import Path

from curiousj_framekit.frame import pkg


class Operation(unittest.TestCase):
    def test_op_detection(self):
        self.assertEqual(pkg.op_of(["-Syu"]), "-S")
        self.assertEqual(pkg.op_of(["--noconfirm", "-U", "x.pkg.tar.zst"]), "-U")
        self.assertEqual(pkg.op_of(["-Qo", "/x"]), "-Q")
        self.assertEqual(pkg.op_of(["--query", "x"]), "--query")
        self.assertEqual(pkg.op_of(["--config", "c", "-Rns", "x"]), "-R")
        self.assertEqual(pkg.op_of(["x"]), "")
        self.assertIn("-Q", pkg.QUERY_OPS)
        self.assertNotIn("-U", pkg.QUERY_OPS)


class OutsidePrefix(unittest.TestCase):
    in_pkg = "home/steamos/.local/"

    def test_clean_package(self):
        entries = [".PKGINFO", ".MTREE", "home/", "home/steamos/", "home/steamos/.local/",
                   "home/steamos/.local/bin/waypipe", "home/steamos/.local/share/man/man1/waypipe.1.gz"]
        self.assertEqual(pkg.outside_prefix(entries, self.in_pkg), [])

    def test_usr_package(self):
        entries = [".PKGINFO", "usr/", "usr/bin/x", "home/steamos/.local/bin/y", "etc/x.conf"]
        self.assertEqual(pkg.outside_prefix(entries, self.in_pkg), ["usr/", "usr/bin/x", "etc/x.conf"])


class Paths(unittest.TestCase):
    def test_confs(self):
        p = pkg.Paths(Path("/home/steamos"))
        self.assertEqual(p.in_pkg, "home/steamos/.local/")
        conf = p.conf_text()
        self.assertIn("DBPath   = /home/steamos/.local/var/lib/pacman\n", conf)
        self.assertIn("GPGDir   = /home/steamos/.local/etc/pacman.d/gnupg\n", conf)
        alarm = p.alarm_conf_text()
        self.assertIn("Include = /home/steamos/.local/etc/pacman.conf\n", alarm)
        self.assertEqual(alarm.count("SigLevel = Required DatabaseOptional"), 3)
        self.assertIn("Server = https://fl.us.mirror.archlinuxarm.org/$arch/$repo\n", alarm)

    def test_rewrite_link(self):
        local = Path("/home/steamos/.local")
        self.assertEqual(pkg.rewrite_link("/usr/lib/libx.so.1", local), "/home/steamos/.local/lib/libx.so.1")
        self.assertEqual(pkg.rewrite_link("/usr", local), "/home/steamos/.local")
        self.assertIsNone(pkg.rewrite_link("../lib/libx.so", local))
        self.assertIsNone(pkg.rewrite_link("/etc/x", local))

    def test_usr_only_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "usr/lib/systemd").mkdir(parents=True)
            (Path(d) / "usr/bin").mkdir(parents=True)
            self.assertEqual(pkg.usr_only_dirs(Path(d)), ["usr/lib/systemd"])


UPSTREAM = """\
# Maintainer: someone
pkgname=jq
pkgver=1.8.2
pkgrel=1
pkgdesc='Command-line JSON processor'
arch=('x86_64')
url='https://jqlang.github.io/jq/'
license=('MIT')
depends=('glibc' 'oniguruma')
makedepends=('git' 'cargo')
backup=('etc/jq.conf')
install=jq.install
options=('!emptydirs')
source=("git+https://github.com/jqlang/jq.git#tag=jq-$pkgver")

build() {
  cd jq
  ./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var
  make
  cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_INSTALL_LIBDIR=/usr/lib
  arch-meson build
  cargo build --release
}

package() {
  cd jq
  make DESTDIR="$pkgdir" install
  install -Dm644 COPYING "$pkgdir"/usr/share/licenses/jq/COPYING
  install -Dm644 jq.conf "$pkgdir/etc/jq.conf"
  install -Dm644 x "${pkgdir}/usr/share/x"
  install -Dm644 y "$pkgdir/opt/y"
}
"""


class Rewrite(unittest.TestCase):
    def setUp(self):
        self.out = pkg.rewrite(UPSTREAM, uses_cargo=True, from_mise=["cargo"])

    def test_arch_and_prefix_block(self):
        self.assertIn("arch=('aarch64' 'x86_64')\n", self.out)
        self.assertIn("pkgname=jq\n\n# homeify: the prefix", self.out)
        self.assertIn("_prefix=$HOME/.local\noptions+=(!debug !lto)\n", self.out)
        self.assertIn("options=('!emptydirs' !debug !lto)\n", self.out)
        self.assertIn("# homeify, dropped (nothing would run it): install=jq.install\n", self.out)
        self.assertIn("backup=('${_prefix#/}/etc/jq.conf')\n", self.out)

    def test_build_lines(self):
        self.assertIn('./configure --prefix="$_prefix" --sysconfdir="$_prefix/etc" --localstatedir="$_prefix/var"\n', self.out)
        self.assertIn('cmake -DCMAKE_INSTALL_PREFIX="$_prefix" -DCMAKE_INSTALL_LIBDIR="$_prefix"/lib\n', self.out)
        self.assertIn('arch-meson --prefix "$_prefix" build\n', self.out)
        self.assertIn('build() {\n  # homeify: what is already under ~/.local', self.out)
        self.assertIn('export RUSTFLAGS="${RUSTFLAGS:-} -C link-arg=-Wl,-rpath,$_prefix/lib"\n', self.out)

    def test_package_lines(self):
        self.assertIn('install -Dm644 COPYING "$pkgdir$_prefix"/share/licenses/jq/COPYING\n', self.out)
        self.assertIn('install -Dm644 jq.conf "$pkgdir$_prefix/etc/jq.conf"\n', self.out)
        # the quote closes after the path here, so the whole path moves
        self.assertIn('install -Dm644 x "${pkgdir}$_prefix/share/x"\n', self.out)
        self.assertIn('install -Dm644 y "$pkgdir$_prefix/opt/y"\n', self.out)

    def test_unlisting_goes_before_the_first_function(self):
        i = self.out.index("for _d in cargo; do")
        self.assertLess(i, self.out.index("build() {"))
        self.assertGreater(i, self.out.index("source=("))

    def test_without_cargo_or_mise(self):
        out = pkg.rewrite(UPSTREAM, uses_cargo=False, from_mise=[])
        self.assertNotIn("RUSTFLAGS", out)
        self.assertNotIn("for _d in", out)

    def test_result_parses(self):
        import subprocess
        with tempfile.NamedTemporaryFile("w", suffix="PKGBUILD", delete=False) as f:
            f.write(self.out)
        self.assertEqual(subprocess.run(["bash", "-n", f.name]).returncode, 0)


class WithoutPacman(unittest.TestCase):
    def test_missing_binary_is_the_kits_error(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(pkg, "HOST_PACMAN", str(Path(tmp) / "no-pacman")):
            p = pkg.Paths(Path(tmp))
            with self.assertRaises(pkg.Error) as cm:
                pkg.pacman(p, p.conf, "-Q", "x", check=False)
            self.assertIn("not found", str(cm.exception))


class Pkgbuilds(unittest.TestCase):
    def test_shipped_with_the_package(self):
        base = pkg.pkgbuilds_dir()
        self.assertEqual(base.parts[-3:], ("curiousj_framekit", "data", "pkgbuilds"))
        self.assertEqual(sorted(d.name for d in base.iterdir() if (d / "PKGBUILD").is_file()),
                         ["emacs", "pacman"])
        name, ver, rel, _ = pkg.pkgbuild_info(base / "pacman")
        self.assertEqual(name, "pacman")
        self.assertTrue(ver and rel)

    def test_stage_copies_into_the_cache_dir(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict("os.environ", {"XDG_CACHE_HOME": tmp}):
            self.assertEqual(pkg.build_dir(), Path(tmp) / "curiousj-framekit/build")
            work, names = pkg.stage(pkg.pkgbuilds_dir() / "pacman")
            self.assertEqual(work, pkg.build_dir() / "pacman")
            self.assertIn("PKGBUILD", names)
            self.assertTrue((work / "PKGBUILD").is_file())
            self.assertEqual((work / "PKGBUILD").read_bytes(), (pkg.pkgbuilds_dir() / "pacman/PKGBUILD").read_bytes())
            # what a build adds is told apart from what was copied
            (work / "src").mkdir()
            (work / "pacman-7.0.0-1-aarch64.pkg.tar.zst").write_bytes(b"")
            junk = sorted(f.name for f in work.iterdir() if f.name not in names)
            self.assertEqual(junk, ["pacman-7.0.0-1-aarch64.pkg.tar.zst", "src"])
            # nothing landed beside the PKGBUILD in the package
            self.assertFalse((pkg.pkgbuilds_dir() / "pacman/src").exists())


class MakepkgConf(unittest.TestCase):
    def test_which_file_turns_ccache_on(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            system = home / "makepkg.conf"
            system.write_text("BUILDENV=(!distcc color !ccache check !sign)\n")
            xdg = home / ".config/pacman/makepkg.conf"
            xdg.parent.mkdir(parents=True)
            with mock.patch.dict("os.environ", {"HOME": tmp, "MAKEPKG_CONF": str(system),
                                                "XDG_CONFIG_HOME": str(home / ".config")}):
                self.assertIsNone(pkg.makepkg_wants("ccache"))
                xdg.write_text("BUILDENV=(!distcc color ccache check !sign)\n")
                self.assertEqual(pkg.makepkg_wants("ccache"), str(xdg))
                self.assertIsNone(pkg.makepkg_wants("distcc"))
                # ~/.makepkg.conf is read last and wins
                (home / ".makepkg.conf").write_text("BUILDENV=(!ccache)\n")
                self.assertIsNone(pkg.makepkg_wants("ccache"))
