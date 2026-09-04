"""
Central configuration, loaded from environment variables / .env.

Every tunable that affects risk or execution lives here so the same
config object drives backtest, paper, and (eventually) live trading —
this is one of the load-bearing pieces of closing the sim-to-real gap:
if backtest and live read different config paths, the comparison
between them is meaningless.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

from alpaca_options_agent.strategy.premium_selling import StrategyParams
from alpaca_options_agent.strategy.types import STRATEGY_TYPE_SLUGS  # re-exported

load_dotenv()

# Dashboard/DB strategy-family slugs. STRATEGY_TYPE_SLUGS (StrategyType -> slug)
# is defined in strategy/types.py and re-exported here for existing importers.
ALL_STRATEGY_SLUGS = ["csp", "covered_call", "credit_spread", "iron_condor"]


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val not in (None, "") else default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str, default: List[str]) -> List[str]:
    val = os.getenv(name)
    if not val:
        return default
    return [s.strip().upper() for s in val.split(",") if s.strip()]


def _env_list_lower(name: str, default: List[str]) -> List[str]:
    val = os.getenv(name)
    if not val:
        return default
    return [s.strip().lower() for s in val.split(",") if s.strip()]


def _strategy_params_from_env() -> StrategyParams:
    """Env-tunable defaults for the strategy decision function. Same
    fallback discipline as the risk/execution configs so the dashboard,
    the CLI, and the backtest all read one place."""
    sp = StrategyParams()
    return replace(
        sp,
        iv_rank_entry_threshold=_env_float("STRAT_IV_RANK_ENTRY_THRESHOLD", sp.iv_rank_entry_threshold),
        short_delta_target=_env_float("STRAT_SHORT_DELTA_TARGET", sp.short_delta_target),
        short_delta_tolerance=_env_float("STRAT_SHORT_DELTA_TOLERANCE", sp.short_delta_tolerance),
        spread_width_pct_of_spot=_env_float("STRAT_SPREAD_WIDTH_PCT_OF_SPOT", sp.spread_width_pct_of_spot),
        min_credit_to_width_ratio=_env_float("STRAT_MIN_CREDIT_TO_WIDTH_RATIO", sp.min_credit_to_width_ratio),
    )


@dataclass(frozen=True)
class RiskConfig:
    max_risk_per_trade_pct: float = _env_float("RISK_MAX_RISK_PER_TRADE_PCT", 0.02)
    max_portfolio_delta: float = _env_float("RISK_MAX_PORTFOLIO_DELTA", 0.30)
    max_concurrent_positions: int = _env_int("RISK_MAX_CONCURRENT_POSITIONS", 6)
    max_daily_drawdown_pct: float = _env_float("RISK_MAX_DAILY_DRAWDOWN_PCT", 0.03)
    min_open_interest: int = _env_int("RISK_MIN_OPEN_INTEREST", 50)
    max_bid_ask_spread_pct: float = _env_float("RISK_MAX_BID_ASK_SPREAD_PCT", 0.15)
    # Options-specific: cap the short-put notional so assignment never exceeds
    # available cash-secured buying power.
    max_single_underlying_exposure_pct: float = _env_float(
        "RISK_MAX_SINGLE_UNDERLYING_EXPOSURE_PCT", 0.25
    )


@dataclass(frozen=True)
class ExecutionConfig:
    limit_price_improvement_ticks: int = _env_int(
        "EXEC_LIMIT_PRICE_IMPROVEMENT_TICKS", 1
    )
    max_slippage_bps: float = _env_float("EXEC_MAX_SLIPPAGE_BPS", 50)
    order_timeout_seconds: int = _env_int("EXEC_ORDER_TIMEOUT_SECONDS", 45)
    # Options tick size below $3.00 is usually $0.05, at/above $3.00 is $0.10.
    tick_size_low: float = 0.05
    tick_size_high: float = 0.10
    tick_price_breakpoint: float = 3.00


@dataclass(frozen=True)
class ManagementConfig:
    """Open-position management rules — kept numerically in sync with
    `backtest.engine.BacktestConfig`'s defaults (profit_target_pct=0.50,
    stop_loss_multiple=2.0) on purpose: this is the live-side half of the
    same exit logic the backtest already runs, so a live cycle manages
    existing short option positions the same way the backtest would have.
    """
    profit_target_pct: float = _env_float("MGMT_PROFIT_TARGET_PCT", 0.50)
    stop_loss_multiple: float = _env_float("MGMT_STOP_LOSS_MULTIPLE", 2.0)


@dataclass(frozen=True)
class AgentConfig:
    api_key: str = os.getenv("ALPACA_API_KEY", "")
    secret_key: str = os.getenv("ALPACA_SECRET_KEY", "")
    paper: bool = _env_bool("ALPACA_PAPER_TRADE", True)
    universe: List[str] = field(
        default_factory=lambda: _env_list(
            "AGENT_UNIVERSE", ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "TSLA"]
        )
    )
    log_dir: Path = field(default_factory=lambda: Path(os.getenv("AGENT_LOG_DIR", "./logs")))
    cli_path: str = os.getenv("ALPACA_CLI_PATH", "alpaca")
    # Equity the paper account started at — used only for total-return / PnL
    # reporting (`agent pnl`), never for risk sizing (that reads live equity).
    baseline_equity: float = _env_float("AGENT_BASELINE_EQUITY", 100_000.0)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    management: ManagementConfig = field(default_factory=ManagementConfig)
    # Option-chain DTE window the live cycle pulls candidates from.
    chain_min_dte: int = _env_int("AGENT_CHAIN_MIN_DTE", 25)
    chain_max_dte: int = _env_int("AGENT_CHAIN_MAX_DTE", 45)
    # Which strategy families the cycle is allowed to open (dashboard slugs:
    # "csp", "covered_call", "credit_spread"). Filtered post-generation.
    enabled_strategy_types: List[str] = field(
        default_factory=lambda: _env_list_lower("AGENT_STRATEGY_TYPES", list(ALL_STRATEGY_SLUGS))
    )
    strategy_params: StrategyParams = field(default_factory=_strategy_params_from_env)

    def __post_init__(self):
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_strategy(cls, strategy: Dict, creds: Dict) -> "AgentConfig":
        """Build a run config from a SaaS `strategies` row + decrypted broker
        creds, falling back to the env-driven defaults (the module-level
        ``CONFIG``) for every field the row leaves unset.

        This is the multi-tenant construction path: the CLI keeps using the
        env singleton untouched, while the API/worker builds one of these per
        user per cycle so backtest / paper / live still read one config shape.

        ``strategy`` keys (all optional): ``universe`` (list[str]),
        ``strategy_types`` (list of dashboard slugs), ``params`` (dict:
        target_delta, min_dte, max_dte, profit_target_pct, stop_loss_multiple,
        iv_rank_entry_threshold, short_delta_tolerance, spread_width_pct_of_spot,
        min_credit_to_width_ratio), ``risk`` (dict mirroring RiskConfig fields),
        ``log_dir`` (str).
        ``creds`` keys: ``api_key``, ``secret_key`` (required), ``paper``
        (default True), ``baseline_equity`` (default env).
        """
        base = CONFIG
        params: Dict = strategy.get("params") or {}
        risk: Dict = strategy.get("risk") or {}

        def _pick(d: Dict, key: str, fallback):
            val = d.get(key)
            return fallback if val is None else val

        risk_cfg = replace(
            base.risk,
            max_risk_per_trade_pct=float(_pick(risk, "max_risk_per_trade_pct", base.risk.max_risk_per_trade_pct)),
            max_portfolio_delta=float(_pick(risk, "max_portfolio_delta", base.risk.max_portfolio_delta)),
            max_concurrent_positions=int(_pick(risk, "max_concurrent_positions", base.risk.max_concurrent_positions)),
            max_daily_drawdown_pct=float(_pick(risk, "max_daily_drawdown_pct", base.risk.max_daily_drawdown_pct)),
            min_open_interest=int(_pick(risk, "min_open_interest", base.risk.min_open_interest)),
            max_bid_ask_spread_pct=float(_pick(risk, "max_bid_ask_spread_pct", base.risk.max_bid_ask_spread_pct)),
            max_single_underlying_exposure_pct=float(
                _pick(risk, "max_single_underlying_exposure_pct", base.risk.max_single_underlying_exposure_pct)
            ),
        )

        mgmt_cfg = replace(
            base.management,
            profit_target_pct=float(_pick(params, "profit_target_pct", base.management.profit_target_pct)),
            stop_loss_multiple=float(_pick(params, "stop_loss_multiple", base.management.stop_loss_multiple)),
        )

        sp = replace(
            base.strategy_params,
            iv_rank_entry_threshold=float(
                _pick(params, "iv_rank_entry_threshold", base.strategy_params.iv_rank_entry_threshold)
            ),
            short_delta_target=float(_pick(params, "target_delta", base.strategy_params.short_delta_target)),
            short_delta_tolerance=float(
                _pick(params, "short_delta_tolerance", base.strategy_params.short_delta_tolerance)
            ),
            spread_width_pct_of_spot=float(
                _pick(params, "spread_width_pct_of_spot", base.strategy_params.spread_width_pct_of_spot)
            ),
            min_credit_to_width_ratio=float(
                _pick(params, "min_credit_to_width_ratio", base.strategy_params.min_credit_to_width_ratio)
            ),
        )

        universe = [
            s.strip().upper()
            for s in (strategy.get("universe") or base.universe)
            if str(s).strip()
        ]
        types = [
            s.strip().lower()
            for s in (strategy.get("strategy_types") or base.enabled_strategy_types)
            if str(s).strip()
        ]

        if not creds.get("api_key") or not creds.get("secret_key"):
            raise RuntimeError("from_strategy requires creds['api_key'] and creds['secret_key']")

        return cls(
            api_key=creds["api_key"],
            secret_key=creds["secret_key"],
            paper=bool(creds.get("paper", True)),
            universe=universe or list(base.universe),
            log_dir=Path(strategy.get("log_dir") or base.log_dir),
            cli_path=base.cli_path,
            baseline_equity=float(creds.get("baseline_equity", base.baseline_equity)),
            risk=risk_cfg,
            execution=base.execution,
            management=mgmt_cfg,
            chain_min_dte=int(_pick(params, "min_dte", base.chain_min_dte)),
            chain_max_dte=int(_pick(params, "max_dte", base.chain_max_dte)),
            enabled_strategy_types=types or list(ALL_STRATEGY_SLUGS),
            strategy_params=sp,
        )

    def validate_credentials(self) -> None:
        if not self.api_key or not self.secret_key:
            raise RuntimeError(
                "ALPACA_API_KEY / ALPACA_SECRET_KEY are not set. Copy .env.example to "
                ".env and fill in your PAPER trading keys from "
                "https://app.alpaca.markets/paper/dashboard/overview"
            )
        if not self.paper:
            raise RuntimeError(
                "ALPACA_PAPER_TRADE is not true. This agent is built and validated "
                "for the paper environment only — flip it deliberately, not by default."
            )


CONFIG = AgentConfig()
