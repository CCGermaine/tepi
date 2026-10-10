"""Look up a lemma in Tesaurus Bahasa Melayu Dewan.

The synonym lists stay on the portal. A hit records whether the lemma is the
panel's headword and, when the panel gives one, the word class.
"""

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urlencode

from tepi.deck import Deck, TepiError

AUTHORITY_ID = "tesaurus-bahasa-melayu-dewan"
LISTED = "listed"
UNLISTED = "unlisted"
STATUSES = (LISTED, UNLISTED)

_CLASS = {
    "kata nama": "noun",
    "kata kerja": "verb",
    "adjektif": "adjective",
    "kata adjektif": "adjective",
    "kata sifat": "adjective",
    "kata keterangan": "adverb",
    "adverb": "adverb",
    "adverba": "adverb",
    "kata tugas": "particle",
    "kata ganti": "pronoun",
    "ganti nama": "pronoun",
    "kata sendi": "preposition",
    "kata sendi nama": "preposition",
    "kata hubung": "conjunction",
    "kata seru": "interjection",
    "penentu": "determiner",
    "bilangan": "number",
    "kata bilangan": "number",
}
CLASS_LABELS = frozenset(_CLASS.values())

_TH = re.compile(r"<th[^>]*>\s*Tesaurus\s*</th>", re.IGNORECASE)
_NEXT_TH = re.compile(r"<th\b", re.IGNORECASE)
_HEAD = re.compile(
    r"<b>\s*<span\b[^>]*font-weight:\s*bold[^>]*>(.*?)</span>\s*</b>"
    r"(?:(?:\s|&nbsp;|&#160;)*\(\s*<font\b[^>]*>\s*<i>(.*?)</i>\s*</font>\s*\))?",
    re.IGNORECASE | re.DOTALL,
)
_SUP = re.compile(r"<sup\b[^>]*>.*?</sup>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_TIADA = "tiada maklumat tesaurus"


@dataclass(frozen=True)
class Authority:
    id: str
    title: str
    publisher: str
    published: str
    isbn: str
    portal: str
    note: str


@dataclass(frozen=True)
class Head:
    form: str
    classes: tuple[str, ...]


@dataclass(frozen=True)
class Place:
    status: str
    word_class: str | None = None


def load_authority(path: Path) -> Authority:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise TepiError(f"Could not read the thesaurus at {path}.") from err
    if not isinstance(raw, dict):
        raise TepiError(f"The thesaurus at {path} is not an object.")
    portal = _field(raw, "portal", path)
    if not portal.startswith("https://"):
        raise TepiError(f"The thesaurus portal in {path} must be an https address.")
    return Authority(
        id=_field(raw, "id", path),
        title=_field(raw, "title", path),
        publisher=_field(raw, "publisher", path),
        published=_field(raw, "published", path),
        isbn=_field(raw, "isbn", path),
        portal=portal.rstrip("/"),
        note=_field(raw, "note", path),
    )


def parse_heads(page: str) -> list[Head]:
    """Read headwords off the Tesaurus panel. Synonym links are ignored."""
    block = _panel(page)
    heads: list[Head] = []
    for match in _HEAD.finditer(block):
        raw_class = match.group(2)
        if raw_class is None:
            classes: tuple[str, ...] = ()
        else:
            classes = _class_tokens(raw_class)
            if not classes:
                form = _plain(match.group(1))
                raise TepiError(f"Tesaurus Bahasa Melayu Dewan lists {form!r} without a word class.")
        heads.append(Head(form=_plain(match.group(1)), classes=classes))
    return heads


def classify(lemma: str, heads: list[Head]) -> Place:
    wanted = _squash(lemma).casefold()
    if not wanted:
        raise TepiError("Give a word to look up.")
    mapped: list[str] = []
    seen: set[str] = set()
    matched = False
    for head in heads:
        if _squash(head.form).casefold() != wanted:
            continue
        matched = True
        for token in head.classes:
            label = _CLASS.get(token)
            if label is None:
                raise TepiError(
                    f"Tesaurus Bahasa Melayu Dewan labels {head.form!r} as {token!r}, which Tepi does not know."
                )
            if label not in seen:
                seen.add(label)
                mapped.append(label)
    if not matched:
        return Place(UNLISTED)
    if not mapped:
        return Place(LISTED)
    return Place(LISTED, "+".join(mapped))


def build_attestation(deck: Deck, by_lemma: Mapping[str, Place], checked: str) -> dict:
    words = []
    for entry in deck.entries:
        place = by_lemma.get(entry.lemma)
        if not isinstance(place, Place) or place.status not in STATUSES:
            raise TepiError(f"{entry.lemma} has no thesaurus status.")
        if place.word_class is not None and not _valid_class(place.word_class):
            raise TepiError(f"{entry.lemma} has a word class Tepi does not know.")
        if place.status == UNLISTED and place.word_class is not None:
            raise TepiError(f"{entry.lemma} is unlisted and has no word class to store.")
        row = {"id": entry.id, "lemma": entry.lemma, "status": place.status}
        if place.word_class:
            row["class"] = place.word_class
        words.append(row)
    return {"authority": AUTHORITY_ID, "checked": checked, "words": words}


def load_attestation(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise TepiError(f"Could not read the thesaurus check at {path}.") from err
    words = raw.get("words") if isinstance(raw, dict) else None
    if raw.get("authority") != AUTHORITY_ID or not isinstance(words, list):
        raise TepiError(f"The thesaurus check at {path} is not a Tesaurus Bahasa Melayu Dewan record.")
    for item in words:
        if not _row_ok(item):
            raise TepiError(f"The thesaurus check at {path} has a row Tepi cannot read.")
    return raw


def write_attestation(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Tesaurus:
    """One session against the public Tesaurus panel."""

    def __init__(self, authority: Authority):
        self.authority = authority

    def search(self, lemma: str) -> list[Head]:
        return parse_heads(self.fetch(lemma))

    def fetch(self, lemma: str) -> str:
        query = _squash(lemma)
        if not query:
            raise TepiError("Give a word to look up.")
        url = self.authority.portal + "/Cari1?" + urlencode({"keyword": query})
        return self._request(url)

    def _request(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Tepi (personal thesaurus check)",
                "Accept": "text/html",
            },
        )
        delay = 1.0
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return response.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as err:
                if err.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise TepiError("Tesaurus Bahasa Melayu Dewan did not answer.") from err
            except urllib.error.URLError as err:
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise TepiError("Tesaurus Bahasa Melayu Dewan did not answer.") from err
        raise TepiError("Tesaurus Bahasa Melayu Dewan did not answer.")


def _panel(page: str) -> str:
    marker = _TH.search(page)
    if marker is None:
        if _TIADA in page.casefold():
            return ""
        raise TepiError("Tesaurus Bahasa Melayu Dewan did not return a thesaurus panel.")
    start = marker.end()
    nxt = _NEXT_TH.search(page, start)
    return page[start:nxt.start()] if nxt else page[start:]


def _class_tokens(raw: str) -> tuple[str, ...]:
    text = unescape(_TAGS.sub(" ", raw))
    tokens = []
    for part in re.split(r"[,;/]+", text):
        token = " ".join(part.strip().strip(".").split()).casefold()
        if token:
            tokens.append(token)
    return tuple(tokens)


def _valid_class(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parts = value.split("+")
    return len(parts) == len(set(parts)) and all(part in CLASS_LABELS for part in parts)


def _row_ok(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    if not isinstance(item.get("id"), str) or not isinstance(item.get("lemma"), str):
        return False
    status = item.get("status")
    if status == UNLISTED:
        return "class" not in item
    if status != LISTED:
        return False
    if "class" not in item:
        return True
    return _valid_class(item.get("class"))


def _field(raw: dict, key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TepiError(f"The thesaurus at {path} is missing {key}.")
    return value.strip()


def _squash(text: str) -> str:
    return " ".join(text.split())


def _plain(inner: str) -> str:
    """Headword text. A homonym number sits in a superscript and is not part of the spelling."""
    return _squash(unescape(_TAGS.sub(" ", _SUP.sub(" ", inner))))
