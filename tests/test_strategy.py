from alpaca_options_agent.strategy.premium_selling import StrategyParams, generate_candidates
from alpaca_options_agent.strategy.signals import TrendSignal, VolSignal
from alpaca_options_agent.strategy.types import OptionQuote


def _make_chain(spot=100.0, sigma=0.30):
    """A small synthetic chain with a clean, liquid 20-delta put and call
    so strike-selection logic is deterministic and easy to assert on."""
    quotes = []
    for strike, delta, opt_type in [
        (90, -0.20, "put"), (85, -0.10, "put"), (95, -0.35, "put"),
        (110, 0.20, "call"), (115, 0.10, "call"), (105, 0.35, "call"),
    ]:
        mid = max(0.30, abs(delta) * 12)
        quotes.append(OptionQuote(
            symbol=f"T_{strike}{opt_type[0]}", underlying="T", strike=strike, expiration="2026-12-18",
            option_type=opt_type, bid=round(mid - 0.05, 2), ask=round(mid + 0.05, 2), last=mid,
            open_interest=500, volume=50, delta=delta, gamma=0.02, theta=-0.03, vega=0.08,
            implied_volatility=sigma,
        ))
    return quotes


def test_no_candidates_when_iv_rank_low():
    chain = _make_chain()
    vsig = VolSignal(underlying="T", atm_iv=0.30, realized_vol_20d=0.28, iv_hv_ratio=1.07,
                      iv_rank=0.20, iv_rank_is_proxy=True, iv_rank_sample_size=5)
    tsig = TrendSignal(underlying="T", spot=100, sma_20=99, sma_50=98, momentum_20d=0.01, regime="neutral")
    out = generate_candidates("T", chain, vsig, tsig, spot=100.0, shares_held=0,
                                min_open_interest=50, max_spread_pct=0.5)
    assert out == []


def test_csp_generated_in_bullish_regime_with_rich_iv():
    chain = _make_chain()
    vsig = VolSignal(underlying="T", atm_iv=0.40, realized_vol_20d=0.25, iv_hv_ratio=1.6,
                      iv_rank=0.85, iv_rank_is_proxy=True, iv_rank_sample_size=5)
    tsig = TrendSignal(underlying="T", spot=100, sma_20=98, sma_50=95, momentum_20d=0.03, regime="bullish")
    out = generate_candidates("T", chain, vsig, tsig, spot=100.0, shares_held=0,
                                min_open_interest=50, max_spread_pct=0.5)
    assert len(out) >= 1
    csp = out[0]
    assert csp.strategy_type.value == "cash_secured_put"
    assert csp.legs[0].quote.strike == 90  # closest to the 0.20-delta target
    assert csp.net_credit_per_contract > 0
    assert 0 <= csp.signal_score <= 1


def test_call_credit_spread_in_bearish_regime():
    chain = _make_chain()
    vsig = VolSignal(underlying="T", atm_iv=0.40, realized_vol_20d=0.25, iv_hv_ratio=1.6,
                      iv_rank=0.85, iv_rank_is_proxy=True, iv_rank_sample_size=5)
    tsig = TrendSignal(underlying="T", spot=100, sma_20=102, sma_50=105, momentum_20d=-0.03, regime="bearish")
    out = generate_candidates("T", chain, vsig, tsig, spot=100.0, shares_held=0,
                                min_open_interest=50, max_spread_pct=0.5)
    types = [c.strategy_type.value for c in out]
    assert "call_credit_spread" in types
    spread = next(c for c in out if c.strategy_type.value == "call_credit_spread")
    assert len(spread.legs) == 2
    assert spread.max_loss_per_contract > 0
    assert spread.net_credit_per_contract > 0


def test_liquidity_filter_excludes_wide_spreads():
    chain = _make_chain()
    # Blow out the spread on the 20-delta put so it should be skipped.
    for q in chain:
        if q.strike == 90:
            q.bid, q.ask = 0.10, 5.00
    vsig = VolSignal(underlying="T", atm_iv=0.40, realized_vol_20d=0.25, iv_hv_ratio=1.6,
                      iv_rank=0.85, iv_rank_is_proxy=True, iv_rank_sample_size=5)
    tsig = TrendSignal(underlying="T", spot=100, sma_20=98, sma_50=95, momentum_20d=0.03, regime="bullish")
    out = generate_candidates("T", chain, vsig, tsig, spot=100.0, shares_held=0,
                                min_open_interest=50, max_spread_pct=0.20)
    if out and out[0].strategy_type.value == "cash_secured_put":
        assert out[0].legs[0].quote.strike != 90


def _rich_neutral():
    vsig = VolSignal(underlying="T", atm_iv=0.40, realized_vol_20d=0.25, iv_hv_ratio=1.6,
                     iv_rank=0.85, iv_rank_is_proxy=True, iv_rank_sample_size=5)
    tsig = TrendSignal(underlying="T", spot=100, sma_20=100, sma_50=100, momentum_20d=0.0,
                       regime="neutral")
    return vsig, tsig


def test_put_credit_spread_in_bullish_regime():
    chain = _make_chain()
    vsig = VolSignal(underlying="T", atm_iv=0.40, realized_vol_20d=0.25, iv_hv_ratio=1.6,
                     iv_rank=0.85, iv_rank_is_proxy=True, iv_rank_sample_size=5)
    tsig = TrendSignal(underlying="T", spot=100, sma_20=98, sma_50=95, momentum_20d=0.03,
                       regime="bullish")
    out = generate_candidates("T", chain, vsig, tsig, spot=100.0, shares_held=0,
                              min_open_interest=50, max_spread_pct=0.5,
                              allowed_slugs={"credit_spread"})
    assert len(out) == 1
    assert out[0].strategy_type.value == "put_credit_spread"
    assert len(out[0].legs) == 2
    assert out[0].max_loss_per_contract > 0


def test_iron_condor_in_neutral_regime():
    chain = _make_chain()
    vsig, tsig = _rich_neutral()
    out = generate_candidates("T", chain, vsig, tsig, spot=100.0, shares_held=0,
                              min_open_interest=50, max_spread_pct=0.5,
                              allowed_slugs={"iron_condor"})
    assert len(out) == 1
    ic = out[0]
    assert ic.strategy_type.value == "iron_condor"
    assert len(ic.legs) == 4
    assert ic.net_credit_per_contract > 0
    assert ic.max_loss_per_contract > 0
    assert ic.collateral_required == ic.max_loss_per_contract


def test_allowed_slugs_filters_before_ranking():
    # In neutral both a CSP and defined-risk spreads generate; restricting to
    # credit_spread must still yield a spread (not an empty list).
    chain = _make_chain()
    vsig, tsig = _rich_neutral()
    out = generate_candidates("T", chain, vsig, tsig, spot=100.0, shares_held=0,
                              min_open_interest=50, max_spread_pct=0.5,
                              allowed_slugs={"credit_spread"})
    assert out and out[0].strategy_type.value.endswith("credit_spread")
