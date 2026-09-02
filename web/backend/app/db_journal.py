"""DBJournal — a `JournalSink` that streams the agent's decision events into
Postgres (`trade_events`) per user/run, and fires Telegram/WhatsApp
notifications on `fill` / `error`. Same method surface as
`alpaca_options_agent.monitoring.journal.Journal`, so `run_cycle(journal=...)`
takes it without knowing the difference.

Synchronous on purpose: `run_cycle` is synchronous and the worker runs it in
a thread.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable, List, Optional

from app import supa_sync
from app.notifier import Notifier

logger = logging.getLogger("saas.db_journal")


class DBJournal:
    def __init__(
        self,
        user_id: str,
        run_id: Optional[str] = None,
        notifier: Optional[Notifier] = None,
        notify_kinds: Iterable[str] = ("fill", "error"),
    ):
        self.user_id = user_id
        self.run_id = run_id
        self._notifier = notifier or Notifier()
        self._notify_kinds = set(notify_kinds)
        self._buffer: List[Dict] = []  # local mirror, for read_all() within a cycle

    # ---- write surface -------------------------------------------------- #
    def _write(self, kind: str, payload: Dict[str, Any], underlying: Optional[str] = None) -> None:
        row = {
            "user_id": self.user_id,
            "run_id": self.run_id,
            "kind": kind,
            "underlying": underlying,
            "payload": payload,
        }
        self._buffer.append({"ts": time.time(), "kind": kind, **payload})
        try:
            supa_sync.insert("trade_events", row, returning=False)
        except Exception:  # noqa: BLE001 — never let logging kill a trading cycle
            logger.exception("trade_events insert failed (kind=%s)", kind)

        if kind in self._notify_kinds:
            try:
                self._notifier.notify(
                    self.user_id,
                    {"kind": kind, "underlying": underlying, "payload": payload, "ts": time.time()},
                )
            except Exception:  # noqa: BLE001
                logger.exception("notify failed (kind=%s)", kind)

    def scan(self, underlying: str, vol_sig: Dict, trend_sig: Dict, n_candidates: int) -> None:
        self._write("scan", {"vol_signal": vol_sig, "trend_signal": trend_sig,
                              "n_candidates": n_candidates}, underlying)

    def candidate(self, candidate: Dict) -> None:
        self._write("candidate", {"candidate": candidate}, candidate.get("underlying"))

    def risk_decision(self, candidate_id: str, underlying: str, approved: bool,
                      sized_contracts: int, reasons: list) -> None:
        self._write("risk_decision", {"candidate_id": candidate_id, "approved": approved,
                                      "sized_contracts": sized_contracts, "reasons": reasons},
                    underlying)

    def fill(self, fill_result: Dict) -> None:
        cand = fill_result.get("candidate") or {}
        self._write("fill", {"fill": fill_result}, cand.get("underlying"))

    def error(self, context: str, message: str) -> None:
        self._write("error", {"context": context, "message": message}, context)

    def note(self, message: str, **extra: Any) -> None:
        self._write("note", {"message": message, **extra})

    # ---- read surface (used by premium-stats within a single cycle) ---- #
    def read_all(self) -> Iterable[Dict]:
        return list(self._buffer)
