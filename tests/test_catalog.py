import unittest
from unittest import mock

from curiousj_framekit import cmdline
from curiousj_framekit.cmdline import Options
from curiousj_framekit.install import catalog, kinds
from curiousj_framekit.install.catalog import Item, State, Status


class Load(unittest.TestCase):
    def test_every_item_has_a_kind_module_and_trust(self):
        items = catalog.load()
        self.assertGreater(len(items), 15)
        for item in items.values():
            kind = kinds.for_item(item)
            self.assertTrue(hasattr(kind, "status"), item.name)
            self.assertIn("trust_root", item.data, item.name)
            self.assertIn("trust_checks", item.data, item.name)
            for need in item.needs:
                self.assertIn(need, items, f"{item.name} needs {need}")

    def test_upstream_items_name_a_known_installer(self):
        from curiousj_framekit.install.kinds import upstream
        for item in catalog.load().values():
            if item.kind == "upstream":
                self.assertIn(item["installer"], upstream.INSTALLERS, item.name)


class Resolve(unittest.TestCase):
    def test_needs_come_first_in_catalog_order(self):
        items = catalog.load()
        names = [it.name for it in catalog.resolve(items, ["zsh"])]
        self.assertEqual(names, ["homebrew", "zsh"])
        names = [it.name for it in catalog.resolve(items, ["moonlight", "cursor"])]
        self.assertEqual(names, ["cursor", "moonlight"])

    def test_unknown_and_cycle(self):
        items = catalog.load()
        with self.assertRaises(cmdline.Error):
            catalog.resolve(items, ["nothing"])
        fake = {"a": Item("a", "config", "a", ("b",)), "b": Item("b", "config", "b", ("a",))}
        with self.assertRaises(cmdline.Error) as cm:
            catalog.resolve(fake, ["a"])
        self.assertIn("cycle", str(cm.exception))


class Needs(unittest.TestCase):
    def test_refusal_names_the_install(self):
        with mock.patch.object(catalog, "status_of", return_value=Status(State.MISSING)):
            with self.assertRaises(cmdline.Error) as cm:
                catalog.needs("krdp", "rdp")
        self.assertEqual(str(cm.exception), "rdp needs the krdp item (KRdp's server, built here as a Flatpak): cjf install krdp")

    def test_silent_when_installed(self):
        with mock.patch.object(catalog, "status_of", return_value=Status(State.OK, "abc")):
            catalog.needs("krdp", "rdp")


class Commands(unittest.TestCase):
    def test_split_words(self):
        from curiousj_framekit.install import commands
        items = catalog.load()
        self.assertEqual(commands.split_words(items, ["tailscale", "waypipe"]), (["tailscale", "waypipe"], []))
        self.assertEqual(commands.split_words(items, ["frametop", "--version", "0.2.3", "--yes"]),
                         (["frametop"], ["--version", "0.2.3", "--yes"]))
        with self.assertRaises(cmdline.Error):
            commands.split_words(items, ["frametop", "krdp", "--bundle"])
        with self.assertRaises(cmdline.Error):
            commands.split_words(items, ["nothing"])

    def test_state_lines(self):
        from curiousj_framekit.install import commands
        items = {"a": Item("a", "config", "the a thing", data={"trust_root": "r", "trust_checks": "c"})}
        lines = commands.state_lines(items, {"a": Status(State.OK, "1.0")}, trust=True)
        self.assertEqual(lines[0].splitlines()[0], "ok        a  the a thing [1.0]")
        self.assertIn("trust: r; checks: c", lines[0])
