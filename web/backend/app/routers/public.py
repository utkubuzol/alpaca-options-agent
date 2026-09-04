"""Unauthenticated read-only endpoints that feed the public landing page.
Everything is served from the in-process TTL cache in app.showcase, so
anonymous traffic never fans out to Supabase / Alpaca per request."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query

from app.showcase import build_showcase, get_quotes

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/showcase")
def showcase() -> Dict[str, Any]:
    """The `LandingData` object (same shape as
    web/frontend/components/landing/data.json), built live from the showcase
    account's journal. Sections whose data is absent come back null and the
    landing degrades honestly."""
    return build_showcase()


@router.get("/quotes")
def quotes(symbols: str = Query("SPY,QQQ,AAPL,MSFT,NVDA")) -> Dict[str, Any]:
    """Live-ish spot + day-change for an allowlisted set of symbols."""
    return {"quotes": get_quotes(symbols.split(","))}
