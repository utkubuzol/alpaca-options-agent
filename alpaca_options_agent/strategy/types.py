"""Shared data types used across strategy, execution, risk, backtest, and monitoring.

Keeping these as plain, serializable dataclasses (not tied to alpaca-py's
wire models) is what lets the *identical* objects flow through the backtest
engine and the live agent loop — the single biggest lever for making a
sim-to-real comparison actually mean something.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional


class StrategyType(str, Enum):
    CASH_SECURED_PUT = "cash_secured_put"
    COVERED_CALL = "covered_call"
    PUT_CREDIT_SPREAD = "put_credit_spread"
    CALL_CREDIT_SPREAD = "call_credit_spread"
    IRON_CONDOR = "iron_condor"


# The finer StrategyType enum -> the dashboard/config slugs a user picks from
# ("csp", "covered_call", "credit_spread", "iron_condor"). Single source of
# truth, imported by both config.py and the strategy engine.
STRATEGY_TYPE_SLUGS = {
    StrategyType.CASH_SECURED_PUT.value: "csp",
    StrategyType.COVERED_CALL.value: "covered_call",
    StrategyType.PUT_CREDIT_SPREAD.value: "credit_spread",
    StrategyType.CALL_CREDIT_SPREAD.value: "credit_spread",
    StrategyType.IRON_CONDOR.value: "iron_condor",
}


class LegAction(str, Enum):
    SELL_TO_OPEN = "sell_to_open"
    BUY_TO_OPEN = "buy_to_open"
    SELL_TO_CLOSE = "sell_to_close"
    BUY_TO_CLOSE = "buy_to_close"


@dataclass
class OptionQuote:
    """A normalized snapshot of one option contract at decision time."""

    symbol: str
    underlying: str
    strike: float
    expiration: str  # YYYY-MM-DD
    option_type: str  # "call" | "put"
    bid: float
    ask: float
    last: Optional[float]
    open_interest: int
    volume: int
    delta: float
    gamma: float
    theta: float
    vega: float
    implied_volatility: float

    @property
    def mid(self) -> float:
        if self.bid and self.ask:
            return round((self.bid + self.ask) / 2, 4)
        return self.last or 0.0

    @property
    def spread(self) -> float:
        return max(self.ask - self.bid, 0.0)

    @property
    def spread_pct(self) -> float:
        return self.spread / self.mid if self.mid else float("inf")


@dataclass
class Leg:
    """One leg of a (possibly multi-leg) options trade."""

    quote: OptionQuote
    action: LegAction
    ratio_qty: int = 1


@dataclass
class TradeCandidate:
    """A fully-specified, not-yet-executed trade idea produced by the strategy
    engine. This is the object the risk manager screens and the execution
    engine fills — in both backtest and live.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    underlying: str = ""
    underlying_price: float = 0.0
    strategy_type: StrategyType = StrategyType.CASH_SECURED_PUT
    legs: List[Leg] = field(default_factory=list)
    contracts: int = 1  # number of spreads/contracts (not legs)
    rationale: str = ""
    signal_score: float = 0.0  # 0-1, higher = stronger conviction
    iv_rank: float = 0.0
    net_credit_per_contract: float = 0.0  # positive = credit received
    max_loss_per_contract: float = 0.0
    max_profit_per_contract: float = 0.0
    prob_of_profit: float = 0.0  # approximated from short-leg delta
    breakeven: float = 0.0
    collateral_required: float = 0.0  # cash-secured / margin requirement
    net_delta: float = 0.0
    net_theta: float = 0.0

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["strategy_type"] = self.strategy_type.value
        for leg in d["legs"]:
            leg["action"] = leg["action"] if isinstance(leg["action"], str) else leg["action"].value
        return d


@dataclass
class FillResult:
    """Outcome of attempting to execute a TradeCandidate — carries both the
    *expected* (model) price and the *realized* (actual) price so the gap
    between them is always on hand, never reconstructed after the fact.
    """

    candidate_id: str
    submitted: bool
    filled: bool
    expected_credit: float
    realized_credit: Optional[float]
    slippage_per_contract: Optional[float]
    slippage_bps: Optional[float]
    order_ids: List[str] = field(default_factory=list)
    reject_reason: Optional[str] = None
    partially_filled_contracts: int = 0
    timestamp: float = field(default_factory=time.time)
