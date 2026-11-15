from pathlib import Path

from gaptek.analyst import AnalystOutput, Issue, format_trace, load_trace, validate
from gaptek.batch import aggregate
from gaptek.config import RunConfig
from gaptek.report import render_report
from gaptek.runner import run
from tests.helpers import bu_sri
from tests.test_agent import demo_task, literal


async def test_trace_to_analysis_to_report(demo_url: str, tmp_path: Path) -> None:
    res = await run(bu_sri(), demo_task(demo_url), RunConfig(runs_dir=tmp_path), decide=literal)
    trace = load_trace(res.run_dir)

    import json

    meta = json.loads((res.run_dir / "run.json").read_text(encoding="utf-8"))
    text = format_trace(meta, trace)
    assert "Checkout" in text and "???" in text  # analyst sees both raw and perceived

    fake = AnalystOutput(
        summary="Stuck at menu.",
        issues=[
            Issue(severity="low", step=2, screen="/", summary="b", evidence=[], suggestion="s"),
            Issue(
                severity="high",
                step=1,
                screen="/",
                summary="'Checkout' unreadable",
                evidence=["step-001.png", "made-up.png"],
                suggestion="Use 'Pesan'",
            ),
            Issue(
                severity="high", step=99, screen="/", summary="bogus", evidence=[], suggestion="x"
            ),
        ],
    )
    issues = validate(fake, trace, res.run_dir)
    assert [i.step for i in issues] == [1, 2]  # step 99 dropped, sorted by severity
    assert issues[0].evidence == ["step-001.png"]
    assert issues[1].evidence == ["step-002.png"]  # filled from the cited step

    html = render_report(res.run_dir).read_text(encoding="utf-8")
    assert "Simulation." in html and "step-001.png" in html

    summary = aggregate([res.run_dir, res.run_dir])
    assert summary["results_by_persona"] == {"bu-sri": {"gave_up": 2}}
    assert summary["stuck_at"] == ["2/2 runs ended without success at /"]
