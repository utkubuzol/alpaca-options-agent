"""
Thin, typed wrapper around alpaca-py's TradingClient + market-data clients.

This is the *only* module that talks to the Alpaca Trading API directly.
Everything else (strategy, execution, risk, backtest) works with the
normalized dataclasses in `strategy.types`, never with alpaca-py's wire
models — that boundary is what lets the backtest engine reuse the exact
same downstream code as the live agent.

Verified against alpaca-py==0.44.0 source (trading/requests.py,
trading/enums.py, data/requests.py, data/historical/option.py).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import (
    OptionChainRequest,
    OptionLatestQuoteRequest,
    OptionSnapshotRequest,
    StockBarsRequest,
    StockLatestQuoteRequest,
)
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (
    ContractType,
    OrderClass,
    OrderSide,
    PositionIntent,
    QueryOrderStatus,
    TimeInForce,
)
from alpaca.trading.requests import (
    GetOptionContractsRequest,
    GetOrdersRequest,
    LimitOrderRequest,
    OptionLegRequest,
)

from alpaca_options_agent.config import CONFIG
from alpaca_options_agent.strategy.types import Leg, LegAction, OptionQuote

logger = logging.getLogger("agent.broker")

_ACTION_TO_SIDE_INTENT = {
    LegAction.SELL_TO_OPEN: (OrderSide.SELL, PositionIntent.SELL_TO_OPEN),
    LegAction.BUY_TO_OPEN: (OrderSide.BUY, PositionIntent.BUY_TO_OPEN),
    LegAction.SELL_TO_CLOSE: (OrderSide.SELL, PositionIntent.SELL_TO_CLOSE),
    LegAction.BUY_TO_CLOSE: (OrderSide.BUY, PositionIntent.BUY_TO_CLOSE),
}


class AlpacaBroker:
    """Everything the agent needs from Alpaca, normalized to our own types."""

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None,
                 paper: Optional[bool] = None):
        api_key = api_key or CONFIG.api_key
        secret_key = secret_key or CONFIG.secret_key
        paper = CONFIG.paper if paper is None else paper

        self.trading = TradingClient(api_key, secret_key, paper=paper)
        self.option_data = OptionHistoricalDataClient(api_key, secret_key)
        self.stock_data = StockHistoricalDataClient(api_key, secret_key)

    # ------------------------------------------------------------------ #
    # Account / positions
    # ------------------------------------------------------------------ #
    def get_account(self) -> Dict:
        acct = self.trading.get_account()
        return {
            "equity": float(acct.equity),
            "cash": float(acct.cash),
            "buying_power": float(acct.buying_power),
            "options_buying_power": float(getattr(acct, "options_buying_power", acct.buying_power) or acct.buying_power),
            "options_approved_level": getattr(acct, "options_approved_level", None),
            "last_equity": float(acct.last_equity),
            "maintenance_margin": float(acct.maintenance_margin or 0),
            "daytrade_count": acct.daytrade_count,
        }

    def get_positions(self) -> List[Dict]:
        positions = self.trading.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "asset_class": str(p.asset_class),
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "market_value": float(p.market_value or 0),
                "unrealized_pl": float(p.unrealized_pl or 0),
                "current_price": float(p.current_price or 0),
            }
            for p in positions
        ]

    def get_open_orders(self) -> List[Dict]:
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, nested=True)
        orders = self.trading.get_orders(req)
        return [{"id": str(o.id), "symbol": o.symbol, "status": str(o.status)} for o in orders]

    # ------------------------------------------------------------------ #
    # Market data
    # ------------------------------------------------------------------ #
    def get_underlying_price(self, symbol: str) -> float:
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = self.stock_data.get_stock_latest_quote(req)[symbol]
        bid, ask = float(quote.bid_price or 0), float(quote.ask_price or 0)
        if bid and ask:
            return round((bid + ask) / 2, 4)
        return float(quote.ask_price or quote.bid_price or 0)

    def get_historical_closes(self, symbol: str, lookback_days: int = 60) -> List[float]:
        """Daily closes, used for realized-volatility / trend filters."""
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=datetime.utcnow() - timedelta(days=int(lookback_days * 1.6) + 5),
        )
        bars = self.stock_data.get_stock_bars(req)
        try:
            rows = bars[symbol]
        except (KeyError, TypeError):
            rows = bars.data.get(symbol, [])
        closes = [float(b.close) for b in rows]
        return closes[-lookback_days:]

    def get_option_chain(
        self,
        underlying: str,
        min_dte: int = 25,
        max_dte: int = 45,
        option_type: Optional[str] = None,
    ) -> List[OptionQuote]:
        """Fetch the live chain (price + greeks + IV) for one underlying,
        pre-filtered to a DTE window. Uses the OPRA/indicative feed the
        account is entitled to — get_option_chain already returns latest
        quote, IV, and greeks per contract in one call.
        """
        today = date.today()
        exp_gte = today + timedelta(days=min_dte)
        exp_lte = today + timedelta(days=max_dte)

        kwargs = dict(
            underlying_symbol=underlying,
            expiration_date_gte=exp_gte,
            expiration_date_lte=exp_lte,
        )
        if option_type:
            kwargs["type"] = ContractType.CALL if option_type == "call" else ContractType.PUT

        req = OptionChainRequest(**kwargs)
        raw = self.option_data.get_option_chain(req)

        # Need strike/expiration/type/OI per symbol — the chain data call doesn't
        # carry contract metadata, so cross-reference with get_option_contracts.
        contracts_req = GetOptionContractsRequest(
            underlying_symbols=[underlying],
            expiration_date_gte=exp_gte,
            expiration_date_lte=exp_lte,
            type=kwargs.get("type"),
            limit=1000,
        )
        contracts = {c.symbol: c for c in self.trading.get_option_contracts(contracts_req).option_contracts}

        quotes: List[OptionQuote] = []
        for sym, snap in raw.items():
            c = contracts.get(sym)
            if c is None or snap is None:
                continue
            lq = snap.latest_quote
            lt = snap.latest_trade
            greeks = snap.greeks
            if lq is None or greeks is None:
                continue
            quotes.append(
                OptionQuote(
                    symbol=sym,
                    underlying=underlying,
                    strike=float(c.strike_price),
                    expiration=str(c.expiration_date),
                    option_type=str(c.type.value if hasattr(c.type, "value") else c.type),
                    bid=float(lq.bid_price or 0),
                    ask=float(lq.ask_price or 0),
                    last=float(lt.price) if lt else None,
                    open_interest=int(getattr(c, "open_interest", 0) or 0),
                    volume=int(getattr(lt, "size", 0) or 0) if lt else 0,
                    delta=float(greeks.delta),
                    gamma=float(greeks.gamma),
                    theta=float(greeks.theta),
                    vega=float(greeks.vega),
                    implied_volatility=float(snap.implied_volatility or 0),
                )
            )
        return quotes

    def get_single_option_quote(self, symbol: str) -> Optional[OptionQuote]:
        """Repriced view of one existing contract by symbol — used to manage
        (and decide whether to close) an already-open position, where
        `get_option_chain`'s DTE-window filter would otherwise miss it as
        expiration approaches.
        """
        contract = self.trading.get_option_contract(symbol)
        snap_map = self.option_data.get_option_snapshot(OptionSnapshotRequest(symbol_or_symbols=symbol))
        snap = snap_map.get(symbol)
        if snap is None or snap.latest_quote is None or snap.greeks is None:
            return None
        lq, lt, greeks = snap.latest_quote, snap.latest_trade, snap.greeks
        return OptionQuote(
            symbol=symbol,
            underlying=contract.underlying_symbol,
            strike=float(contract.strike_price),
            expiration=str(contract.expiration_date),
            option_type=str(contract.type.value if hasattr(contract.type, "value") else contract.type),
            bid=float(lq.bid_price or 0),
            ask=float(lq.ask_price or 0),
            last=float(lt.price) if lt else None,
            open_interest=int(getattr(contract, "open_interest", 0) or 0),
            volume=int(getattr(lt, "size", 0) or 0) if lt else 0,
            delta=float(greeks.delta),
            gamma=float(greeks.gamma),
            theta=float(greeks.theta),
            vega=float(greeks.vega),
            implied_volatility=float(snap.implied_volatility or 0),
        )

    # ------------------------------------------------------------------ #
    # Order submission
    # ------------------------------------------------------------------ #
    def submit_single_leg_limit(self, leg: Leg, contracts: int, limit_price: float) -> str:
        side, intent = _ACTION_TO_SIDE_INTENT[leg.action]
        order = LimitOrderRequest(
            symbol=leg.quote.symbol,
            qty=contracts,
            side=side,
            time_in_force=TimeInForce.DAY,  # options only support DAY TIF
            limit_price=round(limit_price, 2),
            position_intent=intent,
        )
        result = self.trading.submit_order(order)
        return str(result.id)

    def submit_multi_leg_limit(self, legs: List[Leg], contracts: int, net_limit_price: float) -> str:
        """net_limit_price: positive = net credit, negative = net debit,
        matching Alpaca's mleg semantics (limit_price is the *net* price)."""
        if not (2 <= len(legs) <= 4):
            raise ValueError("Alpaca mleg orders require 2-4 legs.")
        leg_requests = []
        for leg in legs:
            side, intent = _ACTION_TO_SIDE_INTENT[leg.action]
            leg_requests.append(
                OptionLegRequest(
                    symbol=leg.quote.symbol,
                    ratio_qty=leg.ratio_qty,
                    side=side,
                    position_intent=intent,
                )
            )
        # Per alpaca-py's OrderRequest contract: symbol/side are only required
        # for non-mleg orders — for mleg, direction and instrument come from
        # each leg's own side/position_intent. limit_price sign convention
        # for mleg is the OPPOSITE of net_limit_price's internal convention
        # here: alpaca-py's own docstring (trading/requests.py) is explicit —
        # "a positive value indicates a debit ... a negative value signifies
        # a credit". Our net_limit_price is positive=credit, so it must be
        # negated, never abs()'d — sending abs() would submit every credit
        # spread as if it were a debit order and get rejected or, worse,
        # mispriced.
        order = LimitOrderRequest(
            qty=contracts,
            time_in_force=TimeInForce.DAY,
            limit_price=round(-net_limit_price, 2),
            order_class=OrderClass.MLEG,
            legs=leg_requests,
        )
        result = self.trading.submit_order(order)
        return str(result.id)

    def get_order(self, order_id: str) -> Dict:
        o = self.trading.get_order_by_id(order_id)
        return {
            "id": str(o.id),
            "status": str(o.status),
            "filled_qty": float(o.filled_qty or 0),
            "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
        }

    def cancel_order(self, order_id: str) -> None:
        self.trading.cancel_order_by_id(order_id)

    def close_position(self, symbol: str) -> None:
        self.trading.close_position(symbol)
