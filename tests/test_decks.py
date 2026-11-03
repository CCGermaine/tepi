"""Two deck files, in teaching order, with the log left intact."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import _guard  # noqa: F401  -- patch load_config before tepi binds it
import tepi.deck as deck_module
from tepi.cli import main
from tepi.db import connect
from tepi.deck import TepiError, load_config, load_deck
from tepi.engine import Session
from tepi.kamus import Hit
from test_engine import TODAY, write_config

ROOT = Path(__file__).resolve().parents[1]


def _word(word_id: str, requires: list[str] | None = None) -> dict:
    return {
        "id": word_id,
        "lemma": word_id,
        "root": word_id,
        "gloss": word_id,
        "sentence": f"{word_id}.",
        "register": "neutral",
        "requires": requires or [],
    }


def _write_deck(directory: Path, name: str, words: list[dict]) -> Path:
    path = directory / name
    path.write_text(
        json.dumps(
            {
                "variety": "ms-MY",
                "orthography": "standard-malaysian",
                "speech": "peninsular",
                "words": words,
            }
        ),
        encoding="utf-8",
    )
    return path


class DeckLoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "tepi.sqlite"
        self._saved_env = {
            key: os.environ.get(key) for key in ("TEPI_DATA_DIR", "TEPI_TODAY", "TEPI_CONFIG")
        }
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _require(self, name):
        fn = getattr(deck_module, name, None)
        self.assertTrue(callable(fn), f"{name} is missing")
        return fn

    def test_the_command_lists_deck_one_then_deck_two(self):
        # Breaks if the session still opens deck/words.json alone.
        os.environ["TEPI_DATA_DIR"] = self.tmp.name
        os.environ["TEPI_TODAY"] = TODAY.isoformat()
        os.environ["TEPI_CONFIG"] = str(write_config(self.tmp.name))
        session = __import__("tepi.cli", fromlist=["_session"])._session()
        try:
            ids = [entry.id for entry in session.deck.entries]
        finally:
            session.close()
        self.assertEqual(ids[:4], ["selamat", "pagi", "saya", "mahu"])
        self.assertEqual(ids[67:72], ["tunggu", "sebentar", "nanti", "tadi", "ajar"])
        self.assertEqual(ids[72], "belajar")
        self.assertEqual(len(ids), 111)

    def test_numbered_deck_files_follow_words_json_by_number(self):
        # Breaks if words-10.json sorts ahead of words-2.json, or the schema is loaded.
        deck_paths = self._require("deck_paths")
        folder = Path(self.tmp.name)
        for name in ("words-10.json", "words-2.json", "words.json", "words.schema.json", "kamus.json"):
            (folder / name).write_text("{}", encoding="utf-8")
        self.assertEqual(
            [path.name for path in deck_paths(folder)],
            ["words.json", "words-2.json", "words-10.json"],
        )
        self.assertEqual(
            [path.name for path in deck_paths(ROOT / "deck")],
            ["words.json", "words-2.json"],
        )

    def test_new_words_finish_deck_one_before_deck_two(self):
        # Breaks if a deck 2 id is introduced while a deck 1 id is still waiting.
        load_curriculum = self._require("load_curriculum")
        deck = load_curriculum(ROOT)
        config = load_config(write_config(self.tmp.name, newPerDay=2))
        deck1 = [entry for entry in deck.entries if entry.index < 71]
        self.assertEqual([entry.id for entry in deck1[-2:]], ["nanti", "tadi"])

        only_deck1_left = self._session(deck, config, [entry for entry in deck1 if entry.id not in ("nanti", "tadi")])
        self.assertEqual(only_deck1_left.ensure_plan().new, ("nanti", "tadi"))
        only_deck1_left.close()

        spill = self._session(deck, config, [entry for entry in deck1 if entry.id != "tadi"])
        self.assertEqual(spill.ensure_plan().new, ("tadi", "ajar"))
        spill.close()

        done = self._session(deck, config, deck1)
        self.assertEqual(done.ensure_plan().new, ("ajar", "belajar"))
        done.close()

    def test_a_repeated_id_across_decks_is_an_error(self):
        load_decks = self._require("load_decks")
        folder = Path(self.tmp.name)
        first = _write_deck(folder, "words.json", [_word("kopi")])
        second = _write_deck(folder, "words-2.json", [_word("kopi")])
        with self.assertRaises(TepiError) as caught:
            load_decks([first, second])
        self.assertIn("'kopi'", str(caught.exception))

    def test_a_require_that_is_missing_is_an_error(self):
        load_decks = self._require("load_decks")
        folder = Path(self.tmp.name)
        first = _write_deck(folder, "words.json", [_word("satu")])
        second = _write_deck(folder, "words-2.json", [_word("dua", ["tiada"])])
        with self.assertRaises(TepiError) as caught:
            load_decks([first, second])
        message = str(caught.exception)
        self.assertIn("dua", message)
        self.assertIn("tiada", message)

    def test_a_require_that_points_later_is_an_error(self):
        load_decks = self._require("load_decks")
        folder = Path(self.tmp.name)
        first = _write_deck(folder, "words.json", [_word("awal", ["kemudian"])])
        second = _write_deck(folder, "words-2.json", [_word("kemudian")])
        with self.assertRaises(TepiError) as caught:
            load_decks([first, second])
        message = str(caught.exception)
        self.assertIn("awal", message)
        self.assertIn("kemudian", message)

    def test_deck_one_due_dates_stay_when_deck_two_is_added(self):
        # Breaks if opening the larger deck rewrites a deck-1-only log.
        load_curriculum = self._require("load_curriculum")
        deck1 = load_deck(ROOT / "deck" / "words.json")
        config = load_config(write_config(self.tmp.name))
        first = Session(connect(self.db), deck1, config, TODAY)
        self.addCleanup(first.close)
        first.ensure_plan()
        before = self._rows(first.conn)
        self.assertEqual(set(before), {"selamat", "pagi"})
        full = load_curriculum(ROOT)
        same_day = Session(first.conn, full, config, TODAY)
        same_day.ensure_plan()
        self.assertEqual(self._rows(same_day.conn), before)
        self.assertEqual(
            {row["word_id"] for row in same_day.conn.execute("SELECT word_id FROM progress")},
            {"selamat", "pagi"},
        )
        next_day = Session(first.conn, full, config, TODAY + timedelta(days=1))
        self.assertEqual(next_day.ensure_plan().new, ("saya", "mahu"))
        after = self._rows(next_day.conn)
        self.assertEqual(after["selamat"], before["selamat"])
        self.assertEqual(after["pagi"], before["pagi"])

    def _session(self, deck, config, introduced):
        conn = connect(Path(self.tmp.name) / f"{len(introduced)}-{introduced[0].id}.sqlite")
        for entry in introduced:
            conn.execute(
                """
                INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
                VALUES (?, '2026-09-01', '2026-12-01', 1, 'in_play', ?)
                """,
                (entry.id, entry.index),
            )
        conn.commit()
        return Session(conn, deck, config, TODAY)

    def _rows(self, conn):
        rows = {}
        for row in conn.execute(
            "SELECT word_id, due, interval_index, state, introduced_on, deck_index FROM progress"
        ):
            rows[row["word_id"]] = (
                row["due"],
                row["interval_index"],
                row["state"],
                row["introduced_on"],
                row["deck_index"],
            )
        return rows


class DeckCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_help_offers_a_single_deck_file(self):
        for command in ("check", "thesaurus"):
            completed = subprocess.run(
                [sys.executable, "-m", "tepi", command, "--help"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("--deck-file", completed.stdout)

    def test_check_asks_every_deck(self):
        # Breaks if check still reads only deck/words.json. The portal is not called.
        asked = []

        class FakeKamus:
            def __init__(self, authority):
                self.authority = authority

            def search(self, lemma):
                asked.append(lemma)
                return [Hit(form=lemma, kind="kata entri")]

        dest = Path(self.tmp.name) / "kamus.json"
        import tepi.cli as cli

        with patch.object(cli, "Kamus", FakeKamus), patch.object(cli.time, "sleep"), patch.object(
            cli, "ATTESTATION_PATH", dest
        ), redirect_stdout(io.StringIO()):
            code = main(["check"])
        self.assertEqual(code, 0)
        self.assertEqual(asked[0], "selamat")
        self.assertGreaterEqual(len(asked), 72, asked[-1] if asked else asked)
        self.assertEqual(asked[70], "tadi")
        self.assertEqual(asked[71], "ajar")
        self.assertEqual(len(asked), 111)
        saved = json.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual([row["lemma"] for row in saved["words"][67:72]], ["tunggu", "sebentar", "nanti", "tadi", "ajar"])

    def test_check_deck_file_asks_that_file_and_keeps_the_other_rows(self):
        import tepi.cli as cli

        asked = []

        class FakeKamus:
            def __init__(self, authority):
                self.authority = authority

            def search(self, lemma):
                asked.append(lemma)
                return [Hit(form=lemma, kind="kata entri")]

        dest = Path(self.tmp.name) / "kamus.json"
        saved = json.loads((ROOT / "deck" / "kamus.json").read_text(encoding="utf-8"))
        saved["words"][0]["lemma"] = "SELAMAT-SENTINEL"
        dest.write_text(json.dumps(saved), encoding="utf-8")
        with patch.object(cli, "Kamus", FakeKamus), patch.object(cli.time, "sleep"), patch.object(
            cli, "ATTESTATION_PATH", dest
        ), redirect_stdout(io.StringIO()):
            try:
                code = main(["check", "--deck-file", str(ROOT / "deck" / "words-2.json")])
            except SystemExit as err:
                self.fail(f"check --deck-file is not accepted ({err})")
        self.assertEqual(code, 0, dest.read_text(encoding="utf-8") if dest.exists() else "")
        self.assertEqual(asked[0], "ajar")
        self.assertEqual(len(asked), 40)
        self.assertNotIn("selamat", asked)
        merged = json.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(merged["words"][0]["id"], "selamat")
        self.assertEqual(merged["words"][0]["lemma"], "SELAMAT-SENTINEL")
        self.assertEqual(merged["words"][71]["lemma"], "ajar")
        self.assertEqual(len(merged["words"]), 111)

    def test_thesaurus_deck_asks_every_deck(self):
        import tepi.cli as cli

        asked = []

        class FakeBook:
            def __init__(self, authority):
                self.authority = authority

            def search(self, lemma):
                asked.append(lemma)
                return []

        dest = Path(self.tmp.name) / "tesaurus.json"
        with patch.object(cli, "Tesaurus", FakeBook), patch.object(cli.time, "sleep"), patch.object(
            cli, "THESAURUS_ATTESTATION_PATH", dest
        ), redirect_stdout(io.StringIO()):
            code = main(["thesaurus", "--deck"])
        self.assertEqual(code, 0)
        self.assertEqual(asked[0], "selamat")
        self.assertGreaterEqual(len(asked), 72, asked[-1] if asked else asked)
        self.assertEqual(asked[70], "tadi")
        self.assertEqual(asked[71], "ajar")
        self.assertEqual(len(asked), 111)
        saved = json.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(saved["words"][71]["lemma"], "ajar")
        self.assertEqual(len(saved["words"]), 111)

    def test_thesaurus_deck_file_asks_that_file_and_keeps_the_other_rows(self):
        import tepi.cli as cli

        asked = []

        class FakeBook:
            def __init__(self, authority):
                self.authority = authority

            def search(self, lemma):
                asked.append(lemma)
                return []

        dest = Path(self.tmp.name) / "tesaurus.json"
        saved = json.loads((ROOT / "deck" / "tesaurus.json").read_text(encoding="utf-8"))
        saved["words"][0]["lemma"] = "SELAMAT-SENTINEL"
        dest.write_text(json.dumps(saved), encoding="utf-8")
        with patch.object(cli, "Tesaurus", FakeBook), patch.object(cli.time, "sleep"), patch.object(
            cli, "THESAURUS_ATTESTATION_PATH", dest
        ), redirect_stdout(io.StringIO()):
            try:
                code = main(["thesaurus", "--deck-file", str(ROOT / "deck" / "words-2.json")])
            except SystemExit as err:
                self.fail(f"thesaurus --deck-file is not accepted ({err})")
        self.assertEqual(code, 0)
        self.assertEqual(asked[0], "ajar")
        self.assertEqual(len(asked), 40)
        self.assertNotIn("selamat", asked)
        merged = json.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(merged["words"][0]["lemma"], "SELAMAT-SENTINEL")
        self.assertEqual(merged["words"][71]["lemma"], "ajar")
        self.assertEqual(len(merged["words"]), 111)
