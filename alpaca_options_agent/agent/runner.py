"""
The autonomous agent's live cycle: one full scan-decide-risk-execute pass
over the configured universe, against Alpaca's paper environment.

Meant to be invoked repeatedly (by `agent/cli.py`, cron, or CI) rather than
run as a long-lived process with its own internal scheduler — that's the
"long-running agent sessions, cron jobs and CI" pattern the Alpaca CLI
(and this design) are built around. Each call is idempotent-ish: it looks
at current live positions before deciding whether to add anything, so
running it every N minutes during market hours is the intended usage
(see scripts/run_paper_agent.sh).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from alpaca_options_agent.broker.cli_bridge import AlpacaCli, AlpacaCliUnavailable
from alpaca_options_agent.broker.client import AlpacaBroker
from alpaca_options_agent.config import AgentConfig
from alpaca_options_agent.execution.cost_model import expected_marketable_limit
from alpaca_options_agent.execution.execution_engine import ExecutionEngine
from alpaca_options_agent.monitoring.journal import Journal
from alpaca_options_agent.risk.risk_manager import AccountSnapshot, RiskManager
from alpaca_options_agent.strategy.premium_selling import StrategyParams, generate_candidates
from alpaca_options_agent.strategy.signals import IVHistoryStore, trend_signal, vol_signal
from alpaca_options_agent.strategy.types import Leg, LegAction, TradeCandidate

logger = logging.getLogger("agent.runner")


def _account_snapshot(broker: AlpacaBroker, positions: List[Dict]) -> AccountSnapshot:
    acct = broker.get_account()
    exposure: Dict[str, float] = {}
    for p in positions:
        exposure[p["symbol"][:6]] = exposure.get(p["symbol"][:6], 0.0) + abs(p["market_value"])
    return AccountSnapshot(
        equity=acct["equity"],
        cash=acct["cash"],
        options_buying_power=acct["options_buying_power"],
        positions_value_by_underlying=exposure,
        open_position_count=len(positions),
        portfolio_net_delta_dollars=0.0,  # live delta aggregation needs per-position greeks lookup;
        # left conservative (0) rather than silently wrong — see README limitations.
        starting_equity_today=acct["last_equity"],
    )


def cli_cross_check(journal: Journal) -> Optional[Dict]:
    """Best-effort: pull account state via the Alpaca CLI (not the SDK) and
    log it. If the CLI isn't installed this is skipped, not fatal — see
    broker/cli_bridge.py docstring.
    """
    cli = AlpacaCli()
    try:
        acct = cli.account_get()
        journal.note("cli_cross_check", account_equity_via_cli=acct.get("equity"))
        return acct
    except AlpacaCliUnavailable as e:
        journal.note("cli_cross_check_skipped", reason=str(e))
        return None


def manage_open_positions(broker: AlpacaBroker, journal: Journal, cfg: AgentConfig,
                            dry_run: bool = False) -> List[Dict]:
    """Live-side counterpart to the backtest engine's exit logic
    (backtest/engine.py: profit-target / stop-loss / expiration). Currently
    covers single-leg short option positions (the short leg of a CSP or a
    covered call) — closing an already-open multi-leg spread as a unit
    would need to reconstruct which two raw option positions belong to the
    same original candidate, which Alpaca's position list doesn't label;
    that's a documented next step, not silently skipped (see README).
    """
    results: List[Dict] = []
    for p in broker.get_positions():
        if not p["asset_class"].lower().startswith("us_option") or p["qty"] >= 0:
            continue  # only managing short single-leg positions for now

        symbol = p["symbol"]
        entry_credit = p["avg_entry_price"]  # premium received per share when opened
        if entry_credit <= 0:
            continue

        quote = broker.get_single_option_quote(symbol)
        if quote is None:
            journal.note(f"manage_skip {symbol}", reason="no current quote available")
            continue

        cost_to_close_est = quote.ask  # what buying it back right now would cost
        profit_captured_pct = (entry_credit - cost_to_close_est) / entry_credit
        profit_hit = profit_captured_pct >= cfg.management.profit_target_pct
        stop_hit = cost_to_close_est >= cfg.management.stop_loss_multiple * entry_credit

        row = {
            "symbol": symbol, "qty": p["qty"], "entry_credit": entry_credit,
            "cost_to_close_est": cost_to_close_est,
            "profit_captured_pct": round(profit_captured_pct, 3),
        }

        if not (profit_hit or stop_hit):
            row["action"] = "hold"
            results.append(row)
            continue

        reason = "profit_target" if profit_hit else "stop_loss"
        row["reason"] = reason
        if dry_run:
            row["action"] = "would_close"
            results.append(row)
            continue

        leg = Leg(quote=quote, action=LegAction.BUY_TO_CLOSE, ratio_qty=1)
        exp = expected_marketable_limit([leg], cfg.execution)
        try:
            order_id = broker.submit_single_leg_limit(leg, contracts=abs(int(p["qty"])),
                                                         limit_price=abs(exp.net_limit_price))
            row["action"] = "close_submitted"
            row["order_id"] = order_id
            journal.note(f"closing {symbol}", reason=reason, entry_credit=entry_credit,
                         cost_to_close_est=cost_to_close_est, order_id=order_id)
        except Exception as e:  # noqa: BLE001 — one position's close failure shouldn't kill the cycle
            row["action"] = "close_failed"
            row["error"] = str(e)
            journal.error(symbol, f"close order failed: {e}")
        results.append(row)
    return results


def run_cycle(cfg: AgentConfig, dry_run: bool = False) -> List[Dict]:
    """Runs one full pass. Returns a list of per-underlying result dicts
    (for CLI JSON output). dry_run=True screens and sizes candidates but
    never submits an order — used by `agent scan` / `agent decide`.
    """
    cfg.validate_credentials()
    broker = AlpacaBroker()
    journal = Journal(cfg.log_dir / "agent_journal.jsonl")
    risk_mgr = RiskManager(cfg.risk)
    exec_engine = ExecutionEngine(broker, cfg.execution)
    iv_store = IVHistoryStore(cfg.log_dir / "iv_history.jsonl")
    params = StrategyParams()

    cli_cross_check(journal)

    management_results = manage_open_positions(broker, journal, cfg, dry_run=dry_run)

    positions = broker.get_positions()
    account = _account_snapshot(broker, positions)
    held_shares_by_underlying = {
        p["symbol"]: p["qty"] for p in positions if p["asset_class"].lower().startswith("us_equity")
    }

    results: List[Dict] = [{"underlying": "__position_management__", "closes": management_results}]
    for underlying in cfg.universe:
        row: Dict = {"underlying": underlying}
        try:
            spot = broker.get_underlying_price(underlying)
            closes = broker.get_historical_closes(underlying, lookback_days=60)
            chain = broker.get_option_chain(underlying, min_dte=25, max_dte=45)

            if len(closes) < 55 or not chain:
                row["status"] = "skipped_insufficient_data"
                journal.note(f"skip {underlying}", reason="insufficient closes or empty chain")
                results.append(row)
                continue

            atm = min(chain, key=lambda q: abs(q.strike - spot))
            vsig = vol_signal(underlying, atm.implied_volatility, closes, iv_store)
            tsig = trend_signal(underlying, closes, spot)
            journal.scan(underlying, vsig.__dict__, tsig.__dict__, 0)

            candidates: List[TradeCandidate] = generate_candidates(
                underlying, chain, vsig, tsig, spot,
                shares_held=held_shares_by_underlying.get(underlying, 0.0),
                min_open_interest=cfg.risk.min_open_interest,
                max_spread_pct=cfg.risk.max_bid_ask_spread_pct,
                params=params,
            )
            row["n_candidates"] = len(candidates)
            if not candidates:
                row["status"] = "no_candidate"
                results.append(row)
                continue

            candidate = candidates[0]
            journal.candidate(candidate.to_dict())
            row["candidate"] = candidate.to_dict()

            decision = risk_mgr.screen(candidate, account)
            journal.risk_decision(candidate.id, underlying, decision.approved,
                                    decision.sized_contracts, decision.reasons)
            row["risk_decision"] = {
                "approved": decision.approved,
                "sized_contracts": decision.sized_contracts,
                "reasons": decision.reasons,
            }

            if not decision.approved:
                row["status"] = "blocked_by_risk"
                results.append(row)
                continue

            candidate.contracts = decision.sized_contracts
            if dry_run:
                row["status"] = "dry_run_approved"
                results.append(row)
                continue

            fill = exec_engine.execute(candidate)
            journal.fill(fill.__dict__)
            row["status"] = "filled" if fill.filled else "not_filled"
            row["fill"] = fill.__dict__
            results.append(row)

        except Exception as e:  # noqa: BLE001 — one underlying's failure shouldn't kill the cycle
            logger.exception("cycle failed for %s", underlying)
            journal.error(underlying, str(e))
            row["status"] = "error"
            row["error"] = str(e)
            results.append(row)

    return results
