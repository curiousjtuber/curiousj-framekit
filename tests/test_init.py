"""cjf init against a fake HOME. No desktop runs there."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from curiousj_framekit.cmdline import Options
from curiousj_framekit.frame import cursor
from curiousj_framekit.install import init


class FakeHome(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.home = Path(self.dir.name)
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home)}, clear=False)
        self.env.start()
        for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME"):
            os.environ.pop(var, None)
        self.out = io.StringIO()
        # init.PATH_RE was compiled with the real home; rebuild it for this one
        self.path_re = mock.patch.object(init, "PATH_RE", init.re.compile(
            r"^[^#]*PATH=.*(~|\$HOME|\$\{HOME\}|%s)/\.local/bin" % init.re.escape(str(self.home)),
            init.re.M))
        self.path_re.start()
        self.completion = mock.patch.object(init, "completion", lambda opts, shell: f"# {shell} completion\n")
        self.completion.start()

    def tearDown(self):
        self.completion.stop()
        self.path_re.stop()
        self.env.stop()
        self.dir.cleanup()

    def run_init(self, **kw):
        with redirect_stdout(self.out):
            return init.run_init(Options(yes=True, **kw))


class Init(FakeHome):
    def test_fresh_home(self):
        changed = self.run_init()
        self.assertTrue(all(changed[k] for k in ("path", "init_sh", "shims", "rc", "distroboxrc", "conf")))
        bashrc = (self.home / ".bashrc").read_text()
        self.assertTrue(bashrc.startswith("# >>> curiousj-framekit: init >>>\n"))
        self.assertIn("export PATH=~/.local/bin:$PATH\n", bashrc)
        self.assertIn("export PATH=~/.local/bin:$PATH\n", (self.home / ".profile").read_text())
        self.assertFalse((self.home / ".zshrc").exists())
        share = self.home / ".local/share/curiousj-framekit"
        init_sh = (share / "init.sh").read_text()
        self.assertIn("function waypipe", init_sh)
        self.assertIn("command -v compdef", init_sh)
        self.assertIn("source ~/.local/share/curiousj-framekit/completion.bash", init_sh)
        self.assertIn("# bash completion", (share / "completion.bash").read_text())
        self.assertIn("# zsh completion", (share / "completion.zsh").read_text())
        shim = self.home / ".local/share/curiousj-framekit/shims/podman"
        self.assertTrue(shim.stat().st_mode & 0o100)
        self.assertIn("curiousj-framekit: shims", (self.home / ".distroboxrc").read_text())
        self.assertEqual(cursor.conf_path().read_text(), cursor.ON_TEXT)
        self.assertTrue((self.home / ".config/autostart" / cursor.ENTRY_NAME).is_file())

    def test_second_run_changes_nothing(self):
        self.run_init()
        self.out = io.StringIO()
        changed = self.run_init()
        self.assertFalse(any(changed.values()), changed)
        self.assertNotIn("change", self.out.getvalue().replace("would change", ""))

    def test_check_writes_nothing(self):
        self.run_init(check=True)
        self.assertFalse((self.home / ".bashrc").exists())
        self.assertFalse((self.home / ".local/share/curiousj-framekit").exists())
        self.assertIn("would create", self.out.getvalue())

    def test_existing_path_line_and_zshrc(self):
        (self.home / ".bashrc").write_text("# mine\nexport PATH=\"$HOME/.local/bin:$PATH\"\n")
        (self.home / ".zshrc").write_text("")
        self.run_init()
        bashrc = (self.home / ".bashrc").read_text()
        self.assertEqual(bashrc.count("/.local/bin"), 1)
        self.assertTrue((self.home / ".zshrc").read_text().startswith("# >>> curiousj-framekit: init >>>"))


class Remove(FakeHome):
    def run_remove(self, **kw):
        with redirect_stdout(self.out):
            return init.run_remove(Options(yes=True, **kw))

    def test_after_init(self):
        (self.home / ".zshrc").write_text("# mine\n")
        self.run_init()
        share = self.home / ".local/share/curiousj-framekit"
        (share / "init.sh.bak-20261117-155806").write_text("")
        (share / "shims/podman.bak-20261117-155806").write_text("")
        changed = self.run_remove()
        self.assertTrue(all(changed.values()), changed)
        self.assertEqual((self.home / ".bashrc").read_text(), init.PATH_LINE + "\n")
        self.assertEqual((self.home / ".zshrc").read_text(), "# mine\n")
        self.assertFalse((self.home / ".distroboxrc").exists())
        self.assertFalse((self.home / ".local/share/curiousj-framekit").exists())
        self.assertFalse(cursor.conf_path().exists())
        self.assertFalse((self.home / ".config/autostart" / cursor.ENTRY_NAME).exists())

    def test_second_run_changes_nothing(self):
        self.run_init()
        self.run_remove()
        changed = self.run_remove()
        self.assertFalse(any(changed.values()), changed)

    def test_check_removes_nothing(self):
        self.run_init()
        changed = self.run_remove(check=True)
        self.assertTrue(all(changed.values()), changed)
        self.assertIn("curiousj-framekit: init", (self.home / ".bashrc").read_text())
        self.assertTrue((self.home / ".local/share/curiousj-framekit/shims/podman").exists())
        self.assertTrue(cursor.conf_path().exists())

    def test_what_is_not_the_kits_stays(self):
        self.run_init()
        share = self.home / ".local/share/curiousj-framekit"
        (share / "mine").write_text("")
        rc = self.home / ".distroboxrc"
        rc.write_text("# mine\n" + rc.read_text())
        cursor.conf_path().write_text("KWIN_FORCE_SW_CURSOR=1\nOTHER=1\n")
        changed = self.run_remove()
        self.assertFalse(changed["conf"])
        self.assertEqual([p.name for p in share.iterdir()], ["mine"])
        self.assertEqual(rc.read_text(), "# mine\n")
        self.assertTrue(cursor.conf_path().exists())
