import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

from tepi.deck import TepiError, load_config, load_deck
from tepi.engine import LearningLog, Presentation, Rated, Session
from tepi.kamus import MISSING, Kamus, build_attestation, classify, load_authority, write_attestation
from tepi.tesaurus import (
    Tesaurus,
    build_attestation as build_thesaurus,
    classify as classify_thesaurus,
    load_authority as load_thesaurus,
    write_attestation as write_thesaurus,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = ROOT / "dictionary" / "kamus-dewan-perdana.json"
ATTESTATION_PATH = ROOT / "deck" / "kamus.json"
THESAURUS_PATH = ROOT / "dictionary" / "tesaurus-bahasa-melayu-dewan.json"
THESAURUS_ATTESTATION_PATH = ROOT / "deck" / "tesaurus.json"
CHECK_PAUSE = 0.4


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd in ("dict", "check"):
        return _dictionary(args)
    if args.cmd == "thesaurus":
        return _thesaurus(args)
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
        "catchUp": card.plan.catch_up,
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
    # Unset TEPI_CONFIG means the repo schedule. The bar never sets it.
    # TEPI_TEST is set by tests/_guard.py. The bar never sets it.
    raw_config = os.environ.get("TEPI_CONFIG")
    config_path = Path(raw_config) if raw_config else ROOT / "config.json"
    if os.environ.get("TEPI_TEST") and config_path.resolve() == (ROOT / "config.json").resolve():
        raise TepiError(f"A test opened the repo config at {config_path}. Pass a temp config instead.")
    return Session.open(data / "tepi.sqlite", load_deck(ROOT / "deck" / "words.json"), load_config(config_path), today)


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
    lookup = commands.add_parser("dict", help="Ask Kamus Dewan Perdana about one spelling")
    lookup.add_argument("words", nargs="+")
    lookup.add_argument("--json", action="store_true")
    check = commands.add_parser("check", help="Check every deck spelling against Kamus Dewan Perdana")
    check.add_argument("--json", action="store_true")
    thesaurus = commands.add_parser(
        "thesaurus",
        help="Ask Tesaurus Bahasa Melayu Dewan whether a lemma is listed",
    )
    thesaurus.add_argument("words", nargs="*")
    thesaurus.add_argument("--deck", action="store_true", help="Check every deck lemma and write deck/tesaurus.json")
    thesaurus.add_argument("--json", action="store_true")
    return parser


def _dictionary(args) -> int:
    try:
        authority = load_authority(AUTHORITY_PATH)
        kamus = Kamus(authority)
        if args.cmd == "dict":
            lemma = " ".join(args.words)
            status = classify(lemma, kamus.search(lemma))
            payload = {"lemma": lemma, "status": status, "authority": authority.id, "title": authority.title}
            _emit(payload if args.json else _format_dict(lemma, status, authority.title), args.json)
            return 1 if status == MISSING else 0
        deck = load_deck(ROOT / "deck" / "words.json")
        by_lemma: dict[str, str] = {}
        for entry in deck.entries:
            if entry.lemma in by_lemma:
                continue
            if by_lemma:
                time.sleep(CHECK_PAUSE)
            by_lemma[entry.lemma] = classify(entry.lemma, kamus.search(entry.lemma))
        payload = build_attestation(deck, by_lemma, date.today().isoformat())
        write_attestation(ATTESTATION_PATH, payload)
        _emit(payload if args.json else _format_check(payload, authority.title), args.json)
        return 1 if any(row["status"] == MISSING for row in payload["words"]) else 0
    except TepiError as err:
        print(err, file=sys.stderr)
        return 2


def _thesaurus(args) -> int:
    if args.deck == bool(args.words):
        print("Give a word, or pass --deck.", file=sys.stderr)
        return 2
    try:
        authority = load_thesaurus(THESAURUS_PATH)
        book = Tesaurus(authority)
        if not args.deck:
            lemma = " ".join(args.words)
            place = classify_thesaurus(lemma, book.search(lemma))
            payload = {
                "lemma": lemma,
                "status": place.status,
                "authority": authority.id,
                "title": authority.title,
            }
            if place.word_class:
                payload["class"] = place.word_class
            _emit(payload if args.json else _format_thesaurus(lemma, place, authority.title), args.json)
            return 0
        deck = load_deck(ROOT / "deck" / "words.json")
        by_lemma = {}
        for entry in deck.entries:
            if entry.lemma in by_lemma:
                continue
            if by_lemma:
                time.sleep(CHECK_PAUSE)
            by_lemma[entry.lemma] = classify_thesaurus(entry.lemma, book.search(entry.lemma))
        payload = build_thesaurus(deck, by_lemma, date.today().isoformat())
        write_thesaurus(THESAURUS_ATTESTATION_PATH, payload)
        _emit(payload if args.json else _format_thesaurus_deck(payload, authority.title), args.json)
        return 0
    except TepiError as err:
        print(err, file=sys.stderr)
        return 2


def _format_thesaurus(lemma: str, place, title: str) -> str:
    lines = [lemma, place.status]
    if place.word_class:
        lines.append(place.word_class)
    lines.append(title)
    return "\n".join(lines) + "\n"


def _format_thesaurus_deck(payload: dict, title: str) -> str:
    listed = [row for row in payload["words"] if row["status"] == "listed"]
    unlisted = [row for row in payload["words"] if row["status"] != "listed"]
    lines = [
        f"{title}  ·  {payload['checked']}  ·  {len(payload['words'])} words",
        f"listed {len(listed)}  ·  unlisted {len(unlisted)}",
    ]
    if unlisted:
        lines.append("")
        width = max(len(row["lemma"]) for row in unlisted)
        for row in unlisted:
            lines.append(f"  {row['lemma']:<{width}}  unlisted")
    if listed:
        lines.append("")
        width = max(len(row["lemma"]) for row in listed)
        for row in listed:
            lines.append(f"  {row['lemma']:<{width}}  {row.get('class', '')}".rstrip())
    return "\n".join(lines) + "\n"


def _format_dict(lemma: str, status: str, title: str) -> str:
    return f"{lemma}\n{status}\n{title}\n"


def _format_check(payload: dict, title: str) -> str:
    counts: dict[str, int] = {}
    for row in payload["words"]:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    lines = [
        f"{title}  ·  {payload['checked']}  ·  {len(payload['words'])} words",
        (
            f"headword {counts.get('headword', 0)}"
            f"  ·  phrase {counts.get('phrase', 0)}"
            f"  ·  derivative {counts.get('derivative', 0)}"
            f"  ·  missing {counts.get('missing', 0)}"
        ),
    ]
    flagged = [row for row in payload["words"] if row["status"] != "headword"]
    if flagged:
        lines.append("")
        width = max(len(row["lemma"]) for row in flagged)
        for row in flagged:
            lines.append(f"  {row['lemma']:<{width}}  {row['status']}")
    return "\n".join(lines) + "\n"


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
        text = f"{card.date.isoformat()}  {label}  {place}/{len(card.plan.reviews)}"
    elif card.mode == "new" and card.plan.new:
        place = card.plan.new.index(card.entry.id) + 1
        text = f"{card.date.isoformat()}  {label}  {place}/{len(card.plan.new)}"
    else:
        text = f"{card.date.isoformat()}  {label}"
    if card.plan.catch_up:
        return f"{text} (catch-up)"
    return text


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
