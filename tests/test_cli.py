import unittest
from unittest import mock

from click.testing import CliRunner

from curiousj_framekit import cli, where
from curiousj_framekit.frame import versions

FRAME = {"ID": "steamos", "VARIANT_ID": "vr", "VERSION_ID": "0.5.6", "BUILD_ID": "1"}
CACHY = {"ID": "cachyos", "PRETTY_NAME": "CachyOS Linux"}


class Help(unittest.TestCase):
    def test_help_lists_status(self):
        result = CliRunner().invoke(cli.cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("cjf -- curiousj's kit for the Steam Frame.", result.output)
        self.assertIn("status      the versions", result.output)
        self.assertIn("--check", result.output)

    def test_command_lines_for_the_picker(self):
        lines = cli.command_lines(cli.cli)
        self.assertTrue(any(line.startswith("status  ") for line in lines))


class Status(unittest.TestCase):
    def test_refuses_on_a_pc(self):
        with mock.patch.object(where, "os_release", return_value=CACHY):
            code = cli.main(["status"])
        self.assertEqual(code, 1)

    def test_prints_rows_on_the_frame(self):
        rows = [versions.Row("SteamOS", "0.5.6", "build 1, beta channel")]
        with mock.patch.object(where, "os_release", return_value=FRAME), \
             mock.patch.object(where, "in_container", return_value=False), \
             mock.patch.object(versions, "rows", return_value=rows):
            result = CliRunner().invoke(cli.cli, ["status"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.output, "SteamOS       0.5.6       build 1, beta channel\n")

    def test_bare_without_a_terminal_is_a_usage_error(self):
        code = cli.main([])
        self.assertEqual(code, 2)
