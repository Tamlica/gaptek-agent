"""Render a run directory into a self-contained-ish report.html (screenshots stay as files)."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from gaptek.analyst import Findings, load_trace

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
)

FEELING_COLORS = {
    "tenang": "#2e7d32",
    "ragu": "#f9a825",
    "bingung": "#ef6c00",
    "kesal": "#c62828",
    "takut": "#6a1b9a",
    "menyerah": "#424242",
}


def render_report(run_dir: Path) -> Path:
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    trace = load_trace(run_dir)
    f = run_dir / "findings.json"
    findings = Findings.model_validate_json(f.read_text(encoding="utf-8")) if f.exists() else None
    html = _env.get_template("report.html.j2").render(
        meta=meta,
        steps=[e for e in trace if "tester" in e],
        events=[e for e in trace if "event" in e],
        findings=findings,
        colors=FEELING_COLORS,
    )
    out = run_dir / "report.html"
    out.write_text(html, encoding="utf-8")
    return out
