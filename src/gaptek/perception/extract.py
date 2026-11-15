"""Pull visible interactive + text elements out of a live page.

Each extracted element is tagged in the DOM with `data-gaptek-id` so the executor can act on it.
Ids are only valid until the next extraction.
"""

from typing import Literal

from playwright.async_api import Page
from pydantic import BaseModel

Kind = Literal["button", "link", "input", "select", "checkbox", "heading", "text"]
RGB = tuple[int, int, int]


class Element(BaseModel):
    id: int
    kind: Kind
    text: str = ""
    aria_label: str | None = None
    placeholder: str | None = None
    value: str | None = None
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0
    font_size: float = 16
    bg_color: RGB | None = None  # None = transparent
    fg_color: RGB = (0, 0, 0)
    is_round: bool = False
    is_icon_only: bool = False
    icon_hint: str = ""  # aria/title/class/alt/src soup, used only by code to guess icon kind
    icon_kind: str | None = None  # set by the icon filter when the persona recognizes the icon
    in_viewport: bool = True

    @property
    def interactive(self) -> bool:
        return self.kind not in ("text", "heading")

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h / 2


class Snapshot(BaseModel):
    url: str
    viewport_w: int
    viewport_h: int
    scroll_y: float
    page_h: float
    elements: list[Element]


_JS = r"""
() => {
  const SEL = 'a[href],button,input:not([type=hidden]),select,textarea,'
            + '[role=button],[role=link],[role=checkbox],[onclick]';
  const vw = window.innerWidth, vh = window.innerHeight;
  document.querySelectorAll('[data-gaptek-id]').forEach(e => e.removeAttribute('data-gaptek-id'));

  const color = c => {
    const m = /rgba?\(([^)]+)\)/.exec(c || '');
    if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    if (p.length > 3 && p[3] === 0) return null;
    return p.slice(0, 3).map(Math.round);
  };
  const visible = el => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) return false;
    for (let a = el; a && a !== document.body; a = a.parentElement) {
      const as = a === el ? s : getComputedStyle(a);
      if (Number(as.opacity) === 0) return false;
      if (a !== el && as.overflow !== 'visible') {  // clipped away by a container (accordion, carousel)
        const ar = a.getBoundingClientRect();
        if (r.right <= ar.left || r.left >= ar.right || r.bottom <= ar.top || r.top >= ar.bottom) return false;
      }
    }
    // Covered by something else (modal overlay, sticky bar)? Only checkable on screen.
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    if (cx >= 0 && cy >= 0 && cx < vw && cy < vh) {
      const hit = document.elementFromPoint(cx, cy);
      if (hit && !el.contains(hit) && !hit.contains(el) && hit.closest('label')?.control !== el) return false;
    }
    return true;
  };
  const ICON_FONT = '[class*="material-icons"],[class*="material-symbols"]';
  // Text a sighted user can actually see inside an element: skips sr-only (1px) and icon-font ligatures.
  const visText = (el, ligatures) => {
    const parts = [];
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) {
      const p = w.currentNode.parentElement;
      if (p.closest(ICON_FONT)) { ligatures.push(w.currentNode.textContent.trim()); continue; }
      const ps = getComputedStyle(p), pr = p.getBoundingClientRect();
      if (pr.width > 1 && pr.height > 1 && ps.visibility !== 'hidden' && ps.display !== 'none'
          && Number(ps.opacity) !== 0) parts.push(w.currentNode.textContent);
    }
    return clean(parts.join(' '));
  };
  const kindOf = el => {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const role = el.getAttribute('role');
    if (/^h[1-6]$/.test(tag)) return 'heading';
    if (tag === 'a' || role === 'link') return 'link';
    if (tag === 'select') return 'select';
    if (tag === 'textarea') return 'input';
    if (tag === 'input') {
      if (type === 'checkbox' || type === 'radio') return 'checkbox';
      if (['submit', 'button', 'reset', 'image'].includes(type)) return 'button';
      return 'input';
    }
    if (role === 'checkbox') return 'checkbox';
    if (tag === 'button' || role === 'button' || el.hasAttribute('onclick')) return 'button';
    return 'text';
  };
  // Text of a block element: its own text nodes plus inline descendants (not nested blocks).
  const consumed = new Set();
  const ownText = el => {
    const parts = [];
    const walk = node => {
      for (const c of node.childNodes) {
        if (c.nodeType === 3) { parts.push(c.textContent); consumed.add(c); }
        else if (c.nodeType === 1 && !c.matches(SEL)
                 && getComputedStyle(c).display.startsWith('inline')) walk(c);
      }
    };
    walk(el);
    return parts.join('');
  };
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();

  const out = [];
  let n = 0;
  const add = (el, kind) => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    const interactive = kind !== 'text' && kind !== 'heading';
    let text;
    const ligatures = [];
    if (kind === 'select') text = el.selectedOptions[0]?.text || '';
    else if (kind === 'input') text = '';
    else if (kind === 'checkbox') text = clean([...(el.labels || [])].map(l => l.innerText).join(' '));
    else if (el.tagName === 'INPUT') text = el.value || '';
    else if (interactive) text = visText(el, ligatures);
    else text = clean(ownText(el));

    const svg = el.querySelector('svg');
    const img = el.tagName === 'IMG' ? el : el.querySelector('img');
    const isSymbol = text.length > 0 && text.length <= 2 && !/[\p{L}\p{N}]/u.test(text);
    const iconOnly = (kind === 'button' || kind === 'link') && (text === '' || isSymbol);
    const cls = typeof el.className === 'string' ? el.className : (el.getAttribute('class') || '');
    const hint = [el.getAttribute('aria-label'), el.getAttribute('title'), cls,
                  img?.alt, img?.getAttribute('src'), svg?.querySelector('title')?.textContent,
                  isSymbol ? text : '', ...ligatures].filter(Boolean).join(' ');
    let fg = color(s.color);
    if (svg) { const f = color(getComputedStyle(svg).fill); if (f) fg = f; }

    el.setAttribute('data-gaptek-id', String(n));
    out.push({
      id: n++, kind, text: iconOnly ? '' : text,
      aria_label: el.getAttribute('aria-label') || el.getAttribute('title') || img?.alt || null,
      placeholder: el.getAttribute('placeholder'),
      value: kind === 'input' ? (el.value || '') : null,
      x: r.left, y: r.top, w: r.width, h: r.height,
      font_size: parseFloat(s.fontSize) || 0,
      bg_color: color(s.backgroundColor), fg_color: fg || [0, 0, 0],
      is_round: parseFloat(s.borderTopLeftRadius) >= Math.min(r.width, r.height) / 2 - 1,
      is_icon_only: iconOnly, icon_hint: hint,
      in_viewport: r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw,
    });
  };

  for (const el of document.querySelectorAll(SEL)) {
    // Controls nested in a link/button are part of it; ones inside clickable cards are kept.
    if (!visible(el) || el.parentElement?.closest('a[href],button')) continue;
    add(el, kindOf(el));
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const t = walker.currentNode;
    if (consumed.has(t) || !t.textContent.trim()) continue;
    const el = t.parentElement;
    if (!el || el.hasAttribute('data-gaptek-id') || el.closest(SEL)
        || el.closest('script,style,noscript,template') || el.closest(ICON_FONT)
        || !visible(el)) continue;
    add(el, kindOf(el));
  }
  return {url: location.href, viewport_w: vw, viewport_h: vh, scroll_y: window.scrollY,
          page_h: document.documentElement.scrollHeight, elements: out};
}
"""


async def extract(page: Page) -> Snapshot:
    return Snapshot.model_validate(await page.evaluate(_JS))
