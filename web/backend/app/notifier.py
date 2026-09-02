"""Per-trade notifications. Telegram is live; WhatsApp is a wired stub.

Both channels implement `Channel.send(chat_target, text) -> dict`. The
`Notifier` decides *which* channels fire for a given event (from the user's
`notification_settings`), formats the message once, sends, and records every
attempt in `notifications_log`.

Called from two places, both synchronous:
  * the API, via FastAPI BackgroundTasks after a manual `/run`
  * the worker, inline after a scheduled cycle
so everything here is blocking `httpx`, no event loop needed.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Protocol

import httpx

from app import supa_sync
from app.crypto import decrypt
from app.settings import get_settings

logger = logging.getLogger("saas.notifier")

TELEGRAM_API = "https://api.telegram.org"


# ------------------------------------------------------------------ #
# Message formatting
# ------------------------------------------------------------------ #
def _fmt_money(v) -> str:
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def format_trade_event(event: Dict) -> str:
    """One human line-set for a journal event. `event` shape:
    {kind, underlying, ts, payload, pnl_after?}. Plain text with light
    Telegram HTML.
    """
    kind = event.get("kind", "event")
    underlying = event.get("underlying") or event.get("payload", {}).get("underlying") or "?"
    p = event.get("payload") or {}

    if kind == "fill":
        f = p.get("fill", p)
        legs = f.get("candidate", {}).get("legs") or p.get("legs") or []
        leg_txt = ", ".join(
            f"{l.get('action','?')} {l.get('quote',{}).get('symbol', l.get('symbol','?'))}"
            for l in legs
        ) or f.get("strategy_type", "")
        status = "✅ FILLED" if f.get("filled") else "❌ not filled"
        lines = [
            f"<b>{status}</b> — {underlying}",
            f"{leg_txt}" if leg_txt else "",
            f"Contracts: {f.get('contracts', '?')}",
            f"Expected credit: {_fmt_money(f.get('expected_credit'))} · "
            f"Realized: {_fmt_money(f.get('realized_credit'))}",
        ]
        if f.get("slippage_bps") is not None:
            lines.append(f"Slippage: {f['slippage_bps']:.1f} bps")
        if f.get("order_id"):
            lines.append(f"Order: <code>{f['order_id']}</code>")
        if event.get("pnl_after"):
            pa = event["pnl_after"]
            lines.append(
                f"Account equity: {_fmt_money(pa.get('equity'))} "
                f"(today {_fmt_money(pa.get('today'))})"
            )
        return "\n".join(x for x in lines if x)

    if kind == "risk_decision":
        return (
            f"🛡️ <b>Risk {'approved' if p.get('approved') else 'blocked'}</b> — {underlying}\n"
            f"Sized: {p.get('sized_contracts', '?')} contracts\n"
            f"{'; '.join(p.get('reasons', []))}"
        )

    if kind == "error":
        return f"⚠️ <b>Agent error</b> — {p.get('context', underlying)}\n{p.get('message', '')}"

    if kind == "candidate":
        c = p.get("candidate", p)
        return (
            f"💡 <b>Candidate</b> — {underlying}\n"
            f"{c.get('strategy_type', '?')} · score {c.get('signal_score', '?')} · "
            f"credit {_fmt_money(c.get('net_credit_per_contract'))}"
        )

    return f"ℹ️ <b>{kind}</b> — {underlying}\n{p}"


# ------------------------------------------------------------------ #
# Channels
# ------------------------------------------------------------------ #
class Channel(Protocol):
    name: str

    def send(self, target: str, text: str) -> Dict: ...


class TelegramChannel:
    name = "telegram"

    def __init__(self, bot_token: str):
        if not bot_token:
            raise ValueError("Telegram bot token is not configured")
        self._token = bot_token

    def send(self, target: str, text: str) -> Dict:
        r = httpx.post(
            f"{TELEGRAM_API}/bot{self._token}/sendMessage",
            json={"chat_id": target, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=15.0,
        )
        ok = r.status_code == 200 and r.json().get("ok") is True
        return {"ok": ok, "status_code": r.status_code, "body": r.text[:500]}


class WhatsAppChannel:
    """STUB. Same interface as TelegramChannel; sends nothing.

    To make this real, pick one:
      * Twilio WhatsApp — POST https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json
        with From='whatsapp:+14155238886' (sandbox), To='whatsapp:{target}', Body=text.
      * Meta WhatsApp Cloud API — POST https://graph.facebook.com/v21.0/{phone_number_id}/messages
        with an approved template (free-form only allowed inside a 24h user-initiated window).
    """

    name = "whatsapp"

    def send(self, target: str, text: str) -> Dict:
        logger.info("WhatsApp stub — would send to %s: %s", target, text[:80])
        return {"ok": False, "status": "not_implemented"}


# ------------------------------------------------------------------ #
# Orchestrator
# ------------------------------------------------------------------ #
class Notifier:
    def __init__(self, settings_row: Optional[Dict] = None):
        self._settings = settings_row  # if None, loaded per call

    def _load_settings(self, user_id: str) -> Optional[Dict]:
        if self._settings is not None:
            return self._settings
        return supa_sync.select(
            "notification_settings", eq={"user_id": user_id}, single=True
        )

    def _telegram_token(self, ns: Dict) -> str:
        enc = ns.get("telegram_bot_token_enc")
        if enc:
            try:
                return decrypt(enc)
            except Exception:  # noqa: BLE001 — fall back to platform bot
                logger.warning("bad per-user telegram token; using platform bot")
        return get_settings().telegram_bot_token

    def notify(self, user_id: str, event: Dict) -> List[Dict]:
        """Fire every enabled channel for this event. Returns per-channel results."""
        ns = self._load_settings(user_id)
        if not ns:
            return []
        kind = event.get("kind", "event")
        allowed = ns.get("event_kinds") or ["fill", "error"]
        if kind not in allowed:
            return []

        channels_cfg = ns.get("channels") or {}
        text = format_trade_event(event)
        results: List[Dict] = []

        if channels_cfg.get("telegram") and ns.get("telegram_chat_id"):
            results.append(self._dispatch(
                user_id, TelegramChannel(self._telegram_token(ns)),
                ns["telegram_chat_id"], text, event,
            ))
        if channels_cfg.get("whatsapp") and ns.get("whatsapp_number"):
            results.append(self._dispatch(
                user_id, WhatsAppChannel(), ns["whatsapp_number"], text, event,
            ))
        return results

    def _dispatch(self, user_id: str, channel: Channel, target: str, text: str,
                  event: Dict) -> Dict:
        status = "sent"
        err = None
        try:
            res = channel.send(target, text)
            if not res.get("ok"):
                status = "failed" if channel.name == "telegram" else "skipped"
                err = res.get("body") or res.get("status")
        except Exception as e:  # noqa: BLE001 — a bad channel must not kill the cycle
            status, err = "failed", str(e)
            logger.exception("notify via %s failed", channel.name)
        try:
            supa_sync.insert("notifications_log", {
                "user_id": user_id,
                "channel": channel.name,
                "event_ref": event.get("kind"),
                "status": status,
                "error": (err or "")[:1000] or None,
            }, returning=False)
        except Exception:  # noqa: BLE001
            logger.exception("could not write notifications_log")
        return {"channel": channel.name, "status": status, "error": err}
