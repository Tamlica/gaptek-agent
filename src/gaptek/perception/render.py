"""Render perceived elements into the Indonesian plain-text observation the tester sees."""

from collections.abc import Sequence

from pydantic import BaseModel

from gaptek.perception.colors import color_name
from gaptek.perception.extract import Element

ICON_NAMES = {
    "back_arrow": "panah kembali",
    "home": "gambar rumah",
    "close_x": "tanda silang",
    "whatsapp": "WhatsApp",
    "phone": "gambar telepon",
    "search": "kaca pembesar",
    "menu_hamburger": "tiga garis",
    "cart": "keranjang belanja",
    "settings": "roda gigi",
    "user": "gambar orang",
}


class Observation(BaseModel):
    text: str
    refs: dict[str, int]  # "E1" -> element id; never shown to the tester


def position(e: Element, vw: float, vh: float) -> str:
    cx, cy = e.center
    v = "atas" if cy < vh * 0.2 else "bawah" if cy > vh * 0.8 else "tengah"
    h = "kiri" if cx < vw * 0.33 else "kanan" if cx > vw * 0.67 else "tengah"
    if v != "tengah" and h != "tengah":
        return f"di pojok {h} {v}"
    if v != "tengah":
        return f"di {v}"
    if h != "tengah":
        return f"di sebelah {h}"
    return "di tengah"


def size_word(e: Element) -> str:
    if e.area >= 6000 and e.h >= 40:
        return " besar"
    if e.h < 36 or e.area < 1600:
        return " kecil"
    return ""


def describe(e: Element, vw: float, vh: float) -> str:
    color = f" {color_name(e.bg_color)}" if e.bg_color else ""
    if e.is_icon_only:
        if e.icon_kind:
            return f"ikon {ICON_NAMES.get(e.icon_kind, e.icon_kind)} {position(e, vw, vh)}"
        if e.bg_color and e.is_round:
            base = f"tombol bulat{size_word(e)}{color}"
        elif e.bg_color:
            base = f"tombol{size_word(e)}{color} tanpa tulisan"
        else:
            base = f"ikon{size_word(e)} {color_name(e.fg_color)}"
        label = f': "{e.aria_label}"' if e.aria_label else ""
        return f"{base} {position(e, vw, vh)}{label}"
    if e.kind == "button":
        return f'tombol{size_word(e)}{color}: "{e.text}"'
    if e.kind == "link":
        return f'tulisan yang bisa dipencet: "{e.text}"'
    if e.kind == "input":
        if e.value:
            return f'kotak isian berisi: "{e.value}"'
        hint = f' dengan tulisan samar: "{e.placeholder}"' if e.placeholder else ""
        return f"kotak isian kosong{hint}"
    if e.kind == "select":
        return f'pilihan: "{e.text}"'
    if e.kind == "checkbox":
        return f'kotak centang: "{e.text}"'
    if e.kind == "heading" or e.font_size >= 20:
        v = position(e, vw, vh).split()[-1]
        where = f" di {v}" if v in ("atas", "bawah") else ""
        return f'tulisan besar{where}: "{e.text}"'
    if e.font_size < 13:
        return f'tulisan kecil: "{e.text}"'
    return f'tulisan: "{e.text}"'


def reading_order(elements: Sequence[Element]) -> list[Element]:
    """Rows top to bottom, then left to right. Vertically overlapping elements share a row."""
    rows: list[list[Element]] = []
    bottom = float("-inf")
    for e in sorted(elements, key=lambda e: e.y):
        if rows and e.y < bottom - 4:
            rows[-1].append(e)
            bottom = max(bottom, e.y + e.h)
        else:
            rows.append([e])
            bottom = e.y + e.h
    return [e for row in rows for e in sorted(row, key=lambda e: e.x)]


def render(
    elements: Sequence[Element],
    vw: float,
    vh: float,
    *,
    messages: Sequence[str] = (),
    tries_on_screen: int | None = None,
    patience: tuple[int, int] | None = None,
    hint_more_below: bool = False,
) -> Observation:
    lines = ["Layar sekarang:"]
    refs: dict[str, int] = {}
    for i, e in enumerate(reading_order(elements), 1):
        ref = f"E{i}"
        refs[ref] = e.id
        lines.append(f"[{ref}] {describe(e, vw, vh)}")
    if len(elements) == 0:
        lines.append("(layar kosong, tidak ada apa-apa)")
    if hint_more_below:
        lines.append("Sepertinya masih ada isi lagi di bawah kalau layar digeser.")
    lines += [f'Muncul pesan di layar: "{m}"' for m in messages]
    status = []
    if tries_on_screen:
        status.append(f"Kamu sudah mencoba {tries_on_screen} kali di layar ini.")
    if patience:
        status.append(f"Kesabaran: {patience[0]}/{patience[1]}.")
    if status:
        lines.append(" ".join(status))
    return Observation(text="\n".join(lines), refs=refs)
