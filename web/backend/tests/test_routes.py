"""Route-level tests with auth, Supa, and the broker all faked."""
import app.routers.account as account_mod
import app.routers.strategies as strat_mod
from app.deps import get_broker, get_supa
from app.main import app
from tests.conftest import TEST_USER


class FakeSupa:
    def __init__(self):
        self.strategies = []
        self.broker_credentials = {}
        self.trade_events = []
        self.positions_snapshots = []

    async def select(self, table, *, columns="*", eq=None, order=None, limit=None,
                      lt=None, gte=None, in_=None, single=False):
        eq = eq or {}
        if table == "strategies":
            rows = [s for s in self.strategies
                    if all(s.get(k) == v for k, v in eq.items())]
        elif table == "broker_credentials":
            row = self.broker_credentials
            rows = [row] if row and all(row.get(k) == v for k, v in eq.items()) else []
        elif table == "trade_events":
            rows = [e for e in self.trade_events
                    if all(str(e.get(k)) == str(v) for k, v in eq.items())]
        elif table == "positions_snapshots":
            rows = list(self.positions_snapshots)
        else:
            rows = []
        if single:
            return rows[0] if rows else None
        return rows[:limit] if limit else rows

    async def insert(self, table, row, *, returning=True):
        getattr(self, table).append({**row, "id": len(getattr(self, table)) + 1})
        return getattr(self, table)[-1]

    async def update(self, table, patch, *, eq):
        for r in getattr(self, table):
            if all(str(r.get(k)) == str(v) for k, v in eq.items()):
                r.update(patch)
                return r
        return None

    async def upsert(self, table, row, *, on_conflict):
        setattr(self, table, row)
        return row

    async def delete(self, table, *, eq):
        lst = getattr(self, table)
        setattr(self, table, [r for r in lst
                              if not all(str(r.get(k)) == str(v) for k, v in eq.items())])


class FakeBroker:
    def get_account(self):
        return {"equity": 101_000.0, "last_equity": 100_500.0, "cash": 80_000.0}

    def get_positions(self):
        return [{"symbol": "AAPL240920P00190000", "asset_class": "us_option",
                 "qty": -1, "avg_entry_price": 2.5, "current_price": 1.0,
                 "market_value": -100.0, "unrealized_pl": 150.0}]


def _wire(fake_supa):
    app.dependency_overrides[get_supa] = lambda: fake_supa
    app.dependency_overrides[get_broker] = lambda: FakeBroker()


def test_pnl_endpoint_shapes_snapshot(client):
    fs = FakeSupa()
    fs.trade_events.append({"user_id": TEST_USER["id"], "kind": "fill",
                            "payload": {"fill": {"filled": True, "expected_credit": 2.0,
                                                 "realized_credit": 1.9, "slippage_bps": 50.0}}})
    fs.positions_snapshots.append({"ts": "2026-09-01T00:00:00Z", "equity": 100_500.0,
                                   "pnl": {"total": 500.0}})
    fs.broker_credentials = {"user_id": TEST_USER["id"],
                             "alpaca_api_key_enc": _enc("KEYKEYKEY"),
                             "alpaca_secret_key_enc": _enc("SECSECSEC"),
                             "paper": True, "baseline_equity": 100_000.0}
    _wire(fs)

    r = client.get("/api/pnl")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pnl"]["total"] == 1_000.0
    assert body["pnl"]["unrealized"] == 150.0
    assert body["premium_journal"]["n_filled"] == 1
    assert body["equity_curve"][0]["total"] == 500.0
    app.dependency_overrides.pop(get_supa, None)
    app.dependency_overrides.pop(get_broker, None)


def test_strategy_create_validates_and_persists(client):
    fs = FakeSupa()
    _wire(fs)
    payload = {
        "name": "20d CSP",
        "universe": ["spy", "aapl"],
        "strategy_types": ["csp"],
        "params": {"target_delta": 0.2, "min_dte": 30, "max_dte": 45},
        "interval_minutes": 30,
    }
    r = client.post("/api/strategies", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["universe"] == ["SPY", "AAPL"]
    assert fs.strategies[0]["user_id"] == TEST_USER["id"]

    listed = client.get("/api/strategies")
    assert listed.json()["strategies"][0]["name"] == "20d CSP"
    app.dependency_overrides.pop(get_supa, None)
    app.dependency_overrides.pop(get_broker, None)


def test_strategy_create_rejects_bad_type(client):
    fs = FakeSupa()
    _wire(fs)
    r = client.post("/api/strategies", json={"name": "x", "strategy_types": ["iron_condor"]})
    assert r.status_code == 422
    app.dependency_overrides.pop(get_supa, None)
    app.dependency_overrides.pop(get_broker, None)


def test_run_now_queues_background_task(client, monkeypatch):
    fs = FakeSupa()
    fs.strategies.append({"id": "s1", "user_id": TEST_USER["id"], "name": "s",
                          "universe": ["SPY"], "strategy_types": ["csp"], "params": {},
                          "risk": {}, "mode": "scan", "interval_minutes": 15})
    fs.broker_credentials = {"user_id": TEST_USER["id"],
                             "alpaca_api_key_enc": _enc("KEYKEYKEY"),
                             "alpaca_secret_key_enc": _enc("SECSECSEC"),
                             "paper": True, "baseline_equity": 100_000.0}
    _wire(fs)
    called = {}
    monkeypatch.setattr(strat_mod, "run_strategy_cycle",
                        lambda *a, **k: called.setdefault("args", a))

    r = client.post("/api/strategies/s1/run?mode=scan")
    assert r.status_code == 200
    assert r.json()["queued"] is True
    assert called["args"][0] == TEST_USER["id"]
    app.dependency_overrides.pop(get_supa, None)
    app.dependency_overrides.pop(get_broker, None)


def _enc(s):
    from app.crypto import encrypt
    return encrypt(s)
