import tempfile
import unittest
from pathlib import Path

from curiousj_framekit.beatsaber import recent

LOG = """\
Mono path[0] = 'Z:/x'
[2026-10-28T18:13:43] custom_level_32dff (Queencard - eurnkung) [BeatmapLevel: -1/BeatmapLevelData: 1]
some other line
[2026-10-28T18:16:57] Overkill [BeatmapLevel: 0/BeatmapLevelData: 1]
"""
PREV = "[2026-10-27T20:00:00] Ghost [BeatmapLevel: 0/x]\n"


class Songs(unittest.TestCase):
    def test_lines_keyed_by_the_launch(self):
        self.assertEqual(recent.songs_in(LOG), [
            "2026-10-28T18:13:43\t2026-10-28T18:13:43\tcustom_level_32dff (Queencard - eurnkung)",
            "2026-10-28T18:13:43\t2026-10-28T18:16:57\tOverkill",
        ])
        self.assertEqual(recent.songs_in("nothing\n"), [])

    def test_both_logs_prev_first(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Player-prev.log").write_text(PREV)
            (Path(d) / "Player.log").write_text(LOG)
            lines = recent.songs_from_logs(Path(d))
            self.assertEqual(len(lines), 3)
            self.assertTrue(lines[0].startswith("2026-10-27T20:00:00\t"))


class Display(unittest.TestCase):
    lines = recent.songs_in(PREV) + recent.songs_in(LOG)

    def test_sessions_and_custom_names(self):
        self.assertEqual(recent.display(self.lines, 0), """\
Session of 2026-10-27
2026-10-27 20:00  Ghost

Session of 2026-10-28
2026-10-28 18:13  Queencard - eurnkung (custom)
2026-10-28 18:16  Overkill""")

    def test_last_n(self):
        self.assertEqual(recent.display(self.lines, 1), """\
Session of 2026-10-28
2026-10-28 18:13  Queencard - eurnkung (custom)
2026-10-28 18:16  Overkill""")
        self.assertEqual(recent.display(self.lines, 5), recent.display(self.lines, 0))

    def test_duplicates_collapse(self):
        self.assertEqual(recent.display(self.lines + self.lines, 0), recent.display(self.lines, 0))


class Hook(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(recent.hook_for("/home/steamos/.local/bin/beat-saber-recent"),
                         "/home/steamos/.local/bin/beat-saber-recent --record; %command%; "
                         "/home/steamos/.local/bin/beat-saber-recent --record")

    def test_history_missing_files(self):
        self.assertEqual(recent.read_history(Path("/nonexistent/a"), Path("/nonexistent/b")), [])
