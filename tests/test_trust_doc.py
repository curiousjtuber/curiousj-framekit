"""docs/TRUST.md's table is generated from the catalog's trust columns;
this fails when an item is added or its columns change without the
table following."""

import unittest
from pathlib import Path

from curiousj_framekit.install import catalog

TRUST = Path(__file__).resolve().parents[1] / "docs" / "TRUST.md"


class TrustTable(unittest.TestCase):
    def test_every_item_has_its_row(self):
        text = TRUST.read_text()
        for item in catalog.load().values():
            row = f"| `{item.name}` | {item['trust_root']} | {item['trust_checks']} |"
            self.assertIn(row, text, f"{item.name}: regenerate the table in docs/TRUST.md")

    def test_no_row_for_an_item_that_is_gone(self):
        names = set(catalog.load())
        for line in TRUST.read_text().splitlines():
            if line.startswith("| `") and line.count("|") == 4:
                name = line.split("`")[1]
                self.assertIn(name, names, f"docs/TRUST.md names {name}, which the catalog doesn't have")
