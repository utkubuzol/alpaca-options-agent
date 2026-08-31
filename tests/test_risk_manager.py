from alpaca_options_agent.config import RiskConfig
from alpaca_options_agent.risk.risk_manager import AccountSnapshot, RiskManager
from alpaca_options_agent.strategy.types import StrategyType, TradeCandidate


def _csp_candidate(strike=90.0, credit=1.50, underlying_price=100.0):
    return TradeCandidate(
        underlying="T", underlying_price=underlying_price, strategy_type=StrategyType.CASH_SECURED_PUT,
        legs=[], contracts=1, net_credit_per_contract=credit,
        max_loss_per_contract=strike * 100 - credit * 100,
        collateral_required=strike * 100, net_delta=-0.20,
    )


def test_daily_drawdown_circuit_breaker_blocks_everything():
    cfg = RiskConfig(max_daily_drawdown_pct=0.03)
    mgr = RiskManager(cfg)
    account = AccountSnapshot(equity=94_000, cash=94_000, options_buying_power=94_000,
                                starting_equity_today=100_000)
    decision = mgr.screen(_csp_candidate(), account)
    assert not decision.approved
    assert "drawdown" in decision.reasons[0]


def test_insufficient_buying_power_blocks_trade():
    cfg = RiskConfig()
    mgr = RiskManager(cfg)
    account = AccountSnapshot(equity=5_000, cash=5_000, options_buying_power=1_000)
    decision = mgr.screen(_csp_candidate(strike=90, credit=1.5), account)  # needs $9,000 collateral
    assert not decision.approved
    assert decision.sized_contracts == 0


def test_healthy_account_approves_and_sizes_at_least_one():
    cfg = RiskConfig(max_risk_per_trade_pct=0.05)
    mgr = RiskManager(cfg)
    account = AccountSnapshot(equity=100_000, cash=100_000, options_buying_power=100_000)
    decision = mgr.screen(_csp_candidate(strike=90, credit=1.5), account)
    assert decision.approved
    assert decision.sized_contracts >= 1


def test_max_concurrent_positions_blocks():
    cfg = RiskConfig(max_concurrent_positions=2)
    mgr = RiskManager(cfg)
    account = AccountSnapshot(equity=100_000, cash=100_000, options_buying_power=100_000,
                                open_position_count=2)
    decision = mgr.screen(_csp_candidate(), account)
    assert not decision.approved


def test_concentration_cap_limits_size():
    cfg = RiskConfig(max_single_underlying_exposure_pct=0.05)  # tight cap: $5,000 on $100k equity
    mgr = RiskManager(cfg)
    account = AccountSnapshot(equity=100_000, cash=100_000, options_buying_power=100_000)
    decision = mgr.screen(_csp_candidate(strike=90, credit=1.5), account)  # $9,000 collateral/contract
    assert decision.sized_contracts == 0
