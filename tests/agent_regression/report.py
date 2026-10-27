"""Write the #231 summary (JSON + markdown). Deterministic: diff it before/after each Agent PR."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# Plain pytest runs write the report to a temp dir so they never dirty the tree; run.py points
# AGENT_REGRESSION_OUT at tests/agent_regression/report on purpose.
OUT = Path(os.environ.get("AGENT_REGRESSION_OUT") or Path(tempfile.gettempdir()) / "comfyart-agent-regression")


def write(results: dict[str, dict]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [results[k] for k in sorted(results)]
    (OUT / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n")
    counts = {}
    for r in rows:
        counts[r["result"]] = counts.get(r["result"], 0) + 1
    lines = ["# Agent regression (#231)", "",
             "Mocks only, $0. " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())), "",
             "| case | lang | result | steps/limit | paid (exp) | LLM req | msgs | tokens | status | note |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['case']} {r['title']} | {r['lang']} | {r['result']} | {r['steps']}/{r['limit']} | "
                     f"{r['paid_calls']} ({r['paid_expected']}) | {r['llm_requests']} | {r['messages']} | {r['tokens']} | "
                     f"{r['status']} | {r['note']}{' — ' + r['error'] if r.get('error') and r['result'] == 'fail' else ''} |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    return OUT
