"""
Decision journal: an append-only, structured (JSONL) record of every
decision the agent makes — not just executed trades, but candidates that
were generated and then rejected by risk, so "why didn't it trade today"
is answerable from the log instead of requiring a debugger.

This is the backbone of the "Live monitoring & explainability" pillar:
every row is one event with a `kind`, a timestamp, and enough structured
data to reconstruct the agent's reasoning after the fact.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable


@runtime_checkable
class JournalSink(Protocol):
    """The write surface `runner.run_cycle` depends on. `Journal` (JSONL,
    below) is the default implementation; the SaaS backend supplies a
    Postgres-backed one (`web/backend/app/db_journal.DBJournal`) with the
    same methods so a live cycle can stream events per-user and fire
    notifications without the runner knowing where the rows go.
    """

    def scan(self, underlying: str, vol_sig: Dict, trend_sig: Dict, n_candidates: int) -> None: ...
    def candidate(self, candidate: Dict) -> None: ...
    def risk_decision(self, candidate_id: str, underlying: str, approved: bool,
                      sized_contracts: int, reasons: list) -> None: ...
    def fill(self, fill_result: Dict) -> None: ...
    def error(self, context: str, message: str) -> None: ...
    def note(self, message: str, **extra: Any) -> None: ...
    def read_all(self) -> Iterable[Dict]: ...


class Journal:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _write(self, kind: str, payload: Dict[str, Any]) -> None:
        row = {"ts": time.time(), "kind": kind, **payload}
        with self.path.open("a") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def scan(self, underlying: str, vol_sig: Dict, trend_sig: Dict, n_candidates: int) -> None:
        self._write(
            "scan",
            {"underlying": underlying, "vol_signal": vol_sig, "trend_signal": trend_sig,
             "n_candidates": n_candidates},
        )

    def candidate(self, candidate: Dict) -> None:
        self._write("candidate", {"candidate": candidate})

    def risk_decision(self, candidate_id: str, underlying: str, approved: bool,
                       sized_contracts: int, reasons: list) -> None:
        self._write(
            "risk_decision",
            {"candidate_id": candidate_id, "underlying": underlying, "approved": approved,
             "sized_contracts": sized_contracts, "reasons": reasons},
        )

    def fill(self, fill_result: Dict) -> None:
        self._write("fill", {"fill": fill_result})

    def error(self, context: str, message: str) -> None:
        self._write("error", {"context": context, "message": message})

    def note(self, message: str, **extra) -> None:
        self._write("note", {"message": message, **extra})

    def read_all(self) -> Iterable[Dict]:
        if not self.path.exists():
            return []
        rows = []
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows
