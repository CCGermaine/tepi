import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import _guard  # noqa: F401  -- patch load_config before tepi binds it
from tepi.cli import _format_today, card_payload
from tepi.db import connect
from tepi.deck import Deck, Entry, TepiError, load_config, load_deck
from tepi.engine import Session

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 11, 3)
OVERDUE = "2026-10-25"

OLD_SCHEMA = """
CREATE TABLE progress (
    word_id TEXT PRIMARY KEY,
    introduced_on TEXT NOT NULL,
    due TEXT,
    interval_index INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('in_play', 'settled')),
    deck_index INTEGER NOT NULL
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    day TEXT NOT NULL,
    word_id TEXT NOT NULL REFERENCES progress(word_id),
    kind TEXT NOT NULL CHECK (kind IN ('introduced', 'revealed', 'known', 'fuzzy', 'missed'))
);
CREATE TABLE plans (
    day TEXT PRIMARY KEY,
    reviews TEXT NOT NULL,
    introduced TEXT NOT NULL
);
CREATE INDEX events_day ON events(day);
"""


def deck_of(*words: str) -> Deck:
    entries = tuple(
        Entry(word, word, word, word.upper(), f"{word}.", "neutral", (), index) for index, word in enumerate(words)
    )
    return Deck(entries)


class CatchUpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "tepi.sqlite"
        self._saved_env = {key: os.environ.get(key) for key in ("TEPI_DATA_DIR", "TEPI_TODAY")}
        os.environ["TEPI_DATA_DIR"] = self.tmp.name
        os.environ["TEPI_TODAY"] = DAY.isoformat()
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def write_config(self, **overrides) -> Path:
        raw = {
            "newPerDay": 0,
            "reviewCap": 4,
            "knownIntervals": [1, 3, 7, 16, 30],
            "fuzzyDays": 2,
            "missedDays": 1,
        }
        raw.update(overrides)
        path = Path(self.tmp.name) / "config.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return path

    def session(self, deck, config, day=DAY):
        opened = Session(connect(self.db), deck, config, day)
        self.addCleanup(opened.close)
        return opened

    def seed(self, session, words, due):
        for index, word in enumerate(words):
            session.conn.execute(
                """
                INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
                VALUES (?, '2026-09-01', ?, 0, 'in_play', ?)
                """,
                (word, due, index),
            )
        session.conn.commit()

    def test_overdue_reviews_use_the_catch_up_cap(self):
        words = [f"w{i:02d}" for i in range(20)]
        config = load_config(self.write_config(catchUp=True, catchUpReviewCap=12))
        session = self.session(deck_of(*words), config)
        self.seed(session, words, OVERDUE)
        plan = session.ensure_plan()
        self.assertEqual(len(plan.reviews), 12)
        self.assertEqual(plan.reviews, tuple(words[:12]))
        self.assertTrue(plan.catch_up)
        card = session.presentation()
        payload = card_payload(card)
        self.assertTrue(payload["catchUp"])
        self.assertEqual(len(payload["plan"]["reviews"]), 12)
        self.assertIn("1/12 (catch-up)", _format_today(card))
        self.assertEqual(session.ensure_plan().reviews, plan.reviews)

    def test_catch_up_false_keeps_the_review_cap(self):
        words = [f"w{i:02d}" for i in range(20)]
        config = load_config(self.write_config(catchUp=False, catchUpReviewCap=12))
        session = self.session(deck_of(*words), config)
        self.seed(session, words, OVERDUE)
        plan = session.ensure_plan()
        self.assertEqual(len(plan.reviews), 4)
        self.assertEqual(plan.reviews, tuple(words[:4]))
        self.assertFalse(plan.catch_up)
        card = session.presentation()
        self.assertFalse(card_payload(card)["catchUp"])
        self.assertNotIn("(catch-up)", _format_today(card))

    def test_catch_up_on_with_nothing_overdue_leaves_the_marker_off(self):
        words = [f"w{i:02d}" for i in range(6)]
        config = load_config(self.write_config(catchUp=True, catchUpReviewCap=12))
        session = self.session(deck_of(*words), config)
        self.seed(session, words, "2026-11-10")
        plan = session.ensure_plan()
        self.assertEqual(plan.reviews, ())
        self.assertFalse(plan.catch_up)
        card = session.presentation()
        self.assertFalse(card_payload(card)["catchUp"])
        self.assertNotIn("(catch-up)", _format_today(card))

    def test_catch_up_on_with_two_overdue_leaves_the_marker_off(self):
        words = ["w00", "w01"]
        config = load_config(self.write_config(catchUp=True, catchUpReviewCap=12))
        session = self.session(deck_of(*words), config)
        self.seed(session, words, OVERDUE)
        plan = session.ensure_plan()
        self.assertEqual(plan.reviews, ("w00", "w01"))
        self.assertFalse(plan.catch_up)
        card = session.presentation()
        self.assertFalse(card_payload(card)["catchUp"])
        self.assertNotIn("(catch-up)", _format_today(card))
        self.assertIn("1/2", _format_today(card))

    def test_catch_up_on_with_twenty_overdue_marks_twelve(self):
        words = [f"w{i:02d}" for i in range(20)]
        config = load_config(self.write_config(catchUp=True, catchUpReviewCap=12))
        session = self.session(deck_of(*words), config)
        self.seed(session, words, OVERDUE)
        plan = session.ensure_plan()
        self.assertEqual(len(plan.reviews), 12)
        self.assertEqual(plan.reviews, tuple(words[:12]))
        self.assertTrue(plan.catch_up)
        card = session.presentation()
        self.assertTrue(card_payload(card)["catchUp"])
        self.assertIn("1/12 (catch-up)", _format_today(card))

    def test_a_test_cannot_open_the_repo_config(self):
        with self.assertRaises(AssertionError) as caught:
            load_config(ROOT / "config.json")
        self.assertIn("repo config", str(caught.exception))

    def test_a_subprocess_cannot_open_the_repo_config(self):
        env = os.environ.copy()
        env["TEPI_DATA_DIR"] = self.tmp.name
        env["TEPI_TODAY"] = DAY.isoformat()
        env.pop("TEPI_CONFIG", None)
        env["PYTHONPATH"] = str(ROOT)
        completed = subprocess.run(
            [sys.executable, "-m", "tepi", "today", "--json"],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(completed.returncode, 0, completed.stdout or completed.stderr)
        self.assertIn("repo config", completed.stderr)

    def test_due_today_stays_on_the_review_cap_while_catch_up_is_true(self):
        words = [f"w{i:02d}" for i in range(20)]
        config = load_config(self.write_config(catchUp=True, catchUpReviewCap=12))
        session = self.session(deck_of(*words), config)
        self.seed(session, words, DAY.isoformat())
        plan = session.ensure_plan()
        self.assertEqual(len(plan.reviews), 4)
        self.assertFalse(plan.catch_up)
        self.assertFalse(card_payload(session.presentation())["catchUp"])

    def test_known_days_clear_the_backlog_and_leave_config_untouched(self):
        path = self.write_config(newPerDay=2, catchUp=True, catchUpReviewCap=12)
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        deck = load_deck(ROOT / "deck" / "words.json")
        config = load_config(path)
        day = DAY
        session = self.session(deck, config, day)
        self.seed(session, [entry.id for entry in deck.entries], OVERDUE)
        saw_wide = False
        cleared_on = None
        for _ in range(120):
            session = Session(session.conn, deck, config, day)
            plan = session.ensure_plan()
            overdue = session.conn.execute(
                "SELECT COUNT(*) FROM progress WHERE state = 'in_play' AND due IS NOT NULL AND due < ?",
                (day.isoformat(),),
            ).fetchone()[0]
            if overdue:
                self.assertGreater(len(plan.reviews), config.review_cap)
                self.assertLessEqual(len(plan.reviews), config.catch_up_review_cap)
                self.assertTrue(plan.catch_up)
                saw_wide = True
                for _word in plan.reviews:
                    session.rate("known")
                day += timedelta(days=1)
                continue
            self.assertLessEqual(len(plan.reviews), config.review_cap)
            self.assertFalse(plan.catch_up)
            cleared_on = day
            break
        self.assertTrue(saw_wide)
        self.assertIsNotNone(cleared_on)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_a_config_without_the_new_keys_uses_the_review_cap(self):
        words = [f"w{i:02d}" for i in range(20)]
        config = load_config(self.write_config())
        self.assertFalse(config.catch_up)
        self.assertEqual(config.catch_up_review_cap, config.review_cap)
        session = self.session(deck_of(*words), config)
        self.seed(session, words, OVERDUE)
        plan = session.ensure_plan()
        self.assertEqual(plan.reviews, tuple(words[:4]))
        self.assertFalse(plan.catch_up)

    def test_a_bad_catch_up_cap_raises_the_same_error_as_a_bad_review_cap(self):
        with self.assertRaises(TepiError) as bad_review:
            load_config(self.write_config(reviewCap="4"))
        with self.assertRaises(TepiError) as bad_cap:
            load_config(self.write_config(catchUp=True, catchUpReviewCap="12"))
        with self.assertRaises(TepiError) as low_cap:
            load_config(self.write_config(catchUp=True, reviewCap=4, catchUpReviewCap=3))
        self.assertEqual(type(bad_cap.exception), type(bad_review.exception))
        self.assertEqual(type(low_cap.exception), type(bad_review.exception))
        self.assertEqual(str(bad_review.exception), "reviewCap must be a number of words, zero or more.")
        self.assertEqual(str(bad_cap.exception), "catchUpReviewCap must be a number of words, zero or more.")
        self.assertIn("catchUpReviewCap", str(low_cap.exception))

    def test_an_existing_plan_is_not_rebuilt(self):
        conn = sqlite3.connect(self.db)
        conn.executescript(OLD_SCHEMA)
        conn.execute("PRAGMA user_version = 1")
        conn.execute(
            "INSERT INTO plans (day, reviews, introduced) VALUES (?, ?, ?)",
            (DAY.isoformat(), json.dumps(["lapar", "ya", "di", "perlu"]), "[]"),
        )
        conn.commit()
        conn.close()
        config = load_config(self.write_config(catchUp=True, catchUpReviewCap=12))
        session = self.session(deck_of("lapar", "ya", "di", "perlu"), config)
        plan = session.ensure_plan()
        self.assertEqual(plan.reviews, ("lapar", "ya", "di", "perlu"))
        self.assertFalse(plan.catch_up)
        self.assertEqual(session.conn.execute("PRAGMA user_version").fetchone()[0], 1)
        stored = session.conn.execute("SELECT reviews, catch_up FROM plans").fetchone()
        self.assertEqual(json.loads(stored["reviews"]), ["lapar", "ya", "di", "perlu"])
        self.assertEqual(stored["catch_up"], 0)

    def test_today_command_marks_catch_up_and_log_stays_plain(self):
        deck = load_deck(ROOT / "deck" / "words.json")
        conn = connect(self.db)
        for entry in deck.entries:
            conn.execute(
                """
                INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
                VALUES (?, '2026-09-01', ?, 0, 'in_play', ?)
                """,
                (entry.id, OVERDUE, entry.index),
            )
        conn.commit()
        conn.close()
        env = os.environ.copy()
        env["TEPI_DATA_DIR"] = self.tmp.name
        env["TEPI_TODAY"] = DAY.isoformat()
        env["TEPI_CONFIG"] = str(self.write_config(newPerDay=2, catchUp=True, catchUpReviewCap=12))
        env["PYTHONPATH"] = str(ROOT)
        payload = _run(["today", "--json"], env)
        self.assertTrue(payload["catchUp"])
        self.assertEqual(len(payload["plan"]["reviews"]), 12)
        text = _run(["today"], env)
        self.assertIn("1/12 (catch-up)", text)
        log = _run(["log", "--json"], env)
        # The command counts every deck file. This test seeds deck 1 only.
        self.assertEqual(log["deck"], 111)
        self.assertNotIn("catchUp", log)


def _run(args, env) -> dict | str:
    completed = subprocess.run(
        [sys.executable, "-m", "tepi", *args],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if "--json" in args:
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)
        return json.loads(completed.stdout)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.stdout
