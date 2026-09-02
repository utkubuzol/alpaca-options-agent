"""Scheduled cycle runner — replaces scripts/crontab.txt for the SaaS.

Every minute: find enabled strategies whose `interval_minutes` is due, and
whose owner's Alpaca clock says the market is open, then run one cycle each
(scan or trade per the strategy's `mode`). One cycle per strategy at a time.

Run as its own process: `python worker.py`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

from alpaca_options_agent.broker.client import AlpacaBroker

from app import supa_sync
from app.crypto import decrypt
from app.cycle import run_strategy_cycle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("saas.worker")

_running: set[str] = set()


def _creds_for(user_id: str) -> dict | None:
    row = supa_sync.select("broker_credentials", eq={"user_id": user_id}, single=True)
    if not row:
        return None
    return {
        "api_key": decrypt(row["alpaca_api_key_enc"]),
        "secret_key": decrypt(row["alpaca_secret_key_enc"]),
        "paper": bool(row.get("paper", True)),
        "baseline_equity": float(row.get("baseline_equity", 100_000.0)),
    }


def _due(strategy: dict, now: datetime) -> bool:
    last = strategy.get("last_run_at")
    if not last:
        return True
    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    return now - last_dt >= timedelta(minutes=int(strategy["interval_minutes"]))


def tick() -> None:
    now = datetime.now(timezone.utc)
    try:
        strategies = supa_sync.select("strategies", eq={"enabled": "true"})
    except Exception:  # noqa: BLE001
        logger.exception("could not load strategies")
        return

    # heartbeat — one line every tick so liveness is observable from the log
    logger.info("tick %s — %d enabled strateg%s", now.strftime("%H:%M:%S"),
                len(strategies), "y" if len(strategies) == 1 else "ies")

    for s in strategies:
        sid = s["id"]
        if sid in _running or not _due(s, now):
            continue
        creds = _creds_for(s["user_id"])
        if not creds:
            logger.warning("strategy %s enabled but user has no broker creds", sid)
            continue
        try:
            clock = AlpacaBroker(
                api_key=creds["api_key"], secret_key=creds["secret_key"], paper=True
            ).get_clock()
        except Exception:  # noqa: BLE001
            logger.exception("clock check failed for strategy %s", sid)
            continue
        if not clock.get("is_open"):
            continue

        _running.add(sid)
        try:
            logger.info("running strategy %s (mode=%s)", sid, s.get("mode"))
            run_strategy_cycle(s["user_id"], s, creds, s.get("mode", "scan"))
        except Exception:  # noqa: BLE001
            logger.exception("cycle raised for strategy %s", sid)
        finally:
            _running.discard(sid)


def main() -> None:
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(tick, "interval", minutes=1, next_run_time=datetime.now(timezone.utc))
    logger.info("worker started — ticking every 60s")
    sched.start()


if __name__ == "__main__":
    main()
