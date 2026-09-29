import argparse
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

from tepi.deck import TepiError, load_config, load_deck
from tepi.engine import LearningLog, Presentation, Rated, Session

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        session = _session()
    except TepiError as err:
        print(err, file=sys.stderr)
        return 2
    try:
        if args.cmd == "today":
            card = session.presentation()
            _emit(card_payload(card) if args.json else _format_today(card), args.json)
        elif args.cmd == "reveal":
            card = session.reveal()
            _emit(card_payload(card) if args.json else _format_revealed(card), args.json)
        elif args.cmd == "rate":
            rated = session.rate(args.rating)
            _emit(rated_payload(rated) if args.json else _format_rated(rated), args.json)
        elif args.cmd == "log":
            learned = session.learning_log(None if args.all else 7)
            _emit(log_payload(learned) if args.json else _format_log(learned), args.json)
        else:
            raise TepiError("Unknown command.")
    except TepiError as err:
        print(err, file=sys.stderr)
        return 2
    except sqlite3.DatabaseError as err:
        print(err, file=sys.stderr)
        return 1
    finally:
        session.close()
    return 0


def card_payload(card: Presentation) -> dict:
    show = card.revealed or card.mode == "rest"
    word = None if card.entry is None else _word(card.entry, show)
    return {
        "date": card.date.isoformat(),
        "mode": card.mode,
        "revealed": card.revealed,
        "word": word,
        "plan": {"reviews": list(card.plan.reviews), "new": list(card.plan.new)},
        "remaining": {"reviews": card.reviews_remaining, "new": card.new_remaining},
    }


def rated_payload(rated: Rated) -> dict:
    return {
        "rating": rated.rating,
        "due": rated.due.isoformat() if rated.due else None,
        "state": rated.state,
        "intervalIndex": rated.interval_index,
        "word": _word(rated.entry, True),
    }


def log_payload(learned: LearningLog) -> dict:
    return {
        "deck": learned.deck_size,
        "settled": [_learned(item) for item in learned.settled],
        "inPlay": [_learned(item) for item in learned.in_play],
        "events": [
            {"day": event.day.isoformat(), "kind": event.kind, "id": event.word_id, "lemma": event.lemma}
            for event in learned.events
        ],
    }


def _session() -> Session:
    raw_today = os.environ.get("TEPI_TODAY")
    today = date.fromisoformat(raw_today) if raw_today else date.today()
    data = Path(os.environ.get("TEPI_DATA_DIR", Path.home() / ".local/share/tepi"))
    return Session.open(data / "tepi.sqlite", load_deck(ROOT / "deck" / "words.json"), load_config(ROOT / "config.json"), today)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tepi",
        description="Introduce two Bahasa Melayu words a day and remember how they went.",
    )
    commands = parser.add_subparsers(dest="cmd", required=True)
    for name, help_text in (
        ("today", "Show the one word for now"),
        ("reveal", "Show the meaning of the current word"),
        ("log", "Show what you have already learned"),
    ):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--json", action="store_true")
        if name == "log":
            sub.add_argument("--all", action="store_true", help="Include every day in the diary")
    rate = commands.add_parser("rate", help="Record a review of the current word")
    rate.add_argument("rating", choices=("known", "fuzzy", "missed"))
    rate.add_argument("--json", action="store_true")
    return parser


def _emit(payload, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload, end="" if payload.endswith("\n") else "\n")


def _format_today(card: Presentation) -> str:
    if card.entry is None:
        return "The deck has nothing to show.\n"
    lines = [_heading(card), "", card.entry.lemma]
    if card.revealed or card.mode == "rest":
        lines.extend((card.entry.gloss, card.entry.sentence))
    lines.append("")
    lines.append(f"reviews left {card.reviews_remaining}  ·  new left {card.new_remaining}")
    hint = _hint(card)
    if hint:
        lines.extend(("", hint))
    return "\n".join(lines) + "\n"


def _format_revealed(card: Presentation) -> str:
    if card.entry is None:
        return "Nothing to reveal.\n"
    lines = [card.entry.lemma, card.entry.gloss, card.entry.sentence, ""]
    if card.mode == "new":
        lines.append("New today.")
    elif card.mode == "review":
        lines.append("tepi rate known|fuzzy|missed")
    return "\n".join(lines) + "\n"


def _format_rated(rated: Rated) -> str:
    due = "settled" if rated.state == "settled" else f"due {rated.due.isoformat()}"
    return "\n".join((f"{rated.entry.lemma}  {rated.rating}", due, rated.entry.gloss, rated.entry.sentence, ""))


def _format_log(learned: LearningLog) -> str:
    waiting = learned.deck_size - len(learned.settled) - len(learned.in_play)
    lines = [
        f"Deck {learned.deck_size}  ·  in play {len(learned.in_play)}  ·  settled {len(learned.settled)}  ·  not yet {waiting}",
        "",
        "Settled",
    ]
    lines.extend(_learned_lines(learned.settled, False))
    lines.extend(("", "In play"))
    lines.extend(_learned_lines(learned.in_play, True))
    lines.extend(("", "Recent"))
    if not learned.events:
        lines.append("  none yet")
    else:
        for event in learned.events:
            lines.append(f"  {event.day.isoformat()}  {event.kind:<12}{event.lemma}")
    return "\n".join(lines) + "\n"


def _learned_lines(items, with_due: bool) -> list[str]:
    if not items:
        return ["  none yet"]
    gloss_width = max(len(item.entry.gloss) for item in items)
    lines = []
    for item in items:
        line = f"  {item.entry.lemma:<16}{item.entry.gloss:<{gloss_width}}"
        if with_due and item.due:
            line += f"  due {item.due.isoformat()}"
        lines.append(line)
    return lines


def _heading(card: Presentation) -> str:
    label = "resting" if card.mode == "rest" else card.mode
    if card.mode == "review" and card.plan.reviews:
        place = card.plan.reviews.index(card.entry.id) + 1
        return f"{card.date.isoformat()}  {label}  {place}/{len(card.plan.reviews)}"
    if card.mode == "new" and card.plan.new:
        place = card.plan.new.index(card.entry.id) + 1
        return f"{card.date.isoformat()}  {label}  {place}/{len(card.plan.new)}"
    return f"{card.date.isoformat()}  {label}"


def _hint(card: Presentation) -> str:
    if card.mode == "new":
        return "tepi reveal"
    if card.mode == "review":
        return "tepi rate known|fuzzy|missed" if card.revealed else "tepi reveal    or    tepi rate known|fuzzy|missed"
    return ""


def _word(entry, show: bool) -> dict:
    return {
        "id": entry.id,
        "lemma": entry.lemma,
        "root": entry.root,
        "register": entry.register,
        "gloss": entry.gloss if show else None,
        "sentence": entry.sentence if show else None,
    }


def _learned(item) -> dict:
    return {
        "id": item.entry.id,
        "lemma": item.entry.lemma,
        "gloss": item.entry.gloss,
        "introducedOn": item.introduced_on.isoformat(),
        "due": item.due.isoformat() if item.due else None,
        "intervalIndex": item.interval_index,
        "state": item.state,
    }
