import app.notifier as notifier_mod
from app.notifier import Notifier, TelegramChannel, WhatsAppChannel, format_trade_event

FILL_EVENT = {
    "kind": "fill",
    "underlying": "AAPL",
    "payload": {"fill": {
        "filled": True, "contracts": 2,
        "expected_credit": 2.00, "realized_credit": 1.90, "slippage_bps": 50.0,
        "order_id": "ord_123",
        "candidate": {"underlying": "AAPL",
                      "legs": [{"action": "sell_to_open", "quote": {"symbol": "AAPL240P"}}]},
    }},
    "pnl_after": {"equity": 101_000.0, "today": 250.0},
}


def test_format_fill_has_key_facts():
    msg = format_trade_event(FILL_EVENT)
    assert "AAPL" in msg
    assert "FILLED" in msg
    assert "$2.00" in msg and "$1.90" in msg
    assert "50.0 bps" in msg
    assert "ord_123" in msg


def test_format_error_event():
    msg = format_trade_event({"kind": "error", "underlying": "NVDA",
                              "payload": {"context": "NVDA", "message": "boom"}})
    assert "error" in msg.lower() and "boom" in msg


def test_whatsapp_stub_sends_nothing():
    res = WhatsAppChannel().send("+1555", "hi")
    assert res["ok"] is False
    assert res["status"] == "not_implemented"


def test_telegram_channel_posts_to_bot_api(monkeypatch):
    calls = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"ok": True}

        text = '{"ok": true}'

    def fake_post(url, json, timeout):
        calls["url"] = url
        calls["json"] = json
        return FakeResp()

    monkeypatch.setattr(notifier_mod.httpx, "post", fake_post)
    res = TelegramChannel("BOT123").send("999", "hello")
    assert res["ok"] is True
    assert calls["url"].endswith("/botBOT123/sendMessage")
    assert calls["json"]["chat_id"] == "999"
    assert calls["json"]["parse_mode"] == "HTML"


def test_notifier_respects_event_kind_filter(monkeypatch):
    sent = []
    monkeypatch.setattr(notifier_mod.supa_sync, "insert", lambda *a, **k: None)

    ns = {"channels": {"telegram": True, "whatsapp": False},
          "telegram_chat_id": "42", "event_kinds": ["fill"]}
    n = Notifier(settings_row=ns)

    monkeypatch.setattr(TelegramChannel, "send",
                        lambda self, target, text: sent.append((target, text)) or {"ok": True})

    assert n.notify("u1", {"kind": "scan", "payload": {}}) == []      # filtered out
    n.notify("u1", FILL_EVENT)
    assert sent and sent[0][0] == "42"


def test_notifier_logs_failure_but_does_not_raise(monkeypatch):
    logged = []
    monkeypatch.setattr(notifier_mod.supa_sync, "insert",
                        lambda table, row, **k: logged.append(row))
    monkeypatch.setattr(TelegramChannel, "send",
                        lambda self, t, x: (_ for _ in ()).throw(RuntimeError("network")))
    ns = {"channels": {"telegram": True}, "telegram_chat_id": "42", "event_kinds": ["fill"]}
    out = Notifier(settings_row=ns).notify("u1", FILL_EVENT)
    assert out[0]["status"] == "failed"
    assert logged and logged[0]["status"] == "failed"
