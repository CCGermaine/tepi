import json
import unittest
from pathlib import Path

from tepi.deck import Deck, Entry, TepiError, load_deck
from tepi.kamus import (
    DERIVATIVE,
    HEADWORD,
    MISSING,
    PHRASE,
    build_attestation,
    classify,
    hits_from_suggestions,
    load_attestation,
    load_authority,
    parse_hits,
)

ROOT = Path(__file__).resolve().parents[1]

PAGE = """
<p>Carian untuk: <span>air</span></p>
<div class="search-result" onclick="syncLemmaId('air', '9')">
<h3>air</h3>
<span class="rounded-full">Kata Entri</span>
</div>
<div class="search-result" onclick="syncLemmaId('air', '9')">
<h3>air mata</h3>
<span class="rounded-full">Frasa Kata Entri</span>
</div>
<div class="search-result" onclick="syncLemmaId('minum', '2')">
<h3>minuman</h3>
<span class="rounded-full">Kata Terbitan</span>
</div>
<div class="search-result" onclick="syncLemmaId('minum', '2')">
<h3>air minum</h3>
<span class="rounded-full">Frasa Kata Terbitan</span>
</div>
<div class="search-result" onclick="syncLemmaId('air', '9')">
<h3>Air</h3>
<span class="rounded-full">Kata Entri</span>
</div>
<div class="search-result" onclick="syncLemmaId('sayat', '4')">
<h3>
sayat
<sup class="text-yellow-400">1</sup>
</h3>
<span class="rounded-full">Kata Entri</span>
</div>
"""


class KamusTest(unittest.TestCase):
    def test_authority_is_kamus_dewan_perdana(self):
        authority = load_authority(ROOT / "dictionary" / "kamus-dewan-perdana.json")
        self.assertEqual(authority.id, "kamus-dewan-perdana")
        self.assertEqual(authority.title, "Kamus Dewan Perdana")
        self.assertEqual(authority.publisher, "Dewan Bahasa dan Pustaka")
        self.assertEqual(authority.published, "2020")
        self.assertEqual(authority.portal, "https://kamus.dbp.gov.my")
        self.assertEqual(authority.portal_since, "2026-04-10")

    def test_a_search_page_keeps_the_entry_kind_and_drops_the_sense(self):
        hits = parse_hits(PAGE)
        self.assertEqual(
            [(hit.form, hit.kind) for hit in hits],
            [
                ("air", "Kata Entri"),
                ("air mata", "Frasa Kata Entri"),
                ("minuman", "Kata Terbitan"),
                ("air minum", "Frasa Kata Terbitan"),
                ("Air", "Kata Entri"),
                ("sayat", "Kata Entri"),
            ],
        )
        self.assertEqual(classify("sayat", hits), HEADWORD)
        self.assertEqual(classify("saya", hits), MISSING)

    def test_classify_matches_the_spelling_and_prefers_a_headword(self):
        hits = parse_hits(PAGE)
        self.assertEqual(classify("air", hits), HEADWORD)
        self.assertEqual(classify("Air", hits), HEADWORD)
        self.assertEqual(classify("air mata", hits), PHRASE)
        self.assertEqual(classify("minuman", hits), DERIVATIVE)
        self.assertEqual(classify("air minum", hits), DERIVATIVE)
        self.assertEqual(classify("kopi", hits), MISSING)
        self.assertEqual(classify("mata", hits), MISSING)

    def test_suggestions_keep_the_spelling_and_the_kind(self):
        payload = {
            "components": [
                {
                    "snapshot": json.dumps(
                        {
                            "data": {
                                "suggestions": [
                                    [
                                        [
                                            {"lemma": "e-mel", "match": "Kata Entri", "homonym_number": None},
                                            {"s": "arr"},
                                        ],
                                        [
                                            {"lemma": "e-mel sampah", "match": "Frasa Kata Entri"},
                                            {"s": "arr"},
                                        ],
                                    ],
                                    {"s": "arr"},
                                ]
                            }
                        }
                    )
                }
            ]
        }
        hits = hits_from_suggestions(payload)
        self.assertEqual(classify("e-mel", hits), HEADWORD)
        self.assertEqual(classify("e-mel sampah", hits), PHRASE)
        self.assertEqual(classify("emel", hits), MISSING)

    def test_an_unknown_badge_stops_the_check(self):
        page = PAGE.replace("Kata Terbitan", "Nota Lama", 1)
        hits = parse_hits(page)
        with self.assertRaises(TepiError):
            classify("minuman", hits)

    def test_a_page_without_a_search_stops_the_check(self):
        with self.assertRaises(TepiError):
            parse_hits("<html><title>KamusDBP</title></html>")

    def test_the_deck_record_follows_teaching_order(self):
        deck = Deck(
            (
                Entry("air", "air", "air", "water", "Air.", "neutral", (), 0),
                Entry("air-mata", "air mata", "air", "tears", "Air mata.", "neutral", ("air",), 1),
            )
        )
        payload = build_attestation(deck, {"air": HEADWORD, "air mata": PHRASE}, "2026-09-30")
        self.assertEqual(payload["authority"], "kamus-dewan-perdana")
        self.assertEqual(payload["checked"], "2026-09-30")
        self.assertEqual(
            payload["words"],
            [
                {"id": "air", "lemma": "air", "status": "headword"},
                {"id": "air-mata", "lemma": "air mata", "status": "phrase"},
            ],
        )

    def test_the_saved_check_covers_the_deck(self):
        deck = load_deck(ROOT / "deck" / "words.json")
        saved = load_attestation(ROOT / "deck" / "kamus.json")
        self.assertEqual(
            [(row["id"], row["lemma"]) for row in saved["words"]],
            [(entry.id, entry.lemma) for entry in deck.entries],
        )
        self.assertTrue(saved["checked"])
        self.assertNotIn(MISSING, {row["status"] for row in saved["words"]})
        json.loads((ROOT / "deck" / "kamus.json").read_text(encoding="utf-8"))
