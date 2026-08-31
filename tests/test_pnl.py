"""PnL snapshot math — pure-dict in, no network."""
import json

from alpaca_options_agent.monitoring.pnl import build_pnl_snapshot, premium_journal_stats


def test_total_splits_into_realized_and_unrealized():
    account = {"equity": 105_000.0, "last_equity": 104_000.0, "cash": 60_000.0}
    positions = [
        {"symbol": "AAPL260101P00190000", "qty": -1, "avg_entry_price": 2.5,
         "current_price": 1.0, "market_value": -100.0, "unrealized_pl": 150.0},
    ]
    snap = build_pnl_snapshot(account, positions, baseline_equity=100_000.0,
                               journal_path="/nonexistent.jsonl")

    assert snap["pnl"]["total"] == 5_000.0
    assert snap["pnl"]["unrealized"] == 150.0
    # realized is implied so realized + unrealized == total, always
    assert snap["pnl"]["realized_implied"] == 5_000.0 - 150.0
    assert snap["pnl"]["today"] == 1_000.0


def test_cli_cross_check_flag():
    account = {"equity": 100_000.0, "last_equity": 100_000.0, "cash": 100_000.0}
    ok = build_pnl_snapshot(account, [], 100_000.0, "/nope", cli_equity=100_000.0)
    bad = build_pnl_snapshot(account, [], 100_000.0, "/nope", cli_equity=99_000.0)
    assert ok["cli_cross_check"]["matches_sdk"] is True
    assert bad["cli_cross_check"]["matches_sdk"] is False


def test_premium_journal_stats_reads_fills(tmp_path):
    j = tmp_path / "journal.jsonl"
    rows = [
        {"ts": 1, "kind": "scan", "underlying": "AAPL"},
        {"ts": 2, "kind": "fill", "fill": {"filled": True, "expected_credit": 2.00,
         "realized_credit": 1.90, "slippage_bps": 50.0}},
        {"ts": 3, "kind": "fill", "fill": {"filled": False, "expected_credit": 1.0,
         "realized_credit": None, "slippage_bps": None}},
    ]
    j.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    stats = premium_journal_stats(j)
    assert stats["n_fills"] == 2
    assert stats["n_filled"] == 1
    assert stats["n_rejected"] == 1
    assert stats["credit_given_up_per_contract"] == 0.1
    assert stats["avg_slippage_bps"] == 50.0
