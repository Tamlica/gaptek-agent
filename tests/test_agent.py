import json
import random
import re
from collections.abc import Sequence
from pathlib import Path

from gaptek.agent.executor import add_typos, pick_target
from gaptek.agent.patience import Patience
from gaptek.agent.tester import Intent, system_prompt
from gaptek.config import RunConfig, Task, load_persona, load_task
from gaptek.runner import run
from tests.helpers import ROOT, bu_sri, el


def test_typos_seeded() -> None:
    a = add_typos("081234567890", 0.3, random.Random(1))
    assert a == add_typos("081234567890", 0.3, random.Random(1))
    assert a != "081234567890"
    assert add_typos("halo", 0.0, random.Random(1)) == "halo"


def test_misclick_hits_nearest_neighbor() -> None:
    target = el(1, kind="button", x=0, y=0, w=50, h=50)
    near = el(2, kind="button", x=60, y=0, w=50, h=50)
    far = el(3, kind="button", x=300, y=600, w=50, h=50)
    text = el(4, kind="text", x=55, y=0, w=5, h=5)  # not tappable
    hit, missed = pick_target(target, [target, near, far, text], 1.0, random.Random(0))
    assert missed and hit is not None and hit.id == 2
    hit, missed = pick_target(target, [target, near], 0.0, random.Random(0))
    assert not missed and hit is not None and hit.id == 1
    hit, missed = pick_target(target, [target, far], 1.0, random.Random(0))
    assert missed and hit is None  # nothing within reach: the tap lands on empty space


def test_patience() -> None:
    p = Patience(5)
    p.update(screen_changed=False, error_seen=True, feeling="kesal", progress=False)
    assert p.value == 2
    p.update(screen_changed=True, error_seen=False, feeling="tenang", progress=True)
    assert p.value == 3
    for _ in range(5):
        p.update(screen_changed=True, error_seen=False, feeling="tenang", progress=True)
    assert p.value == 5  # capped
    for _ in range(5):
        p.update(screen_changed=False, error_seen=False, feeling="bingung", progress=False)
    assert p.exhausted and p.value == 0


def test_prompt_has_no_dev_terms() -> None:
    task = load_task(ROOT / "tasks/example.yaml")
    prompt = system_prompt(bu_sri(), task).lower()
    for term in ("html", "button", "element", "selector", "url", "click", "dom", "aria"):
        assert term not in prompt


# --- loop on the real demo app with scripted testers ---------------------------------------


def ref(obs: str, pattern: str) -> str | None:
    m = re.search(rf"\[(E\d+)\] [^\n]*{pattern}", obs)
    return m[1] if m else None


async def savvy(obs: str, history: Sequence[str]) -> Intent:
    """Stand-in for a capable user who can read everything."""
    if r := ref(obs, '"Checkout"'):
        return Intent(pikiran="pesan", perasaan="tenang", aksi="tekan", target=r)
    if r := ref(obs, 'kotak isian kosong dengan tulisan samar: "08'):
        return Intent(pikiran="isi", perasaan="tenang", aksi="ketik", target=r, teks="0812345")
    if r := ref(obs, 'kotak isian kosong dengan tulisan samar: "6 digit'):
        return Intent(pikiran="isi", perasaan="tenang", aksi="ketik", target=r, teks="482913")
    if r := ref(obs, '"Submit"'):
        return Intent(pikiran="kirim", perasaan="tenang", aksi="tekan", target=r)
    return Intent(pikiran="?", perasaan="bingung", aksi="menyerah")


async def literal(obs: str, history: Sequence[str]) -> Intent:
    """Stand-in for a user who only presses things whose label they can read."""
    for r, label in re.findall(r'\[(E\d+)\] tombol[^:\n]*: "([^"]*)"', obs):
        if "???" not in label:
            return Intent(pikiran="ini kebaca", perasaan="ragu", aksi="tekan", target=r)
    if len(history) >= 3:
        return Intent(pikiran="saya tidak paham", perasaan="menyerah", aksi="menyerah")
    return Intent(pikiran="bingung", perasaan="bingung", aksi="tunggu")


def demo_task(url: str, max_steps: int = 12) -> Task:
    t = load_task(ROOT / "tasks/example.yaml")
    return t.model_copy(update={"url": url, "max_steps": max_steps})


async def test_control_persona_succeeds(demo_url: str, tmp_path: Path) -> None:
    p = load_persona(ROOT / "personas/kontrol-melek-teknologi.yaml")
    res = await run(p, demo_task(demo_url), RunConfig(runs_dir=tmp_path), decide=savvy)
    assert res.result == "success"
    lines = (res.run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert {"observation", "raw_observation", "tester", "executed", "screenshot"} <= first.keys()
    assert (res.run_dir / first["screenshot"]).exists()


async def test_bu_sri_stuck_on_jargon(demo_url: str, tmp_path: Path) -> None:
    res = await run(bu_sri(), demo_task(demo_url), RunConfig(runs_dir=tmp_path), decide=literal)
    assert res.result == "gave_up"
    trace = (res.run_dir / "trace.jsonl").read_text(encoding="utf-8")
    assert "Checkout" not in trace.split('"raw_observation"')[0]  # tester never saw it


async def test_same_seed_same_noise(demo_url: str, tmp_path: Path) -> None:
    p = bu_sri()
    p.behavior.misclick_rate, p.behavior.typo_rate = 0.5, 0.3

    async def clumsy(obs: str, history: Sequence[str]) -> Intent:
        if r := ref(obs, "kotak isian"):
            return Intent(pikiran="isi", perasaan="ragu", aksi="ketik", target=r, teks="0812")
        r = ref(obs, "tombol") or "E1"
        return Intent(pikiran="coba", perasaan="ragu", aksi="tekan", target=r)

    def noise(i: int) -> list[tuple[bool, str | None]]:
        rd = next((tmp_path / str(i)).iterdir())
        rows = [json.loads(x) for x in (rd / "trace.jsonl").read_text("utf-8").splitlines()]
        return [
            (r["executed"]["misclicked"], r["executed"]["typed_text"])
            for r in rows
            if "executed" in r
        ]

    for i in (1, 2):
        await run(
            p, demo_task(demo_url, 6), RunConfig(seed=42, runs_dir=tmp_path / str(i)), decide=clumsy
        )
    assert noise(1) == noise(2) and len(noise(1)) > 0


async def test_back_on_first_screen_reopens_app(demo_url: str, tmp_path: Path) -> None:
    async def back_then_quit(obs: str, history: Sequence[str]) -> Intent:
        if not history:
            return Intent(pikiran="balik", perasaan="bingung", aksi="kembali")
        return Intent(pikiran="sudah", perasaan="menyerah", aksi="menyerah")

    res = await run(
        bu_sri(), demo_task(demo_url), RunConfig(runs_dir=tmp_path), decide=back_then_quit
    )
    rows = [json.loads(x) for x in (res.run_dir / "trace.jsonl").read_text("utf-8").splitlines()]
    assert rows[0]["left_app"] is True
    assert "Pilih makanan" in rows[1]["observation"]  # back on the app, not a blank page
    assert res.steps == 2


def test_system_prompt_device_wording() -> None:
    from pathlib import Path

    from gaptek.agent.tester import system_prompt
    from gaptek.config import load_persona, load_task

    task = load_task(Path("tasks/example.yaml"))
    laptop = system_prompt(load_persona(Path("personas/bu-ratna-staf-kantor-laptop.yaml")), task)
    phone = system_prompt(load_persona(Path("personas/bu-sri.yaml")), task)
    assert "di laptop:" in laptop and "panah kembali di browser" in laptop
    assert "di HP" not in laptop and "kembali di HP" not in laptop
    assert "di HP:" in phone and "di laptop" not in phone
