"""Request/response models. Responses are mostly passthrough dicts from
PostgREST / the agent, so this is thin — bodies that need validation only."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

STRATEGY_SLUGS = {"csp", "covered_call", "credit_spread", "iron_condor"}


class BrokerCredentialsIn(BaseModel):
    api_key: str = Field(min_length=8)
    secret_key: str = Field(min_length=8)
    paper: bool = True
    baseline_equity: float = 100_000.0

    @field_validator("paper")
    @classmethod
    def _paper_only(cls, v: bool) -> bool:
        if not v:
            raise ValueError("live trading is out of scope — paper only")
        return v


class StrategyParamsIn(BaseModel):
    target_delta: Optional[float] = Field(default=None, ge=0.01, le=0.6)
    min_dte: Optional[int] = Field(default=None, ge=1, le=120)
    max_dte: Optional[int] = Field(default=None, ge=1, le=180)
    profit_target_pct: Optional[float] = Field(default=None, ge=0.05, le=1.0)
    stop_loss_multiple: Optional[float] = Field(default=None, ge=1.0, le=10.0)
    iv_rank_entry_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    spread_width_pct_of_spot: Optional[float] = Field(default=None, ge=0.005, le=0.2)
    min_credit_to_width_ratio: Optional[float] = Field(default=None, ge=0.05, le=0.9)


class StrategyRiskIn(BaseModel):
    max_risk_per_trade_pct: Optional[float] = Field(default=None, ge=0.001, le=0.25)
    max_concurrent_positions: Optional[int] = Field(default=None, ge=1, le=50)
    max_daily_drawdown_pct: Optional[float] = Field(default=None, ge=0.005, le=0.5)
    min_open_interest: Optional[int] = Field(default=None, ge=0, le=100_000)
    max_bid_ask_spread_pct: Optional[float] = Field(default=None, ge=0.01, le=1.0)
    max_single_underlying_exposure_pct: Optional[float] = Field(default=None, ge=0.01, le=1.0)
    max_portfolio_delta: Optional[float] = Field(default=None, ge=0.0, le=5.0)


class StrategyIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = False
    universe: List[str] = Field(default_factory=list, max_length=40)
    strategy_types: List[str] = Field(default_factory=lambda: sorted(STRATEGY_SLUGS))
    params: StrategyParamsIn = Field(default_factory=StrategyParamsIn)
    risk: StrategyRiskIn = Field(default_factory=StrategyRiskIn)
    mode: str = "scan"
    interval_minutes: int = Field(default=15, ge=1, le=1440)

    @field_validator("universe")
    @classmethod
    def _tickers(cls, v: List[str]) -> List[str]:
        return [s.strip().upper() for s in v if s.strip()]

    @field_validator("strategy_types")
    @classmethod
    def _types(cls, v: List[str]) -> List[str]:
        bad = set(v) - STRATEGY_SLUGS
        if bad:
            raise ValueError(f"unknown strategy_types: {sorted(bad)}")
        return v or sorted(STRATEGY_SLUGS)

    @field_validator("mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in ("scan", "trade"):
            raise ValueError("mode must be 'scan' or 'trade'")
        return v

    def to_row(self) -> Dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "universe": self.universe,
            "strategy_types": self.strategy_types,
            "params": self.params.model_dump(exclude_none=True),
            "risk": self.risk.model_dump(exclude_none=True),
            "mode": self.mode,
            "interval_minutes": self.interval_minutes,
        }


class NotificationSettingsIn(BaseModel):
    telegram_chat_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None  # plaintext in; stored encrypted
    whatsapp_number: Optional[str] = None
    channels: Dict[str, bool] = Field(default_factory=lambda: {"telegram": True, "whatsapp": False})
    event_kinds: List[str] = Field(default_factory=lambda: ["fill", "error"])

    @field_validator("event_kinds")
    @classmethod
    def _kinds(cls, v: List[str]) -> List[str]:
        allowed = {"scan", "candidate", "risk_decision", "fill", "error", "note"}
        bad = set(v) - allowed
        if bad:
            raise ValueError(f"unknown event_kinds: {sorted(bad)}")
        return v
