"""Post-run analysis: a strong model reads the trace and writes developer-facing findings."""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from gaptek.llm import structured

Severity = Literal["high", "medium", "low"]


class Issue(BaseModel):
    severity: Severity
    step: int
    screen: str
    summary: str
    evidence: list[str]
    suggestion: str


class AnalystOutput(BaseModel):
    summary: str
    issues: list[Issue]


class Findings(BaseModel):
    result: str
    steps: int
    persona: str
    task: str
    seed: int
    simulated: bool = True  # always: this is a simulation, not real user research
    summary: str
    issues: list[Issue]


SYSTEM = """You are a senior UX researcher reviewing a usability test session.

The session was SIMULATED: an LLM played a non-technical Indonesian user ("persona") whose
perception was mechanically limited. For each step you get what was really on screen
(unfiltered), what the persona could perceive ("???" = a word they could not read or understand;
icons without labels mean they could not tell what the icon does), the persona's inner
thoughts/feelings/action, and what the executor actually did.

Write findings for the app's developers:
- Report real usability problems in the APP: jargon, English text, icon-only controls, tiny text,
  unclear next step, unhelpful error messages, missing feedback, etc.
- Every issue must cite the step number where it shows most clearly, and evidence screenshot file
  names taken from the trace (e.g. "step-007.png"). Only cite steps that exist.
- "misclicked" is injected simulation noise (fat-finger). Do not report it as an app bug unless the
  UI made it likely (tiny targets placed close together).
- Severity: high = blocked the task or caused giving up; medium = caused repeated attempts,
  confusion or fear; low = minor friction.
- One issue per distinct problem; merge repeats and mention how many steps it affected.
- Suggestions must be concrete, in plain wording an Indonesian non-technical user would understand
  (quote the suggested Indonesian UI text).
- `screen` is the screen id given in the trace.
- `summary`: 2-3 sentences on how the session went overall.
Write in English."""


def load_trace(run_dir: Path) -> list[dict[str, Any]]:
    lines = (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines if x.strip()]


def format_trace(meta: dict[str, Any], trace: list[dict[str, Any]]) -> str:
    out = [
        f"Persona: {meta['persona_name']} ({meta['persona']})",
        f"Goal given to persona: {meta['goal']}",
        f"Outcome (judged by the runner, not the persona): {meta['result']} "
        f"after {meta['steps']} steps",
    ]
    for e in trace:
        if e.get("event"):
            out.append(f"\n## Step {e['step']}: {e['event']}")
            continue
        shot = Path(e["screenshot"]).name
        out.append(f"\n## Step {e['step']} - screen {e['screen']} - screenshot {shot}")
        out.append(f"### Really on screen\n{e['raw_observation']}")
        out.append(f"### Persona perceived\n{e['observation']}")
        t = e["tester"]
        out.append(
            f"### Persona\nthought: {t['pikiran']}\nfeeling: {t['perasaan']}\n"
            f"action: {t['aksi']} target={t.get('target')} text={t.get('teks')!r}"
        )
        if ex := e.get("executed"):
            out.append(
                f"### Executed\nmisclicked={ex['misclicked']} typed={ex['typed_text']!r} "
                f"error={ex['error']}\nscreen_changed={e['screen_changed']} "
                f"patience={e['patience']} ({', '.join(e['patience_reasons']) or 'no change'})"
            )
    return "\n".join(out)


def validate(out: AnalystOutput, trace: list[dict[str, Any]], run_dir: Path) -> list[Issue]:
    """Drop issues that cite non-existent steps; keep only evidence files that exist."""
    shots = {e["step"]: Path(e["screenshot"]).name for e in trace if "screenshot" in e}
    issues = []
    for i in out.issues:
        if i.step not in shots:
            continue
        ev = [Path(x).name for x in i.evidence]
        ev = [x for x in ev if (run_dir / "screenshots" / x).exists()] or [shots[i.step]]
        issues.append(i.model_copy(update={"evidence": ev}))
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(issues, key=lambda i: (order[i.severity], i.step))


async def analyze(run_dir: Path, model: str) -> Findings:
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    trace = load_trace(run_dir)
    out, reason = await structured(model, SYSTEM, format_trace(meta, trace), AnalystOutput, 16000)
    if out is None:
        raise RuntimeError(f"analyst returned no findings (stop_reason={reason})")
    findings = Findings(
        result=meta["result"],
        steps=meta["steps"],
        persona=meta["persona"],
        task=meta["task"],
        seed=meta["seed"],
        summary=out.summary,
        issues=validate(out, trace, run_dir),
    )
    (run_dir / "findings.json").write_text(findings.model_dump_json(indent=2), encoding="utf-8")
    return findings
