import unittest
from unittest import mock

from curiousj_framekit import cmdline
from curiousj_framekit.cmdline import Options
from curiousj_framekit.install import catalog, kinds
from curiousj_framekit.install.catalog import Item, State, Status


class Load(unittest.TestCase):
    def test_every_item_has_a_kind_module_and_trust(self):
        items = catalog.load()
        self.assertGreater(len(items), 6)
        for item in items.values():
            kind = kinds.for_item(item)
            self.assertTrue(hasattr(kind, "status"), item.name)
            self.assertIn("trust_root", item.data, item.name)
            self.assertIn("trust_checks", item.data, item.name)
            for need in item.needs:
                self.assertIn(need, items, f"{item.name} needs {need}")


class Resolve(unittest.TestCase):
    def test_needs_come_first_in_catalog_order(self):
        items = {"base": Item("base", "config", "b"), "other": Item("other", "config", "o"),
                 "app": Item("app", "config", "a", ("base",))}
        names = [it.name for it in catalog.resolve(items, ["app"])]
        self.assertEqual(names, ["base", "app"])
        names = [it.name for it in catalog.resolve(catalog.load(), ["krdc", "cursor"])]
        self.assertEqual(names, ["cursor", "krdc"])

    def test_unknown_and_cycle(self):
        items = catalog.load()
        with self.assertRaises(cmdline.Error):
            catalog.resolve(items, ["nothing"])
        fake = {"a": Item("a", "config", "a", ("b",)), "b": Item("b", "config", "b", ("a",))}
        with self.assertRaises(cmdline.Error) as cm:
            catalog.resolve(fake, ["a"])
        self.assertIn("cycle", str(cm.exception))


class SimpleInstalls(unittest.TestCase):
    def test_a_simple_install_is_not_an_item(self):
        """What brew, mise, flatpak or uv installs, or an upstream's own
        instructions do, is docs/simple-installs.md's, not the
        catalog's."""
        self.assertFalse({"homebrew", "zsh", "rust", "distrobox", "curiousj-tools", "stream-frame",
                          "moonlight", "deskflow", "bsmanager", "full-keyboard", "nerd-fonts",
                          "frametop"} & set(catalog.load()))
        self.assertEqual({it.kind for it in catalog.load().values()},
                         {"config", "system-service", "pacman-home"})


class Needs(unittest.TestCase):
    def test_refusal_names_the_install(self):
        with mock.patch.object(catalog, "status_of", return_value=Status(State.MISSING)):
            with self.assertRaises(cmdline.Error) as cm:
                catalog.needs("krdpserver", "rdp")
        self.assertEqual(str(cm.exception), "rdp needs the krdpserver item (KRdp's server, built here for ~/.local against the host's libraries): cjf install krdpserver")

    def test_silent_when_installed(self):
        with mock.patch.object(catalog, "status_of", return_value=Status(State.OK, "abc")):
            catalog.needs("krdpserver", "rdp")


class Commands(unittest.TestCase):
    def test_split_words(self):
        from curiousj_framekit.install import commands
        items = catalog.load()
        self.assertEqual(commands.split_words(items, ["tailscale", "waypipe"]), (["tailscale", "waypipe"], []))
        self.assertEqual(commands.split_words(items, ["tailscale", "--trust", "x"]),
                         (["tailscale"], ["--trust", "x"]))
        with self.assertRaises(cmdline.Error):
            commands.split_words(items, ["tailscale", "krdpserver", "--yes"])
        with self.assertRaises(cmdline.Error):
            commands.split_words(items, ["nothing"])

    def test_state_lines(self):
        from curiousj_framekit.install import commands
        items = {"a": Item("a", "config", "the a thing", data={"trust_root": "r", "trust_checks": "c"})}
        lines = commands.state_lines(items, {"a": Status(State.OK, "1.0")}, trust=True)
        self.assertEqual(lines[0].splitlines()[0], "ok        a  the a thing [1.0]")
        self.assertIn("trust: r; checks: c", lines[0])


class Uninstall(unittest.TestCase):
    """An item that an installed item needs is not removed: wayvr needs
    xwayland-satellite, and only the catalog says so."""

    def run_uninstall(self, state: State):
        from click.testing import CliRunner
        from curiousj_framekit import cli, where
        from curiousj_framekit.install import commands
        kind = mock.Mock()
        kind.uninstall.return_value = True
        with mock.patch.object(where, "require_frame"), \
                mock.patch.object(catalog, "status_of", return_value=Status(state)), \
                mock.patch.object(commands.kinds, "for_item", return_value=kind):
            result = CliRunner().invoke(cli.cli, ["uninstall", "xwayland-satellite"])
        return result, kind

    def test_refused_while_a_dependant_is_installed(self):
        result, kind = self.run_uninstall(State.OK)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("wayvr needs xwayland-satellite: cjf uninstall wayvr first", result.output + str(result.exception))
        kind.uninstall.assert_not_called()

    def test_removed_when_no_dependant_is_installed(self):
        result, kind = self.run_uninstall(State.MISSING)
        self.assertEqual(result.exit_code, 0, result.output)
        kind.uninstall.assert_called_once()
