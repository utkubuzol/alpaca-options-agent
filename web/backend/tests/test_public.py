"""Public (unauthenticated) showcase + quotes endpoints."""
import app.showcase as sc
from app.showcase import build_showcase, classify_gate, get_quotes


def _reset(monkeypatch, uid="show-user"):
    sc._cache.clear()
    monkeypatch.setattr(sc.get_settings(), "showcase_user_id", uid, raising=False)


SCAN = {"id": 1, "ts": "2026-09-02T13:31:00Z", "kind": "scan", "underlying": "AAPL",
        "payload": {"vol_signal": {"iv_rank": 0.77}, "trend_signal": {"regime": "bullish"}}}
CAND = {"id": 2, "ts": "2026-09-02T13:31:01Z", "kind": "candidate", "underlying": "AAPL",
        "payload": {"candidate": {"id": "c1", "strategy_type": "put_credit_spread",
                                  "max_profit_per_contract": 68, "max_loss_per_contract": 432,
                                  "legs": [{"quote": {"strike": 190}}, {"quote": {"strike": 185}}]}}}
REJ = {"id": 3, "ts": "2026-09-02T13:31:02Z", "kind": "risk_decision", "underlying": "SPY",
       "payload": {"candidate_id": "c1", "approved": False, "sized_contracts": 0,
                   "reasons": ["single-underlying concentration cap reached for SPY"]}}
FILL = {"id": 4, "ts": "2026-09-02T13:31:03Z", "kind": "fill", "underlying": "AAPL",
        "payload": {"fill": {"filled": True, "expected_credit": 2.0, "realized_credit": 1.9,
                             "slippage_bps": 50.0}}}


def test_classify_gate_maps_known_reasons():
    assert classify_gate("single-underlying concentration cap reached") == "Single-name concentration"
    assert classify_gate("daily drawdown breaker tripped") == "Daily drawdown breaker"
    assert classify_gate("bid-ask spread too wide") == "Bid-ask spread ceiling"


def test_showcase_empty_when_no_showcase_user(monkeypatch):
    _reset(monkeypatch, uid="")
    out = build_showcase()
    assert out["recordCount"] == 0 and out["ivRank"] is None and out["mode"] is None


def test_showcase_aggregates_events(monkeypatch):
    _reset(monkeypatch)

    def fake_select(table, **kw):
        if table == "trade_events":
            return [SCAN, CAND, REJ, FILL]
        if table == "strategies":
            return [{"params": {"iv_rank_entry_threshold": 0.6}}]
        return []

    monkeypatch.setattr(sc.supa_sync, "select", fake_select)
    out = build_showcase()

    assert out["mode"] == "live"
    assert out["recordCount"] == 4
    assert out["ivRank"] == [0.77]
    assert out["ivThreshold"] == 0.6
    assert out["payoff"] and out["payoff"][0]["pnl"] == -432  # flat max-loss floor
    assert out["rejections"][0]["gate"] == "Single-name concentration"
    assert out["rejections"][0]["strategy"] == "put_credit_spread"
    assert out["fills"] == [{"trade": 1, "expected": 2.0, "realized": 1.9}]
    assert out["stats"]["fills"] == 1 and out["stats"]["rejected"] == 1
    assert out["stats"]["avgSlippageBps"] == 50


def test_showcase_cache_serves_one_upstream_read(monkeypatch):
    _reset(monkeypatch)
    calls = {"n": 0}

    def fake_select(table, **kw):
        calls["n"] += 1
        return [] if table == "trade_events" else []

    monkeypatch.setattr(sc.supa_sync, "select", fake_select)
    build_showcase()
    n_after_first = calls["n"]
    build_showcase()
    assert calls["n"] == n_after_first  # second call fully cached


def test_quotes_allowlist_and_shape(monkeypatch):
    _reset(monkeypatch)

    class FakeBroker:
        def get_underlying_price(self, s):
            return 100.0
        def get_historical_closes(self, s, lookback_days=3):
            return [90.0, 95.0, 100.0]

    monkeypatch.setattr(sc, "_showcase_broker", lambda: FakeBroker())
    out = get_quotes(["spy", "notareal", "aapl"])
    syms = {q["symbol"] for q in out}
    assert syms == {"SPY", "AAPL"}  # "NOTAREAL" filtered by allowlist
    q = out[0]
    assert q["price"] == 100.0 and q["prevClose"] == 95.0 and q["changePct"] == 5.26


def test_endpoints_need_no_auth(client, monkeypatch):
    _reset(monkeypatch, uid="")
    monkeypatch.setattr(sc, "_showcase_broker", lambda: None)
    assert client.get("/api/public/showcase").status_code == 200
    assert client.get("/api/public/quotes?symbols=SPY").status_code == 200
