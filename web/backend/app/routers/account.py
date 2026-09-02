"""Account, positions, and the PnL snapshot (dashboard Overview)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends

from alpaca_options_agent.broker.client import AlpacaBroker
from alpaca_options_agent.monitoring.pnl import build_pnl_snapshot, premium_stats_from_fills

from app.deps import get_broker, get_current_user, get_supa, load_broker_creds
from app.supa import Supa

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/account")
async def account(broker: AlpacaBroker = Depends(get_broker)) -> Dict:
    return broker.get_account()


@router.get("/positions")
async def positions(broker: AlpacaBroker = Depends(get_broker)) -> Dict:
    return {"positions": broker.get_positions()}


@router.get("/pnl")
async def pnl(
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
    broker: AlpacaBroker = Depends(get_broker),
) -> Dict:
    creds = await load_broker_creds(user["id"], supa)
    account = broker.get_account()
    positions = broker.get_positions()

    snap = build_pnl_snapshot(
        account=account,
        positions=positions,
        baseline_equity=creds["baseline_equity"],
        journal_path=Path("/nonexistent"),
    )

    # premium-selling stats from every fill this user has ever logged
    fill_rows = await supa.select(
        "trade_events",
        columns="payload",
        eq={"user_id": user["id"], "kind": "fill"},
        order="id.desc",
        limit=1000,
    )
    fills = [r["payload"].get("fill", r["payload"]) for r in fill_rows]
    snap["premium_journal"] = premium_stats_from_fills(fills)

    # equity curve from stored snapshots
    curve = await supa.select(
        "positions_snapshots",
        columns="ts,equity,pnl",
        eq={"user_id": user["id"]},
        order="ts.asc",
        limit=1000,
    )
    snap["equity_curve"] = [
        {"ts": c["ts"], "equity": c["equity"],
         "total": (c.get("pnl") or {}).get("total")}
        for c in curve
    ]
    return snap
