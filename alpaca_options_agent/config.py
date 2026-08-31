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
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


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

    def __post_init__(self):
        self.log_dir.mkdir(parents=True, exist_ok=True)

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
