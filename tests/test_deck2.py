"""Deck 2 content: forty attested words, root families, and closed sentences."""

import json
import re
import unittest
from pathlib import Path

import _guard  # noqa: F401  -- patch load_config before tepi binds it
from tepi.deck import load_deck
from tepi.kamus import MISSING, load_attestation

ROOT = Path(__file__).resolve().parents[1]
DECK2 = ROOT / "deck" / "words-2.json"

# Closed-class words a sentence may use besides lemmas already taught.
FUNCTION_WORDS = frozenset(
    {
        "yang",
        "untuk",
        "dengan",
        "pada",
        "kepada",
        "daripada",
        "oleh",
        "itu",
        "atau",
        "kalau",
        "jika",
        "kerana",
        "sebab",
        "pun",
        "lah",
        "kah",
        "tah",
        "nya",
        "akan",
        "telah",
        "sedang",
        "supaya",
        "agar",
        "dalam",
        "atas",
        "bawah",
        "tentang",
    }
)

_TOKEN = re.compile(r"[^\w\s-]+", re.UNICODE)


def _tokens(sentence: str) -> list[str]:
    return [token for token in _TOKEN.sub(" ", sentence.casefold()).split() if token]


def _phrases(lemmas: set[str]) -> list[tuple[str, ...]]:
    return sorted((tuple(lemma.casefold().split()) for lemma in lemmas), key=len, reverse=True)


# A root may appear in its standard meN- or ber- form. `ajar` is taught as `mengajar`.
_ACTIVE_PREFIXES = ("meng", "meny", "mem", "men", "me", "ber")


def _active_form(token: str, lemmas: set[str]) -> bool:
    for lemma in lemmas:
        folded = lemma.casefold()
        if " " in folded or len(folded) < 3 or not token.endswith(folded):
            continue
        if token[: -len(folded)] in _ACTIVE_PREFIXES:
            return True
    return False


def _unknown(tokens: list[str], lemmas: set[str]) -> list[str]:
    phrases = _phrases(lemmas)
    unknown = []
    index = 0
    while index < len(tokens):
        matched = False
        for phrase in phrases:
            size = len(phrase)
            if tuple(tokens[index : index + size]) == phrase:
                index += size
                matched = True
                break
        if matched:
            continue
        if tokens[index] in FUNCTION_WORDS or _active_form(tokens[index], lemmas):
            index += 1
            continue
        unknown.append(tokens[index])
        index += 1
    return unknown


class Deck2ContentTest(unittest.TestCase):
    def _raw(self) -> dict:
        self.assertTrue(DECK2.is_file(), "deck/words-2.json is missing")
        return json.loads(DECK2.read_text(encoding="utf-8"))

    def test_deck_two_matches_the_deck_schema(self):
        raw = self._raw()
        self.assertEqual(set(raw), {"variety", "orthography", "speech", "words"})
        self.assertEqual(raw["variety"], "ms-MY")
        self.assertEqual(raw["orthography"], "standard-malaysian")
        self.assertEqual(raw["speech"], "peninsular")
        self.assertIsInstance(raw["words"], list)
        fields = {"id", "lemma", "root", "gloss", "sentence", "register", "requires"}
        for word in raw["words"]:
            self.assertEqual(set(word), fields)
            for key in ("id", "lemma", "root", "gloss", "sentence"):
                self.assertIsInstance(word[key], str)
                self.assertTrue(word[key].strip())
            self.assertIn(word["register"], ("neutral", "casual", "formal"))
            self.assertIsInstance(word["requires"], list)
            for req in word["requires"]:
                self.assertIsInstance(req, str)
                self.assertTrue(req)

    def test_deck_two_has_forty_words_and_is_mostly_neutral(self):
        words = self._raw()["words"]
        self.assertEqual(len(words), 40)
        neutral = sum(1 for word in words if word["register"] == "neutral")
        other = len(words) - neutral
        self.assertGreater(neutral, other)

    def test_deck_two_has_four_root_families(self):
        # Breaks if a shared root has fewer than three words, or fewer than four such roots.
        words = self._raw()["words"]
        groups: dict[str, list[str]] = {}
        for word in words:
            groups.setdefault(word["root"], []).append(word["id"])
        families = {root: ids for root, ids in groups.items() if len(ids) >= 3}
        self.assertGreaterEqual(len(families), 4)
        for root, ids in families.items():
            self.assertGreaterEqual(len(ids), 3)
            self.assertEqual(ids[0], root)

    def test_deck_two_does_not_repeat_a_deck_one_lemma(self):
        self._raw()
        deck1 = load_deck(ROOT / "deck" / "words.json")
        deck2 = load_deck(DECK2)
        lemmas = {entry.lemma.casefold() for entry in deck1.entries}
        ids = {entry.id for entry in deck1.entries}
        repeated = [entry.lemma for entry in deck2.entries if entry.lemma.casefold() in lemmas]
        self.assertEqual(repeated, [])
        self.assertEqual({entry.id for entry in deck2.entries} & ids, set())

    def test_a_derived_form_requires_its_earlier_base(self):
        self._raw()
        deck2 = load_deck(DECK2)
        groups: dict[str, list] = {}
        for entry in deck2.entries:
            groups.setdefault(entry.root, []).append(entry)
        for root, entries in groups.items():
            if len(entries) < 3:
                continue
            base = entries[0]
            self.assertEqual(base.lemma, root)
            for later in entries[1:]:
                self.assertLess(base.index, later.index)
                self.assertIn(base.id, later.requires)

    def test_sentences_stay_short_and_inside_the_words_already_taught(self):
        self._raw()
        deck1 = load_deck(ROOT / "deck" / "words.json")
        deck2 = load_deck(DECK2)
        known = {entry.lemma for entry in deck1.entries}
        problems = []
        for entry in deck2.entries:
            tokens = _tokens(entry.sentence)
            if not tokens or len(tokens) > 12:
                problems.append(f"{entry.id}: {len(tokens)} words")
            unknown = _unknown(tokens, known | {entry.lemma})
            if unknown:
                problems.append(f"{entry.id}: {', '.join(unknown)}")
            known.add(entry.lemma)
        self.assertEqual(problems, [])

    def test_every_deck_two_lemma_is_attested(self):
        self._raw()
        deck1 = load_deck(ROOT / "deck" / "words.json")
        deck2 = load_deck(DECK2)
        saved = load_attestation(ROOT / "deck" / "kamus.json")
        rows = saved["words"]
        self.assertEqual(
            [(row["id"], row["lemma"]) for row in rows],
            [(entry.id, entry.lemma) for entry in (*deck1.entries, *deck2.entries)],
        )
        for row in rows:
            self.assertNotEqual(row["status"], MISSING)
