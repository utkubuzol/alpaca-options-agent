"""Notification settings + a test-send."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from app.crypto import encrypt
from app.deps import get_current_user, get_supa
from app.notifier import Notifier, TelegramChannel
from app.schemas import NotificationSettingsIn
from app.settings import get_settings
from app.supa import Supa

router = APIRouter(prefix="/api/notification-settings", tags=["notifications"])


@router.get("")
async def get_settings_row(
    user: Dict = Depends(get_current_user), supa: Supa = Depends(get_supa)
) -> Dict:
    row = await supa.select("notification_settings", eq={"user_id": user["id"]}, single=True)
    if not row:
        return {"channels": {"telegram": True, "whatsapp": False}, "event_kinds": ["fill", "error"]}
    row.pop("telegram_bot_token_enc", None)
    row["has_custom_bot_token"] = bool(row.get("telegram_bot_token_enc"))
    return row


@router.put("")
async def put_settings_row(
    body: NotificationSettingsIn,
    user: Dict = Depends(get_current_user),
    supa: Supa = Depends(get_supa),
) -> Dict:
    patch: Dict = {
        "user_id": user["id"],
        "telegram_chat_id": body.telegram_chat_id,
        "whatsapp_number": body.whatsapp_number,
        "channels": body.channels,
        "event_kinds": body.event_kinds,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if body.telegram_bot_token:
        patch["telegram_bot_token_enc"] = encrypt(body.telegram_bot_token)
    await supa.upsert("notification_settings", patch, on_conflict="user_id")
    return {"ok": True}


@router.post("/test")
async def test_notification(
    user: Dict = Depends(get_current_user), supa: Supa = Depends(get_supa)
) -> Dict:
    row = await supa.select("notification_settings", eq={"user_id": user["id"]}, single=True)
    if not row or not row.get("telegram_chat_id"):
        raise HTTPException(400, "set a Telegram chat id first")
    token = get_settings().telegram_bot_token
    enc = row.get("telegram_bot_token_enc")
    if enc:
        from app.crypto import decrypt
        token = decrypt(enc)
    if not token:
        raise HTTPException(400, "no Telegram bot token configured (platform or per-user)")
    res = TelegramChannel(token).send(
        row["telegram_chat_id"],
        "✅ <b>alpaca-options-saas</b> test message — notifications are wired up.",
    )
    if not res.get("ok"):
        raise HTTPException(400, f"Telegram send failed: {res.get('body')}")
    return {"ok": True}
