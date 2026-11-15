"""Aggregate many runs into frequency counts ("4/6 runs stuck at #/form")."""

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from gaptek.analyst import Findings, load_trace


def last_screen(run_dir: Path) -> str:
    screens = [e["screen"] for e in load_trace(run_dir) if "screen" in e]
    return screens[-1] if screens else "?"


def aggregate(run_dirs: list[Path]) -> dict[str, Any]:
    by_persona: dict[str, Counter[str]] = defaultdict(Counter)
    stuck: Counter[str] = Counter()
    issue_screens: dict[str, set[str]] = defaultdict(set)
    issue_examples: dict[str, list[str]] = defaultdict(list)
    for rd in run_dirs:
        meta = json.loads((rd / "run.json").read_text(encoding="utf-8"))
        by_persona[meta["persona"]][meta["result"]] += 1
        if meta["result"] != "success":
            stuck[last_screen(rd)] += 1
        f = rd / "findings.json"
        if f.exists():
            for i in Findings.model_validate_json(f.read_text(encoding="utf-8")).issues:
                if i.severity in ("high", "medium"):
                    issue_screens[i.screen].add(rd.name)
                    issue_examples[i.screen].append(f"[{i.severity}] {i.summary}")
    n = len(run_dirs)
    return {
        "runs": n,
        "results_by_persona": {p: dict(c) for p, c in by_persona.items()},
        "stuck_at": [f"{c}/{n} runs ended without success at {s}" for s, c in stuck.most_common()],
        "issues_by_screen": [
            {"screen": s, "runs": f"{len(r)}/{n}", "examples": issue_examples[s][:5]}
            for s, r in sorted(issue_screens.items(), key=lambda kv: -len(kv[1]))
        ],
        "run_dirs": [str(rd) for rd in run_dirs],
    }
