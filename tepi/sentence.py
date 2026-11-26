"""Tokenize a sentence and decide which words it may use.

The closed-class allow-list and the active-form allow-list first lived in
tests/test_deck2.py. They live here so the command and the tests share one
tokenizer instead of two copies that can drift apart.
"""

import re

# Closed-class words a sentence may use besides lemmas already taught.
FUNCTION_WORDS = frozenset(
    {
        "yang",
        "untuk",
        "dengan",
        "pada",
        "kepada",
        "daripada",
        "oleh",
        "itu",
        "atau",
        "kalau",
        "jika",
        "kerana",
        "sebab",
        "pun",
        "lah",
        "kah",
        "tah",
        "nya",
        "akan",
        "telah",
        "sedang",
        "supaya",
        "agar",
        "dalam",
        "atas",
        "bawah",
        "tentang",
    }
)

_TOKEN = re.compile(r"[^\w\s-]+", re.UNICODE)

# Derived forms deck 2+ sentences actually use. Any other meN- or ber- shape stays unknown.
_ACTIVE_FORMS = {
    "ajar": frozenset({"mengajar"}),
    "jalan": frozenset({"berjalan"}),
    "beli": frozenset({"membeli"}),
    "main": frozenset({"bermain"}),
    "cuci": frozenset({"mencuci"}),
    "kerja": frozenset({"bekerja"}),
    "cakap": frozenset({"bercakap"}),
    "bayar": frozenset({"membayar"}),
    "masak": frozenset({"memasak"}),
    "tidur": frozenset({"tertidur"}),
}


def make_cloze(sentence: str, lemma: str, override: str | None = None) -> str | None:
    """Return a fill-in-the-blank version of `sentence` with `lemma` blanked out.

    Returns None when the sentence has fewer than two tokens or does not contain
    the target lemma (or one of its known active forms).
    """
    if override and override.strip():
        return override.strip()
    if len(tokens(sentence)) < 2:
        return None
    candidates = [lemma, *sorted(_ACTIVE_FORMS.get(lemma.casefold(), ()))]
    for target in candidates:
        pattern = re.compile(r"(?<!\w)" + re.escape(target) + r"(?!\w)", re.IGNORECASE | re.UNICODE)
        if pattern.search(sentence):
            return pattern.sub("___", sentence, count=1)
    return None


def tokens(sentence: str) -> list[str]:
    return [token for token in _TOKEN.sub(" ", sentence.casefold()).split() if token]


def _phrases(lemmas: set[str]) -> list[tuple[str, ...]]:
    return sorted((tuple(lemma.casefold().split()) for lemma in lemmas), key=len, reverse=True)


def active_form(token: str, lemmas: set[str]) -> bool:
    known = {lemma.casefold() for lemma in lemmas}
    folded = token.casefold()
    for root, forms in _ACTIVE_FORMS.items():
        if root in known and folded in forms:
            return True
    return False


def unknown(tokens: list[str], lemmas: set[str], *, active: bool = True) -> list[str]:
    """Tokens that are neither a known lemma (or phrase) nor a function word.

    With active=True the deck-2 active forms are also accepted when their root
    is known. A settled-word prompt passes active=False: every non-function
    word must itself be a settled lemma, not a derived shape of one.
    """
    phrases = _phrases(lemmas)
    unknown_tokens = []
    index = 0
    while index < len(tokens):
        matched = False
        for phrase in phrases:
            size = len(phrase)
            if tuple(tokens[index : index + size]) == phrase:
                index += size
                matched = True
                break
        if matched:
            continue
        if tokens[index] in FUNCTION_WORDS or (active and active_form(tokens[index], lemmas)):
            index += 1
            continue
        unknown_tokens.append(tokens[index])
        index += 1
    return unknown_tokens
