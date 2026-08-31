"""
Historical daily-close loader for the backtest engine.

Two sources:
  - `load_from_alpaca`: real historical stock bars via alpaca-py (requires
    API keys — works with a free paper account, stock data doesn't need
    an options subscription).
  - `synthetic_gbm_closes`: a seeded geometric-Brownian-motion generator,
    used only so the backtest engine (and therefore the whole pipeline)
    can be smoke-tested with zero network access / zero API keys. This
    is clearly logged as synthetic and is not a substitute for the real
    loader — see README's "Verification" section.
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


def load_from_alpaca(
    api_key: str, secret_key: str, universe: List[str], start: date, end: date
) -> Tuple[Dict[str, List[float]], Dict[str, List[date]]]:
    client = StockHistoricalDataClient(api_key, secret_key)
    req = StockBarsRequest(
        symbol_or_symbols=universe,
        timeframe=TimeFrame.Day,
        start=datetime.combine(start, datetime.min.time()),
        end=datetime.combine(end, datetime.min.time()),
    )
    bars = client.get_stock_bars(req)

    closes: Dict[str, List[float]] = {}
    dates: Dict[str, List[date]] = {}
    for symbol in universe:
        try:
            rows = bars[symbol]
        except (KeyError, TypeError):
            rows = bars.data.get(symbol, [])
        closes[symbol] = [float(b.close) for b in rows]
        dates[symbol] = [b.timestamp.date() for b in rows]
    return closes, dates


def synthetic_gbm_closes(
    universe: List[str], start: date, end: date, seed: int = 42, annual_vol: float = 0.22
) -> Tuple[Dict[str, List[float]], Dict[str, List[date]]]:
    rng = random.Random(seed)
    trading_dates: List[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri, ignores holidays (fine for a smoke test)
            trading_dates.append(d)
        d += timedelta(days=1)

    dt = 1 / 252
    closes: Dict[str, List[float]] = {}
    dates: Dict[str, List[date]] = {}
    for i, symbol in enumerate(universe):
        s0 = 100.0 + 40 * i
        vol = annual_vol * (1 + 0.15 * math.sin(i))
        path = [s0]
        for _ in trading_dates[1:]:
            shock = rng.gauss(0, 1)
            drift = (0.06 - 0.5 * vol**2) * dt
            path.append(max(1.0, path[-1] * math.exp(drift + vol * math.sqrt(dt) * shock)))
        closes[symbol] = path
        dates[symbol] = list(trading_dates)
    return closes, dates
