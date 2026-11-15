"""Browser-backed check that extraction feeds the filters what they expect on the demo app."""

import random

from gaptek.browser import open_session
from gaptek.perception.extract import extract
from gaptek.perception.filters import perceive
from gaptek.perception.render import render
from tests.helpers import bu_sri


async def test_demo_form_hides_otp_and_icon_submit(demo_url: str) -> None:
    async with open_session() as s:
        await s.page.goto(demo_url + "#/form")
        snap = await extract(s.page)
    submit = next(e for e in snap.elements if e.aria_label == "Submit")
    assert submit.is_icon_only and submit.is_round and submit.bg_color is not None

    obs = render(perceive(snap, bu_sri(), random.Random(0)), 360, 800).text
    assert 'tulisan: "???"' in obs  # "Verifikasi OTP"
    assert "tombol bulat biru di pojok kanan bawah\n" in obs + "\n"
    assert "Submit" not in obs and "OTP" not in obs


LEAKY_PAGE = """
<html><body style="margin:0">
  <button id="del"><svg width="20" height="20"></svg>
    <span style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)"
      >Hapus akun permanen</span>
  </button>
  <div style="opacity:0"><button>Rahasia</button></div>
  <div style="height:0;overflow:hidden"><button>Tersembunyi</button></div>
  <button><span class="material-icons">arrow_back</span></button>
  <div onclick="void 0" style="padding:10px"><p>Kartu</p><input placeholder="Jumlah"></div>
  <button style="position:absolute;top:300px;left:20px">Di belakang</button>
  <div style="position:fixed;inset:250px 0 0 0;background:#fff">
    <button style="margin:30px">Tutup</button>
  </div>
</body></html>
"""


async def test_extraction_ignores_what_a_sighted_user_cannot_see() -> None:
    async with open_session() as s:
        await s.page.set_content(LEAKY_PAGE)
        snap = await extract(s.page)
    texts = {e.text for e in snap.elements}
    for hidden in ("Hapus akun permanen", "Rahasia", "Tersembunyi", "Di belakang", "arrow_back"):
        assert not any(hidden in t for t in texts), hidden
    assert "Tutup" in texts
    icons = [e for e in snap.elements if e.is_icon_only]
    assert len(icons) == 2 and any("arrow_back" in e.icon_hint for e in icons)
    assert any(e.kind == "input" and e.placeholder == "Jumlah" for e in snap.elements)
