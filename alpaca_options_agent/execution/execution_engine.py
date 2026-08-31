"""
Live execution engine: turns a TradeCandidate into a real (paper) order,
waits for it to fill, and always reports expected-vs-realized price —
that comparison is written to the decision journal for every single
trade, which is what "reducing the sim-to-real gap" needs to mean in
practice: not a claim, a logged number per trade.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from alpaca_options_agent.broker.client import AlpacaBroker
from alpaca_options_agent.config import ExecutionConfig
from alpaca_options_agent.execution.cost_model import expected_marketable_limit, slippage_stats
from alpaca_options_agent.strategy.types import FillResult, LegAction, TradeCandidate

_SELL_ACTIONS = (LegAction.SELL_TO_OPEN, LegAction.SELL_TO_CLOSE)

logger = logging.getLogger("agent.execution")

_POLL_INTERVAL_SECONDS = 3
_TERMINAL_FILLED = {"filled"}
_TERMINAL_DEAD = {"canceled", "expired", "rejected", "done_for_day"}
_TERMINAL_PARTIAL = {"partially_filled"}


class ExecutionEngine:
    def __init__(self, broker: AlpacaBroker, cfg: ExecutionConfig):
        self.broker = broker
        self.cfg = cfg

    def execute(self, candidate: TradeCandidate) -> FillResult:
        exp = expected_marketable_limit(candidate.legs, self.cfg)
        expected_credit = exp.net_limit_price

        try:
            if len(candidate.legs) == 1:
                order_id = self.broker.submit_single_leg_limit(
                    candidate.legs[0], candidate.contracts, abs(exp.net_limit_price)
                )
            else:
                order_id = self.broker.submit_multi_leg_limit(
                    candidate.legs, candidate.contracts, exp.net_limit_price
                )
        except Exception as e:  # noqa: BLE001 — surface broker rejects as a reject_reason, not a crash
            logger.exception("order submission failed for candidate %s", candidate.id)
            return FillResult(
                candidate_id=candidate.id,
                submitted=False,
                filled=False,
                expected_credit=expected_credit,
                realized_credit=None,
                slippage_per_contract=None,
                slippage_bps=None,
                reject_reason=str(e),
            )

        status, filled_avg_price, filled_qty = self._poll_until_terminal(order_id)

        if status not in _TERMINAL_FILLED | _TERMINAL_PARTIAL or filled_avg_price is None:
            if status not in _TERMINAL_DEAD:
                self.broker.cancel_order(order_id)
            return FillResult(
                candidate_id=candidate.id,
                submitted=True,
                filled=False,
                expected_credit=expected_credit,
                realized_credit=None,
                slippage_per_contract=None,
                slippage_bps=None,
                order_ids=[order_id],
                reject_reason=f"unfilled_status={status}",
            )

        realized_credit = self._recover_signed_credit(candidate, filled_avg_price)
        slip, slip_bps = slippage_stats(expected_credit, realized_credit)

        return FillResult(
            candidate_id=candidate.id,
            submitted=True,
            filled=(status in _TERMINAL_FILLED),
            expected_credit=expected_credit,
            realized_credit=realized_credit,
            slippage_per_contract=slip,
            slippage_bps=slip_bps,
            order_ids=[order_id],
            partially_filled_contracts=int(filled_qty) if status in _TERMINAL_PARTIAL else 0,
        )

    @staticmethod
    def _recover_signed_credit(candidate: TradeCandidate, filled_avg_price: float) -> float:
        """Convert Alpaca's reported fill price into our internal convention
        (positive = net credit received, negative = net debit paid).

        Single-leg orders: Alpaca reports an unsigned per-contract price —
        sign comes from whether the (single) leg was a sell (credit) or buy
        (debit).

        Multi-leg (mleg) orders: per alpaca-py's own OrderRequest docstring,
        the *submitted* limit_price for mleg uses "positive = debit,
        negative = credit" — the opposite of our internal convention (see
        broker/client.py::submit_multi_leg_limit). We assume, by symmetry,
        that a filled mleg order's reported price follows the same signed
        convention as what was submitted for it (that's the only way the
        two numbers are comparable at all). This assumption is flagged here
        deliberately: verify it against a real fill during initial paper
        testing before trusting the sign on a live account, and see the
        journal's `slippage_bps` on the very first mleg fill as the check —
        a flipped sign shows up immediately as a wildly wrong number.
        """
        if len(candidate.legs) == 1:
            sign = 1 if candidate.legs[0].action in _SELL_ACTIONS else -1
            return sign * filled_avg_price
        return -filled_avg_price

    def _poll_until_terminal(self, order_id: str):
        deadline = time.time() + self.cfg.order_timeout_seconds
        status, filled_avg_price, filled_qty = "new", None, 0.0
        while time.time() < deadline:
            order = self.broker.get_order(order_id)
            status = order["status"]
            filled_avg_price = order["filled_avg_price"]
            filled_qty = order["filled_qty"]
            if status in _TERMINAL_FILLED | _TERMINAL_DEAD:
                break
            time.sleep(_POLL_INTERVAL_SECONDS)
        return status, filled_avg_price, filled_qty
