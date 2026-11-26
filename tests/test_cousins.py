"""Root cousins: families derived from the deck `root` field, in teaching order."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import _guard  # noqa: F401  -- patch load_config before tepi binds it
from tepi.cli import card_payload
from tepi.db import connect
from tepi.deck import Config, Deck, Entry
from tepi.engine import Session

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 9, 29)


def write_config(directory) -> Path:
    raw = {
        "newPerDay": 2,
        "reviewCap": 4,
        "catchUpReviewCap": 12,
        "catchUp": True,
        "knownIntervals": [1, 3, 7, 16, 30],
        "fuzzyDays": 2,
        "missedDays": 1,
    }
    path = Path(directory) / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _run(args, env):
    return subprocess.run(
        [sys.executable, "-m", "tepi", *args],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


class CousinsEngineTest(unittest.TestCase):
    def test_families_group_by_root_across_both_decks(self):
        from tepi.deck import load_curriculum
        from tepi.engine import cousin_families, cousins_of

        deck = load_curriculum(ROOT)
        families = cousin_families(deck)
        by_root = {family.root: family for family in families}
        self.assertEqual(len(deck.entries), 151)
        expected_roots = [
            "kerja",
            "komputer",
            "baca",
            "ajar",
            "jalan",
            "beli",
            "main",
            "cuci",
            "cakap",
            "bayar",
            "masak",
        ]
        self.assertEqual(set(by_root), set(expected_roots))
        self.assertEqual(len(by_root["komputer"].members), 2)
        for root in ("kerja", "baca", "ajar", "jalan", "beli", "main", "cuci"):
            self.assertEqual(len(by_root[root].members), 4)
        for root in ("cakap", "bayar", "masak"):
            self.assertEqual(len(by_root[root].members), 3)
        for family in families:
            self.assertTrue(all(member.root == family.root for member in family.members))
        # A root with one word has no cousins and is not a family.
        self.assertEqual(cousins_of(deck, deck.entry("air")), ())

    def test_members_and_families_follow_teaching_index(self):
        from tepi.deck import load_curriculum
        from tepi.engine import cousin_families, cousins_of

        deck = load_curriculum(ROOT)
        families = cousin_families(deck)
        first_indexes = [family.members[0].index for family in families]
        self.assertEqual(first_indexes, sorted(first_indexes))
        self.assertEqual(
            [family.root for family in families],
            ["kerja", "komputer", "baca", "ajar", "jalan", "beli", "main", "cuci", "cakap", "bayar", "masak"],
        )
        for family in families:
            indexes = [member.index for member in family.members]
            self.assertEqual(indexes, sorted(indexes))
        ajar = next(family for family in families if family.root == "ajar")
        self.assertEqual([member.id for member in ajar.members], ["ajar", "belajar", "pelajar", "pelajaran"])
        self.assertEqual(cousins_of(deck, deck.entry("belajar")), ("ajar", "pelajar", "pelajaran"))


class CousinsCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = os.environ.copy()
        self.env["TEPI_DATA_DIR"] = self.tmp.name
        self.env["TEPI_TODAY"] = TODAY.isoformat()
        self.env["TEPI_CONFIG"] = str(write_config(self.tmp.name))
        self.env["TEPI_TEST"] = "1"
        self.env["PYTHONPATH"] = str(ROOT)

    def test_cousins_command_returns_the_family_for_an_id(self):
        done = _run(["cousins", "belajar", "--json"], self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["root"], "ajar")
        self.assertEqual([member["id"] for member in payload["members"]], ["ajar", "belajar", "pelajar", "pelajaran"])

    def test_cousins_command_lists_every_family_in_root_order(self):
        done = _run(["cousins", "--json"], self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        families = json.loads(done.stdout)["families"]
        self.assertEqual(
            [family["root"] for family in families],
            ["kerja", "komputer", "baca", "ajar", "jalan", "beli", "main", "cuci", "cakap", "bayar", "masak"],
        )
        text = _run(["cousins"], self.env)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("ajar", text.stdout)
        self.assertIn("pelajaran", text.stdout)

    def test_cousins_unknown_id_gives_a_clear_error(self):
        done = _run(["cousins", "zzzz"], self.env)
        self.assertEqual(done.returncode, 2)
        self.assertIn("no word", done.stderr)

    def test_cousins_singleton_reports_no_cousins(self):
        done = _run(["cousins", "air", "--json"], self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["cousins"], [])
        text = _run(["cousins", "air"], self.env)
        self.assertIn("has no cousins", text.stdout)

    def test_cousins_never_opens_the_progress_log(self):
        done = _run(["cousins", "--json"], self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse((Path(self.tmp.name) / "tepi.sqlite").exists())


class CousinsChipPayloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "tepi.sqlite"

    def _deck(self):
        entries = (
            Entry("a", "a", "r", "A", "A.", "neutral", (), 0),
            Entry("b", "b", "r", "B", "B.", "neutral", ("a",), 1),
            Entry("c", "c", "c", "C", "C.", "neutral", (), 2),
        )
        return Deck(entries)

    def test_card_payload_carries_cousins_for_the_chip(self):
        deck = self._deck()
        config = Config(2, 4, (1, 3, 7, 16, 30), 2, 1)
        session = Session(connect(self.db), deck, config, TODAY)
        session.ensure_plan()
        session.reveal()
        session.reveal()
        card = session.presentation()
        self.assertEqual(card.mode, "rest")
        self.assertIsNotNone(card.entry)
        self.assertEqual(card.entry.id, "b")
        payload = card_payload(card, deck)
        self.assertEqual(payload["word"]["cousins"], ["a"])
        session.close()

    def test_card_payload_without_a_deck_keeps_cousins_empty(self):
        deck = self._deck()
        config = Config(2, 4, (1, 3, 7, 16, 30), 2, 1)
        session = Session(connect(self.db), deck, config, TODAY)
        session.ensure_plan()
        card = session.presentation()
        payload = card_payload(card)
        self.assertEqual(payload["word"]["cousins"], [])
        session.close()


if __name__ == "__main__":
    unittest.main()
