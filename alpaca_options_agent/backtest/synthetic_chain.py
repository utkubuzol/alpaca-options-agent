"""Build a synthetic OptionQuote chain for one underlying/date using the
Black-Scholes pricer in `pricing.py`. Strike grid + a modeled bid/ask
spread that widens for further-OTM / lower open-interest contracts, so
the strategy's liquidity filters are exercised meaningfully rather than
trivially satisfied.
"""
from __future__ import annotations

from typing import List

from alpaca_options_agent.backtest.pricing import black_scholes
from alpaca_options_agent.strategy.types import OptionQuote


def build_synthetic_chain(
    underlying: str,
    spot: float,
    sigma: float,
    expiration_label: str,
    dte_days: float,
    strike_step_pct: float = 0.025,
    n_strikes_each_side: int = 10,
    base_spread_pct: float = 0.06,
) -> List[OptionQuote]:
    quotes: List[OptionQuote] = []
    step = max(0.5, round(spot * strike_step_pct, 1))

    for i in range(-n_strikes_each_side, n_strikes_each_side + 1):
        strike = round(spot + i * step, 2)
        if strike <= 0:
            continue
        moneyness = abs(strike - spot) / spot

        for option_type in ("call", "put"):
            bs = black_scholes(spot, strike, dte_days, sigma, option_type)
            mid = max(bs.price, 0.01)

            # Spread widens with distance from ATM (thinner OI further OTM).
            spread_pct = base_spread_pct * (1 + 4 * moneyness)
            half_spread = mid * spread_pct / 2
            bid = max(0.01, round(mid - half_spread, 2))
            ask = round(mid + half_spread, 2)

            open_interest = int(max(20, 2000 * (1 - min(moneyness * 3, 0.97))))

            quotes.append(
                OptionQuote(
                    symbol=f"{underlying}_{expiration_label}_{option_type[0].upper()}{strike}",
                    underlying=underlying,
                    strike=strike,
                    expiration=expiration_label,
                    option_type=option_type,
                    bid=bid,
                    ask=ask,
                    last=round(mid, 2),
                    open_interest=open_interest,
                    volume=max(1, open_interest // 10),
                    delta=bs.delta,
                    gamma=bs.gamma,
                    theta=bs.theta,
                    vega=bs.vega,
                    implied_volatility=sigma,
                )
            )
    return quotes
