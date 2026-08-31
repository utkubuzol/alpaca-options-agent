"""
Backtest engine: walks a historical daily-close series one trading day at
a time, calling the *exact same* strategy, risk, and cost-model code the
live agent uses (see module docstrings in `strategy/premium_selling.py`,
`risk/risk_manager.py`, `execution/cost_model.py`). Only two things are
backtest-only: the synthetic Black-Scholes chain (see `synthetic_chain.py`
— real historical OPRA chains aren't available on a paper account) and
`cost_model.simulate_fill` (there's no real order book to fill against).

Everything downstream of "here is today's chain" is identical to live.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from alpaca_options_agent.backtest.pricing import black_scholes
from alpaca_options_agent.backtest.synthetic_chain import build_synthetic_chain
from alpaca_options_agent.config import AgentConfig
from alpaca_options_agent.execution.cost_model import expected_marketable_limit, simulate_fill
from alpaca_options_agent.monitoring.journal import Journal
from alpaca_options_agent.risk.risk_manager import AccountSnapshot, RiskManager
from alpaca_options_agent.strategy.premium_selling import StrategyParams, generate_candidates
from alpaca_options_agent.strategy.signals import IVHistoryStore, realized_vol, trend_signal, vol_signal
from alpaca_options_agent.strategy.types import Leg, LegAction, OptionQuote, TradeCandidate

_CALENDAR_DAYS_PER_TRADING_DAY = 365 / 252

# Sign of the cash flow needed to CLOSE a leg that was opened with this
# action: closing a short (SELL_TO_OPEN) costs money to buy back (+);
# closing a long (BUY_TO_OPEN) returns money when sold (-).
_CLOSE_SIGN = {LegAction.SELL_TO_OPEN: 1, LegAction.BUY_TO_OPEN: -1}


@dataclass
class OpenPosition:
    candidate: TradeCandidate
    contracts: int
    entry_credit_realized: float  # per contract, from simulate_fill
    entry_expected_credit: float
    entry_date: date
    dte_remaining: float
    initial_dte: float
    last_cost_to_close: float = 0.0  # per contract, refreshed daily; used for MTM equity


@dataclass
class TradeLogRow:
    underlying: str
    strategy_type: str
    entry_date: str
    exit_date: str
    contracts: int
    expected_credit: float
    realized_entry_credit: float
    slippage_per_contract: float
    exit_reason: str
    pnl: float


@dataclass
class BacktestResult:
    equity_curve: List[float] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    trades: List[TradeLogRow] = field(default_factory=list)
    starting_equity: float = 0.0
    ending_equity: float = 0.0

    def summary(self) -> Dict:
        n = len(self.trades)
        wins = [t for t in self.trades if t.pnl > 0]
        total_pnl = sum(t.pnl for t in self.trades)
        avg_slippage_bps = 0.0
        if n:
            slips = [
                (t.slippage_per_contract / t.expected_credit * 10000) if t.expected_credit else 0.0
                for t in self.trades
            ]
            avg_slippage_bps = sum(slips) / n

        peak = -float("inf")
        max_dd = 0.0
        for e in self.equity_curve:
            peak = max(peak, e)
            if peak > 0:
                max_dd = max(max_dd, (peak - e) / peak)

        total_return = (
            (self.ending_equity - self.starting_equity) / self.starting_equity
            if self.starting_equity else 0.0
        )
        return {
            "n_trades": n,
            "win_rate": (len(wins) / n) if n else 0.0,
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": round(total_return * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "avg_expected_vs_realized_slippage_bps": round(avg_slippage_bps, 1),
            "starting_equity": round(self.starting_equity, 2),
            "ending_equity": round(self.ending_equity, 2),
        }


def _reprice_leg(leg: Leg, spot: float, sigma: float, dte_days: float) -> Leg:
    bs = black_scholes(spot, leg.quote.strike, dte_days, sigma, leg.quote.option_type)
    new_quote = OptionQuote(
        symbol=leg.quote.symbol, underlying=leg.quote.underlying, strike=leg.quote.strike,
        expiration=leg.quote.expiration, option_type=leg.quote.option_type,
        bid=bs.price, ask=bs.price, last=bs.price,
        open_interest=leg.quote.open_interest, volume=leg.quote.volume,
        delta=bs.delta, gamma=bs.gamma, theta=bs.theta, vega=bs.vega,
        implied_volatility=sigma,
    )
    return Leg(quote=new_quote, action=leg.action, ratio_qty=leg.ratio_qty)


def _cost_to_close(pos: OpenPosition, spot: float, sigma: float) -> float:
    """Net debit/credit to flatten this position right now, per contract."""
    total = 0.0
    for leg in pos.candidate.legs:
        repriced = _reprice_leg(leg, spot, sigma, pos.dte_remaining)
        total += _CLOSE_SIGN[leg.action] * repriced.quote.mid * leg.ratio_qty
    return total


def _current_delta_dollars(pos: OpenPosition, spot: float, sigma: float) -> float:
    net_delta = 0.0
    for leg in pos.candidate.legs:
        repriced = _reprice_leg(leg, spot, sigma, pos.dte_remaining)
        # Position delta = +1x the option's own delta if long (BUY_TO_OPEN),
        # -1x if short (SELL_TO_OPEN) — a short put therefore contributes
        # positive (long-equivalent) delta, a short call negative.
        sign = -1 if leg.action == LegAction.SELL_TO_OPEN else 1
        net_delta += sign * repriced.quote.delta * leg.ratio_qty
    return net_delta * 100 * pos.contracts * spot


@dataclass
class BacktestConfig:
    universe: List[str]
    starting_equity: float = 100_000.0
    min_dte: int = 25
    max_dte: int = 45
    profit_target_pct: float = 0.50  # close at 50% of max credit captured
    stop_loss_multiple: float = 2.0  # close if cost-to-close > 2x entry credit
    min_dte_before_forced_exit: int = 3
    random_seed: int = 7


def run_backtest(
    closes_by_underlying: Dict[str, List[float]],
    dates_by_underlying: Dict[str, List[date]],
    agent_cfg: AgentConfig,
    bt_cfg: BacktestConfig,
    journal_path: Optional[Path] = None,
) -> BacktestResult:
    rng = random.Random(bt_cfg.random_seed)
    risk_mgr = RiskManager(agent_cfg.risk)
    journal_path = journal_path or (agent_cfg.log_dir / "backtest_journal.jsonl")
    journal = Journal(journal_path)
    # IV history lives alongside the journal (not hardcoded to agent_cfg.log_dir)
    # so that passing a distinct journal_path fully isolates one backtest run's
    # accumulated state from another's — required for reproducibility (same
    # seed -> same result) when running more than one backtest in a process,
    # e.g. a parameter sweep, without one run's IV history silently leaking
    # into the next and changing its iv_rank percentile calculations.
    iv_store = IVHistoryStore(journal_path.parent / f"{journal_path.stem}_iv_history.jsonl")
    strategy_params = StrategyParams()

    # Assumes all underlyings share the same trading-day calendar (true for
    # US equities); use the first as the master index.
    master_dates = dates_by_underlying[bt_cfg.universe[0]]

    cash = bt_cfg.starting_equity
    open_positions: List[OpenPosition] = []
    result = BacktestResult(starting_equity=bt_cfg.starting_equity)
    starting_equity_today = bt_cfg.starting_equity
    last_trading_day_seen = None

    for t_idx, today in enumerate(master_dates):
        if last_trading_day_seen != today.isocalendar()[1]:
            starting_equity_today = cash - sum(
                p.last_cost_to_close * 100 * p.contracts for p in open_positions
            )  # reset drawdown reference weekly (a pragmatic proxy for "start of day equity")
            last_trading_day_seen = today.isocalendar()[1]

        spots = {u: closes_by_underlying[u][t_idx] for u in bt_cfg.universe if t_idx < len(closes_by_underlying[u])}

        # ---- 1) manage open positions: decay DTE, check exit rules ----
        still_open: List[OpenPosition] = []
        for pos in open_positions:
            spot = spots.get(pos.candidate.underlying)
            if spot is None:
                still_open.append(pos)
                continue
            pos.dte_remaining = max(0.0, pos.dte_remaining - _CALENDAR_DAYS_PER_TRADING_DAY)
            sigma = max(0.05, realized_vol(closes_by_underlying[pos.candidate.underlying][: t_idx + 1], 20) or 0.25)

            cost_to_close = _cost_to_close(pos, spot, sigma)
            pos.last_cost_to_close = cost_to_close
            profit_captured = pos.entry_credit_realized - cost_to_close
            profit_target_hit = (
                pos.candidate.net_credit_per_contract > 0
                and profit_captured >= bt_cfg.profit_target_pct * pos.entry_credit_realized
            )
            stop_hit = cost_to_close >= bt_cfg.stop_loss_multiple * max(pos.entry_credit_realized, 0.01)
            expired = pos.dte_remaining <= 0

            if profit_target_hit or stop_hit or expired:
                reason = "profit_target" if profit_target_hit else ("stop_loss" if stop_hit else "expiration")
                pnl = profit_captured * 100 * pos.contracts
                # Real cash flow: pay (or receive, if negative) the cost to
                # close. The entry credit was already booked into cash when
                # the position was opened — collateral was never subtracted
                # from cash in the first place (it's a buying-power
                # reservation, tracked separately, not a cash outflow).
                cash -= cost_to_close * 100 * pos.contracts
                result.trades.append(
                    TradeLogRow(
                        underlying=pos.candidate.underlying,
                        strategy_type=pos.candidate.strategy_type.value,
                        entry_date=pos.entry_date.isoformat(),
                        exit_date=today.isoformat(),
                        contracts=pos.contracts,
                        expected_credit=pos.entry_expected_credit,
                        realized_entry_credit=pos.entry_credit_realized,
                        slippage_per_contract=round(pos.entry_credit_realized - pos.entry_expected_credit, 4),
                        exit_reason=reason,
                        pnl=round(pnl, 2),
                    )
                )
                journal.note(f"closed {pos.candidate.underlying} {pos.candidate.strategy_type.value}",
                              reason=reason, pnl=round(pnl, 2))
            else:
                still_open.append(pos)
        open_positions = still_open

        # ---- 2) scan for new entries ----
        for underlying in bt_cfg.universe:
            if any(p.candidate.underlying == underlying for p in open_positions):
                continue  # one position per underlying at a time, kept simple
            if t_idx >= len(closes_by_underlying[underlying]):
                continue
            closes_window = closes_by_underlying[underlying][: t_idx + 1]
            if len(closes_window) < 55:
                continue  # need enough history for SMA-50 / HV-20
            spot = spots[underlying]

            hv20 = realized_vol(closes_window, 20)
            if hv20 != hv20:  # NaN guard
                continue
            simulated_iv = max(0.05, hv20 * (1.08 + 0.06 * rng.gauss(0, 1)))

            vsig = vol_signal(underlying, simulated_iv, closes_window, iv_store)
            tsig = trend_signal(underlying, closes_window, spot)

            expiration_dte = rng.choice(range(bt_cfg.min_dte, bt_cfg.max_dte + 1))
            expiration_label = (today + timedelta(days=expiration_dte)).isoformat()
            chain = build_synthetic_chain(underlying, spot, simulated_iv, expiration_label, expiration_dte)

            candidates = generate_candidates(
                underlying, chain, vsig, tsig, spot, shares_held=0.0,
                min_open_interest=agent_cfg.risk.min_open_interest,
                max_spread_pct=agent_cfg.risk.max_bid_ask_spread_pct,
                params=strategy_params,
            )
            journal.scan(underlying, vsig.__dict__, tsig.__dict__, len(candidates))
            if not candidates:
                continue

            candidate = candidates[0]
            journal.candidate(candidate.to_dict())

            # Collateral is a buying-power reservation, not a cash outflow —
            # equity marks unrealized option liability (last_cost_to_close);
            # options_buying_power is cash net of reserved collateral.
            unrealized_liability = sum(p.last_cost_to_close * 100 * p.contracts for p in open_positions)
            equity_now = cash - unrealized_liability
            positions_value_by_underlying: Dict[str, float] = {}
            for p in open_positions:
                positions_value_by_underlying[p.candidate.underlying] = (
                    positions_value_by_underlying.get(p.candidate.underlying, 0.0)
                    + p.candidate.collateral_required * p.contracts
                )
            reserved_collateral = sum(positions_value_by_underlying.values())
            portfolio_delta_dollars = sum(
                _current_delta_dollars(p, spots.get(p.candidate.underlying, spot), hv20 or 0.25)
                for p in open_positions
            )
            account = AccountSnapshot(
                equity=equity_now,
                cash=cash,
                options_buying_power=max(0.0, cash - reserved_collateral),
                positions_value_by_underlying=positions_value_by_underlying,
                open_position_count=len(open_positions),
                portfolio_net_delta_dollars=portfolio_delta_dollars,
                starting_equity_today=starting_equity_today,
            )
            decision = risk_mgr.screen(candidate, account)
            journal.risk_decision(candidate.id, underlying, decision.approved,
                                    decision.sized_contracts, decision.reasons)
            if not decision.approved:
                continue

            # "Expected" here means the same thing it means in the live engine
            # (execution/execution_engine.py): the net marketable-limit price
            # we intended to get, not the raw theoretical mid — otherwise
            # backtest "slippage" would silently include the edge deliberately
            # given up for marketability, while live slippage wouldn't, and
            # the two numbers in the gap report would not be comparable.
            entry_expected_credit = expected_marketable_limit(candidate.legs, agent_cfg.execution).net_limit_price
            realized_credit = simulate_fill(candidate, agent_cfg.execution, rng)
            cash += realized_credit * 100 * decision.sized_contracts  # real cash flow: premium received

            open_positions.append(
                OpenPosition(
                    candidate=candidate,
                    contracts=decision.sized_contracts,
                    entry_credit_realized=realized_credit,
                    entry_expected_credit=entry_expected_credit,
                    entry_date=today,
                    dte_remaining=float(expiration_dte),
                    initial_dte=float(expiration_dte),
                    last_cost_to_close=candidate.net_credit_per_contract,
                )
            )
            journal.fill({
                "candidate_id": candidate.id, "underlying": underlying,
                "expected_credit": entry_expected_credit,
                "realized_credit": realized_credit, "contracts": decision.sized_contracts,
            })

        equity_today = cash - sum(p.last_cost_to_close * 100 * p.contracts for p in open_positions)
        result.equity_curve.append(round(equity_today, 2))
        result.dates.append(today.isoformat())

    result.ending_equity = result.equity_curve[-1] if result.equity_curve else bt_cfg.starting_equity
    return result
