"""Tiny PostgREST client (service-role key → RLS bypassed, so every query
here MUST carry its own user_id filter). Kept deliberately thin instead of
pulling in supabase-py: a handful of REST calls is all the backend needs.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.settings import get_settings


class SupaError(RuntimeError):
    pass


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


class Supa:
    """One instance per request (cheap). Async."""

    def __init__(self) -> None:
        self._base = get_settings().rest_url

    async def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, headers=_headers(), timeout=15.0)

    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        eq: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        lt: Optional[Dict[str, Any]] = None,
        gte: Optional[Dict[str, Any]] = None,
        in_: Optional[Dict[str, List[Any]]] = None,
        single: bool = False,
    ) -> Any:
        params: Dict[str, Any] = {"select": columns}
        for k, v in (eq or {}).items():
            params[k] = f"eq.{v}"
        for k, v in (lt or {}).items():
            params[k] = f"lt.{v}"
        for k, v in (gte or {}).items():
            params[k] = f"gte.{v}"
        for k, vals in (in_ or {}).items():
            params[k] = "in.(" + ",".join(str(x) for x in vals) + ")"
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = limit
        async with await self._client() as c:
            r = await c.get(f"/{table}", params=params)
        _raise(r)
        rows = r.json()
        if single:
            return rows[0] if rows else None
        return rows

    async def insert(self, table: str, row: Dict[str, Any], *, returning: bool = True) -> Any:
        async with httpx.AsyncClient(
            base_url=self._base,
            headers=_headers("return=representation" if returning else "return=minimal"),
            timeout=15.0,
        ) as c:
            r = await c.post(f"/{table}", json=row)
        _raise(r)
        if not returning:
            return None
        data = r.json()
        return data[0] if isinstance(data, list) and data else data

    async def update(self, table: str, patch: Dict[str, Any], *, eq: Dict[str, Any]) -> Any:
        params = {k: f"eq.{v}" for k, v in eq.items()}
        async with httpx.AsyncClient(
            base_url=self._base, headers=_headers("return=representation"), timeout=15.0
        ) as c:
            r = await c.patch(f"/{table}", params=params, json=patch)
        _raise(r)
        data = r.json()
        return data[0] if isinstance(data, list) and data else data

    async def upsert(self, table: str, row: Dict[str, Any], *, on_conflict: str) -> Any:
        async with httpx.AsyncClient(
            base_url=self._base,
            headers=_headers("return=representation,resolution=merge-duplicates"),
            timeout=15.0,
        ) as c:
            r = await c.post(f"/{table}", params={"on_conflict": on_conflict}, json=row)
        _raise(r)
        data = r.json()
        return data[0] if isinstance(data, list) and data else data

    async def delete(self, table: str, *, eq: Dict[str, Any]) -> None:
        params = {k: f"eq.{v}" for k, v in eq.items()}
        async with await self._client() as c:
            r = await c.delete(f"/{table}", params=params)
        _raise(r)


def _raise(r: httpx.Response) -> None:
    if r.status_code >= 400:
        raise SupaError(f"{r.request.method} {r.request.url.path} -> {r.status_code}: {r.text}")
