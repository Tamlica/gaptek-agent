"""Turn an Intent into a real browser action, with seeded fat-finger noise."""

import math
import random

from playwright.async_api import Page
from pydantic import BaseModel

from gaptek.agent.tester import Intent
from gaptek.config import Behavior
from gaptek.perception.extract import Element

_ROWS = ["1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm"]


def _neighbors(ch: str) -> str:
    for r, row in enumerate(_ROWS):
        c = row.find(ch)
        if c >= 0:
            out = row[max(c - 1, 0) : c] + row[c + 1 : c + 2]
            for rr in (r - 1, r + 1):
                if 0 <= rr < len(_ROWS):
                    out += _ROWS[rr][max(c - 1, 0) : c + 1]
            return out
    return ""


def add_typos(text: str, rate: float, rng: random.Random) -> str:
    out = []
    for ch in text:
        # One roll per character (+1 choice when it's a typo): deterministic for a given seed
        # and the same sequence of actions.
        roll = rng.random()
        near = _neighbors(ch.lower())
        out.append(rng.choice(near) if roll < rate and near else ch)
    return "".join(out)


MISS_RADIUS_PX = 48  # a fat finger lands near the target, not across the screen


def gap(a: Element, b: Element) -> float:
    """Distance between the edges of two boxes (0 if they touch or overlap)."""
    dx = max(b.x - (a.x + a.w), a.x - (b.x + b.w), 0)
    dy = max(b.y - (a.y + a.h), a.y - (b.y + b.h), 0)
    return math.hypot(dx, dy)


def pick_target(
    intended: Element, candidates: list[Element], rate: float, rng: random.Random
) -> tuple[Element | None, bool]:
    """With probability `rate` the tap misses: it hits the nearest other tappable element
    within MISS_RADIUS_PX, or nothing (None) if there is none that close."""
    if rng.random() >= rate:
        return intended, False
    near = [
        c
        for c in candidates
        if c.id != intended.id
        and c.interactive
        and c.in_viewport
        and gap(intended, c) <= MISS_RADIUS_PX
    ]
    cx, cy = intended.center
    return (min(near, key=lambda c: math.dist((cx, cy), c.center)) if near else None), True


class ExecResult(BaseModel):
    action: str
    target_ref: str | None = None
    intended_id: int | None = None
    actual_id: int | None = None
    misclicked: bool = False
    typed_text: str | None = None
    error: str | None = None


async def execute(
    page: Page,
    intent: Intent,
    refs: dict[str, int],
    elements: list[Element],
    behavior: Behavior,
    rng: random.Random,
) -> ExecResult:
    res = ExecResult(action=intent.aksi, target_ref=intent.target)
    try:
        if intent.aksi in ("tekan", "ketik"):
            by_id = {e.id: e for e in elements}
            eid = refs.get((intent.target or "").strip("[] ").upper())
            if eid is None or eid not in by_id:
                res.error = f"target {intent.target!r} tidak ada di layar"
                return res
            hit, res.misclicked = pick_target(by_id[eid], elements, behavior.misclick_rate, rng)
            res.intended_id = eid
            if intent.aksi == "ketik":
                res.typed_text = add_typos(intent.teks or "", behavior.typo_rate, rng)
            if hit is None:  # tapped empty space
                return res
            res.actual_id = hit.id
            loc = page.locator(f'[data-gaptek-id="{hit.id}"]')
            await loc.click(timeout=3000)
            if res.typed_text is not None:
                if hit.kind == "input":  # typing replaces the box content, so typos can be redone
                    await loc.fill("")
                await page.keyboard.type(res.typed_text)
        elif intent.aksi == "gulir":
            await page.evaluate("window.scrollBy(0, window.innerHeight * 0.7)")
        elif intent.aksi == "kembali":
            await page.go_back(timeout=5000)
        elif intent.aksi == "tunggu":
            await page.wait_for_timeout(1500)
    except Exception as e:  # a failed tap is data for the report, not a crash
        res.error = f"{type(e).__name__}: {str(e).splitlines()[0]}"
    return res
