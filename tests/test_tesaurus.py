import json
import tempfile
import unittest
from pathlib import Path

import _guard  # noqa: F401  -- patch load_config before tepi binds it
from tepi.deck import Deck, Entry, TepiError, load_curriculum
from tepi.tesaurus import (
    CLASS_LABELS,
    LISTED,
    UNLISTED,
    Place,
    build_attestation,
    classify,
    load_attestation,
    load_authority,
    parse_heads,
    write_attestation,
)

ROOT = Path(__file__).resolve().parents[1]

PANEL = """
<html><body>
<table>
<tr><th>Tesaurus</th></tr>
<tr><td>
<b><span style="font-size:16px; font-weight:bold;">rumah</span></b>&nbsp;(<font color="blue"><i>kata nama</i></font>)
<b>1.</b> <b>Bersinonim dengan</b> <a href="cari1.aspx?keyword=contohsinonim">contohsinonim</a>
<b><span style="font-size:16px; font-weight:bold;">riba</span></b>&nbsp;(<font color="blue"><i>kata nama,</i></font>)
<b><span style="font-size:16px; font-weight:bold;">tolong</span></b></td>
<b><span style="font-size:16px; font-weight:bold;">makan</span></b>&nbsp;(<font color="blue"><i>kata nama, kata kerja</i></font>)
<b><span style="font-size:16px; font-weight:bold;">sayat<sup>1</sup></span></b>&nbsp;(<font color="blue"><i>kata kerja</i></font>)
<b><span style="font-size:16px; font-weight:bold;">tadi</span></b>&nbsp;(<font color="blue"><i>adverba</i></font>)
</td></tr>
<tr><th>Puisi</th></tr>
<tr><td>
<b><span style="font-size:16px; font-weight:bold;">puisi</span></b>&nbsp;(<font color="blue"><i>kata nama</i></font>)
contohsinonim
</td></tr>
</table>
</body></html>
"""

TIADA = """
<tr><th>Tesaurus</th></tr>
<tr><td><b>Tiada maklumat tesaurus untuk kata <font color="blue">air</font></b></td></tr>
<tr><th>Puisi</th></tr>
"""

UNKNOWN = """
<tr><th>Tesaurus</th></tr>
<tr><td>
<b><span style="font-weight:bold;">lama</span></b>&nbsp;(<font color="blue"><i>kata purba</i></font>)
</td></tr>
<tr><th>Puisi</th></tr>
"""


class TesaurusTest(unittest.TestCase):
    def test_authority_is_tesaurus_bahasa_melayu_dewan(self):
        authority = load_authority(ROOT / "dictionary" / "tesaurus-bahasa-melayu-dewan.json")
        self.assertEqual(authority.id, "tesaurus-bahasa-melayu-dewan")
        self.assertEqual(authority.title, "Tesaurus Bahasa Melayu Dewan Edisi Baharu")
        self.assertEqual(authority.publisher, "Dewan Bahasa dan Pustaka")
        self.assertEqual(authority.published, "2015")
        self.assertEqual(authority.isbn, "9789836285584")
        self.assertEqual(authority.portal, "https://prpm.dbp.gov.my")
        self.assertIn("word class", authority.note)
        self.assertIn("unlisted", authority.note)

    def test_the_panel_keeps_the_headword_and_the_class(self):
        heads = parse_heads(PANEL)
        self.assertEqual(
            [(head.form, head.classes) for head in heads],
            [
                ("rumah", ("kata nama",)),
                ("riba", ("kata nama",)),
                ("tolong", ()),
                ("makan", ("kata nama", "kata kerja")),
                ("sayat", ("kata kerja",)),
                ("tadi", ("adverba",)),
            ],
        )
        self.assertNotIn("contohsinonim", [head.form for head in heads])
        self.assertNotIn("puisi", [head.form for head in heads])

    def test_classify_requires_the_same_headword(self):
        heads = parse_heads(PANEL)
        self.assertEqual(classify("rumah", heads), Place(LISTED, "noun"))
        self.assertEqual(classify("Rumah", heads), Place(LISTED, "noun"))
        self.assertEqual(classify("komputer riba", heads), Place(UNLISTED))
        self.assertEqual(classify("riba", heads), Place(LISTED, "noun"))
        self.assertEqual(classify("tolong", heads), Place(LISTED))
        self.assertEqual(classify("makan", heads), Place(LISTED, "noun+verb"))
        self.assertEqual(classify("sayat", heads), Place(LISTED, "verb"))
        self.assertEqual(classify("tadi", heads), Place(LISTED, "adverb"))
        self.assertEqual(classify("puisi", heads), Place(UNLISTED))

    def test_a_page_without_an_entry_is_unlisted(self):
        self.assertEqual(parse_heads(TIADA), [])
        self.assertEqual(classify("air", []), Place(UNLISTED))
        self.assertEqual(classify("air", parse_heads("Tiada maklumat tesaurus untuk kata air")), Place(UNLISTED))

    def test_an_unknown_class_stops_the_check(self):
        heads = parse_heads(UNKNOWN)
        with self.assertRaises(TepiError):
            classify("lama", heads)

    def test_a_blank_class_stops_the_check(self):
        page = UNKNOWN.replace("kata purba", " , ")
        with self.assertRaises(TepiError):
            parse_heads(page)

    def test_a_page_without_a_panel_stops_the_check(self):
        with self.assertRaises(TepiError):
            parse_heads("<html><title>PRPM</title><th>Kamus</th></html>")

    def test_the_deck_record_follows_teaching_order(self):
        deck = Deck(
            (
                Entry("rumah", "rumah", "rumah", "house", "Rumah.", "neutral", (), 0),
                Entry("tolong", "tolong", "tolong", "please; help", "Tolong.", "neutral", (), 1),
                Entry("air", "air", "air", "water", "Air.", "neutral", (), 2),
            )
        )
        payload = build_attestation(
            deck,
            {
                "rumah": Place(LISTED, "noun"),
                "tolong": Place(LISTED),
                "air": Place(UNLISTED),
            },
            "2026-09-30",
        )
        self.assertEqual(payload["authority"], "tesaurus-bahasa-melayu-dewan")
        self.assertEqual(payload["checked"], "2026-09-30")
        self.assertEqual(
            payload["words"],
            [
                {"id": "rumah", "lemma": "rumah", "status": "listed", "class": "noun"},
                {"id": "tolong", "lemma": "tolong", "status": "listed"},
                {"id": "air", "lemma": "air", "status": "unlisted"},
            ],
        )

    def test_a_stored_class_must_be_one_tepi_knows(self):
        deck = Deck((Entry("lama", "lama", "lama", "old", "Lama.", "neutral", (), 0),))
        payload = build_attestation(deck, {"lama": Place(LISTED, "noun")}, "2026-09-30")
        payload["words"][0]["class"] = "teapot"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tesaurus.json"
            write_attestation(path, payload)
            with self.assertRaises(TepiError):
                load_attestation(path)

    def test_the_saved_check_covers_the_deck(self):
        deck = load_curriculum(ROOT)
        saved = load_attestation(ROOT / "deck" / "tesaurus.json")
        self.assertEqual(
            [(row["id"], row["lemma"]) for row in saved["words"]],
            [(entry.id, entry.lemma) for entry in deck.entries],
        )
        self.assertTrue(saved["checked"])
        for row in saved["words"]:
            self.assertIn(row["status"], (LISTED, UNLISTED))
            if row["status"] == UNLISTED:
                self.assertNotIn("class", row)
            elif "class" in row:
                self.assertTrue(set(row["class"].split("+")) <= CLASS_LABELS)
        json.loads((ROOT / "deck" / "tesaurus.json").read_text(encoding="utf-8"))
