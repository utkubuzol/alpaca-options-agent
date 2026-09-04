"""
Premium-selling options strategy engine.

This is the single source of truth for "what trade, if any, should we put
on for this underlying right now" — called identically by the backtest
engine (against historical chains) and the live agent loop (against live
chains). Nothing in here talks to the network or to Alpaca directly; it
is pure functions over `OptionQuote` lists, which is what makes it
testable and what makes backtest-vs-paper a fair comparison rather than
two different codebases that happen to have similar names.

Strategy logic (deliberately simple and explainable, not curve-fit):
  - Sell premium only when IV is rich relative to its own recent history
    (iv_rank above a threshold) — selling options is a short-volatility
    bet, so it should only be sized up when volatility is priced rich.
  - Direction comes from a trend filter, not a forecast: bullish/neutral
    regimes favor cash-secured puts, bearish/neutral regimes favor call
    credit spreads, strong trend in either direction with existing
    long shares favors covered calls.
  - Strike selection targets a delta band (not a fixed strike), which is
    the standard way quant desks parameterize premium-selling strike
    distance in a way that adapts to the option's own moneyness/vol.
  - Every candidate carries `rationale` — a plain-English explanation of
    why the model picked it — logged verbatim by the monitoring layer so
    a reviewer (or a judge) can audit *why*, not just *what*.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from alpaca_options_agent.strategy.signals import TrendSignal, VolSignal
from alpaca_options_agent.strategy.types import (
    STRATEGY_TYPE_SLUGS,
    Leg,
    LegAction,
    OptionQuote,
    StrategyType,
    TradeCandidate,
)


@dataclass
class StrategyParams:
    iv_rank_entry_threshold: float = 0.50
    short_delta_target: float = 0.20  # ~20-delta short strike, classic premium-selling zone
    short_delta_tolerance: float = 0.08
    spread_width_pct_of_spot: float = 0.03  # long leg strike distance for credit spreads
    min_credit_to_width_ratio: float = 0.20  # reject spreads paying <20% of width as credit
    max_candidates_per_underlying: int = 1


def _passes_liquidity(q: OptionQuote, min_open_interest: int, max_spread_pct: float) -> bool:
    if q.bid <= 0 or q.ask <= 0:
        return False
    if q.open_interest < min_open_interest:
        return False
    if q.spread_pct > max_spread_pct:
        return False
    return True


def _closest_by_delta(
    quotes: List[OptionQuote], target_abs_delta: float, tolerance: float
) -> Optional[OptionQuote]:
    candidates = [q for q in quotes if abs(abs(q.delta) - target_abs_delta) <= tolerance]
    pool = candidates or quotes
    if not pool:
        return None
    return min(pool, key=lambda q: abs(abs(q.delta) - target_abs_delta))


def _prob_of_profit(short_delta: float) -> float:
    """Rough, standard-desk approximation: P(OTM at expiration) ~= 1 - |delta|."""
    return max(0.0, min(1.0, 1 - abs(short_delta)))


def build_cash_secured_put(
    chain: List[OptionQuote],
    spot: float,
    params: StrategyParams,
    min_open_interest: int,
    max_spread_pct: float,
) -> Optional[TradeCandidate]:
    puts = [q for q in chain if q.option_type == "put" and q.strike < spot]
    puts = [q for q in puts if _passes_liquidity(q, min_open_interest, max_spread_pct)]
    short = _closest_by_delta(puts, params.short_delta_target, params.short_delta_tolerance)
    if short is None:
        return None

    credit = short.mid
    collateral = short.strike * 100
    max_loss = collateral - credit * 100  # strike goes to 0, minus premium collected
    pop = _prob_of_profit(short.delta)

    return TradeCandidate(
        underlying=short.underlying,
        strategy_type=StrategyType.CASH_SECURED_PUT,
        legs=[Leg(quote=short, action=LegAction.SELL_TO_OPEN, ratio_qty=1)],
        contracts=1,
        rationale=(
            f"Sell {short.strike:.2f}p exp {short.expiration} (delta {short.delta:+.2f}, "
            f"OI {short.open_interest}) for ${credit:.2f} credit — IV rich vs recent history, "
            f"trend neutral/bullish supports being assigned or keeping the premium."
        ),
        net_credit_per_contract=credit,
        max_loss_per_contract=max_loss,
        max_profit_per_contract=credit * 100,
        prob_of_profit=pop,
        breakeven=short.strike - credit,
        collateral_required=collateral,
        net_delta=short.delta,
        net_theta=short.theta,
    )


def build_covered_call(
    chain: List[OptionQuote],
    spot: float,
    params: StrategyParams,
    min_open_interest: int,
    max_spread_pct: float,
    shares_held: float,
) -> Optional[TradeCandidate]:
    if shares_held < 100:
        return None  # can't cover without >=100 shares
    calls = [q for q in chain if q.option_type == "call" and q.strike > spot]
    calls = [q for q in calls if _passes_liquidity(q, min_open_interest, max_spread_pct)]
    short = _closest_by_delta(calls, params.short_delta_target, params.short_delta_tolerance)
    if short is None:
        return None

    credit = short.mid
    max_contracts = int(shares_held // 100)
    upside_cap_per_contract = max(0.0, (short.strike - spot)) * 100 + credit * 100

    return TradeCandidate(
        underlying=short.underlying,
        strategy_type=StrategyType.COVERED_CALL,
        legs=[Leg(quote=short, action=LegAction.SELL_TO_OPEN, ratio_qty=1)],
        contracts=max_contracts,
        rationale=(
            f"Sell {short.strike:.2f}c exp {short.expiration} (delta {short.delta:+.2f}) against "
            f"{shares_held:.0f} held shares for ${credit:.2f} credit — monetizes rich IV on an "
            f"existing long without adding new capital at risk."
        ),
        net_credit_per_contract=credit,
        max_loss_per_contract=0.0,  # loss is on the underlying shares, not this leg
        max_profit_per_contract=upside_cap_per_contract,
        prob_of_profit=_prob_of_profit(short.delta),
        breakeven=spot - credit,
        collateral_required=0.0,
        net_delta=short.delta,
        net_theta=short.theta,
    )


def _build_credit_spread(
    chain: List[OptionQuote],
    spot: float,
    params: StrategyParams,
    min_open_interest: int,
    max_spread_pct: float,
    option_type: str,
    bullish: bool,
) -> Optional[TradeCandidate]:
    legs_pool = [q for q in chain if q.option_type == option_type]
    legs_pool = [q for q in legs_pool if _passes_liquidity(q, min_open_interest, max_spread_pct)]
    if option_type == "put":
        legs_pool = [q for q in legs_pool if q.strike < spot]
    else:
        legs_pool = [q for q in legs_pool if q.strike > spot]
    if not legs_pool:
        return None

    short = _closest_by_delta(legs_pool, params.short_delta_target, params.short_delta_tolerance)
    if short is None:
        return None

    width = round(spot * params.spread_width_pct_of_spot, 0) or 1
    long_target_strike = short.strike - width if option_type == "put" else short.strike + width
    same_expiry = [q for q in legs_pool if q.expiration == short.expiration and q.symbol != short.symbol]
    if not same_expiry:
        return None
    long_leg = min(same_expiry, key=lambda q: abs(q.strike - long_target_strike))

    net_credit = short.mid - long_leg.mid
    actual_width = abs(short.strike - long_leg.strike)
    if actual_width <= 0 or net_credit <= 0:
        return None
    if net_credit / actual_width < params.min_credit_to_width_ratio:
        return None  # not paid enough for the risk taken

    max_loss = (actual_width - net_credit) * 100
    strategy_type = (
        StrategyType.PUT_CREDIT_SPREAD if option_type == "put" else StrategyType.CALL_CREDIT_SPREAD
    )
    direction = "bullish" if bullish else "bearish"

    return TradeCandidate(
        underlying=short.underlying,
        strategy_type=strategy_type,
        legs=[
            Leg(quote=short, action=LegAction.SELL_TO_OPEN, ratio_qty=1),
            Leg(quote=long_leg, action=LegAction.BUY_TO_OPEN, ratio_qty=1),
        ],
        contracts=1,
        rationale=(
            f"{direction.capitalize()} {option_type} credit spread: sell {short.strike:.2f}, "
            f"buy {long_leg.strike:.2f} (exp {short.expiration}) for ${net_credit:.2f} net credit "
            f"on ${actual_width:.2f} width — defined-risk way to monetize rich IV with a "
            f"{direction} trend filter, without tying up cash-secured collateral."
        ),
        net_credit_per_contract=net_credit,
        max_loss_per_contract=max_loss,
        max_profit_per_contract=net_credit * 100,
        prob_of_profit=_prob_of_profit(short.delta),
        breakeven=(short.strike - net_credit) if option_type == "put" else (short.strike + net_credit),
        collateral_required=max_loss,  # spread risk = margin requirement
        net_delta=short.delta - long_leg.delta,
        net_theta=short.theta - long_leg.theta,
    )


def generate_candidates(
    underlying: str,
    chain: List[OptionQuote],
    vol_sig: VolSignal,
    trend_sig: TrendSignal,
    spot: float,
    shares_held: float,
    min_open_interest: int,
    max_spread_pct: float,
    params: Optional[StrategyParams] = None,
    allowed_slugs: Optional[set] = None,
) -> List[TradeCandidate]:
    """The strategy's decision function. Returns a ranked list (possibly
    empty) of trade candidates for this underlying, right now.

    `allowed_slugs`: if given, only keep candidates whose family is in this set
    ("csp" / "covered_call" / "credit_spread"). Applied *before* ranking and the
    max-per-underlying cut, so restricting to e.g. credit spreads doesn't just
    get a higher-ranked CSP dropped and leave nothing.
    """
    params = params or StrategyParams()

    if not chain or vol_sig.iv_rank < params.iv_rank_entry_threshold:
        return []  # volatility isn't rich enough to justify selling premium

    candidates: List[TradeCandidate] = []

    if trend_sig.regime in ("bullish", "neutral"):
        c = build_cash_secured_put(chain, spot, params, min_open_interest, max_spread_pct)
        if c:
            candidates.append(c)

    if trend_sig.regime in ("bearish", "neutral"):
        c = _build_credit_spread(
            chain, spot, params, min_open_interest, max_spread_pct,
            option_type="call", bullish=False,
        )
        if c:
            candidates.append(c)

    if trend_sig.regime == "bullish" and shares_held >= 100:
        c = build_covered_call(chain, spot, params, min_open_interest, max_spread_pct, shares_held)
        if c:
            candidates.append(c)

    if allowed_slugs is not None:
        candidates = [
            c for c in candidates
            if STRATEGY_TYPE_SLUGS.get(c.strategy_type.value) in allowed_slugs
        ]

    for c in candidates:
        liquidity_quality = 1.0 - min(
            1.0, sum(l.quote.spread_pct for l in c.legs) / max(1, len(c.legs)) / max_spread_pct
        )
        trend_alignment = 1.0 if trend_sig.regime != "neutral" else 0.6
        c.underlying_price = spot
        c.iv_rank = vol_sig.iv_rank
        c.signal_score = round(
            0.5 * vol_sig.iv_rank + 0.25 * liquidity_quality + 0.25 * trend_alignment, 4
        )

    candidates.sort(key=lambda c: c.signal_score, reverse=True)
    return candidates[: params.max_candidates_per_underlying]
