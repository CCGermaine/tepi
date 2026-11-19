"""A sentence built only from settled, attested words."""

import json
import os
import sqlite3
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


def _entry(word_id, lemma, sentence, index):
    return Entry(word_id, lemma, lemma, lemma.upper(), sentence, "neutral", (), index)


def _settled(entry):
    return Learned(entry, date(2026, 9, 1), None, 5, "settled")


def _attestation(*rows):
    return {
        "authority": "kamus-dewan-perdana",
        "checked": "2026-11-19",
        "words": [{"id": word_id, "lemma": lemma, "status": status} for word_id, lemma, status in rows],
    }


def _run(args, env):
    return subprocess.run(
        [sys.executable, "-m", "tepi", *args],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


class PromptEngineTest(unittest.TestCase):
    def test_prompt_uses_only_settled_words_and_is_short(self):
        from tepi.engine import prompt_sentence
        from tepi.sentence import FUNCTION_WORDS, tokens, unknown

        entries = [_entry("saya", "saya", "Saya mahu air.", 0), _entry("mahu", "mahu", "Mahu.", 1), _entry("air", "air", "Air.", 2)]
        settled = tuple(_settled(entry) for entry in entries)
        attestation = _attestation(("saya", "saya", "headword"), ("mahu", "mahu", "headword"), ("air", "air", "headword"))
        prompt = prompt_sentence(settled, attestation)
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.entry.id, "saya")
        self.assertEqual(prompt.sentence, "Saya mahu air.")
        toks = tokens(prompt.sentence)
        self.assertLessEqual(len(toks), 12)
        lemmas = {entry.lemma for entry in entries}
        self.assertEqual(unknown(toks, lemmas, active=False), [])
        self.assertTrue(all(token in lemmas or token in FUNCTION_WORDS for token in toks))

    def test_prompt_skips_settled_word_without_attestation(self):
        from tepi.engine import attested_settled, prompt_sentence
        from tepi.sentence import tokens

        entries = [_entry("air", "air", "Air.", 0), _entry("kopi", "kopi", "Kopi.", 1)]
        settled = tuple(_settled(entry) for entry in entries)
        attestation = _attestation(("air", "air", "missing"), ("kopi", "kopi", "headword"))
        usable = attested_settled(settled, attestation)
        self.assertEqual([item.entry.id for item in usable], ["kopi"])
        prompt = prompt_sentence(settled, attestation)
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.entry.id, "kopi")
        self.assertNotIn("air", tokens(prompt.sentence))

    def test_prompt_skips_sentence_needing_an_unsettled_word(self):
        from tepi.engine import prompt_sentence

        entries = [_entry("kopi", "kopi", "Saya mahu kopi.", 0), _entry("air", "air", "Air.", 1)]
        settled = tuple(_settled(entry) for entry in entries)
        attestation = _attestation(("kopi", "kopi", "headword"), ("air", "air", "headword"))
        prompt = prompt_sentence(settled, attestation)
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.entry.id, "air")
        self.assertEqual(prompt.sentence, "Air.")

    def test_prompt_rejects_an_active_form_that_is_not_itself_settled(self):
        from tepi.engine import prompt_sentence
        from tepi.sentence import tokens

        entries = [_entry("ajar", "ajar", "Saya mengajar.", 0), _entry("saya", "saya", "Saya.", 1)]
        settled = tuple(_settled(entry) for entry in entries)
        attestation = _attestation(("ajar", "ajar", "headword"), ("saya", "saya", "headword"))
        prompt = prompt_sentence(settled, attestation)
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.entry.id, "saya")
        self.assertNotIn("mengajar", tokens(prompt.sentence))

    def test_prompt_none_when_nothing_is_settled(self):
        from tepi.engine import attested_settled, prompt_sentence

        attestation = _attestation(("air", "air", "headword"))
        self.assertEqual(attested_settled((), attestation), ())
        self.assertIsNone(prompt_sentence((), attestation))


class PromptCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = os.environ.copy()
        self.env["TEPI_DATA_DIR"] = self.tmp.name
        self.env["TEPI_TODAY"] = TODAY.isoformat()
        self.env["TEPI_CONFIG"] = str(write_config(self.tmp.name))
        self.env["TEPI_TEST"] = "1"
        self.env["PYTHONPATH"] = str(ROOT)

    def test_prompt_with_nothing_settled_prints_the_noop_message(self):
        done = _run(["prompt"], self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "No settled words yet.\n")
        payload = json.loads(_run(["prompt", "--json"], self.env).stdout)
        self.assertIsNone(payload["sentence"])
        self.assertEqual(payload["message"], "No settled words yet.")
        self.assertEqual(payload["settled"], 0)
        # The prompt introduces nothing and writes no progress.
        conn = sqlite3.connect(Path(self.tmp.name) / "tepi.sqlite")
        count = conn.execute("SELECT COUNT(*) FROM progress").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    def test_prompt_with_settled_words_stays_inside_the_settled_vocabulary(self):
        from tepi.sentence import FUNCTION_WORDS, tokens, unknown

        deck = load_curriculum(ROOT)
        chosen = ["saya", "mahu", "air"]
        conn = connect(Path(self.tmp.name) / "tepi.sqlite")
        for word_id in chosen:
            conn.execute(
                """
                INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
                VALUES (?, '2026-09-01', NULL, 5, 'settled', ?)
                """,
                (word_id, deck.by_id[word_id].index),
            )
        conn.commit()
        conn.close()
        done = _run(["prompt", "--json"], self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertIsNotNone(payload["sentence"])
        self.assertEqual(payload["settled"], 3)
        lemmas = {deck.by_id[word_id].lemma for word_id in chosen}
        toks = tokens(payload["sentence"])
        self.assertLessEqual(len(toks), 12)
        self.assertEqual(unknown(toks, lemmas, active=False), [])
        self.assertTrue(all(token in lemmas or token in FUNCTION_WORDS for token in toks))
        self.assertIn(payload["sentence"], {deck.by_id[word_id].sentence for word_id in chosen})


if __name__ == "__main__":
    unittest.main()
