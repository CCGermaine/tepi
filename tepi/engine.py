import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from tepi.db import connect
from tepi.deck import Config, Deck, Entry, TepiError
from tepi.kamus import MISSING
from tepi.sentence import tokens, unknown

RATINGS = ("known", "fuzzy", "missed")


@dataclass(frozen=True)
class Plan:
    day: date
    reviews: tuple[str, ...]
    new: tuple[str, ...]
    catch_up: bool = False


@dataclass(frozen=True)
class Presentation:
    date: date
    mode: str
    entry: Entry | None
    revealed: bool
    plan: Plan
    reviews_remaining: int
    new_remaining: int


@dataclass(frozen=True)
class Rated:
    entry: Entry
    rating: str
    due: date | None
    state: str
    interval_index: int


@dataclass(frozen=True)
class Learned:
    entry: Entry
    introduced_on: date
    due: date | None
    interval_index: int
    state: str


@dataclass(frozen=True)
class Event:
    day: date
    kind: str
    word_id: str
    lemma: str


@dataclass(frozen=True)
class LearningLog:
    settled: tuple[Learned, ...]
    in_play: tuple[Learned, ...]
    events: tuple[Event, ...]
    deck_size: int


@dataclass(frozen=True)
class Family:
    root: str
    members: tuple[Entry, ...]


def cousin_families(deck: Deck) -> tuple[Family, ...]:
    """Root families with two or more members, derived from the deck alone.

    Members keep teaching order. Families are ordered by the teaching index of
    their first member. A root with a single word has no cousins and is left out.
    This reads no progress log.
    """
    groups: dict[str, list[Entry]] = {}
    for entry in deck.entries:
        groups.setdefault(entry.root, []).append(entry)
    families = [Family(root, tuple(members)) for root, members in groups.items() if len(members) >= 2]
    families.sort(key=lambda family: family.members[0].index)
    return tuple(families)


def cousins_of(deck: Deck, entry: Entry) -> tuple[str, ...]:
    """The other lemmas in this word's family, in teaching order."""
    for family in cousin_families(deck):
        if any(member.id == entry.id for member in family.members):
            return tuple(member.lemma for member in family.members if member.id != entry.id)
    return ()


@dataclass(frozen=True)
class Prompt:
    entry: Entry
    sentence: str


def attested_settled(settled, attestation) -> tuple[Learned, ...]:
    """Settled words whose spelling the saved dictionary check attests.

    A settled word with no row, or a row marked missing, is left out. The
    incoming order (teaching order) is kept.
    """
    rows = {row["id"]: row for row in attestation["words"]}
    usable = []
    for item in settled:
        row = rows.get(item.entry.id)
        if row and row["lemma"] == item.entry.lemma and row["status"] != MISSING:
            usable.append(item)
    return tuple(usable)


def prompt_sentence(settled, attestation) -> Prompt | None:
    """The first settled, attested word whose own sentence can be formed.

    A sentence qualifies when it has at most 12 tokens and every non-function
    word is itself a settled, attested lemma. Only a sentence already in the
    deck is returned, so no spelling is invented. Returns None when no settled
    word can form its sentence. Reads no progress log; the caller passes the
    settled words.
    """
    usable = attested_settled(settled, attestation)
    allowed = {item.entry.lemma for item in usable}
    for item in usable:
        sentence = item.entry.sentence
        toks = tokens(sentence)
        if toks and len(toks) <= 12 and not unknown(toks, allowed, active=False):
            return Prompt(item.entry, sentence)
    return None


class Session:
    def __init__(self, conn, deck: Deck, config: Config, today: date):
        self.conn = conn
        self.deck = deck
        self.config = config
        self.today = today

    @classmethod
    def open(cls, db_path, deck: Deck, config: Config, today: date) -> "Session":
        return cls(connect(db_path), deck, config, today)

    def close(self) -> None:
        self.conn.close()

    def ensure_plan(self) -> Plan:
        existing = self.conn.execute(
            "SELECT reviews, introduced, catch_up FROM plans WHERE day = ?",
            (_iso(self.today),),
        ).fetchone()
        if existing:
            return Plan(
                self.today,
                tuple(json.loads(existing["reviews"])),
                tuple(json.loads(existing["introduced"])),
                bool(existing["catch_up"]),
            )
        reviews, catch_up = self._due_ids()
        fresh = self._next_new_words()
        tomorrow = self.today + timedelta(days=1)
        now = _now()
        for entry in fresh:
            self.conn.execute(
                """
                INSERT INTO progress (word_id, introduced_on, due, interval_index, state, deck_index)
                VALUES (?, ?, ?, 0, 'in_play', ?)
                """,
                (entry.id, _iso(self.today), _iso(tomorrow), entry.index),
            )
            self._event(entry.id, "introduced", now)
        plan = Plan(self.today, reviews, tuple(entry.id for entry in fresh), catch_up)
        self.conn.execute(
            "INSERT INTO plans (day, reviews, introduced, catch_up) VALUES (?, ?, ?, ?)",
            (_iso(self.today), json.dumps(plan.reviews), json.dumps(plan.new), int(plan.catch_up)),
        )
        self.conn.commit()
        return plan

    def presentation(self) -> Presentation:
        plan = self.ensure_plan()
        rated, revealed = self._today_marks()
        reviews_left = [word_id for word_id in plan.reviews if word_id not in rated]
        new_left = [word_id for word_id in plan.new if word_id not in revealed]
        if reviews_left:
            return self._card(plan, reviews_left[0], "review", reviews_left[0] in revealed, reviews_left, new_left)
        if new_left:
            return self._card(plan, new_left[0], "new", False, reviews_left, new_left)
        if plan.new:
            resting = plan.new[-1]
        elif plan.reviews:
            resting = plan.reviews[-1]
        else:
            resting = self._latest_introduced()
        return self._card(plan, resting, "rest", True, reviews_left, new_left)

    def reveal(self) -> Presentation:
        card = self.presentation()
        if card.entry is None:
            raise TepiError("Nothing to reveal.")
        self._event(card.entry.id, "revealed", _now())
        self.conn.commit()
        return Presentation(
            card.date,
            card.mode,
            card.entry,
            True,
            card.plan,
            card.reviews_remaining,
            card.new_remaining,
        )

    def rate(self, rating: str) -> Rated:
        if rating not in RATINGS:
            raise TepiError("Rate a word known, fuzzy, or missed.")
        card = self.presentation()
        if card.mode == "new" and card.entry is not None:
            due = _parse(self._progress(card.entry.id)["due"])
            raise TepiError(
                f"{card.entry.lemma} is new today. It is due {due.isoformat()}. tepi reveal shows the meaning."
            )
        if card.mode != "review" or card.entry is None:
            raise TepiError("Nothing to rate.")
        row = self._progress(card.entry.id)
        index = row["interval_index"]
        state = "in_play"
        due: date | None
        if rating == "known" and index >= len(self.config.known_intervals):
            # The ladder, including the longest gap, is already behind this word.
            state = "settled"
            due = None
            new_index = index
        elif rating == "known":
            due = self.today + timedelta(days=self.config.known_intervals[index])
            new_index = index + 1
        elif rating == "fuzzy":
            due = self.today + timedelta(days=self.config.fuzzy_days)
            new_index = index
        else:
            due = self.today + timedelta(days=self.config.missed_days)
            new_index = 0
        self.conn.execute(
            "UPDATE progress SET due = ?, interval_index = ?, state = ? WHERE word_id = ?",
            (_iso(due) if due else None, new_index, state, card.entry.id),
        )
        self._event(card.entry.id, rating, _now())
        self.conn.commit()
        return Rated(card.entry, rating, due, state, new_index)

    def learning_log(self, recent_days: int | None = 7) -> LearningLog:
        learned = [self._learned(row) for row in self.conn.execute("SELECT * FROM progress ORDER BY deck_index")]
        events = []
        for row in self.conn.execute("SELECT day, kind, word_id FROM events ORDER BY id"):
            day = _parse(row["day"])
            if recent_days is not None and day < self.today - timedelta(days=recent_days - 1):
                continue
            entry = self.deck.by_id.get(row["word_id"])
            events.append(Event(day, row["kind"], row["word_id"], entry.lemma if entry else row["word_id"]))
        return LearningLog(
            tuple(item for item in learned if item.state == "settled"),
            tuple(item for item in learned if item.state == "in_play"),
            tuple(events),
            len(self.deck.entries),
        )

    def _due_ids(self) -> tuple[tuple[str, ...], bool]:
        today = _iso(self.today)
        rows = self.conn.execute(
            """
            SELECT word_id, due FROM progress
            WHERE state = 'in_play' AND due IS NOT NULL AND due <= ?
            ORDER BY due ASC, deck_index ASC
            """,
            (today,),
        ).fetchall()
        # Overdue means due before today. A word due today does not raise the cap.
        # The marker stays off unless the higher cap actually adds reviews.
        overdue = any(row["due"] < today for row in rows)
        use_higher = bool(self.config.catch_up and overdue)
        cap = self.config.catch_up_review_cap if use_higher else self.config.review_cap
        chosen = tuple(row["word_id"] for row in rows[:cap])
        catch_up = use_higher and len(chosen) > self.config.review_cap
        return chosen, catch_up

    def _next_new_words(self) -> tuple[Entry, ...]:
        if self.config.new_per_day == 0:
            return ()
        introduced = {row["word_id"] for row in self.conn.execute("SELECT word_id FROM progress")}
        fresh: list[Entry] = []
        batch: set[str] = set()
        for entry in self.deck.entries:
            if entry.id in introduced:
                continue
            ready = all(req in introduced or req in batch for req in entry.requires)
            if not ready:
                break
            fresh.append(entry)
            batch.add(entry.id)
            if len(fresh) == self.config.new_per_day:
                break
        return tuple(fresh)

    def _today_marks(self) -> tuple[set[str], set[str]]:
        rated: set[str] = set()
        revealed: set[str] = set()
        for row in self.conn.execute("SELECT word_id, kind FROM events WHERE day = ?", (_iso(self.today),)):
            if row["kind"] in RATINGS:
                rated.add(row["word_id"])
            elif row["kind"] == "revealed":
                revealed.add(row["word_id"])
        return rated, revealed

    def _latest_introduced(self) -> str | None:
        row = self.conn.execute(
            "SELECT word_id FROM progress ORDER BY introduced_on DESC, deck_index DESC LIMIT 1"
        ).fetchone()
        return row["word_id"] if row else None

    def _card(self, plan, word_id, mode, revealed, reviews_left, new_left) -> Presentation:
        entry = self.deck.entry(word_id) if word_id else None
        return Presentation(
            self.today,
            "empty" if entry is None else mode,
            entry,
            revealed if entry else False,
            plan,
            len(reviews_left),
            len(new_left),
        )

    def _progress(self, word_id: str):
        row = self.conn.execute("SELECT * FROM progress WHERE word_id = ?", (word_id,)).fetchone()
        if row is None:
            raise TepiError(f"{word_id} is not in the log.")
        return row

    def _learned(self, row) -> Learned:
        entry = self.deck.by_id.get(row["word_id"])
        if entry is None:
            entry = Entry(row["word_id"], row["word_id"], row["word_id"], "(not in the deck)", "", "neutral", (), row["deck_index"])
        return Learned(entry, _parse(row["introduced_on"]), _parse(row["due"]) if row["due"] else None, row["interval_index"], row["state"])

    def _event(self, word_id: str, kind: str, ts: str) -> None:
        self.conn.execute(
            "INSERT INTO events (ts, day, word_id, kind) VALUES (?, ?, ?, ?)",
            (ts, _iso(self.today), word_id, kind),
        )


def _iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


def _parse(value: str) -> date:
    return date.fromisoformat(value)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
