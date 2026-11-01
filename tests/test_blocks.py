import unittest

from curiousj_framekit import blocks

RC = """\
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


class Names(unittest.TestCase):
    def test_finds_old_blocks(self):
        self.assertEqual(blocks.names(RC, blocks.OLD_PREFIX), ["top", "end"])
        self.assertEqual(blocks.names(RC, blocks.PREFIX), [])


class Remove(unittest.TestCase):
    def test_removes_both_and_tidies_blank_lines(self):
        text = blocks.remove(RC, "top", blocks.OLD_PREFIX)
        text = blocks.remove(text, "end", blocks.OLD_PREFIX)
        self.assertEqual(text, "#\n# ~/.bashrc\n#\nexport PATH=~/.local/bin:$PATH\n"
                               'eval "$(mise activate bash)"\n')
        self.assertEqual(blocks.remove(text, "top", blocks.OLD_PREFIX), text)

    def test_outside(self):
        self.assertIn("mise activate", blocks.outside(RC, blocks.OLD_PREFIX))
        self.assertNotIn("_sfu", blocks.outside(RC, blocks.OLD_PREFIX))


class Ensure(unittest.TestCase):
    def test_add_at_top_then_update_in_place(self):
        text = "export PATH=~/.local/bin:$PATH\n"
        once = blocks.ensure(text, "init", "source ~/x", "top")
        self.assertEqual(once, "# >>> curiousj-framekit: init >>>\nsource ~/x\n"
                               "# <<< curiousj-framekit: init <<<\n\nexport PATH=~/.local/bin:$PATH\n")
        self.assertEqual(blocks.ensure(once, "init", "source ~/x", "top"), once)
        twice = blocks.ensure(once + "more\n", "init", "source ~/y", "top")
        self.assertEqual(twice.count(">>> curiousj-framekit: init >>>"), 1)
        self.assertIn("source ~/y\n", twice)
        self.assertNotIn("source ~/x", twice)
        self.assertTrue(twice.endswith("more\n"))

    def test_add_at_end_and_empty_file(self):
        self.assertEqual(blocks.ensure("", "shims", "case x"),
                         "# >>> curiousj-framekit: shims >>>\ncase x\n# <<< curiousj-framekit: shims <<<\n")
        self.assertEqual(blocks.ensure("a", "shims", "b"),
                         "a\n# >>> curiousj-framekit: shims >>>\nb\n# <<< curiousj-framekit: shims <<<\n")

    def test_block_text(self):
        self.assertTrue(blocks.block(RC, "end", blocks.OLD_PREFIX).startswith("# >>> steam-frame-utils: end >>>\n"))
        self.assertIsNone(blocks.block(RC, "x", blocks.OLD_PREFIX))
