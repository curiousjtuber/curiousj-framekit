import io
import os
import tempfile
import unittest
from pathlib import Path

from curiousj_framekit import cmdline
from curiousj_framekit.cmdline import Options


def answers(*replies):
    it = iter(replies)
    return lambda prompt: next(it)


class Confirm(unittest.TestCase):
    def test_check_says_no_yes_says_yes(self):
        self.assertFalse(cmdline.confirm(Options(check=True), "go?", True, answers("y")))
        self.assertTrue(cmdline.confirm(Options(yes=True), "go?", False, answers("n")))

    def test_enter_takes_the_default(self):
        self.assertTrue(cmdline.confirm(Options(), "go?", True, answers("")))
        self.assertFalse(cmdline.confirm(Options(), "go?", False, answers("")))

    def test_answers_and_reprompt(self):
        self.assertTrue(cmdline.confirm(Options(), "go?", False, answers("yes")))
        self.assertFalse(cmdline.confirm(Options(), "go?", True, answers("N")))
        self.assertTrue(cmdline.confirm(Options(), "go?", False, answers("maybe", "y")))

    def test_eof_aborts(self):
        def eof(prompt):
            raise EOFError
        with self.assertRaises(cmdline.Abort):
            cmdline.confirm(Options(), "go?", True, eof)


class Tilde(unittest.TestCase):
    def test_home_becomes_tilde(self):
        home = str(Path.home())
        self.assertEqual(cmdline.tilde(home + "/.bashrc"), "~/.bashrc")
        self.assertEqual(cmdline.tilde(home), "~")
        self.assertEqual(cmdline.tilde(home + "x/y"), home + "x/y")
        self.assertEqual(cmdline.tilde("/etc/os-release"), "/etc/os-release")


class WriteFile(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "sub" / "rc"
        self.out = io.StringIO()

    def tearDown(self):
        self.dir.cleanup()

    def test_create(self):
        changed = cmdline.write_file(Options(yes=True), self.path, "a\n", out=self.out)
        self.assertTrue(changed)
        self.assertEqual(self.path.read_text(), "a\n")
        self.assertIn("create", self.out.getvalue())
        self.assertEqual(os.listdir(self.path.parent), ["rc"])

    def test_unchanged_is_ok_and_false(self):
        self.path.parent.mkdir()
        self.path.write_text("a\n")
        changed = cmdline.write_file(Options(), self.path, "a\n", ask=answers(), out=self.out)
        self.assertFalse(changed)
        self.assertIn("ok", self.out.getvalue())

    def test_change_shows_diff_and_backs_up(self):
        self.path.parent.mkdir()
        self.path.write_text("a\nb\n")
        changed = cmdline.write_file(Options(), self.path, "a\nc\n", ask=answers("y"), out=self.out)
        self.assertTrue(changed)
        self.assertEqual(self.path.read_text(), "a\nc\n")
        text = self.out.getvalue()
        self.assertIn("-b\n+c\n", text)
        self.assertIn("backup", text)
        backups = [n for n in os.listdir(self.path.parent) if n.startswith("rc.bak-")]
        self.assertEqual(len(backups), 1)
        self.assertEqual((self.path.parent / backups[0]).read_text(), "a\nb\n")

    def test_no_means_no(self):
        self.path.parent.mkdir()
        self.path.write_text("a\n")
        changed = cmdline.write_file(Options(), self.path, "b\n", ask=answers("n"), out=self.out)
        self.assertFalse(changed)
        self.assertEqual(self.path.read_text(), "a\n")
        self.assertEqual(os.listdir(self.path.parent), ["rc"])

    def test_check_reports_and_writes_nothing(self):
        changed = cmdline.write_file(Options(check=True), self.path, "a\n", ask=answers(), out=self.out)
        self.assertFalse(changed)
        self.assertFalse(self.path.exists())
        self.assertIn("would create", self.out.getvalue())

    def test_mode(self):
        cmdline.write_file(Options(yes=True), self.path, "#!/bin/sh\n", mode=0o755, out=self.out)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o755)


class Run(unittest.TestCase):
    def test_missing_command_is_an_error(self):
        with self.assertRaises(cmdline.Error) as cm:
            cmdline.run(Options(), ["no-such-command-xyz"])
        self.assertIn("missing required command", str(cm.exception))

    def test_failure_names_the_command(self):
        with self.assertRaises(cmdline.Error) as cm:
            cmdline.run(Options(), ["sh", "-c", "echo bad >&2; exit 3"], capture=True)
        self.assertIn("sh failed (exit 3): bad", str(cm.exception))

    def test_output_default_on_missing_or_failing(self):
        self.assertIsNone(cmdline.output(Options(), ["no-such-command-xyz"]))
        self.assertEqual(cmdline.output(Options(), ["sh", "-c", "exit 1"], default="?"), "?")
        self.assertEqual(cmdline.output(Options(), ["sh", "-c", "echo  hi "]), "hi")


class RunMain(unittest.TestCase):
    def test_error_is_one_line_with_prog(self):
        import click

        @click.command(cls=cmdline.Command, help="t")
        def c():
            raise cmdline.Error("went wrong")

        err = io.StringIO()
        with unittest.mock.patch("sys.stderr", err):
            code = cmdline.run_main(c, [], "cjf")
        self.assertEqual(code, 1)
        self.assertEqual(err.getvalue(), "cjf: went wrong\n")

    def test_abort_is_130(self):
        import click

        @click.command(cls=cmdline.Command, help="t")
        def c():
            raise cmdline.Abort

        self.assertEqual(cmdline.run_main(c, [], "cjf"), 130)


import unittest.mock  # noqa: E402
