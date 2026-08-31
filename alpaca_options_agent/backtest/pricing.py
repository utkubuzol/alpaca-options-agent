"""
Black-Scholes-Merton pricer used only by the backtest engine.

Why a parametric pricer instead of "real" historical option chains: Alpaca's
historical options data requires knowing specific contract symbols that
existed on a specific past date, and reconstructing that chain-by-chain for
a multi-month backtest needs a paid historical OPRA dataset that a paper
account doesn't include. Rather than quietly skip backtesting or fake
"historical chain" data from today's quotes, this engine is explicit about
using a model: synthetic contracts are priced with Black-Scholes off of
each day's trailing realized volatility, get a simulated bid/ask spread,
and are run through the *exact same* strategy/execution/risk code the live
agent uses.

This is also the second half of the sim-to-real story the monitoring
report tells: model-priced backtest fills vs OPRA-quoted paper fills are
two different price sources by construction, and the report says so
explicitly rather than implying the backtest is a reconstruction of
history.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

_SQRT_2PI = math.sqrt(2 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


@dataclass
class BSResult:
    price: float
    delta: float
    gamma: float
    theta: float  # per calendar day
    vega: float  # per 1 vol point (0.01)


def black_scholes(
    spot: float, strike: float, dte_days: float, sigma: float, option_type: str, r: float = 0.045
) -> BSResult:
    """dte_days: calendar days to expiration (>= 0). At/after expiration,
    returns intrinsic value with zero greeks.
    """
    if dte_days <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
        intrinsic = max(0.0, spot - strike) if option_type == "call" else max(0.0, strike - spot)
        return BSResult(price=intrinsic, delta=0.0, gamma=0.0, theta=0.0, vega=0.0)

    t = dte_days / 365.0
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)

    if option_type == "call":
        price = spot * _norm_cdf(d1) - strike * math.exp(-r * t) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        theta_annual = (
            -(spot * _norm_pdf(d1) * sigma) / (2 * math.sqrt(t))
            - r * strike * math.exp(-r * t) * _norm_cdf(d2)
        )
    else:
        price = strike * math.exp(-r * t) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1
        theta_annual = (
            -(spot * _norm_pdf(d1) * sigma) / (2 * math.sqrt(t))
            + r * strike * math.exp(-r * t) * _norm_cdf(-d2)
        )

    gamma = _norm_pdf(d1) / (spot * sigma * math.sqrt(t))
    vega = spot * _norm_pdf(d1) * math.sqrt(t) * 0.01

    return BSResult(
        price=max(price, 0.0),
        delta=delta,
        gamma=gamma,
        theta=theta_annual / 365.0,
        vega=vega,
    )
