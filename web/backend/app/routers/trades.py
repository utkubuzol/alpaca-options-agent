"""Trade-event feed: paginated history + a Server-Sent-Events live stream."""
from __future__ import annotations

import asyncio
import json
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.deps import get_current_user, get_supa
from app.supa import Supa

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("")
async def list_trades(
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
    kind: Optional[str] = None,
    underlying: Optional[str] = None,
    before_id: Optional[int] = Query(None, description="return events with id < this"),
    limit: int = Query(50, ge=1, le=200),
) -> Dict:
    eq: Dict[str, str] = {"user_id": user["id"]}
    if kind:
        eq["kind"] = kind
    if underlying:
        eq["underlying"] = underlying.upper()
    rows = await supa.select(
        "trade_events",
        eq=eq,
        lt={"id": before_id} if before_id else None,
        order="id.desc",
        limit=limit,
    )
    next_cursor = rows[-1]["id"] if len(rows) == limit else None
    return {"events": rows, "next_before_id": next_cursor}


@router.get("/stream")
async def stream_trades(
    request: Request,
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
    poll_seconds: float = Query(3.0, ge=1.0, le=30.0),
) -> EventSourceResponse:
    """Polls trade_events for rows newer than the last seen id and pushes
    them as SSE. Good enough for a dashboard; swap for Postgres
    LISTEN/NOTIFY if fan-out grows."""
    seed = await supa.select(
        "trade_events", columns="id", eq={"user_id": user["id"]},
        order="id.desc", limit=1,
    )
    last_id = seed[0]["id"] if seed else 0

    async def gen():
        nonlocal last_id
        while True:
            if await request.is_disconnected():
                break
            rows = await supa.select(
                "trade_events", eq={"user_id": user["id"]},
                gte={"id": last_id + 1}, order="id.asc", limit=100,
            )
            for row in rows:
                last_id = max(last_id, row["id"])
                yield {"event": "trade", "data": json.dumps(row, default=str)}
            await asyncio.sleep(poll_seconds)

    return EventSourceResponse(gen())
