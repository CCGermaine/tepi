"""Look up a spelling in Kamus Dewan Perdana.

The portal text stays on the portal. A hit records the entry kind only.
"""

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from html import unescape
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import unquote, urlencode, urljoin

from tepi.deck import Deck, TepiError

AUTHORITY_ID = "kamus-dewan-perdana"
HEADWORD = "headword"
PHRASE = "phrase"
DERIVATIVE = "derivative"
MISSING = "missing"
STATUSES = (HEADWORD, PHRASE, DERIVATIVE, MISSING)

_KIND = {
    "kata entri": HEADWORD,
    "frasa kata entri": PHRASE,
    "kata terbitan": DERIVATIVE,
    "frasa kata terbitan": DERIVATIVE,
}
_RANK = {HEADWORD: 3, PHRASE: 2, DERIVATIVE: 1, MISSING: 0}
_CARD = re.compile(r"""onclick="syncLemmaId\('([^']*)',\s*'(\d+)'\)\"""")
_FORM = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.IGNORECASE | re.DOTALL)
_SUP = re.compile(r"<sup\b[^>]*>.*?</sup>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_BADGE = re.compile(r'<span[^>]*rounded-full[^>]*>\s*([^<]+?)\s*</span>', re.IGNORECASE)
_TOKEN = re.compile(r'name="_token" value="([^"]+)"')


@dataclass(frozen=True)
class Authority:
    id: str
    title: str
    publisher: str
    published: str
    portal: str
    portal_since: str


@dataclass(frozen=True)
class Hit:
    form: str
    kind: str


def load_authority(path: Path) -> Authority:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise TepiError(f"Could not read the dictionary at {path}.") from err
    if not isinstance(raw, dict):
        raise TepiError(f"The dictionary at {path} is not an object.")
    portal = _field(raw, "portal", path)
    if not portal.startswith("https://"):
        raise TepiError(f"The dictionary portal in {path} must be an https address.")
    return Authority(
        id=_field(raw, "id", path),
        title=_field(raw, "title", path),
        publisher=_field(raw, "publisher", path),
        published=_field(raw, "published", path),
        portal=portal.rstrip("/"),
        portal_since=_field(raw, "portalSince", path),
    )


def parse_hits(page: str) -> list[Hit]:
    """Read entry kinds off a search page. The sense text is ignored."""
    if "Carian untuk" not in page and "search-result" not in page:
        raise TepiError("Kamus Dewan Perdana did not return a search page.")
    hits: list[Hit] = []
    for match in _CARD.finditer(page):
        window = page[match.end():match.end() + 8000]
        nxt = window.find("search-result")
        if nxt != -1:
            window = window[:nxt]
        form = _FORM.search(window)
        badge = _BADGE.search(window)
        if form is None or badge is None:
            raise TepiError("Kamus Dewan Perdana changed the search card, so Tepi stopped.")
        hits.append(Hit(form=_plain(form.group(1)), kind=_squash(unescape(badge.group(1)))))
    return hits


def classify(lemma: str, hits: list[Hit]) -> str:
    wanted = _squash(lemma).casefold()
    if not wanted:
        raise TepiError("Give a word to look up.")
    found = MISSING
    for hit in hits:
        if _squash(hit.form).casefold() != wanted:
            continue
        status = _KIND.get(hit.kind.casefold())
        if status is None:
            raise TepiError(f"Kamus Dewan Perdana labels {hit.form!r} as {hit.kind!r}, which Tepi does not know.")
        if _RANK[status] > _RANK[found]:
            found = status
    return found


def build_attestation(deck: Deck, by_lemma: Mapping[str, str], checked: str) -> dict:
    words = []
    for entry in deck.entries:
        status = by_lemma.get(entry.lemma)
        if status not in STATUSES:
            raise TepiError(f"{entry.lemma} has no dictionary status.")
        words.append({"id": entry.id, "lemma": entry.lemma, "status": status})
    return {"authority": AUTHORITY_ID, "checked": checked, "words": words}


def load_attestation(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise TepiError(f"Could not read the dictionary check at {path}.") from err
    words = raw.get("words") if isinstance(raw, dict) else None
    if raw.get("authority") != AUTHORITY_ID or not isinstance(words, list):
        raise TepiError(f"The dictionary check at {path} is not a Kamus Dewan Perdana record.")
    for item in words:
        if not isinstance(item, dict) or item.get("status") not in STATUSES:
            raise TepiError(f"The dictionary check at {path} has a row Tepi cannot read.")
        if not isinstance(item.get("id"), str) or not isinstance(item.get("lemma"), str):
            raise TepiError(f"The dictionary check at {path} has a row Tepi cannot read.")
    return raw


def write_attestation(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Kamus:
    """One session against the portal.

    Three letters or more come from the public suggestion list, which names the
    entry kind and not the definition. Shorter words are not in that list, so
    they are read off the search page.
    """

    def __init__(self, authority: Authority):
        self.authority = authority
        self._jar = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            _StopRedirect(),
        )
        self._token = ""
        self._xsrf = ""
        self._snapshot = ""

    def search(self, lemma: str) -> list[Hit]:
        query = _squash(lemma)
        if not query:
            raise TepiError("Give a word to look up.")
        if len(query) >= 3:
            return self._suggest(query)
        return parse_hits(self.fetch(query))

    def fetch(self, lemma: str) -> str:
        query = _squash(lemma)
        if not query:
            raise TepiError("Give a word to look up.")
        self._ensure_session()
        status, headers, _body = self._request(
            self.authority.portal + "/carian",
            data=urlencode({"_token": self._token, "query": query}).encode(),
            referer=self.authority.portal + "/",
            full=True,
        )
        if status not in (301, 302, 303, 307, 308):
            raise TepiError("Kamus Dewan Perdana did not accept the search.")
        location = headers.get("Location")
        if not location:
            raise TepiError("Kamus Dewan Perdana did not return a search page.")
        return self._follow(urljoin(self.authority.portal + "/", location))

    def _suggest(self, query: str) -> list[Hit]:
        self._ensure_session()
        payload = self._livewire(query)
        if payload is None:
            self._snapshot = ""
            self._ensure_session()
            payload = self._livewire(query)
        if payload is None:
            raise TepiError("Kamus Dewan Perdana did not return suggestions.")
        return hits_from_suggestions(payload)

    def _livewire(self, query: str) -> dict | None:
        body = json.dumps(
            {
                "_token": self._token,
                "components": [{"snapshot": self._snapshot, "updates": {"query": query}, "calls": []}],
            }
        ).encode()
        request = urllib.request.Request(
            self.authority.portal + "/livewire/update",
            data=body,
            headers={
                "User-Agent": "Tepi (personal spelling check)",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Livewire": "",
                "Referer": self.authority.portal + "/",
                "X-XSRF-TOKEN": self._xsrf,
            },
        )
        try:
            with self._opener.open(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None

    def _ensure_session(self) -> None:
        if self._snapshot:
            return
        home = self._request(self.authority.portal + "/")
        token = _TOKEN.search(home)
        snapshot = re.search(r'wire:snapshot="([^"]+)"', home)
        if token is None or snapshot is None:
            raise TepiError("Kamus Dewan Perdana did not offer a search.")
        self._token = token.group(1)
        self._snapshot = unescape(snapshot.group(1))
        self._xsrf = next((unquote(cookie.value) for cookie in self._jar if cookie.name == "XSRF-TOKEN"), "")

    def _follow(self, url: str) -> str:
        for _ in range(4):
            status, headers, body = self._request(url, full=True)
            if status == 200:
                return body
            if status not in (301, 302, 303, 307, 308):
                raise TepiError("Kamus Dewan Perdana did not return a search page.")
            location = headers.get("Location") or ""
            if "/login" in location:
                raise TepiError("Kamus Dewan Perdana asked for a sign-in, so Tepi stopped.")
            if not location:
                raise TepiError("Kamus Dewan Perdana did not return a search page.")
            url = urljoin(url, location)
        raise TepiError("Kamus Dewan Perdana did not return a search page.")

    def _request(self, url: str, data: bytes | None = None, referer: str | None = None, full: bool = False):
        headers = {
            "User-Agent": "Tepi (personal spelling check)",
            "Accept": "text/html",
        }
        if referer:
            headers["Referer"] = referer
        request = urllib.request.Request(url, data=data, headers=headers)
        delay = 1.0
        for attempt in range(3):
            try:
                with self._opener.open(request, timeout=30) as response:
                    page = response.read().decode("utf-8", errors="replace")
                    if full:
                        return response.status, response.headers, page
                    return page
            except urllib.error.HTTPError as err:
                if full and err.code in (301, 302, 303, 307, 308):
                    page = err.read().decode("utf-8", errors="replace")
                    return err.code, err.headers, page
                if err.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise TepiError("Kamus Dewan Perdana did not answer.") from err
            except urllib.error.URLError as err:
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise TepiError("Kamus Dewan Perdana did not answer.") from err
        raise TepiError("Kamus Dewan Perdana did not answer.")


class _StopRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _field(raw: dict, key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TepiError(f"The dictionary at {path} is missing {key}.")
    return value.strip()


def hits_from_suggestions(payload: dict) -> list[Hit]:
    try:
        snapshot = json.loads(payload["components"][0]["snapshot"])
        suggestions = snapshot["data"]["suggestions"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as err:
        raise TepiError("Kamus Dewan Perdana did not return suggestions.") from err
    hits: list[Hit] = []

    def walk(node) -> None:
        if isinstance(node, dict) and isinstance(node.get("lemma"), str) and isinstance(node.get("match"), str):
            hits.append(Hit(form=_squash(node["lemma"]), kind=_squash(node["match"])))
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)

    walk(suggestions)
    return hits


def _squash(text: str) -> str:
    return " ".join(text.split())


def _plain(inner: str) -> str:
    """Headword text. A homonym number sits in a superscript and is not part of the spelling."""
    return _squash(unescape(_TAGS.sub(" ", _SUP.sub(" ", inner))))
