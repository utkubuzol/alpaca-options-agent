"""Public landing-page data: aggregates the showcase account's `trade_events`
into the `LandingData` shape the Kestrel landing imports, plus a small live
quote feed. Everything here is cached in-process so anonymous traffic never
fans out to Supabase / Alpaca.

The aggregation mirrors `scripts/build_landing_data.py` (which does the same
from a JSONL journal); the difference is the row shape — here each event is
`{kind, underlying, ts (ISO), payload: {...}}` from Postgres, not a flattened
JSONL line.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from alpaca_options_agent.monitoring.pnl import premium_stats_from_fills

from app import supa_sync
from app.crypto import decrypt
from app.settings import get_settings

DEFINED_RISK = {"put_credit_spread", "call_credit_spread"}

# reason-string -> landing gate label. Verbatim from scripts/build_landing_data.py.
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

# Symbols the public quote endpoint will serve (the agent universe + a couple
# of common index ETFs). Anything else is ignored.
QUOTE_ALLOWLIST = {
    "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMD", "TSLA",
    "GOOGL", "AMZN", "META", "NFLX",
}

_SHOWCASE_TTL = 60.0
_QUOTES_TTL = 30.0
_cache: Dict[str, Dict[str, Any]] = {}


def _cached(key: str, ttl: float, build):
    hit = _cache.get(key)
    now = time.time()
    if hit and now - hit["ts"] < ttl:
        return hit["value"]
    value = build()
    _cache[key] = {"ts": now, "value": value}
    return value


# ------------------------------------------------------------------ #
# showcase (LandingData)
# ------------------------------------------------------------------ #
def classify_gate(reason: str) -> str:
    low = f" {reason.lower()} "
    for needle, label in _GATE_KEYWORDS:
        if needle in low:
            return label
    words = reason.strip().split()
    return " ".join(words[:4]) if words else "Risk gate"


def _iv_rank(rows: List[Dict], recent: int = 40):
    obs = []
    for r in rows:
        if r["kind"] != "scan":
            continue
        vs = (r.get("payload") or {}).get("vol_signal") or {}
        rank = vs.get("iv_rank")
        if rank is None:
            continue
        obs.append((r.get("id", 0), float(rank), bool(vs.get("iv_rank_is_proxy", False))))
    if not obs:
        return None, None
    obs.sort(key=lambda t: t[0])
    tail = obs[-recent:]
    return [round(v, 4) for _, v, _ in tail], None


def _payoff(rows: List[Dict]) -> Optional[List[Dict[str, float]]]:
    best = None
    for r in rows:
        if r["kind"] != "candidate":
            continue
        c = (r.get("payload") or {}).get("candidate") or {}
        if c.get("strategy_type") not in DEFINED_RISK:
            continue
        if best is None or r.get("id", 0) >= best[0]:
            best = (r.get("id", 0), c)
    if best is None:
        return None
    c = best[1]
    strikes = sorted(
        float(leg["quote"]["strike"])
        for leg in c.get("legs", [])
        if leg.get("quote", {}).get("strike") is not None
    )
    if len(strikes) < 2:
        return None
    lo, hi = strikes[0], strikes[-1]
    max_profit = float(c.get("max_profit_per_contract", 0.0))
    max_loss = float(c.get("max_loss_per_contract", 0.0))
    is_put = c.get("strategy_type") == "put_credit_spread"
    pad = max(hi - lo, 1.0)

    def pnl(x: float) -> float:
        if is_put:
            if x >= hi:
                return max_profit
            if x <= lo:
                return -max_loss
        else:
            if x <= lo:
                return max_profit
            if x >= hi:
                return -max_loss
        frac = (x - lo) / (hi - lo)
        low_val = -max_loss if is_put else max_profit
        high_val = max_profit if is_put else -max_loss
        return low_val + (high_val - low_val) * frac

    xs = sorted({round(x, 2) for x in [lo - pad, lo, (lo + hi) / 2, hi, hi + pad]})
    return [{"price": x, "pnl": round(pnl(x), 2)} for x in xs]


def _rejections(rows: List[Dict], recent: int = 6) -> Optional[List[Dict[str, str]]]:
    strat_by_cid = {
        ((r.get("payload") or {}).get("candidate") or {}).get("id"):
        ((r.get("payload") or {}).get("candidate") or {}).get("strategy_type")
        for r in rows if r["kind"] == "candidate"
    }
    out = []
    for r in rows:
        p = r.get("payload") or {}
        if r["kind"] != "risk_decision" or p.get("approved"):
            continue
        reasons = p.get("reasons") or []
        reason = str(reasons[0]) if reasons else "rejected"
        out.append({
            "ts": r.get("ts", ""),
            "underlying": str(r.get("underlying") or ""),
            "strategy": str(strat_by_cid.get(p.get("candidate_id")) or ""),
            "gate": classify_gate(reason),
            "reason": reason,
        })
    return out[-recent:] if out else None


def _fills(rows: List[Dict], recent: int = 20):
    raw = []
    for r in rows:
        if r["kind"] != "fill":
            continue
        f = (r.get("payload") or {}).get("fill") or {}
        if not f.get("filled"):
            continue
        exp, real = f.get("expected_credit"), f.get("realized_credit")
        if exp is None or real is None:
            continue
        raw.append((round(float(exp), 2), round(float(real), 2)))
    if not raw:
        return None
    tail = raw[-recent:]
    return [{"trade": i + 1, "expected": e, "realized": rl} for i, (e, rl) in enumerate(tail)]


def _stats(rows: List[Dict]) -> Optional[Dict[str, int]]:
    fills = [(r.get("payload") or {}).get("fill") or {} for r in rows if r["kind"] == "fill"]
    ps = premium_stats_from_fills(fills)
    if not ps.get("n_filled"):
        return None
    rejected = sum(
        1 for r in rows
        if r["kind"] == "risk_decision" and not (r.get("payload") or {}).get("approved")
    )
    return {
        "fills": ps["n_filled"],
        "avgSlippageBps": round(ps.get("avg_slippage_bps") or 0),
        "worstSlippageBps": round(ps.get("worst_slippage_bps") or 0),
        "rejected": rejected,
    }


def build_showcase() -> Dict[str, Any]:
    return _cached("showcase", _SHOWCASE_TTL, _build_showcase)


def _build_showcase() -> Dict[str, Any]:
    uid = get_settings().showcase_user_id
    empty = {
        "mode": None, "source": None, "asOf": None, "recordCount": 0,
        "ivRank": None, "ivThreshold": None, "payoff": None,
        "rejections": None, "fills": None, "stats": None,
    }
    if not uid:
        return empty
    try:
        rows = supa_sync.select(
            "trade_events", columns="id,ts,kind,underlying,payload",
            eq={"user_id": uid}, order="id.asc", limit=4000,
        )
    except Exception:  # noqa: BLE001 — public endpoint: degrade, never 500
        return empty
    if not rows:
        return empty

    iv_rank, _ = _iv_rank(rows)
    iv_threshold = None
    try:
        strat = supa_sync.select(
            "strategies", columns="params", eq={"user_id": uid}, order="created_at.asc", limit=1,
        )
        if strat:
            iv_threshold = (strat[0].get("params") or {}).get("iv_rank_entry_threshold")
    except Exception:  # noqa: BLE001
        pass

    return {
        "mode": "live",
        "source": "Live paper account",
        "asOf": rows[-1].get("ts"),
        "recordCount": len(rows),
        "ivRank": iv_rank,
        "ivThreshold": iv_threshold,
        "payoff": _payoff(rows),
        "rejections": _rejections(rows),
        "fills": _fills(rows),
        "stats": _stats(rows),
    }


# ------------------------------------------------------------------ #
# quotes
# ------------------------------------------------------------------ #
def _showcase_broker():
    uid = get_settings().showcase_user_id
    if not uid:
        return None
    row = supa_sync.select("broker_credentials", eq={"user_id": uid}, single=True)
    if not row:
        return None
    from alpaca_options_agent.broker.client import AlpacaBroker
    return AlpacaBroker(
        api_key=decrypt(row["alpaca_api_key_enc"]),
        secret_key=decrypt(row["alpaca_secret_key_enc"]),
        paper=True,
    )


def get_quotes(symbols: List[str]) -> List[Dict[str, Any]]:
    wanted = [s for s in (s.strip().upper() for s in symbols) if s in QUOTE_ALLOWLIST]
    if not wanted:
        return []
    key = "quotes:" + ",".join(sorted(wanted))
    return _cached(key, _QUOTES_TTL, lambda: _build_quotes(wanted))


def _build_quotes(symbols: List[str]) -> List[Dict[str, Any]]:
    broker = _showcase_broker()
    if broker is None:
        return []
    out: List[Dict[str, Any]] = []
    for sym in symbols:
        try:
            price = float(broker.get_underlying_price(sym))
            closes = broker.get_historical_closes(sym, lookback_days=3)
            prev = float(closes[-2]) if len(closes) >= 2 else (float(closes[-1]) if closes else price)
            change_pct = round(100.0 * (price - prev) / prev, 2) if prev else 0.0
            out.append({"symbol": sym, "price": round(price, 2),
                        "prevClose": round(prev, 2), "changePct": change_pct})
        except Exception:  # noqa: BLE001 — one bad symbol shouldn't drop the strip
            continue
    return out
