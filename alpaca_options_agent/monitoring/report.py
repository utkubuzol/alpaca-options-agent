"""
The sim-to-real gap report: reads the backtest result and the live paper
decision journal and puts expected-vs-realized numbers side by side. This
is the artifact meant to directly answer the hackathon's "how do you
reduce the gap between simulated strategy and real-world trading" prompt
— not as a claim in a README, but as a generated table of actual numbers
every time the agent has traded.
"""
from __future__ import annotations

import statistics
from pathlib import Path
from typing import Dict, List, Optional

from alpaca_options_agent.monitoring.journal import Journal


def _live_fill_rows(journal_path: Path) -> List[Dict]:
    journal = Journal(journal_path)
    rows = []
    for row in journal.read_all():
        if row.get("kind") == "fill":
            f = row["fill"]
            if f.get("filled") and f.get("realized_credit") is not None:
                rows.append(f)
    return rows


def build_gap_report(
    backtest_summary: Optional[Dict],
    backtest_trades: Optional[List[Dict]],
    live_journal_path: Path,
    out_path: Optional[Path] = None,
) -> Dict:
    live_fills = _live_fill_rows(live_journal_path)

    live_slippage_bps = [f["slippage_bps"] for f in live_fills if f.get("slippage_bps") is not None]
    bt_summary = backtest_summary
    bt_slippage_bps = (
        [
            (t["slippage_per_contract"] / t["expected_credit"] * 10000) if t.get("expected_credit") else 0.0
            for t in backtest_trades
        ]
        if backtest_trades
        else []
    )

    report = {
        "backtest": bt_summary,
        "paper_live": {
            "n_fills": len(live_fills),
            "avg_slippage_bps": round(statistics.mean(live_slippage_bps), 1) if live_slippage_bps else None,
            "median_slippage_bps": round(statistics.median(live_slippage_bps), 1) if live_slippage_bps else None,
            "worst_slippage_bps": round(max(live_slippage_bps), 1) if live_slippage_bps else None,
        },
        "gap": {
            "backtest_avg_slippage_bps": round(statistics.mean(bt_slippage_bps), 1) if bt_slippage_bps else None,
            "paper_avg_slippage_bps": round(statistics.mean(live_slippage_bps), 1) if live_slippage_bps else None,
            "note": (
                "Backtest slippage is modeled (synthetic Black-Scholes chain + a "
                "stochastic fill-cost model — see execution/cost_model.py and "
                "backtest/pricing.py). Paper slippage is real OPRA-quoted "
                "expected-vs-realized fill price from live orders. The gap between "
                "these two numbers, tracked over time, is the direct evidence of "
                "how well the execution-cost model approximates real market "
                "friction — the whole point of running both."
            ),
        },
    }

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_markdown(report, out_path)
    return report


def _write_markdown(report: Dict, out_path: Path) -> None:
    lines = ["# Sim-to-Real Gap Report", ""]

    bt = report["backtest"]
    lines.append("## Backtest (modeled)")
    if bt:
        for k, v in bt.items():
            lines.append(f"- **{k}**: {v}")
    else:
        lines.append("- no backtest run yet (`agent backtest` to generate one)")

    pl = report["paper_live"]
    lines.append("")
    lines.append("## Paper trading (real OPRA fills)")
    for k, v in pl.items():
        lines.append(f"- **{k}**: {v}")

    lines.append("")
    lines.append("## Gap")
    g = report["gap"]
    lines.append(f"- Backtest avg expected-vs-modeled slippage: **{g['backtest_avg_slippage_bps']} bps**")
    lines.append(f"- Paper avg expected-vs-realized slippage: **{g['paper_avg_slippage_bps']} bps**")
    lines.append("")
    lines.append(g["note"])

    out_path.write_text("\n".join(lines))
