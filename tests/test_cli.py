import contextlib
import io
import unittest
from unittest import mock

from click.testing import CliRunner

from curiousj_framekit import cli, cmdline, where
from curiousj_framekit.frame import versions

FRAME = {"ID": "steamos", "VARIANT_ID": "vr", "VERSION_ID": "0.5.6", "BUILD_ID": "1"}
CACHY = {"ID": "cachyos", "PRETTY_NAME": "CachyOS Linux"}


class Help(unittest.TestCase):
    def test_help_lists_status(self):
        result = CliRunner().invoke(cli.cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("cjf -- curiousj's kit for the Steam Frame.", result.output)
        self.assertRegex(result.output, r"\n    status +the versions")
        for name in ("cursor", "wifi", "vr", "controllers", "rdp", "panel"):
            self.assertRegex(result.output, rf"\n    {name} +\S")
            self.assertIn(name, cli.cli.commands)
        self.assertIn("--check", result.output)

    def test_menu_lines_for_the_picker(self):
        lines = cli.menu_lines(cli.entries(cli.cli))
        self.assertTrue(any(line.startswith("status  ") for line in lines))
        self.assertTrue(any(line.startswith("uninstall NAME  ") for line in lines))


def picks(*lines):
    """A pick.choose that answers with the item whose label is next in
    lines, and records each menu's prompt and header."""
    it = iter(lines)
    seen = []

    def choose(items, prompt, header=""):
        seen.append((prompt, header))
        want = next(it)
        return next(i for i in items if i.split("  ")[0].rstrip() == want)
    choose.seen = seen
    return choose


TTY = mock.Mock(isatty=lambda: True)


class Menu(unittest.TestCase):
    def pick(self, choose, ask=None):
        with mock.patch("sys.stdin", TTY), mock.patch.object(cli.pick, "choose", choose):
            ctx = cli.cli.make_context("cjf", [], resilient_parsing=True)
            return cli.pick_argv(ctx, ask or (lambda name: self.fail(f"asked for {name}")))

    def run_bare(self, choose, argv=()):
        """cjf run bare with the picks given: status, stdout, stderr."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", TTY), mock.patch.object(cli.pick, "choose", choose), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_a_plain_command_runs_as_it_is(self):
        self.assertEqual(self.pick(picks("status")), ["status"])

    def test_a_group_gets_a_second_menu(self):
        choose = picks("rdp", "start")
        self.assertEqual(self.pick(choose), ["rdp", "start"])
        self.assertEqual(choose.seen[0][0], "cjf>")
        self.assertEqual(choose.seen[0][1].splitlines(),
                         ["cjf -- curiousj's kit for the Steam Frame.", "ENTER runs the command"])
        self.assertEqual(choose.seen[1][0], "cjf rdp>")
        self.assertEqual(choose.seen[1][1].splitlines(),
                         ["cjf rdp -- serve a Plasma desktop on the Frame over RDP",
                          "ENTER runs the command"])

    def test_vr_offers_its_actions(self):
        self.assertEqual(self.pick(picks("vr", "status")), ["vr"])
        self.assertEqual(self.pick(picks("vr", "off left")), ["vr", "off", "left"])

    def test_help_at_either_level(self):
        self.assertEqual(self.pick(picks("help")), ["--help"])
        self.assertEqual(self.pick(picks("pkg", "help")), ["pkg", "--help"])

    def test_a_required_argument_is_asked_for(self):
        asked = []

        def ask(name):
            asked.append(name)
            return "emacs"
        self.assertEqual(self.pick(picks("uninstall NAME"), ask), ["uninstall", "emacs"])
        self.assertEqual(self.pick(picks("cursor", "theme NAME"), ask), ["cursor", "theme", "emacs"])
        self.assertEqual(self.pick(picks("controllers", "off NAME"), ask),
                         ["controllers", "off", "emacs"])
        self.assertEqual(asked, ["NAME"] * 3)

    def test_leaving_a_menu_or_a_question_aborts(self):
        with self.assertRaises(cmdline.Abort):
            self.pick(lambda items, prompt, header="": None)
        with self.assertRaises(cmdline.Abort), mock.patch("builtins.input", return_value=""):
            self.pick(picks("uninstall NAME"), cli.ask_value)
        with self.assertRaises(cmdline.Abort), mock.patch("builtins.input", side_effect=EOFError):
            self.pick(picks("uninstall NAME"), cli.ask_value)
        with mock.patch("builtins.input", return_value=" emacs "):
            self.assertEqual(self.pick(picks("uninstall NAME"), cli.ask_value),
                             ["uninstall", "emacs"])

    def test_the_menu_lists_every_command_with_its_required_arguments(self):
        labels = [e.label for e in cli.entries(cli.cli)]
        self.assertEqual(labels, sorted(labels))
        self.assertIn("uninstall NAME", labels)
        self.assertEqual([e.label for e in cli.entries(cli.cli.commands["cursor"])],
                         ["apply", "size", "software", "theme NAME"])
        self.assertEqual([e.label for e in cli.entries(cli.cli.commands["pkg"])],
                         ["build", "homeify NAME", "outdated"])
        self.assertIsNone(cli.entries(cli.cli.commands["status"]))

    def test_bare_runs_the_pick_and_says_what_ran(self):
        from curiousj_framekit.install import status as status_mod
        with mock.patch.object(where, "os_release", return_value=FRAME), \
             mock.patch.object(where, "in_container", return_value=False), \
             mock.patch.object(versions, "rows", return_value=[]), \
             mock.patch.object(status_mod, "kit_line", return_value="kit"), \
             mock.patch.object(status_mod, "live_lines", return_value=[]):
            code, out, err = self.run_bare(picks("status"))
        self.assertEqual(code, 0, out + err)
        self.assertEqual(err, "ran: cjf status\n")

    def test_help_entry_prints_the_help(self):
        code, out, err = self.run_bare(picks("rdp", "help"))
        self.assertEqual(code, 0, out + err)
        self.assertIn("cjf rdp -- serve a Plasma desktop", out)
        self.assertEqual(err, "ran: cjf rdp --help\n")
        code, out, err = self.run_bare(picks("help"))
        self.assertEqual(code, 0, out + err)
        self.assertIn("cjf -- curiousj's kit for the Steam Frame.", out)
        self.assertEqual(err, "ran: cjf --help\n")

    def test_the_options_reach_the_picked_command(self):
        seen = {}
        with mock.patch.object(where, "require_host", side_effect=lambda *a: None), \
             mock.patch("curiousj_framekit.frame.rdp.instance_pid",
                        side_effect=lambda opts: seen.setdefault("opts", opts) and None):
            code, out, err = self.run_bare(picks("rdp", "stop"), ["--yes", "-v"])
        self.assertEqual(code, 0, out + err)
        self.assertTrue(seen["opts"].yes)
        self.assertEqual(seen["opts"].verbose, 1)
        self.assertEqual(out, "not running\n")
        self.assertEqual(err, "ran: cjf rdp stop\n")

    def test_a_failure_still_says_what_ran(self):
        with mock.patch.object(where, "os_release", return_value=CACHY):
            code, out, err = self.run_bare(picks("vr", "off"))
        self.assertEqual(code, 1)
        self.assertEqual(err.splitlines(), ["ran: cjf vr off",
                                            "cjf: vr runs on the Frame; this is a PC (CachyOS Linux)"])

    def test_leaving_the_menu_runs_nothing_and_says_nothing(self):
        code, out, err = self.run_bare(lambda items, prompt, header="": None)
        self.assertEqual(code, 130)
        self.assertEqual(out + err, "")
