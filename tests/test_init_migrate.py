"""cjf init and cjf migrate against a fake HOME laid out as the Frame's
was after setup.sh. No desktop runs there, Steam's debug port is faked."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from curiousj_framekit import blocks, config
from curiousj_framekit.cmdline import Options
from curiousj_framekit.frame import cursor, steam
from curiousj_framekit.install import init, migrate

BASHRC = """\
# >>> steam-frame-utils: top >>>
# https://github.com/curiousjtuber/steam-frame-utils#shell-init
for _sfu in brew frametop bin; do
    _sfu="$HOME/steam-frame-utils/shell-init/$_sfu.sh"
    [[ -r $_sfu ]] && source "$_sfu"
done
unset _sfu
# <<< steam-frame-utils: top <<<
#
# ~/.bashrc
#
export PATH=~/.local/bin:$PATH
eval "$(mise activate bash)"
# >>> steam-frame-utils: end >>>
for _sfu in waypipe tailscale; do
    _sfu="$HOME/steam-frame-utils/shell-init/$_sfu.sh"
    [[ -r $_sfu ]] && source "$_sfu"
done
unset _sfu
# <<< steam-frame-utils: end <<<
"""
DISTROBOXRC = """\
# >>> steam-frame-utils: podman >>>
case $PATH in
  "$HOME/steam-frame-utils/bin:"*) ;;
  *) PATH="$HOME/steam-frame-utils/bin:$PATH" ;;
esac
# <<< steam-frame-utils: podman <<<
"""
OLD_HOOK = ("/home/steamos/steam-frame-utils/bin/beat-saber-recent --record; %command%; "
            "/home/steamos/steam-frame-utils/bin/beat-saber-recent --record")


class FakeSteam:
    def __init__(self, was):
        self.was = was
        self.calls = []

    def launch_options(self, appid, set_to=None, force=False):
        self.calls.append((appid, set_to, force))
        if set_to is None:
            return {"was": self.was}
        self.was = set_to
        return {"was": OLD_HOOK, "now": set_to}


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


class Migrate(FakeHome):
    def setUp(self):
        super().setUp()
        (self.home / ".bashrc").write_text(BASHRC)
        (self.home / ".zshrc").write_text(BASHRC.replace("bash", "zsh"))
        (self.home / ".profile").write_text("export PATH=~/.local/bin:$PATH\n")
        (self.home / ".distroboxrc").write_text(DISTROBOXRC)
        conf = self.home / ".config/environment.d" / cursor.CONF_NAME
        conf.parent.mkdir(parents=True)
        conf.write_text("# steam-frame-utils: sw-cursor on\nKWIN_FORCE_SW_CURSOR=1\n")
        old_entry = self.home / ".config/autostart" / cursor.OLD_ENTRY_NAME
        old_entry.parent.mkdir(parents=True)
        old_entry.write_text("[Desktop Entry]\nName=steam-frame-utils cursor size\nExec=x --apply\n")
        hist = self.home / ".local/state/steam-frame-utils/beat-saber-songs.tsv"
        hist.parent.mkdir(parents=True)
        hist.write_text("a\ta\tOld Song\n")
        menu = self.home / migrate.MENU_ENTRY
        menu.parent.mkdir(parents=True)
        menu.write_text("[Desktop Entry]\nName=KRdp Server\nExec=/home/steamos/steam-frame-utils/bin/krdpd-gui\n")
        bindir = self.home / ".local/bin"
        bindir.mkdir(parents=True)
        (bindir / "podman").write_text("#!/bin/sh\n# steam-frame-utils: podman ...\nexec podman\n")
        (bindir / "mine").write_text("#!/bin/sh\n# my own script\n")
        self.fake = FakeSteam(OLD_HOOK)
        self.steam = mock.patch.object(steam, "launch_options", self.fake.launch_options)
        self.steam.start()
        self.old_hist = mock.patch.object(migrate.recent, "OLD_HIST",
                                          self.home / ".local/state/steam-frame-utils/beat-saber-songs.tsv")
        self.old_hist.start()

    def tearDown(self):
        self.old_hist.stop()
        self.steam.stop()
        super().tearDown()

    def run_migrate(self, **kw):
        from click.testing import CliRunner
        with mock.patch("curiousj_framekit.where.require_frame", lambda what="": None):
            return CliRunner().invoke(migrate.migrate, [], obj=Options(yes=True, **kw))

    def test_everything_moves_over(self):
        result = self.run_migrate()
        self.assertEqual(result.exit_code, 0, result.output)
        for rc in (".bashrc", ".zshrc", ".distroboxrc"):
            text = (self.home / rc).read_text()
            self.assertEqual(blocks.names(text, blocks.OLD_PREFIX), [], rc)
            self.assertEqual(len(blocks.names(text, blocks.PREFIX)), 1, rc)
        bashrc = (self.home / ".bashrc").read_text()
        self.assertIn('eval "$(mise activate bash)"', bashrc)
        self.assertEqual(bashrc.count("/.local/bin:$PATH"), 1)
        self.assertIn("activates mise on a line of its own", result.output)
        # the cursor: choice carried, old entry replaced
        self.assertIs(config.get("cursor", "software"), True)
        self.assertFalse((self.home / ".config/autostart" / cursor.OLD_ENTRY_NAME).exists())
        self.assertTrue((self.home / ".config/autostart" / cursor.ENTRY_NAME).is_file())
        # launch options
        self.assertEqual(self.fake.was, f"{self.home}/.local/bin/beat-saber-recent --record; %command%; "
                                        f"{self.home}/.local/bin/beat-saber-recent --record")
        # history moved and merged
        self.assertFalse((self.home / ".local/state/steam-frame-utils").exists())
        self.assertEqual((self.home / ".local/state/curiousj-framekit/beat-saber-songs.tsv").read_text(),
                         "a\ta\tOld Song\n")
        # menu entry
        self.assertIn("rdp gui\n", (self.home / migrate.MENU_ENTRY).read_text())
        # old copies
        names = sorted(p.name for p in (self.home / ".local/bin").iterdir())
        self.assertNotIn("podman", names)
        self.assertTrue(any(n.startswith("podman.bak-") for n in names))
        self.assertIn("mine", names)

    def test_second_run_finds_nothing(self):
        self.run_migrate()
        result = self.run_migrate()
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("nothing to do", result.output)

    def test_check_touches_nothing(self):
        result = self.run_migrate(check=True)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual((self.home / ".bashrc").read_text(), BASHRC)
        self.assertEqual(self.fake.was, OLD_HOOK)
        self.assertTrue((self.home / ".local/state/steam-frame-utils/beat-saber-songs.tsv").exists())
        self.assertIn("run without --check to apply", result.output)


class NewHook(unittest.TestCase):
    def test_replaces_only_the_old_path(self):
        self.assertEqual(migrate.new_hook(OLD_HOOK, "/h/.local/bin/beat-saber-recent"),
                         "/h/.local/bin/beat-saber-recent --record; %command%; /h/.local/bin/beat-saber-recent --record")
        self.assertIsNone(migrate.new_hook("", "/x"))
        self.assertIsNone(migrate.new_hook("gamemoderun %command%", "/x"))
