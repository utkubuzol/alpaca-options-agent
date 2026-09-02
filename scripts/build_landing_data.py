#!/usr/bin/env python3
"""
build_landing_data.py — one-off developer tool.

Reads the agent's append-only JSONL decision journal (read-only) and emits
`web/frontend/components/landing/data.json`, matching the `LandingData` shape
the Kestrel landing page imports at build time.

Design constraints (deliberate):
  * The journal is opened read-only. It is never written, moved, or truncated.
  * Nothing at runtime reads the journal — the site imports the emitted JSON,
    which keeps `/` statically prerenderable with no data fetching.
  * Standard library only. No third-party dependencies.
  * Deterministic: the same journal in produces the same JSON out.
  * Anything the journal cannot back is emitted as `null`. No value is
    invented, interpolated, or "reasonably estimated".

The journal record schema is defined in
`alpaca_options_agent/monitoring/journal.py` and the dataclasses in
`alpaca_options_agent/strategy/types.py` / `risk/risk_manager.py`. Each row is
`{"ts": <float unix seconds>, "kind": <str>, ...}` with kinds:
scan, candidate, risk_decision, fill, error, note.

Usage:
    python scripts/build_landing_data.py <path/to/agent_journal.jsonl>
    python scripts/build_landing_data.py logs/agent_journal.jsonl --mode auto
    python scripts/build_landing_data.py fx.jsonl --out /tmp/preview.json --iv-threshold 0.6
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "web" / "frontend" / "components" / "landing" / "data.json"

DEFINED_RISK = {"put_credit_spread", "call_credit_spread"}

# Map a risk-manager reason string onto one of the landing page's gate labels.
# This is deterministic classification of text the agent already wrote — it
# does not invent the rejection, only shortens the label. The full reason is
# always preserved verbatim alongside it.
_GATE_KEYWORDS = [
    ("drawdown", "Daily drawdown breaker"),
    ("concentration", "Single-name concentration"),
    ("delta", "Portfolio delta"),
    ("risk budget", "Max loss per trade"),
    ("max loss", "Max loss per trade"),
    ("open interest", "Open interest floor"),
    (" oi ", "Open interest floor"),
    ("spread", "Bid-ask spread ceiling"),
    ("buying power", "Buying power"),
    ("collateral", "Buying power"),
    ("concurrent positions", "Concurrent positions"),
]


def classify_gate(reason: str) -> str:
    low = f" {reason.lower()} "
    for needle, label in _GATE_KEYWORDS:
        if needle in low:
            return label
    # Fall back to the first few words, title-cased — still the agent's words.
    words = reason.strip().split()
    return " ".join(words[:4]) if words else "Risk gate"


def iso(ts: float) -> str:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def read_journal(path: Path) -> List[Dict[str, Any]]:
    """Read the journal read-only. Malformed lines are skipped, mirroring
    `Journal.read_all`. The file is only ever opened for reading."""
    rows: List[Dict[str, Any]] = []
    with path.open("r") as f:  # read-only; never "a"/"w"
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def detect_mode(rows: List[Dict[str, Any]], path: Path, override: str) -> tuple[str, str]:
    """Return (mode, how). mode is 'live' or 'backtest'."""
    if override in ("live", "backtest"):
        return override, "forced via --mode"
    # Only the live runner performs a CLI cross-check; the backtest never does.
    for r in rows:
        if r.get("kind") == "note" and str(r.get("message", "")).startswith("cli_cross_check"):
            return "live", "cli_cross_check note present (live runner)"
    name = path.name.lower()
    if "backtest" in name:
        return "backtest", "filename contains 'backtest'"
    if "agent" in name:
        return "live", "filename contains 'agent'"
    return "backtest", "inconclusive — defaulted to backtest (use --mode to override)"


def build_iv_rank(rows, recent: int) -> tuple[Optional[List[float]], int]:
    """IV-rank observations from `scan` records, chronological, last `recent`.
    Returns (values or None, proxy_count)."""
    obs: List[tuple[float, float, bool]] = []
    for r in rows:
        if r.get("kind") != "scan":
            continue
        vs = r.get("vol_signal") or {}
        rank = vs.get("iv_rank")
        if rank is None:
            continue
        obs.append((float(r.get("ts", 0.0)), float(rank), bool(vs.get("iv_rank_is_proxy", False))))
    if not obs:
        return None, 0
    obs.sort(key=lambda t: t[0])
    tail = obs[-recent:]
    proxy_count = sum(1 for _, _, p in tail if p)
    return [round(v, 4) for _, v, _ in tail], proxy_count


def build_payoff(rows) -> Optional[List[Dict[str, float]]]:
    """Payoff curve of the most recent *defined-risk* candidate (a spread), so
    the flat max-loss floor is real. CSPs/covered calls have no bounded floor
    and are skipped (payoff stays null)."""
    best: Optional[Dict[str, Any]] = None
    for r in rows:
        if r.get("kind") != "candidate":
            continue
        c = r.get("candidate") or {}
        if c.get("strategy_type") not in DEFINED_RISK:
            continue
        if best is None or float(c.get("created_at", r.get("ts", 0))) >= float(
            best.get("created_at", 0)
        ):
            best = c
    if best is None:
        return None

    strikes = sorted(
        float(leg["quote"]["strike"])
        for leg in best.get("legs", [])
        if leg.get("quote", {}).get("strike") is not None
    )
    if len(strikes) < 2:
        return None
    lo, hi = strikes[0], strikes[-1]
    max_profit = float(best.get("max_profit_per_contract", 0.0))
    max_loss = float(best.get("max_loss_per_contract", 0.0))
    is_put = best.get("strategy_type") == "put_credit_spread"
    pad = max(hi - lo, 1.0)

    def pnl(x: float) -> float:
        # Profit when the short strike expires out-of-the-money.
        if is_put:
            if x >= hi:
                return max_profit
            if x <= lo:
                return -max_loss
        else:  # call credit spread — mirrored
            if x <= lo:
                return max_profit
            if x >= hi:
                return -max_loss
        # Linear across the spread width between the two strikes.
        frac = (x - lo) / (hi - lo)
        low_val = -max_loss if is_put else max_profit
        high_val = max_profit if is_put else -max_loss
        return low_val + (high_val - low_val) * frac

    xs = [lo - pad, lo, (lo + hi) / 2, hi, hi + pad]
    xs = sorted(set(round(x, 2) for x in xs))
    return [{"price": x, "pnl": round(pnl(x), 2)} for x in xs]


def build_rejections(rows, recent: int) -> Optional[List[Dict[str, str]]]:
    strat_by_cid = {
        (r.get("candidate") or {}).get("id"): (r.get("candidate") or {}).get("strategy_type")
        for r in rows
        if r.get("kind") == "candidate"
    }
    out: List[Dict[str, str]] = []
    for r in rows:
        if r.get("kind") != "risk_decision" or r.get("approved"):
            continue
        reasons = r.get("reasons") or []
        reason = str(reasons[0]) if reasons else "rejected"
        out.append(
            {
                "ts": iso(r.get("ts", 0.0)),
                "underlying": str(r.get("underlying", "")),
                "strategy": str(strat_by_cid.get(r.get("candidate_id")) or ""),
                "gate": classify_gate(reason),
                "reason": reason,
            }
        )
    if not out:
        return None
    return out[-recent:]


def build_fills(rows, recent: int) -> Optional[List[Dict[str, float]]]:
    out: List[Dict[str, float]] = []
    for r in rows:
        if r.get("kind") != "fill":
            continue
        f = r.get("fill") or {}
        if not f.get("filled"):
            continue
        exp, real = f.get("expected_credit"), f.get("realized_credit")
        if exp is None or real is None:
            continue
        out.append({"expected": round(float(exp), 2), "realized": round(float(real), 2)})
    if not out:
        return None
    tail = out[-recent:]
    return [{"trade": i + 1, "expected": t["expected"], "realized": t["realized"]} for i, t in enumerate(tail)]


def build_stats(rows) -> Optional[Dict[str, int]]:
    slippages: List[float] = []
    fill_count = 0
    for r in rows:
        if r.get("kind") != "fill":
            continue
        f = r.get("fill") or {}
        if not f.get("filled") or f.get("realized_credit") is None:
            continue
        fill_count += 1
        sb = f.get("slippage_bps")
        if sb is not None:
            slippages.append(abs(float(sb)))
    if fill_count == 0:
        # No fills → cannot report slippage honestly; the whole group stays null.
        return None
    rejected = sum(1 for r in rows if r.get("kind") == "risk_decision" and not r.get("approved"))
    avg = round(sum(slippages) / len(slippages)) if slippages else 0
    worst = round(max(slippages)) if slippages else 0
    return {
        "fills": fill_count,
        "avgSlippageBps": avg,
        "worstSlippageBps": worst,
        "rejected": rejected,
    }


def latest_ts(rows) -> Optional[float]:
    used_kinds = {"scan", "candidate", "risk_decision", "fill"}
    tss = [float(r.get("ts", 0.0)) for r in rows if r.get("kind") in used_kinds and r.get("ts")]
    return max(tss) if tss else None


def main() -> int:
    p = argparse.ArgumentParser(description="Build the Kestrel landing data.json from the agent journal.")
    p.add_argument("journal", help="Path to the JSONL journal (agent_journal.jsonl or backtest_journal.jsonl).")
    p.add_argument("--out", default=str(DEFAULT_OUT), help=f"Output path (default: {DEFAULT_OUT}).")
    p.add_argument("--mode", choices=["auto", "live", "backtest"], default="auto", help="Override journal-type detection.")
    p.add_argument("--recent-iv", type=int, default=40, help="How many recent IV-rank observations to keep.")
    p.add_argument("--recent-fills", type=int, default=20, help="How many recent fills to keep.")
    p.add_argument("--recent-rejections", type=int, default=5, help="How many recent rejections to keep.")
    p.add_argument(
        "--iv-threshold",
        type=float,
        default=None,
        help="Operator-supplied entry threshold (config value, NOT in the journal). Omitted => null.",
    )
    args = p.parse_args()

    journal_path = Path(args.journal)
    if not journal_path.exists() or not journal_path.is_file():
        print(f"error: journal not found: {journal_path}", file=sys.stderr)
        print("This tool refuses to run without a real journal. It will not fabricate data.", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    # Guard: never write into logs/ and never write over the journal itself.
    if out_path.resolve() == journal_path.resolve():
        print("error: --out must not be the journal file.", file=sys.stderr)
        return 2
    if "logs" in out_path.resolve().parts:
        print("error: refusing to write output inside logs/.", file=sys.stderr)
        return 2

    rows = read_journal(journal_path)
    record_count = len(rows)
    mode, how = detect_mode(rows, journal_path, args.mode)

    iv_rank, proxy_count = build_iv_rank(rows, args.recent_iv)
    payoff = build_payoff(rows)
    rejections = build_rejections(rows, args.recent_rejections)
    fills = build_fills(rows, args.recent_fills)
    stats = build_stats(rows)
    last = latest_ts(rows)

    data = {
        "mode": mode if record_count else None,
        "source": str(journal_path),
        "asOf": iso(last) if last else None,
        "recordCount": record_count,
        "ivRank": iv_rank,
        "ivThreshold": args.iv_threshold,  # not in journal schema; null unless operator supplies it
        "payoff": payoff,
        "rejections": rejections,
        "fills": fills,
        "stats": stats,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # ---- human-readable summary ----
    def status(key: str, val: Any) -> str:
        if val is None:
            return "null (no backing records)"
        if isinstance(val, list):
            return f"{len(val)} item(s)"
        return "present"

    print(f"Read {record_count} record(s) from {journal_path}")
    print(f"Journal type: {mode}  ({how})")
    print(f"asOf: {data['asOf']}")
    print("Produced:")
    print(f"  ivRank        : {status('ivRank', iv_rank)}"
          + (f"  [{proxy_count} of them proxy]" if iv_rank else ""))
    print(f"  ivThreshold   : {'null (config value, not journaled — pass --iv-threshold to set)' if data['ivThreshold'] is None else data['ivThreshold']}")
    print(f"  payoff        : {status('payoff', payoff)}")
    print(f"  rejections    : {status('rejections', rejections)}")
    print(f"  fills         : {status('fills', fills)}")
    print(f"  stats         : {status('stats', stats)}")
    nulls = [k for k in ("ivRank", "ivThreshold", "payoff", "rejections", "fills", "stats") if data[k] is None]
    if nulls:
        print(f"Left null (page degrades honestly for these): {', '.join(nulls)}")
    print(f"Wrote {out_path}")
    if mode == "backtest":
        print("NOTE: backtest journal — section 5 (expected vs realized) must NOT present these as live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
