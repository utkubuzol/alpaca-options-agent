"""Alpaca credential storage + a live 'does this key work' test."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from alpaca_options_agent.broker.client import AlpacaBroker

from app.crypto import decrypt, encrypt, mask
from app.deps import get_current_user, get_supa
from app.schemas import BrokerCredentialsIn
from app.supa import Supa

router = APIRouter(prefix="/api/broker-credentials", tags=["broker"])


@router.get("")
async def get_credentials(
    user: Dict = Depends(get_current_user), supa: Supa = Depends(get_supa)
) -> Dict:
    row = await supa.select("broker_credentials", eq={"user_id": user["id"]}, single=True)
    if not row:
        return {"configured": False}
    return {
        "configured": True,
        "api_key_preview": mask(decrypt(row["alpaca_api_key_enc"])),
        "paper": row["paper"],
        "baseline_equity": row["baseline_equity"],
        "updated_at": row["updated_at"],
    }


@router.put("")
async def put_credentials(
    body: BrokerCredentialsIn,
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
) -> Dict:
    row = {
        "user_id": user["id"],
        "alpaca_api_key_enc": encrypt(body.api_key),
        "alpaca_secret_key_enc": encrypt(body.secret_key),
        "paper": True,
        "baseline_equity": body.baseline_equity,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await supa.upsert("broker_credentials", row, on_conflict="user_id")
    return {"configured": True, "api_key_preview": mask(body.api_key)}


@router.post("/test")
async def test_credentials(
    body: BrokerCredentialsIn | None = None,
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
) -> Dict:
    """Test the posted keys, or the stored ones if the body is omitted."""
    if body is not None:
        api_key, secret_key = body.api_key, body.secret_key
    else:
        row = await supa.select("broker_credentials", eq={"user_id": user["id"]}, single=True)
        if not row:
            raise HTTPException(400, "no stored credentials to test")
        api_key = decrypt(row["alpaca_api_key_enc"])
        secret_key = decrypt(row["alpaca_secret_key_enc"])
    try:
        broker = AlpacaBroker(api_key=api_key, secret_key=secret_key, paper=True)
        acct = broker.get_account()
        clock = broker.get_clock()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Alpaca rejected these credentials: {e}") from e
    return {"ok": True, "equity": acct["equity"], "market_open": clock["is_open"]}
