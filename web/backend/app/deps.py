"""Auth + per-user broker construction, as FastAPI dependencies."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from alpaca_options_agent.broker.client import AlpacaBroker

from app.crypto import decrypt
from app.settings import get_settings
from app.supa import Supa

_AUDIENCE = "authenticated"


@lru_cache
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(get_settings().jwks_url)


def _decode_local(token: str) -> Dict:
    """Verify a Supabase access token offline. Tries asymmetric JWKS first
    (the default for projects created since 2025), then the legacy HS256
    shared secret if SUPABASE_JWT_SECRET is configured."""
    s = get_settings()
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, signing_key, algorithms=["RS256", "ES256"], audience=_AUDIENCE)
    except Exception:
        pass
    if s.supabase_jwt_secret:
        return jwt.decode(
            token, s.supabase_jwt_secret, algorithms=["HS256"], audience=_AUDIENCE
        )
    raise jwt.InvalidTokenError("no usable verification method")


async def _decode_remote(token: str) -> Dict:
    """Last resort: ask Supabase Auth to validate the token."""
    s = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(
            s.auth_user_url,
            headers={"apikey": s.supabase_service_role_key, "Authorization": f"Bearer {token}"},
        )
    if r.status_code != 200:
        raise jwt.InvalidTokenError(f"auth/v1/user -> {r.status_code}")
    u = r.json()
    return {"sub": u["id"], "email": u.get("email")}


async def get_current_user(authorization: str = Header(default="")) -> Dict:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = _decode_local(token)
    except Exception:
        try:
            claims = await _decode_remote(token)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}") from e
    uid = claims.get("sub")
    if not uid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token has no subject")
    return {"id": uid, "email": claims.get("email")}


def get_supa() -> Supa:
    return Supa()


async def load_broker_creds(user_id: str, supa: Supa) -> Dict:
    row = await supa.select(
        "broker_credentials", eq={"user_id": user_id}, single=True
    )
    if not row:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "no Alpaca credentials on file — add them in Settings first",
        )
    return {
        "api_key": decrypt(row["alpaca_api_key_enc"]),
        "secret_key": decrypt(row["alpaca_secret_key_enc"]),
        "paper": bool(row.get("paper", True)),
        "baseline_equity": float(row.get("baseline_equity", 100_000.0)),
    }


async def get_broker(
    user: Dict = Depends(get_current_user), supa: Supa = Depends(get_supa)
) -> AlpacaBroker:
    creds = await load_broker_creds(user["id"], supa)
    return AlpacaBroker(
        api_key=creds["api_key"], secret_key=creds["secret_key"], paper=creds["paper"]
    )
