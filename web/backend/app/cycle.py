"""Run one strategy cycle for one user, end to end, with DB bookkeeping.
Shared by the API's manual `/run` (in a BackgroundTask) and the worker's
scheduled tick. Synchronous.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from alpaca_options_agent.agent.runner import run_cycle
from alpaca_options_agent.broker.client import AlpacaBroker
from alpaca_options_agent.config import AgentConfig
from alpaca_options_agent.monitoring.pnl import build_pnl_snapshot

from app import supa_sync
from app.db_journal import DBJournal

logger = logging.getLogger("saas.cycle")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_strategy_cycle(user_id: str, strategy: Dict, creds: Dict, mode: str) -> Dict:
    """mode: 'scan' (dry run) or 'trade' (submit paper orders).
    Returns {run_id, status, results}. Raises on hard failure after marking
    the run 'error'.
    """
    dry_run = mode != "trade"
    run = supa_sync.insert("runs", {
        "user_id": user_id,
        "strategy_id": strategy.get("id"),
        "mode": mode,
        "status": "running",
    })
    run_id = run["id"]
    journal = DBJournal(user_id=user_id, run_id=run_id)

    try:
        cfg = AgentConfig.from_strategy({**strategy, "log_dir": f"./logs/{user_id}"}, creds)
        results = run_cycle(cfg, dry_run=dry_run, journal=journal)

        snapshot = _snapshot(user_id, cfg, creds)
        n_fills = sum(
            1 for r in results
            if isinstance(r, dict) and r.get("status") == "filled"
        )
        summary = {
            "underlyings": len(cfg.universe),
            "n_filled": n_fills,
            "equity": snapshot.get("equity"),
            "pnl": snapshot.get("pnl"),
        }
        supa_sync.update("runs", {
            "status": "ok", "finished_at": _now(), "summary": summary,
        }, eq={"id": run_id})
        if strategy.get("id"):
            supa_sync.update("strategies", {"last_run_at": _now()}, eq={"id": strategy["id"]})
        return {"run_id": run_id, "status": "ok", "results": results, "summary": summary}

    except Exception as e:  # noqa: BLE001
        logger.exception("cycle failed for user=%s strategy=%s", user_id, strategy.get("id"))
        journal.error("cycle", str(e))
        supa_sync.update("runs", {
            "status": "error", "finished_at": _now(), "summary": {"error": str(e)},
        }, eq={"id": run_id})
        raise


def _snapshot(user_id: str, cfg: AgentConfig, creds: Dict) -> Dict:
    """Pull account + positions once, store a positions_snapshot row, return
    the pnl block. Best-effort — a snapshot failure must not fail the run."""
    try:
        broker = AlpacaBroker(
            api_key=cfg.api_key, secret_key=cfg.secret_key, paper=cfg.paper
        )
        account = broker.get_account()
        positions = broker.get_positions()
        snap = build_pnl_snapshot(
            account=account,
            positions=positions,
            baseline_equity=float(creds.get("baseline_equity", cfg.baseline_equity)),
            journal_path=Path("/nonexistent"),  # per-run premium stats live in /api/pnl
        )
        supa_sync.insert("positions_snapshots", {
            "user_id": user_id,
            "equity": snap["equity"],
            "cash": snap["cash"],
            "pnl": snap["pnl"],
            "positions": snap["open_positions"],
        }, returning=False)
        return {"equity": snap["equity"], "pnl": snap["pnl"]}
    except Exception:  # noqa: BLE001
        logger.exception("snapshot failed for user=%s", user_id)
        return {}
