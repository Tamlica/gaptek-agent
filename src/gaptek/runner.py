"""Main loop: perceive -> decide -> act -> log, until success, give-up, or max steps."""

import json
import random
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from pydantic import BaseModel

from gaptek.agent.executor import execute
from gaptek.agent.patience import Patience
from gaptek.agent.tester import Decide, Tester
from gaptek.browser import open_session
from gaptek.config import Persona, RunConfig, Task
from gaptek.perception.extract import extract
from gaptek.perception.filters import more_below, perceive, perceive_message, viewport
from gaptek.perception.render import render

Result = Literal["success", "gave_up", "max_steps", "false_done", "error"]

# What the persona would "see change": url + visible text + typed values.
_SIGNATURE_JS = """() => location.href + '\\n' + document.body.innerText + '\\n' +
  [...document.querySelectorAll('input,textarea,select')].map(e => e.value).join('|') +
  '\\n' + Math.round(window.scrollY)"""


class RunResult(BaseModel):
    run_dir: Path
    result: Result
    steps: int
    error: str | None = None


def screen_of(url: str) -> str:
    u = urlsplit(url)
    return (u.path or "/") + (f"#{u.fragment}" if u.fragment else "")


async def succeeded(page: Page, task: Task) -> bool:
    s = task.success
    if s.url_contains and s.url_contains not in page.url:
        return False
    if s.text_visible:
        body: str = await page.evaluate("() => document.body.innerText")
        if s.text_visible not in body:
            return False
    return True


def new_run_dir(cfg: RunConfig, task: Task, persona: Persona) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # random suffix: two runs started in the same second must not share a directory
    return cfg.runs_dir / f"{stamp}-{task.id}-{persona.id}-s{cfg.seed}-{secrets.token_hex(2)}"


async def settle(page: Page) -> None:
    """Wait for navigation/rendering caused by the last action to finish."""
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightError:
        pass  # long-polling pages never go idle; carry on
    await page.wait_for_timeout(300)


async def signature(page: Page) -> str:
    try:
        return str(await page.evaluate(_SIGNATURE_JS))
    except PlaywrightError:  # page navigated mid-evaluate
        await settle(page)
        return str(await page.evaluate(_SIGNATURE_JS))


async def run(
    persona: Persona,
    task: Task,
    cfg: RunConfig,
    decide: Decide | None = None,
    run_dir: Path | None = None,
) -> RunResult:
    run_dir = run_dir or new_run_dir(cfg, task, persona)
    (run_dir / "screenshots").mkdir(parents=True, exist_ok=True)
    decide = decide or Tester(persona, task, cfg.tester_model).decide
    # Separate streams so perception draws never shift the action-noise sequence.
    perception_rng = random.Random(f"{cfg.seed}-perception")
    noise_rng = random.Random(f"{cfg.seed}-noise")
    patience = Patience(persona.patience.patience_max)
    max_steps = min(task.max_steps, persona.patience.max_steps)
    history: list[str] = []
    hints_reached: set[str] = set()
    tries_on_screen = 0
    result: Result = "max_steps"
    error: str | None = None
    step = 0
    decisions = 0  # tester turns; what "steps" means in results

    trace = (run_dir / "trace.jsonl").open("w", encoding="utf-8")

    def log(entry: dict[str, Any]) -> None:
        trace.write(json.dumps(entry, ensure_ascii=False) + "\n")
        trace.flush()

    try:
        async with open_session(persona.device, cfg.headed) as session:
            page = session.page
            await page.goto(task.url)
            await settle(page)
            for step in range(1, max_steps + 1):
                shot = f"screenshots/step-{step:03d}.png"
                if await succeeded(page, task):
                    await page.screenshot(path=run_dir / shot)
                    log(
                        {
                            "step": step,
                            "screen": screen_of(page.url),
                            "event": "success",
                            "screenshot": shot,
                        }
                    )
                    result = "success"
                    break

                snap = await extract(page)
                messages = session.pop_messages()
                seen = perceive(snap, persona, perception_rng)
                obs = render(
                    seen,
                    snap.viewport_w,
                    snap.viewport_h,
                    messages=[perceive_message(m, persona) for m in messages],
                    tries_on_screen=tries_on_screen,
                    patience=(patience.value, patience.max),
                    hint_more_below=persona.perception.scrolls_spontaneously and more_below(snap),
                )
                raw = render(
                    viewport(snap.elements), snap.viewport_w, snap.viewport_h, messages=messages
                ).text
                await page.screenshot(path=run_dir / shot)
                entry: dict[str, Any] = {
                    "step": step,
                    "url": page.url,
                    "screen": screen_of(page.url),
                    "screenshot": shot,
                    "observation": obs.text,
                    "raw_observation": raw,
                    "messages": messages,
                }

                intent = await decide(obs.text, history)
                decisions += 1
                entry["tester"] = intent.model_dump()
                if intent.aksi in ("menyerah", "selesai"):
                    if intent.aksi == "menyerah":
                        result = "gave_up"
                    else:
                        result = "success" if await succeeded(page, task) else "false_done"
                    entry["patience"] = patience.value
                    log(entry)
                    break

                before = await signature(page)
                ex = await execute(
                    page, intent, obs.refs, snap.elements, persona.behavior, noise_rng
                )
                await settle(page)
                left_app = urlsplit(page.url).netloc != urlsplit(task.url).netloc
                if left_app:
                    # Back past the first screen / external link: like closing the app and
                    # opening it again. Counted as an error for patience.
                    await page.goto(task.url)
                    await settle(page)
                changed = await signature(page) != before
                screen = screen_of(page.url)
                progress = any(h in screen and h not in hints_reached for h in task.progress_hints)
                hints_reached |= {h for h in task.progress_hints if h in screen}
                reasons = patience.update(
                    screen_changed=changed,
                    error_seen=bool(session.messages) or ex.error is not None or left_app,
                    feeling=intent.perasaan,
                    progress=progress,
                )
                tries_on_screen = 0 if changed else tries_on_screen + 1
                entry |= {
                    "executed": ex.model_dump(),
                    "screen_changed": changed,
                    "left_app": left_app,
                    "patience": patience.value,
                    "patience_reasons": reasons,
                }
                log(entry)
                did = f"{intent.aksi} {intent.target or ''}".strip()
                outcome = "layar berubah" if changed else "tidak ada yang berubah"
                history.append(f"- Langkah {step}: {did} ({outcome}). Pikiranmu: {intent.pikiran}")

                if patience.exhausted:
                    result = "gave_up"
                    log({"step": step, "event": "patience_exhausted"})
                    break
            else:
                if await succeeded(page, task):
                    result = "success"
    except Exception as e:  # e.g. API auth/network failure: keep the partial trace, say why
        result, error = "error", f"{type(e).__name__}: {e}"
        log({"step": step, "event": "error", "error": error})
    finally:
        trace.close()

    out = RunResult(run_dir=run_dir, result=result, steps=decisions, error=error)
    meta = {
        "persona": persona.id,
        "persona_name": persona.name,
        "task": task.id,
        "goal": task.goal_for_persona,
        "seed": cfg.seed,
        "tester_model": cfg.tester_model,
        "result": result,
        "steps": decisions,
        "error": error,
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")
    return out


class Outcome(BaseModel):
    run: RunResult
    findings_ok: bool
    analysis_error: str | None = None
    report: Path


async def run_and_report(
    persona: Persona,
    task: Task,
    cfg: RunConfig,
    *,
    analyze: bool = True,
    decide: Decide | None = None,
    run_dir: Path | None = None,
) -> Outcome:
    """Run, then analyze (best effort), then always write report.html."""
    from gaptek.analyst import analyze as analyze_run
    from gaptek.report import render_report

    res = await run(persona, task, cfg, decide=decide, run_dir=run_dir)
    error = None
    if analyze and res.result != "error":
        try:
            await analyze_run(res.run_dir, cfg.analyst_model)
        except Exception as e:  # the trace is still valuable without findings
            error = f"{type(e).__name__}: {e}"
    return Outcome(
        run=res,
        findings_ok=analyze and error is None,
        analysis_error=error,
        report=render_report(res.run_dir),
    )
