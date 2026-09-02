"""
PnL snapshot: one structured view of where the paper account stands right
now — total, realized, unrealized, today — plus the premium-selling
journal stats (expected vs. realized credit) that say how the execution
model is holding up.

Design choices:
- Total PnL is `equity - baseline_equity`. Unambiguous, always right.
- Unrealized PnL is summed straight from Alpaca's per-position
  `unrealized_pl`.
- Realized PnL is therefore `total - unrealized` — no need to replay the
  activity ledger and no risk of double-counting assignments/expiries.
- Today's PnL is `equity - last_equity` (Alpaca resets `last_equity` at
  each session boundary).

Kept free of any alpaca-py import: it takes plain dicts (the same shape
`AlpacaBroker.get_account()` / `.get_positions()` already return), so it
is unit-testable without network or keys.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from alpaca_options_agent.monitoring.journal import Journal


def _pct(numer: float, denom: float) -> Optional[float]:
    return round(100.0 * numer / denom, 4) if denom else None


def premium_journal_stats(journal_path: Path) -> Dict:
    """Aggregate every `fill` row the agent has written: how much premium
    it expected to collect vs. actually collected, and the slippage
    between the two.
    """
    if not Path(journal_path).exists():
        return {"n_fills": 0}

    fills = [r["fill"] for r in Journal(journal_path).read_all() if r.get("kind") == "fill"]
    return premium_stats_from_fills(fills)


def premium_stats_from_fills(fills: List[Dict]) -> Dict:
    """Same aggregation as `premium_journal_stats`, but over an already-loaded
    list of `fill` dicts — lets the SaaS backend feed rows straight from the
    `trade_events` table instead of a JSONL file."""
    if not fills:
        return {"n_fills": 0}

    filled = [f for f in fills if f.get("filled")]
    slips = [f["slippage_bps"] for f in filled if f.get("slippage_bps") is not None]

    exp = sum(f.get("expected_credit") or 0.0 for f in filled)
    real = sum(f.get("realized_credit") or 0.0 for f in filled)
    return {
        "n_fills": len(fills),
        "n_filled": len(filled),
        "n_rejected": sum(1 for f in fills if not f.get("filled")),
        "total_expected_credit_per_contract": round(exp, 4),
        "total_realized_credit_per_contract": round(real, 4),
        "credit_given_up_per_contract": round(exp - real, 4),
        "avg_slippage_bps": round(sum(slips) / len(slips), 1) if slips else None,
        "worst_slippage_bps": round(max(slips), 1) if slips else None,
    }


def build_pnl_snapshot(
    account: Dict,
    positions: List[Dict],
    baseline_equity: float,
    journal_path: Path,
    cli_equity: Optional[float] = None,
) -> Dict:
    equity = float(account["equity"])
    last_equity = float(account.get("last_equity") or equity)

    unrealized = round(sum(float(p.get("unrealized_pl") or 0.0) for p in positions), 2)
    total = round(equity - baseline_equity, 2)
    today = round(equity - last_equity, 2)

    pos_rows = [
        {
            "symbol": p["symbol"],
            "qty": p["qty"],
            "avg_entry_price": p["avg_entry_price"],
            "current_price": p.get("current_price"),
            "market_value": p.get("market_value"),
            "unrealized_pl": round(float(p.get("unrealized_pl") or 0.0), 2),
            "unrealized_pl_pct": _pct(
                float(p.get("unrealized_pl") or 0.0),
                abs(float(p.get("market_value") or 0.0) - float(p.get("unrealized_pl") or 0.0)),
            ),
        }
        for p in positions
    ]

    snap = {
        "equity": equity,
        "cash": float(account.get("cash") or 0.0),
        "baseline_equity": baseline_equity,
        "pnl": {
            "total": total,
            "total_return_pct": _pct(total, baseline_equity),
            "realized_implied": round(total - unrealized, 2),
            "unrealized": unrealized,
            "today": today,
            "today_return_pct": _pct(today, last_equity),
        },
        "open_positions": pos_rows,
        "premium_journal": premium_journal_stats(journal_path),
    }

    if cli_equity is not None:
        snap["cli_cross_check"] = {
            "equity_via_cli": cli_equity,
            "matches_sdk": abs(cli_equity - equity) < 0.01,
        }
    return snap
