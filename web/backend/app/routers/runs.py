"""Run history + detail (with the events that run produced)."""
from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_current_user, get_supa
from app.supa import Supa

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
async def list_runs(
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
    limit: int = Query(30, ge=1, le=100),
) -> Dict:
    rows = await supa.select(
        "runs", eq={"user_id": user["id"]}, order="started_at.desc", limit=limit
    )
    return {"runs": rows}


@router.get("/{run_id}")
async def run_detail(
    run_id: str,
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
) -> Dict:
    run = await supa.select("runs", eq={"id": run_id, "user_id": user["id"]}, single=True)
    if not run:
        raise HTTPException(404, "run not found")
    events = await supa.select(
        "trade_events", eq={"run_id": run_id, "user_id": user["id"]}, order="id.asc"
    )
    return {"run": run, "events": events}
