"""Pure persona-limit filters over extracted elements. No browser needed.

Order applied by `perceive`: viewport -> salience -> icon blindness -> reading limit -> vocabulary.
"""

import random
import re
from functools import cache
from pathlib import Path

from gaptek.config import Persona, Vocabulary
from gaptek.perception.extract import Element, Snapshot

UNKNOWN = "???"
_DATA = Path(__file__).parent / "data"
_WORD = re.compile(r"[A-Za-z][A-Za-z']*")
_RUNS_OF_UNKNOWN = re.compile(r"\?\?\?(?:[\s\-/]+\?\?\?)+")

# icon kind -> keywords found in the element's icon_hint (aria-label, class, alt, src, symbol)
ICON_KEYWORDS: dict[str, set[str]] = {
    "back_arrow": {"back", "kembali", "arrow-left", "arrow_back", "chevron-left", "←", "‹", "<"},
    "home": {"home", "beranda", "rumah"},
    "close_x": {"close", "tutup", "dismiss", "×", "✕", "x"},
    "whatsapp": {"whatsapp", "wa"},
    "phone": {"phone", "telepon", "call", "telp"},
    "search": {"search", "cari", "🔍"},
    "menu_hamburger": {"hamburger", "menu", "☰"},
    "cart": {"cart", "keranjang", "basket"},
    "settings": {"settings", "setting", "gear", "pengaturan"},
    "user": {"user", "profile", "account", "akun", "profil"},
}


@cache
def wordlist(name: str) -> frozenset[str]:
    return frozenset((_DATA / f"{name}.txt").read_text(encoding="utf-8").lower().split())


def word_known(word: str, vocab: Vocabulary) -> bool:
    w = word.lower()
    if w in {k.lower() for k in vocab.knows_words}:
        return True
    if w in {k.lower() for k in vocab.unknown_terms}:
        return False
    if w in wordlist(vocab.base):
        return True
    # ponytail: English detection is a curated UI word list; extend english_ui.txt as misses show up
    return not (vocab.unknown_english_default and w in wordlist("english_ui"))


def filter_text(text: str, vocab: Vocabulary) -> str:
    out = _WORD.sub(lambda m: m[0] if word_known(m[0], vocab) else UNKNOWN, text)
    return _RUNS_OF_UNKNOWN.sub(UNKNOWN, out)


def truncate(text: str, max_words: int) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]) + "..."


def detect_icon_kind(hint: str) -> str | None:
    h = hint.lower()
    tokens = set(re.split(r"[^\w\-]+", h)) | set(
        re.split(r"[^\w]+", h)
    )  # "arrow-left", "btn"+"close"
    for kind, keys in ICON_KEYWORDS.items():
        if tokens & keys or any(k in hint for k in keys if not k.isascii()):
            return kind
    return None


# --- filters -------------------------------------------------------------------------------


def viewport(elements: list[Element]) -> list[Element]:
    return [e for e in elements if e.in_viewport]


def is_small(e: Element, min_font: float) -> bool:
    if e.area < 400:
        return True
    big_colored = e.interactive and e.bg_color is not None and e.area >= 1500
    has_text = not e.is_icon_only and e.kind not in ("input", "select")
    return has_text and e.font_size < min_font and not big_colored


def salience(elements: list[Element], persona: Persona, rng: random.Random) -> list[Element]:
    p = persona.perception
    kept = []
    for e in elements:
        # One draw per small element keeps the RNG stream stable for a given page.
        if is_small(e, p.min_noticed_font_px) and rng.random() < p.small_element_miss_rate:
            continue
        kept.append(e)
    return kept


def icon_blindness(elements: list[Element], persona: Persona) -> list[Element]:
    p = persona.perception
    if not p.icon_blindness:
        return elements
    out = []
    for e in elements:
        if e.is_icon_only:
            kind = detect_icon_kind(e.icon_hint)
            known = kind if kind in p.recognized_icons else None
            e = e.model_copy(update={"aria_label": None, "icon_kind": known})
        out.append(e)
    return out


def reading_limit(elements: list[Element], persona: Persona) -> list[Element]:
    n = persona.perception.max_words_read
    return [e.model_copy(update={"text": truncate(e.text, n)}) for e in elements]


def vocabulary(elements: list[Element], persona: Persona) -> list[Element]:
    v = persona.perception.vocabulary

    def f(s: str | None) -> str | None:
        return None if s is None else filter_text(s, v)

    return [
        e.model_copy(
            update={
                "text": filter_text(e.text, v),
                "placeholder": f(e.placeholder),
                "value": f(e.value),  # text the app pre-filled is read like any other text
                "aria_label": f(e.aria_label),
            }
        )
        for e in elements
    ]


def perceive(snapshot: Snapshot, persona: Persona, rng: random.Random) -> list[Element]:
    els = viewport(snapshot.elements)
    els = salience(els, persona, rng)
    els = icon_blindness(els, persona)
    els = reading_limit(els, persona)
    return vocabulary(els, persona)


def perceive_message(message: str, persona: Persona) -> str:
    """Filter a popup/dialog message the same way as on-screen text."""
    p = persona.perception
    return filter_text(truncate(message, p.max_words_read), p.vocabulary)


def more_below(snapshot: Snapshot) -> bool:
    return any(e.y >= snapshot.viewport_h for e in snapshot.elements)
