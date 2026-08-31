import random

from alpaca_options_agent.config import ExecutionConfig
from alpaca_options_agent.execution.cost_model import (
    expected_marketable_limit,
    net_mid_price,
    simulate_fill,
    slippage_stats,
)
from alpaca_options_agent.strategy.types import Leg, LegAction, OptionQuote


def _quote(strike, bid, ask, delta=-0.2, oi=500):
    return OptionQuote(
        symbol=f"TEST_{strike}", underlying="TEST", strike=strike, expiration="2026-12-18",
        option_type="put", bid=bid, ask=ask, last=(bid + ask) / 2, open_interest=oi, volume=10,
        delta=delta, gamma=0.01, theta=-0.02, vega=0.05, implied_volatility=0.3,
    )


def test_net_mid_price_single_short_leg():
    leg = Leg(quote=_quote(100, 1.90, 2.10), action=LegAction.SELL_TO_OPEN)
    assert net_mid_price([leg]) == 2.00


def test_expected_marketable_limit_gives_up_edge_on_credit():
    leg = Leg(quote=_quote(100, 1.90, 2.10), action=LegAction.SELL_TO_OPEN)
    cfg = ExecutionConfig()
    exp = expected_marketable_limit([leg], cfg)
    assert exp.net_mid == 2.00
    assert exp.net_limit_price < exp.net_mid  # selling: priced below mid to be marketable
    assert exp.edge_given_up > 0


def test_wider_spread_and_thin_oi_cost_more_edge():
    tight = Leg(quote=_quote(100, 1.95, 2.05, oi=1000), action=LegAction.SELL_TO_OPEN)
    wide = Leg(quote=_quote(100, 1.50, 2.50, oi=20), action=LegAction.SELL_TO_OPEN)
    cfg = ExecutionConfig()
    exp_tight = expected_marketable_limit([tight], cfg)
    exp_wide = expected_marketable_limit([wide], cfg)
    assert exp_wide.edge_given_up > exp_tight.edge_given_up


def test_simulate_fill_never_beats_mid_on_credit():
    leg = Leg(quote=_quote(100, 1.90, 2.10), action=LegAction.SELL_TO_OPEN)
    from alpaca_options_agent.strategy.types import TradeCandidate, StrategyType
    candidate = TradeCandidate(underlying="TEST", strategy_type=StrategyType.CASH_SECURED_PUT, legs=[leg])
    cfg = ExecutionConfig()
    rng = random.Random(1)
    for _ in range(200):
        realized = simulate_fill(candidate, cfg, rng)
        assert realized <= 2.00 + 1e-9


def test_slippage_stats_sign():
    slip, bps = slippage_stats(expected_credit=2.00, realized_credit=1.90)
    assert slip < 0
    assert bps < 0
