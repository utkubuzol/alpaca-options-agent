"""
Execution cost model — the piece most sim-to-real gap analyses skip.

A backtest that fills every order at the theoretical mid price is not a
backtest of a tradeable strategy, it's a backtest of a strategy that
doesn't pay the bid-ask spread. This module is the *single* place that
decides "what price do we actually expect to pay/receive," and it is
called identically by:
  - the live execution engine, to build the marketable limit order sent
    to Alpaca, and to compute expected-vs-realized slippage afterward;
  - the backtest engine, to simulate a fill against historical quotes
    with the same pricing logic (see `simulate_fill`).

That symmetry is what makes "expected backtest P&L" and "realized paper
P&L" comparable numbers instead of two unrelated curves.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List

from alpaca_options_agent.config import ExecutionConfig
from alpaca_options_agent.strategy.types import Leg, LegAction, TradeCandidate

_SELL_ACTIONS = (LegAction.SELL_TO_OPEN, LegAction.SELL_TO_CLOSE)


def tick_size(price: float, cfg: ExecutionConfig) -> float:
    return cfg.tick_size_low if price < cfg.tick_price_breakpoint else cfg.tick_size_high


def _leg_sign(leg: Leg) -> int:
    return 1 if leg.action in _SELL_ACTIONS else -1


def net_mid_price(legs: List[Leg]) -> float:
    """Positive = net credit, negative = net debit, at the theoretical mid."""
    return round(sum(_leg_sign(l) * l.quote.mid * l.ratio_qty for l in legs), 4)


def _liquidity_penalty_ticks(legs: List[Leg], cfg: ExecutionConfig) -> float:
    """Wider quoted spreads and thinner open interest both make a resting
    limit order less likely to fill at a good price — model that as extra
    ticks of edge you have to give up, not as a free mid-price fill.
    """
    worst_spread_pct = max((l.quote.spread_pct for l in legs), default=0.0)
    thinnest_oi = min((l.quote.open_interest for l in legs), default=0)

    spread_penalty = min(3.0, worst_spread_pct / 0.05)  # every 5% of spread ~ 1 extra tick
    oi_penalty = 1.5 if thinnest_oi < 100 else (0.5 if thinnest_oi < 500 else 0.0)
    return spread_penalty + oi_penalty


@dataclass
class ExpectedExecution:
    net_mid: float
    net_limit_price: float
    edge_given_up: float
    edge_given_up_bps: float
    ticks_given_up: float


def expected_marketable_limit(legs: List[Leg], cfg: ExecutionConfig) -> ExpectedExecution:
    """The net limit price we'd actually submit to be reasonably sure of a
    fill, and how much theoretical edge (vs mid) that costs us.
    """
    net_mid = net_mid_price(legs)
    ref_price = max(sum(l.quote.mid for l in legs) / max(1, len(legs)), 0.01)
    tick = tick_size(ref_price, cfg)

    ticks = cfg.limit_price_improvement_ticks + _liquidity_penalty_ticks(legs, cfg)
    edge = round(ticks * tick, 4)

    # Selling a net credit: give up edge by pricing *below* mid (more marketable).
    # Paying a net debit: give up edge by pricing *above* mid (paying more).
    net_limit = net_mid - edge if net_mid >= 0 else net_mid + edge
    net_limit = round(net_limit, 2)

    edge_bps = (edge / abs(net_mid) * 10000) if net_mid else 0.0
    return ExpectedExecution(
        net_mid=net_mid,
        net_limit_price=net_limit,
        edge_given_up=edge,
        edge_given_up_bps=edge_bps,
        ticks_given_up=ticks,
    )


def simulate_fill(
    candidate: TradeCandidate, cfg: ExecutionConfig, rng: random.Random
) -> float:
    """Backtest-only: simulate a realized net credit for a candidate that
    the live engine would have sent as a marketable limit order.

    Uses the *same* expected_marketable_limit() as the live path as the
    center of the fill distribution, then adds stochastic noise scaled to
    the quoted spread — approximating the fact that a real limit order
    sometimes fills better (queue priority, a passing market order) and
    sometimes needs to be chased (walked further from mid) before it
    fills, which a naive "always fill exactly at my limit" backtest hides.
    """
    exp = expected_marketable_limit(candidate.legs, cfg)
    worst_spread = max((l.quote.spread_pct for l in candidate.legs), default=0.02)
    noise_std = max(0.005, worst_spread * 0.35) * abs(exp.net_mid or 0.01)
    noise = rng.gauss(0, noise_std)
    # Fills are bounded: can't do meaningfully better than mid, can be chased worse.
    realized = exp.net_limit_price + noise
    if exp.net_mid >= 0:
        realized = min(realized, exp.net_mid)  # never better than mid on a credit sale
    else:
        realized = max(realized, exp.net_mid)
    return round(realized, 4)


def slippage_stats(expected_credit: float, realized_credit: float) -> tuple[float, float]:
    slippage = round(realized_credit - expected_credit, 4)
    bps = (slippage / abs(expected_credit) * 10000) if expected_credit else 0.0
    return slippage, round(bps, 1)
