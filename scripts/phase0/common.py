"""Shared helpers for the Phase 0 probes. Probes measure; they never change production code."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
USER_AGENT = "RecapShorts-Phase0/0.1"


def films() -> list[dict]:
    return json.loads((HERE / "films.json").read_text())


def out_dir(name: str) -> Path:
    path = Path(os.environ.get("PROBE_OUT", "work/phase0")) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_report(directory: Path, report: dict, summary_lines: list[str]) -> None:
    (directory / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    text = "\n".join(summary_lines) + "\n"
    (directory / "summary.md").write_text(text)
    print(text, flush=True)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as stream:
            stream.write(text)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
