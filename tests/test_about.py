"""The --about hint: prefer a settled word or cousin, else fall back."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import _guard  # noqa: F401  -- patch load_config before tepi binds it
from tepi.db import connect
from tepi.deck import Entry, load_curriculum
from tepi.engine import Learned

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


def _entry(word_id, lemma, root, sentence, index):
    return Entry(word_id, lemma, root, lemma.upper(), sentence, "neutral", (), index)


def _settled(entry):
    return Learned(entry, date(2026, 9, 1), None, 5, "settled")


def _attestation(*rows):
    return {
        "authority": "kamus-dewan-perdana",
        "checked": "2026-11-19",
        "words": [{"id": word_id, "lemma": lemma, "status": status} for word_id, lemma, status in rows],
    }


def _family_fixture():
    entries = [
        _entry("belajar", "belajar", "ajar", "Belajar.", 0),
        _entry("pelajar", "pelajar", "ajar", "Pelajar.", 1),
        _entry("air", "air", "air", "Air.", 2),
    ]
    settled = tuple(_settled(entry) for entry in entries)
    attestation = _attestation(
        ("belajar", "belajar", "headword"),
        ("pelajar", "pelajar", "headword"),
        ("air", "air", "headword"),
    )
    return settled, attestation


def _run(args, env):
    return subprocess.run(
        [sys.executable, "-m", "tepi", *args],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


class AboutEngineTest(unittest.TestCase):
    def test_about_picks_the_matching_settled_word(self):
        from tepi.engine import prompt_sentence

        settled, attestation = _family_fixture()
        prompt = prompt_sentence(settled, attestation, about="pelajar")
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.entry.id, "pelajar")
        self.assertEqual(prompt.sentence, "Pelajar.")

    def test_about_a_root_picks_a_settled_cousin(self):
        from tepi.engine import prompt_sentence

        settled, attestation = _family_fixture()
        prompt = prompt_sentence(settled, attestation, about="ajar")
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.entry.root, "ajar")
        self.assertEqual(prompt.entry.id, "belajar")

    def test_about_prefers_a_match_even_when_it_comes_later(self):
        from tepi.engine import prompt_sentence

        settled, attestation = _family_fixture()
        prompt = prompt_sentence(settled, attestation, about="air")
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.entry.id, "air")

    def test_about_an_unknown_hint_falls_back_to_the_first_eligible(self):
        from tepi.engine import prompt_sentence

        settled, attestation = _family_fixture()
        prompt = prompt_sentence(settled, attestation, about="zzzz")
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.entry.id, "belajar")

    def test_about_with_nothing_settled_returns_none(self):
        from tepi.engine import prompt_sentence

        _, attestation = _family_fixture()
        self.assertIsNone(prompt_sentence((), attestation, about="ajar"))


class AboutCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = os.environ.copy()
        self.env["TEPI_DATA_DIR"] = self.tmp.name
        self.env["TEPI_TODAY"] = TODAY.isoformat()
        self.env["TEPI_CONFIG"] = str(write_config(self.tmp.name))
        self.env["TEPI_TEST"] = "1"
        self.env["PYTHONPATH"] = str(ROOT)
        deck = load_curriculum(ROOT)
        conn = connect(Path(self.tmp.name) / "tepi.sqlite")
        for word_id in ("saya", "mahu", "air"):
            conn.execute(
                """
                INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
                VALUES (?, '2026-09-01', NULL, 5, 'settled', ?)
                """,
                (word_id, deck.by_id[word_id].index),
            )
        conn.commit()
        conn.close()

    def test_about_command_picks_the_named_settled_word(self):
        done = _run(["prompt", "--about", "air", "--json"], self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["word"]["id"], "air")
        self.assertEqual(payload["sentence"], "Saya mahu air.")

    def test_about_command_unknown_hint_falls_back(self):
        done = _run(["prompt", "--about", "zzzz", "--json"], self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["word"]["id"], "saya")
        self.assertEqual(payload["sentence"], "Saya.")


if __name__ == "__main__":
    unittest.main()
