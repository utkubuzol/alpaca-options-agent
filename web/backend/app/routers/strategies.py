"""Strategy CRUD + manual run trigger. 'Create strategy from dashboard'."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.cycle import run_strategy_cycle
from app.deps import get_current_user, get_supa, load_broker_creds
from app.schemas import StrategyIn
from app.supa import Supa

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


async def _owned(supa: Supa, user_id: str, strategy_id: str) -> Dict:
    row = await supa.select("strategies", eq={"id": strategy_id, "user_id": user_id}, single=True)
    if not row:
        raise HTTPException(404, "strategy not found")
    return row


@router.get("")
async def list_strategies(
    user: Dict = Depends(get_current_user), supa: Supa = Depends(get_supa)
) -> Dict:
    rows = await supa.select(
        "strategies", eq={"user_id": user["id"]}, order="created_at.desc"
    )
    return {"strategies": rows}


@router.post("")
async def create_strategy(
    body: StrategyIn,
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
) -> Dict:
    row = {**body.to_row(), "user_id": user["id"]}
    return await supa.insert("strategies", row)


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    body: StrategyIn,
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
) -> Dict:
    await _owned(supa, user["id"], strategy_id)
    patch = {**body.to_row(), "updated_at": datetime.now(timezone.utc).isoformat()}
    return await supa.update("strategies", patch, eq={"id": strategy_id})


@router.patch("/{strategy_id}/enabled")
async def toggle_enabled(
    strategy_id: str,
    enabled: bool = Query(...),
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
) -> Dict:
    await _owned(supa, user["id"], strategy_id)
    return await supa.update("strategies", {"enabled": enabled}, eq={"id": strategy_id})


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: str,
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
) -> Dict:
    await _owned(supa, user["id"], strategy_id)
    await supa.delete("strategies", eq={"id": strategy_id})
    return {"deleted": strategy_id}


@router.post("/{strategy_id}/run")
async def run_now(
    strategy_id: str,
    background: BackgroundTasks,
    mode: str = Query("scan", pattern="^(scan|trade)$"),
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
) -> Dict:
    strategy = await _owned(supa, user["id"], strategy_id)
    creds = await load_broker_creds(user["id"], supa)
    # run_strategy_cycle is synchronous + does its own DB writes; hand it to
    # a background thread so the request returns immediately.
    background.add_task(run_strategy_cycle, user["id"], strategy, creds, mode)
    return {"queued": True, "mode": mode, "strategy_id": strategy_id}
