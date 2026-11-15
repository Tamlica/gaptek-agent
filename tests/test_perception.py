import random

from gaptek.perception import filters as f
from gaptek.perception.colors import color_name
from gaptek.perception.extract import Snapshot
from gaptek.perception.render import render
from tests.helpers import bu_sri, el


def test_vocabulary_hides_jargon_and_english() -> None:
    v = bu_sri().perception.vocabulary
    assert f.filter_text("Verifikasi OTP", v) == "???"
    assert f.filter_text("Kode OTP", v) == "Kode ???"
    assert f.filter_text("Checkout sekarang", v) == "??? sekarang"
    assert f.filter_text("Nasi Goreng Rp15.000", v) == "Nasi Goreng Rp15.000"
    assert f.filter_text("Kirim via WhatsApp", v) == "Kirim via WhatsApp"  # knows_words
    assert f.filter_text("LOGIN", v) == "???"  # case-insensitive


def test_vocabulary_off_for_control_persona() -> None:
    p = bu_sri()
    p.perception.vocabulary.unknown_terms = []
    p.perception.vocabulary.unknown_english_default = False
    assert f.filter_text("Verifikasi OTP Checkout", p.perception.vocabulary) == (
        "Verifikasi OTP Checkout"
    )


def test_icon_blindness_strips_label_unless_recognized() -> None:
    p = bu_sri()
    submit = el(1, kind="button", is_icon_only=True, aria_label="Submit", icon_hint="Submit fab")
    back = el(2, kind="button", is_icon_only=True, aria_label="Back", icon_hint="Back")
    out = f.icon_blindness([submit, back], p)
    assert out[0].aria_label is None and out[0].icon_kind is None
    assert out[1].aria_label is None and out[1].icon_kind == "back_arrow"

    p.perception.icon_blindness = False
    assert f.icon_blindness([submit], p)[0].aria_label == "Submit"


def test_reading_limit() -> None:
    p = bu_sri()  # max_words_read = 6
    out = f.reading_limit([el(text="satu dua tiga empat lima enam tujuh delapan")], p)
    assert out[0].text == "satu dua tiga empat lima enam..."


def test_salience_is_seeded_and_keeps_big_buttons() -> None:
    p = bu_sri()  # miss rate 0.4, min font 14
    tiny = [el(i, font_size=11, text="kecil") for i in range(50)]
    big = el(99, kind="button", text="Bayar", font_size=12, w=300, h=48, bg_color=(46, 125, 50))
    a = f.salience([*tiny, big], p, random.Random(7))
    b = f.salience([*tiny, big], p, random.Random(7))
    assert [e.id for e in a] == [e.id for e in b]
    assert 10 < len(a) - 1 < 45  # some, not all, small elements missed
    assert a[-1].id == 99


def test_viewport_filter() -> None:
    assert [e.id for e in f.viewport([el(1), el(2, in_viewport=False)])] == [1]


def test_detect_icon_kind() -> None:
    assert f.detect_icon_kind("btn-close") == "close_x"
    assert f.detect_icon_kind("×") == "close_x"
    assert f.detect_icon_kind("Kembali ke beranda") == "back_arrow"
    assert f.detect_icon_kind("Submit") is None


def test_color_names() -> None:
    assert color_name((46, 125, 50)) == "hijau"
    assert color_name((21, 101, 192)) == "biru"
    assert color_name((136, 136, 136)) == "abu-abu"
    assert color_name((220, 30, 30)) == "merah"
    assert color_name((255, 255, 255)) == "putih"


def test_render_matches_spec_format() -> None:
    p = bu_sri()
    snap = Snapshot(
        url="x",
        viewport_w=360,
        viewport_h=800,
        scroll_y=0,
        page_h=800,
        elements=[
            el(0, kind="heading", text="Selamat datang di Dashboard", y=20, font_size=24),
            el(1, kind="button", text="Login", y=300, w=300, h=48, bg_color=(46, 125, 50)),
            el(
                2,
                kind="button",
                is_icon_only=True,
                aria_label="Settings",
                icon_hint="gear",
                x=320,
                y=10,
                w=32,
                h=32,
                fg_color=(136, 136, 136),
            ),
            el(3, kind="input", placeholder="Nomor telepon", y=400),
        ],
    )
    obs = render(
        f.perceive(snap, p, random.Random(0)), 360, 800, tries_on_screen=2, patience=(3, 5)
    )
    assert obs.text == (
        "Layar sekarang:\n"
        '[E1] tulisan besar di atas: "Selamat datang di ???"\n'
        "[E2] ikon kecil abu-abu di pojok kanan atas\n"
        '[E3] tombol besar hijau: "???"\n'
        '[E4] kotak isian kosong dengan tulisan samar: "Nomor telepon"\n'
        "Kamu sudah mencoba 2 kali di layar ini. Kesabaran: 3/5."
    )
    assert obs.refs == {"E1": 0, "E2": 2, "E3": 1, "E4": 3}
    assert "Settings" not in obs.text and "gear" not in obs.text


def test_dialog_message_filtered() -> None:
    assert f.perceive_message("Field required", bu_sri()) == "???"


def test_reading_order_keeps_rows_together() -> None:
    from gaptek.perception.render import reading_order

    name = el(1, text="Nasi Goreng", x=10, y=100, h=20)
    btn = el(2, kind="button", text="Pesan", x=250, y=90, h=44)  # taller, starts higher
    name2 = el(3, text="Mie Ayam", x=10, y=160, h=20)
    btn2 = el(4, kind="button", text="Pesan", x=250, y=150, h=44)
    assert [e.id for e in reading_order([btn2, name2, btn, name])] == [1, 2, 3, 4]


def test_prefilled_value_is_filtered() -> None:
    out = f.vocabulary([el(kind="input", value="Enter your name")], bu_sri())
    assert out[0].value == "???"
