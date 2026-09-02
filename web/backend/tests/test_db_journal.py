import app.db_journal as dbj
from alpaca_options_agent.monitoring.journal import JournalSink
from app.db_journal import DBJournal


def _capture(monkeypatch):
    rows = []
    monkeypatch.setattr(dbj.supa_sync, "insert",
                        lambda table, row, **k: rows.append((table, row)))
    return rows


def test_dbjournal_satisfies_journalsink_protocol():
    j = DBJournal(user_id="u1")
    assert isinstance(j, JournalSink)


def test_writes_trade_events_rows_with_scoping(monkeypatch):
    rows = _capture(monkeypatch)
    j = DBJournal(user_id="u1", run_id="r1")

    j.scan("AAPL", {"iv_rank": 0.6}, {"regime": "bullish"}, 1)
    j.risk_decision("cid", "AAPL", True, 2, ["ok"])

    assert [t for t, _ in rows] == ["trade_events", "trade_events"]
    for _, row in rows:
        assert row["user_id"] == "u1"
        assert row["run_id"] == "r1"
    assert rows[0][1]["kind"] == "scan"
    assert rows[0][1]["underlying"] == "AAPL"


def test_fill_triggers_notify(monkeypatch):
    _capture(monkeypatch)
    notified = []

    class FakeNotifier:
        def notify(self, user_id, event):
            notified.append((user_id, event["kind"]))

    j = DBJournal(user_id="u1", notifier=FakeNotifier())
    j.fill({"filled": True, "candidate": {"underlying": "AAPL"}})
    j.scan("AAPL", {}, {}, 0)  # not in notify_kinds

    assert notified == [("u1", "fill")]


def test_read_all_mirrors_written_rows_in_journal_shape(monkeypatch):
    _capture(monkeypatch)
    j = DBJournal(user_id="u1")
    j.fill({"filled": True, "expected_credit": 2.0, "realized_credit": 1.8})

    rows = list(j.read_all())
    assert rows[0]["kind"] == "fill"
    assert rows[0]["fill"]["expected_credit"] == 2.0


def test_insert_failure_does_not_raise(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(dbj.supa_sync, "insert", boom)
    j = DBJournal(user_id="u1")
    j.note("still fine")  # must not raise
