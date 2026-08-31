from alpaca_options_agent.backtest.pricing import black_scholes


def test_call_put_parity_roughly():
    spot, strike, dte, sigma = 100.0, 100.0, 30, 0.25
    call = black_scholes(spot, strike, dte, sigma, "call")
    put = black_scholes(spot, strike, dte, sigma, "put")
    # put-call parity (ignoring dividends): C - P ~= S - K*e^-rT
    import math
    r, t = 0.045, dte / 365
    parity_rhs = spot - strike * math.exp(-r * t)
    assert abs((call.price - put.price) - parity_rhs) < 0.05


def test_deep_itm_call_delta_near_one():
    bs = black_scholes(150.0, 80.0, 30, 0.20, "call")
    assert bs.delta > 0.95


def test_deep_otm_put_delta_near_zero():
    bs = black_scholes(150.0, 80.0, 30, 0.20, "put")
    assert bs.delta > -0.05


def test_zero_dte_is_intrinsic():
    bs = black_scholes(105.0, 100.0, 0, 0.20, "call")
    assert abs(bs.price - 5.0) < 1e-9
    assert bs.delta == 0.0
