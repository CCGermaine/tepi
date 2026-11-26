"""Level 2 prompts (word / cloze / reverse) and portable JSON export/import."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path

import _guard  # noqa: F401  -- patch load_config before tepi binds it
from tepi.cli import card_payload, main
from tepi.db import connect
from tepi.deck import Config, Deck, Entry, TepiError
from tepi.engine import EXPORT_FORMAT, Session, card_prompt
from tepi.sentence import make_cloze

TODAY = date(2026, 9, 29)


def _deck() -> Deck:
    return Deck(
        (
            Entry("saya", "saya", "saya", "I", "Saya.", "neutral", (), 0, sentence_gloss="I / me."),
            Entry(
                "mahu",
                "mahu",
                "mahu",
                "want",
                "Saya mahu.",
                "neutral",
                ("saya",),
                1,
                sentence_gloss="I want.",
                note="Neutral 'want'.",
            ),
            Entry(
                "air",
                "air",
                "air",
                "water",
                "Saya mahu air.",
                "neutral",
                ("saya", "mahu"),
                2,
                sentence_gloss="I want water.",
            ),
        )
    )


class Level2PromptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "tepi.sqlite"
        self.config = Config(1, 4, (1, 3, 7, 16, 30), 2, 1)

    def _session_at_rung(self, word_id: str, rung: int) -> Session:
        conn = connect(self.db)
        deck = _deck()
        entry = deck.entry(word_id)
        conn.execute(
            """
            INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
            VALUES (?, '2026-09-01', ?, ?, 'in_play', ?)
            """,
            (entry.id, TODAY.isoformat(), rung, entry.index),
        )
        conn.commit()
        return Session(conn, deck, self.config, TODAY)

    def test_make_cloze_blanks_lemma_and_rejects_single_word_sentence(self):
        self.assertEqual(make_cloze("Saya mahu air.", "air"), "Saya mahu ___.")
        self.assertIsNone(make_cloze("Saya.", "saya"))
        self.assertEqual(make_cloze("Saya.", "saya", "___ di rumah."), "___ di rumah.")
        self.assertEqual(make_cloze("Saya mahu mengajar.", "ajar"), "Saya mahu ___.")

    def test_rungs_zero_to_two_stay_word_mode(self):
        for rung in (0, 1, 2):
            db_path = Path(self.tmp.name) / f"rung-{rung}.sqlite"
            conn = connect(db_path)
            deck = _deck()
            entry = deck.entry("air")
            conn.execute(
                """
                INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
                VALUES (?, '2026-09-01', ?, ?, 'in_play', ?)
                """,
                (entry.id, TODAY.isoformat(), rung, entry.index),
            )
            conn.commit()
            session = Session(conn, deck, self.config, TODAY)
            card = session.presentation()
            mode, cloze = card_prompt(card)
            self.assertEqual(mode, "word")
            self.assertIsNone(cloze)
            payload = card_payload(card, deck)
            self.assertEqual(payload["promptMode"], "word")
            self.assertIsNone(payload["word"]["gloss"])
            self.assertIsNone(payload["word"]["sentenceGloss"])
            session.close()

    def test_rungs_three_and_four_use_cloze_and_expose_sentence_gloss(self):
        session = self._session_at_rung("air", 3)
        self.addCleanup(session.close)
        card = session.presentation()
        mode, cloze = card_prompt(card)
        self.assertEqual(mode, "cloze")
        self.assertEqual(cloze, "Saya mahu ___.")
        payload = card_payload(card, session.deck)
        self.assertEqual(payload["promptMode"], "cloze")
        self.assertEqual(payload["cloze"], "Saya mahu ___.")
        self.assertEqual(payload["intervalIndex"], 3)
        self.assertEqual(payload["ladderLength"], 5)
        self.assertIsNone(payload["word"]["gloss"])
        self.assertEqual(payload["word"]["sentenceGloss"], "I want water.")

    def test_single_token_sentence_at_rung_three_falls_back_to_reverse(self):
        session = self._session_at_rung("saya", 3)
        self.addCleanup(session.close)
        card = session.presentation()
        mode, cloze = card_prompt(card)
        self.assertEqual(mode, "reverse")
        self.assertIsNone(cloze)

    def test_rung_five_uses_reverse_and_exposes_english_cues(self):
        session = self._session_at_rung("air", 5)
        self.addCleanup(session.close)
        card = session.presentation()
        mode, cloze = card_prompt(card)
        self.assertEqual(mode, "reverse")
        self.assertIsNone(cloze)
        payload = card_payload(card, session.deck)
        self.assertEqual(payload["promptMode"], "reverse")
        self.assertEqual(payload["word"]["gloss"], "water")
        self.assertEqual(payload["word"]["sentenceGloss"], "I want water.")
        self.assertIsNone(payload["word"]["sentence"])


class ExportImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._saved_env = {k: os.environ.get(k) for k in ("TEPI_DATA_DIR", "TEPI_TODAY", "TEPI_CONFIG")}
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_export_and_import_round_trip(self):
        src_db = Path(self.tmp.name) / "src.sqlite"
        dst_db = Path(self.tmp.name) / "dst.sqlite"
        config = Config(2, 4, (1, 3, 7, 16, 30), 2, 1)
        deck = _deck()

        src = Session(connect(src_db), deck, config, TODAY)
        src.ensure_plan()
        src.reveal()
        src.close()

        day2 = Session(connect(src_db), deck, config, TODAY + timedelta(days=1))
        day2.ensure_plan()
        day2.rate("known")
        snap = day2.export_snapshot()
        day2.close()

        self.assertEqual(snap["format"], EXPORT_FORMAT)
        self.assertEqual(len(snap["progress"]), 3)
        self.assertGreaterEqual(len(snap["events"]), 4)

        dst = Session(connect(dst_db), deck, config, TODAY + timedelta(days=1))
        words_n, events_n = dst.import_snapshot(snap)
        self.assertEqual(words_n, 3)
        self.assertEqual(events_n, len(snap["events"]))
        with self.assertRaises(TepiError):
            dst.import_snapshot(snap, replace=False)
        dst.import_snapshot(snap, replace=True)
        dst.close()

    def test_cli_export_and_import_commands(self):
        data_a = Path(self.tmp.name) / "a"
        data_b = Path(self.tmp.name) / "b"
        cfg = Path(self.tmp.name) / "config.json"
        cfg.write_text(
            json.dumps(
                {
                    "newPerDay": 2,
                    "reviewCap": 4,
                    "catchUpReviewCap": 12,
                    "catchUp": True,
                    "knownIntervals": [1, 3, 7, 16, 30],
                    "fuzzyDays": 2,
                    "missedDays": 1,
                }
            ),
            encoding="utf-8",
        )
        os.environ["TEPI_DATA_DIR"] = str(data_a)
        os.environ["TEPI_TODAY"] = TODAY.isoformat()
        os.environ["TEPI_CONFIG"] = str(cfg)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["today", "--json"]), 0)
        snap_path = Path(self.tmp.name) / "snap.json"
        self.assertEqual(main(["export", "--out", str(snap_path)]), 0)
        self.assertTrue(snap_path.is_file())

        os.environ["TEPI_DATA_DIR"] = str(data_b)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["import", str(snap_path), "--json"]), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["importedWords"], 2)


if __name__ == "__main__":
    unittest.main()
