"""Deck 3 content: forty Peninsular Malaysia words, root families, and closed sentences."""

import json
import unittest
from pathlib import Path

import _guard  # noqa: F401  -- patch load_config before tepi binds it
from tepi.deck import load_deck
from tepi.sentence import tokens as _tokens, unknown as _unknown

ROOT = Path(__file__).resolve().parents[1]
DECK3 = ROOT / "deck" / "words-3.json"


class Deck3ContentTest(unittest.TestCase):
    def _raw(self) -> dict:
        self.assertTrue(DECK3.is_file(), "deck/words-3.json is missing")
        return json.loads(DECK3.read_text(encoding="utf-8"))

    def test_deck_three_matches_the_deck_schema(self):
        raw = self._raw()
        self.assertEqual(set(raw), {"variety", "orthography", "speech", "words"})
        self.assertEqual(raw["variety"], "ms-MY")
        self.assertEqual(raw["orthography"], "standard-malaysian")
        self.assertEqual(raw["speech"], "peninsular")
        required_fields = {"id", "lemma", "root", "gloss", "sentence", "sentenceGloss", "register", "requires"}
        optional_fields = {"cloze", "note"}
        for word in raw["words"]:
            self.assertTrue(required_fields.issubset(set(word)))
            self.assertTrue(set(word).issubset(required_fields | optional_fields))
            for key in ("id", "lemma", "root", "gloss", "sentence", "sentenceGloss"):
                self.assertIsInstance(word[key], str)
                self.assertTrue(word[key].strip())
            self.assertIn(word["register"], ("neutral", "casual", "formal"))
            self.assertIsInstance(word["requires"], list)

    def test_deck_three_has_forty_words_and_is_mostly_neutral(self):
        words = self._raw()["words"]
        self.assertEqual(len(words), 40)
        neutral = sum(1 for word in words if word["register"] == "neutral")
        self.assertGreater(neutral, len(words) - neutral)

    def test_deck_three_does_not_repeat_earlier_lemmas_or_ids(self):
        d1 = load_deck(ROOT / "deck" / "words.json")
        d2 = load_deck(ROOT / "deck" / "words-2.json")
        d3 = load_deck(DECK3)
        earlier_ids = {e.id for e in (*d1.entries, *d2.entries)}
        earlier_lemmas = {e.lemma.casefold() for e in (*d1.entries, *d2.entries)}
        self.assertEqual({e.id for e in d3.entries} & earlier_ids, set())
        self.assertEqual([e.lemma for e in d3.entries if e.lemma.casefold() in earlier_lemmas], [])

    def test_sentences_stay_short_and_inside_taught_words(self):
        d1 = load_deck(ROOT / "deck" / "words.json")
        d2 = load_deck(ROOT / "deck" / "words-2.json")
        d3 = load_deck(DECK3)
        known = {e.lemma for e in (*d1.entries, *d2.entries)}
        problems = []
        for entry in d3.entries:
            toks = _tokens(entry.sentence)
            if not toks or len(toks) > 12:
                problems.append(f"{entry.id}: {len(toks)} words")
            unk = _unknown(toks, known | {entry.lemma})
            if unk:
                problems.append(f"{entry.id}: {', '.join(unk)}")
            known.add(entry.lemma)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
