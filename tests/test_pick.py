import io
import unittest

from curiousj_framekit import cmdline, pick

ITEMS = ["alpha", "beta", "gamma"]


def answers(*replies):
    it = iter(replies)
    return lambda prompt: next(it)


class ParseMenuReply(unittest.TestCase):
    def test_numbers_all_abort_junk(self):
        self.assertEqual(pick.parse_menu_reply("1 3", 3), [1, 3])
        self.assertEqual(pick.parse_menu_reply("2,3", 3), [2, 3])
        self.assertEqual(pick.parse_menu_reply("a", 3), [])
        self.assertIsNone(pick.parse_menu_reply("", 3))
        self.assertIsNone(pick.parse_menu_reply("q", 3))
        with self.assertRaises(ValueError):
            pick.parse_menu_reply("9", 3)


class MenuPick(unittest.TestCase):
    def test_choice_and_reprompt(self):
        out = io.StringIO()
        self.assertEqual(pick.menu_pick(ITEMS, "items", answers("9", "1 3"), out),
                         ["alpha", "gamma"])
        self.assertIn("  1) alpha", out.getvalue())
        self.assertIn("not a choice: 9", out.getvalue())

    def test_abort(self):
        with self.assertRaises(cmdline.Abort):
            pick.menu_pick(ITEMS, "items", answers("q"), io.StringIO())


class ChooseNumbered(unittest.TestCase):
    def test_number_name_and_quit(self):
        out = io.StringIO()
        self.assertEqual(pick.choose_numbered(ITEMS, "cjf>", "", answers("2"), out), "beta")
        self.assertEqual(pick.choose_numbered(ITEMS, "cjf>", "", answers("gamma"), out), "gamma")
        self.assertIsNone(pick.choose_numbered(ITEMS, "cjf>", "", answers("q"), out))
        self.assertEqual(pick.choose_numbered(ITEMS, "cjf>", "h", answers("x", "1"), out), "alpha")
        self.assertIn("h\n", out.getvalue())
        self.assertIn("not a choice: x", out.getvalue())
