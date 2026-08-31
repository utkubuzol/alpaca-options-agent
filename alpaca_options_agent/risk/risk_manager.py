"""
Risk manager: the layer that is allowed to say no.

Every candidate the strategy engine produces passes through here before
it reaches the execution engine — in both backtest and live, so a
strategy that "backtests great" but only because the backtest let it
oversize positions or ignore buying-power limits gets caught before it
ever reaches a comparison-worthy paper track record.

Checks implemented, roughly in the order a real options desk would apply
them: liquidity/assignment sanity -> position sizing vs buying power ->
per-trade max loss -> portfolio-level exposure (delta, concentration,
position count) -> daily drawdown circuit breaker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from alpaca_options_agent.config import RiskConfig
from alpaca_options_agent.strategy.types import StrategyType, TradeCandidate

# Defined-risk structures (credit spreads): max_loss_per_contract is a real,
# bounded number, so the per-trade risk budget check applies directly to it.
# Undefined-risk structures (cash-secured puts, covered calls) report
# max_loss_per_contract as "if the stock goes to zero," which is a real but
# extremely conservative bound that no desk actually sizes day-to-day risk
# off of — they size those by collateral/buying-power and concentration
# limits instead (both already enforced below). Gating a CSP's size on the
# to-zero loss would make max_risk_per_trade_pct bind long before buying
# power does, which isn't the risk model being asked for.
_DEFINED_RISK_STRATEGIES = {StrategyType.PUT_CREDIT_SPREAD, StrategyType.CALL_CREDIT_SPREAD}


@dataclass
class AccountSnapshot:
    equity: float
    cash: float
    options_buying_power: float
    positions_value_by_underlying: Dict[str, float] = field(default_factory=dict)
    open_position_count: int = 0
    portfolio_net_delta_dollars: float = 0.0  # sum of (net_delta * 100 * contracts * underlying_price)
    starting_equity_today: Optional[float] = None


@dataclass
class RiskDecision:
    approved: bool
    sized_contracts: int
    reasons: List[str] = field(default_factory=list)


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg

    def screen(self, candidate: TradeCandidate, account: AccountSnapshot) -> RiskDecision:
        reasons: List[str] = []

        # --- Daily drawdown circuit breaker: blocks *all* new risk, checked first. ---
        if account.starting_equity_today:
            drawdown = (account.starting_equity_today - account.equity) / account.starting_equity_today
            if drawdown >= self.cfg.max_daily_drawdown_pct:
                return RiskDecision(
                    approved=False,
                    sized_contracts=0,
                    reasons=[
                        f"daily drawdown circuit breaker tripped: {drawdown:.2%} >= "
                        f"{self.cfg.max_daily_drawdown_pct:.2%} — no new positions today"
                    ],
                )

        # --- Portfolio-level position count ---
        if account.open_position_count >= self.cfg.max_concurrent_positions:
            reasons.append(
                f"max concurrent positions reached ({account.open_position_count}/"
                f"{self.cfg.max_concurrent_positions})"
            )

        # --- Per-trade max-loss sizing vs risk budget (defined-risk only; see module docstring) ---
        risk_budget = account.equity * self.cfg.max_risk_per_trade_pct
        if candidate.max_loss_per_contract <= 0 or candidate.strategy_type not in _DEFINED_RISK_STRATEGIES:
            size_by_risk = candidate.contracts  # sizing instead governed by collateral/concentration below
        else:
            size_by_risk = max(0, int(risk_budget // candidate.max_loss_per_contract))

        # --- Collateral / buying power sizing (binding for CSPs especially) ---
        if candidate.collateral_required > 0:
            size_by_collateral = max(0, int(account.options_buying_power // candidate.collateral_required))
        else:
            size_by_collateral = candidate.contracts

        # --- Single-underlying concentration cap ---
        existing_exposure = account.positions_value_by_underlying.get(candidate.underlying, 0.0)
        max_underlying_notional = account.equity * self.cfg.max_single_underlying_exposure_pct
        remaining_notional = max(0.0, max_underlying_notional - existing_exposure)
        per_contract_notional = max(candidate.collateral_required, candidate.max_loss_per_contract, 1.0)
        size_by_concentration = max(0, int(remaining_notional // per_contract_notional))

        sized_contracts = min(
            candidate.contracts, size_by_risk, size_by_collateral, size_by_concentration
        )

        if size_by_risk == 0:
            reasons.append(
                f"per-trade risk budget (${risk_budget:,.0f}) smaller than one contract's max "
                f"loss (${candidate.max_loss_per_contract:,.0f})"
            )
        if size_by_collateral == 0 and candidate.collateral_required > 0:
            reasons.append(
                f"insufficient options buying power (${account.options_buying_power:,.0f}) for "
                f"one contract's collateral (${candidate.collateral_required:,.0f})"
            )
        if size_by_concentration == 0:
            reasons.append(f"single-underlying concentration cap reached for {candidate.underlying}")

        # --- Portfolio delta cap, expressed in delta-*dollars* (net_delta in
        # delta-shares-per-contract * 100 shares/contract * contracts * underlying
        # price), capped as a fraction of account equity. This is the standard
        # way a desk normalizes directional exposure across underlyings that
        # trade at very different prices (e.g. SPY vs a $20 stock). ---
        candidate_delta_dollars = (
            candidate.net_delta * 100 * max(sized_contracts, 1) * candidate.underlying_price
        )
        projected_delta_dollars = account.portfolio_net_delta_dollars + candidate_delta_dollars
        delta_dollar_limit = account.equity * self.cfg.max_portfolio_delta
        if abs(projected_delta_dollars) > delta_dollar_limit:
            reasons.append(
                f"would breach portfolio delta cap (${projected_delta_dollars:,.0f} projected "
                f"delta-dollars vs ${delta_dollar_limit:,.0f} limit)"
            )
            sized_contracts = 0

        approved = sized_contracts > 0 and account.open_position_count < self.cfg.max_concurrent_positions
        if not approved and not reasons:
            reasons.append("blocked for an unspecified sizing reason (sized_contracts == 0)")

        return RiskDecision(approved=approved, sized_contracts=max(sized_contracts, 0), reasons=reasons)
