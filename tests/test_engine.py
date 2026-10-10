import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from tepi.db import connect
from tepi.deck import Config, Deck, Entry, TepiError, load_config, load_deck
from tepi.engine import Session

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 9, 29)


def tiny(*words: str, intervals=(1, 3, 7, 16, 30), new_per_day=2, review_cap=4) -> tuple[Deck, Config]:
    entries = tuple(
        Entry(word, word, word, word.upper(), f"{word}.", "neutral", (), index) for index, word in enumerate(words)
    )
    config = Config(new_per_day, review_cap, intervals, 2, 1)
    return Deck(entries), config


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "tepi.sqlite"

    def session(self, deck, config, day, conn=None):
        connection = conn or connect(self.db)
        return Session(connection, deck, config, day)

    def test_first_day_of_the_real_deck_introduces_the_greeting(self):
        deck = load_deck(ROOT / "deck" / "words.json")
        config = load_config(ROOT / "config.json")
        session = self.session(deck, config, TODAY)
        plan = session.ensure_plan()
        self.assertEqual(plan.new, ("selamat", "pagi"))
        self.assertEqual(plan.reviews, ())
        card = session.presentation()
        self.assertEqual(card.mode, "new")
        self.assertEqual(card.entry.id, "selamat")
        self.assertFalse(card.revealed)
        row = session.conn.execute("SELECT due, interval_index FROM progress WHERE word_id = 'pagi'").fetchone()
        self.assertEqual(row["due"], "2026-09-30")
        self.assertEqual(row["interval_index"], 0)
        session.ensure_plan()
        count = session.conn.execute("SELECT COUNT(*) FROM events WHERE kind = 'introduced'").fetchone()[0]
        self.assertEqual(count, 2)

    def test_introduction_is_due_tomorrow_even_when_the_ladder_starts_later(self):
        deck, config = tiny("air", intervals=(9,))
        session = self.session(deck, config, TODAY)
        session.ensure_plan()
        row = session.conn.execute("SELECT due, interval_index FROM progress").fetchone()
        self.assertEqual(row["due"], "2026-09-30")
        self.assertEqual(row["interval_index"], 0)

    def test_a_day_shows_reviews_before_new_words_and_then_rests(self):
        deck = load_deck(ROOT / "deck" / "words.json")
        config = load_config(ROOT / "config.json")
        first = self.session(deck, config, TODAY)
        first.ensure_plan()
        second = Session(first.conn, deck, config, TODAY + timedelta(days=1))
        card = second.presentation()
        self.assertEqual(card.mode, "review")
        self.assertEqual(card.entry.id, "selamat")
        self.assertEqual(card.plan.new, ("saya", "mahu"))
        self.assertEqual(second.rate("known").entry.id, "selamat")
        self.assertEqual(second.presentation().entry.id, "pagi")
        second.rate("known")
        self.assertEqual(second.presentation().mode, "new")
        revealed = second.reveal()
        self.assertEqual(revealed.entry.id, "saya")
        self.assertTrue(revealed.revealed)
        self.assertEqual(second.presentation().entry.id, "mahu")
        second.reveal()
        resting = second.presentation()
        self.assertEqual(resting.mode, "rest")
        self.assertEqual(resting.entry.id, "mahu")
        self.assertEqual(resting.reviews_remaining, 0)
        self.assertEqual(resting.new_remaining, 0)

    def test_reveal_does_not_move_the_schedule(self):
        deck, config = tiny("air")
        session = self.session(deck, config, TODAY)
        session.ensure_plan()
        before = session.conn.execute("SELECT due, interval_index FROM progress").fetchone()
        session.reveal()
        after = session.conn.execute("SELECT due, interval_index FROM progress").fetchone()
        self.assertEqual(before["due"], after["due"])
        self.assertEqual(before["interval_index"], after["interval_index"])

    def test_a_new_word_cannot_be_rated_today(self):
        deck, config = tiny("air")
        session = self.session(deck, config, TODAY)
        with self.assertRaises(TepiError):
            session.rate("known")
        row = session.conn.execute("SELECT due, interval_index, state FROM progress").fetchone()
        self.assertEqual(row["due"], "2026-09-30")
        self.assertEqual(row["interval_index"], 0)
        self.assertEqual(row["state"], "in_play")

    def test_known_walks_the_ladder_and_the_next_success_settles(self):
        deck, config = tiny("air")
        first = self.session(deck, config, TODAY)
        first.ensure_plan()
        day = TODAY + timedelta(days=1)
        conn = first.conn
        for step, gap in enumerate(config.known_intervals):
            session = Session(conn, deck, config, day)
            rated = session.rate("known")
            self.assertEqual(rated.state, "in_play")
            self.assertEqual(rated.interval_index, step + 1)
            self.assertEqual(rated.due, day + timedelta(days=gap))
            day = rated.due
        settled = Session(conn, deck, config, day).rate("known")
        self.assertEqual(settled.state, "settled")
        self.assertIsNone(settled.due)
        later = Session(conn, deck, config, day + timedelta(days=3))
        self.assertEqual(later.presentation().plan.reviews, ())

    def test_fuzzy_keeps_the_index_and_missed_returns_to_the_start(self):
        deck, config = tiny("air")
        session = self.session(deck, config, TODAY)
        session.conn.execute(
            """
            INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
            VALUES ('air', '2026-09-01', '2026-09-29', 3, 'in_play', 0)
            """
        )
        session.conn.commit()
        fuzzy = session.rate("fuzzy")
        self.assertEqual(fuzzy.interval_index, 3)
        self.assertEqual(fuzzy.due, TODAY + timedelta(days=2))
        session.conn.execute(
            "UPDATE progress SET due = ?, interval_index = 3 WHERE word_id = 'air'",
            (TODAY.isoformat(),),
        )
        session.conn.execute("DELETE FROM plans")
        session.conn.execute("DELETE FROM events WHERE kind = 'fuzzy'")
        session.conn.commit()
        missed = session.rate("missed")
        self.assertEqual(missed.interval_index, 0)
        self.assertEqual(missed.due, TODAY + timedelta(days=1))

    def test_review_cap_keeps_the_oldest_due_and_leaves_the_rest(self):
        deck, config = tiny("a", "b", "c", new_per_day=0, review_cap=2)
        session = self.session(deck, config, TODAY)
        for word, due, index in (("a", "2026-09-27", 0), ("b", "2026-09-28", 1), ("c", "2026-09-29", 2)):
            session.conn.execute(
                """
                INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
                VALUES (?, '2026-09-01', ?, 0, 'in_play', ?)
                """,
                (word, due, index),
            )
        session.conn.commit()
        plan = session.ensure_plan()
        self.assertEqual(plan.reviews, ("a", "b"))
        session.rate("known")
        session.rate("known")
        self.assertEqual(session.presentation().mode, "rest")
        tomorrow = Session(session.conn, deck, config, TODAY + timedelta(days=1))
        self.assertEqual(tomorrow.presentation().plan.reviews[0], "c")

    def test_an_unready_word_stops_the_new_words_for_the_day(self):
        deck = Deck(
            (
                Entry("a", "a", "a", "A", "A.", "neutral", (), 0),
                Entry("b", "b", "b", "B", "B.", "neutral", ("c",), 1),
                Entry("c", "c", "c", "C", "C.", "neutral", (), 2),
            )
        )
        config = Config(3, 4, (1,), 2, 1)
        session = self.session(deck, config, TODAY)
        self.assertEqual(session.ensure_plan().new, ("a",))

    def test_log_lists_what_was_learned_without_introducing_more(self):
        deck, config = tiny("air", "kopi")
        session = self.session(deck, config, TODAY)
        empty = session.learning_log()
        self.assertEqual(empty.in_play, ())
        self.assertEqual(session.conn.execute("SELECT COUNT(*) FROM progress").fetchone()[0], 0)
        session.ensure_plan()
        learned = session.learning_log()
        self.assertEqual([item.entry.id for item in learned.in_play], ["air", "kopi"])
        self.assertEqual(learned.settled, ())
        self.assertEqual(learned.deck_size, 2)
        self.assertEqual([event.kind for event in learned.events], ["introduced", "introduced"])

    def test_command_hides_a_new_gloss_until_reveal(self):
        env = os.environ.copy()
        env["TEPI_DATA_DIR"] = self.tmp.name
        env["TEPI_TODAY"] = TODAY.isoformat()
        env["PYTHONPATH"] = str(ROOT)
        today = _run(["today", "--json"], env)
        self.assertEqual(today["mode"], "new")
        self.assertEqual(today["word"]["lemma"], "selamat")
        self.assertIsNone(today["word"]["gloss"])
        revealed = _run(["reveal", "--json"], env)
        self.assertEqual(revealed["word"]["gloss"], "safe; well")
        self.assertEqual(revealed["word"]["sentence"], "Selamat.")
        log = _run(["log"], env)
        self.assertIn("selamat", log)
        self.assertIn("pagi", log)
        rated = _run(["rate", "known"], env)
        self.assertIn("new today", rated.lower())


def _run(args, env) -> dict | str:
    completed = subprocess.run(
        [sys.executable, "-m", "tepi", *args],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if args[-1] == "--json" or "--json" in args:
        self_check = completed.returncode
        if self_check != 0:
            raise AssertionError(completed.stderr)
        return json.loads(completed.stdout)
    return completed.stdout + completed.stderr
