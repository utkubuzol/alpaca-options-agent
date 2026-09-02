"""Synchronous PostgREST helpers — for the APScheduler worker and the
notifier, which run outside an event loop. Mirrors app.supa.Supa but blocking.
Service-role key: every call must filter by user_id itself."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.settings import get_settings


def _headers(prefer: Optional[str] = None) -> Dict[str, str]:
    s = get_settings()
    h = {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _base() -> str:
    return get_settings().rest_url


def select(
    table: str,
    *,
    columns: str = "*",
    eq: Optional[Dict[str, Any]] = None,
    order: Optional[str] = None,
    limit: Optional[int] = None,
    single: bool = False,
) -> Any:
    params: Dict[str, Any] = {"select": columns}
    for k, v in (eq or {}).items():
        params[k] = f"eq.{v}"
    if order:
        params["order"] = order
    if limit is not None:
        params["limit"] = limit
    r = httpx.get(f"{_base()}/{table}", params=params, headers=_headers(), timeout=15.0)
    r.raise_for_status()
    rows = r.json()
    if single:
        return rows[0] if rows else None
    return rows


def insert(table: str, row: Dict[str, Any], *, returning: bool = True) -> Any:
    r = httpx.post(
        f"{_base()}/{table}",
        json=row,
        headers=_headers("return=representation" if returning else "return=minimal"),
        timeout=15.0,
    )
    r.raise_for_status()
    if not returning:
        return None
    data = r.json()
    return data[0] if isinstance(data, list) and data else data


def update(table: str, patch: Dict[str, Any], *, eq: Dict[str, Any]) -> Any:
    params = {k: f"eq.{v}" for k, v in eq.items()}
    r = httpx.patch(
        f"{_base()}/{table}",
        params=params,
        json=patch,
        headers=_headers("return=representation"),
        timeout=15.0,
    )
    r.raise_for_status()
    data = r.json()
    return data[0] if isinstance(data, list) and data else data
