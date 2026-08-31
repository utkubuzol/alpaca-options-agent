"""
Cron/CI-friendly command-line entry point for the agent — structured JSON
on stdout, non-zero exit on hard failure, no interactive prompts. Mirrors
the design conventions of Alpaca's own CLI (see broker/cli_bridge.py)
because that's the pattern the hackathon's CLI/MCP requirement is asking
agent builders to adopt, not just "use the SDK from a terminal."

Subcommands:
  scan       — one dry-run pass: generate + risk-screen candidates, no orders sent
  trade      — one live pass against the paper account: generate, screen, execute
  status     — account + open positions (via the SDK, cross-checked via the CLI)
  backtest   — run the synthetic-chain backtest over a date range
  report     — build the sim-to-real gap report from the latest backtest + live journal
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from alpaca_options_agent.backtest.data_loader import load_from_alpaca, synthetic_gbm_closes
from alpaca_options_agent.backtest.engine import BacktestConfig, run_backtest
from alpaca_options_agent.broker.client import AlpacaBroker
from alpaca_options_agent.config import CONFIG
from alpaca_options_agent.monitoring.report import build_gap_report


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_scan(args: argparse.Namespace) -> int:
    from alpaca_options_agent.agent.runner import run_cycle

    results = run_cycle(CONFIG, dry_run=True)
    _print({"status": "ok", "dry_run": True, "results": results})
    return 0


def cmd_trade(args: argparse.Namespace) -> int:
    from alpaca_options_agent.agent.runner import run_cycle

    if not args.yes:
        _print({
            "status": "aborted",
            "reason": "trade requires --yes to confirm live (paper) order submission",
        })
        return 1
    results = run_cycle(CONFIG, dry_run=False)
    _print({"status": "ok", "dry_run": False, "results": results})
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    CONFIG.validate_credentials()
    broker = AlpacaBroker()
    account = broker.get_account()
    positions = broker.get_positions()
    orders = broker.get_open_orders()

    from alpaca_options_agent.broker.cli_bridge import AlpacaCli, AlpacaCliUnavailable
    cli_status = {"available": False}
    try:
        cli = AlpacaCli()
        cli_status = {"available": True, "account": cli.account_get()}
    except AlpacaCliUnavailable as e:
        cli_status = {"available": False, "reason": str(e)}

    _print({
        "status": "ok",
        "account_sdk": account,
        "positions": positions,
        "open_orders": orders,
        "cli_cross_check": cli_status,
    })
    return 0


def cmd_pnl(args: argparse.Namespace) -> int:
    from alpaca_options_agent.monitoring.pnl import build_pnl_snapshot

    CONFIG.validate_credentials()
    broker = AlpacaBroker()
    account = broker.get_account()
    positions = broker.get_positions()

    cli_equity = None
    from alpaca_options_agent.broker.cli_bridge import AlpacaCli, AlpacaCliUnavailable
    try:
        acct_cli = AlpacaCli().account_get()
        cli_equity = float(acct_cli.get("equity")) if acct_cli.get("equity") is not None else None
    except (AlpacaCliUnavailable, TypeError, ValueError):
        cli_equity = None

    snapshot = build_pnl_snapshot(
        account=account,
        positions=positions,
        baseline_equity=CONFIG.baseline_equity,
        journal_path=CONFIG.log_dir / "agent_journal.jsonl",
        cli_equity=cli_equity,
    )
    _print({"status": "ok", "pnl_snapshot": snapshot})
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    universe = args.universe.split(",") if args.universe else CONFIG.universe
    end = date.fromisoformat(args.end) if args.end else date.today()
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=args.days)

    if args.source == "synthetic":
        closes, dates = synthetic_gbm_closes(universe, start, end, seed=args.seed)
    else:
        CONFIG.validate_credentials()
        closes, dates = load_from_alpaca(CONFIG.api_key, CONFIG.secret_key, universe, start, end)

    bt_cfg = BacktestConfig(universe=universe, starting_equity=args.equity)
    result = run_backtest(closes, dates, CONFIG, bt_cfg)

    out_dir = CONFIG.log_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": result.summary(),
        "trades": [t.__dict__ for t in result.trades],
        "equity_curve": result.equity_curve,
        "dates": result.dates,
        "config": {"universe": universe, "start": start.isoformat(), "end": end.isoformat(),
                    "source": args.source, "starting_equity": args.equity},
    }
    (out_dir / "backtest_result.json").write_text(json.dumps(payload, indent=2, default=str))

    _print({"status": "ok", "summary": result.summary(), "n_trades": len(result.trades),
            "saved_to": str(out_dir / "backtest_result.json")})
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    bt_path = CONFIG.log_dir / "backtest_result.json"
    bt_summary, bt_trades = None, None
    if bt_path.exists():
        payload = json.loads(bt_path.read_text())
        bt_summary, bt_trades = payload["summary"], payload["trades"]

    out_path = CONFIG.log_dir / "gap_report.md"
    report = build_gap_report(bt_summary, bt_trades, CONFIG.log_dir / "agent_journal.jsonl", out_path)
    _print({"status": "ok", "report": report, "saved_to": str(out_path)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent", description="Alpaca Options Alpha Agent CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="dry-run: generate and risk-screen candidates, no orders").set_defaults(func=cmd_scan)

    trade_p = sub.add_parser("trade", help="live pass against the paper account")
    trade_p.add_argument("--yes", action="store_true", help="confirm live (paper) order submission")
    trade_p.set_defaults(func=cmd_trade)

    sub.add_parser("status", help="account, positions, open orders").set_defaults(func=cmd_status)

    sub.add_parser(
        "pnl", help="realized / unrealized / today PnL + premium-journal stats"
    ).set_defaults(func=cmd_pnl)

    bt_p = sub.add_parser("backtest", help="run the synthetic-chain backtest")
    bt_p.add_argument("--universe", type=str, default=None, help="comma-separated tickers")
    bt_p.add_argument("--start", type=str, default=None, help="YYYY-MM-DD")
    bt_p.add_argument("--end", type=str, default=None, help="YYYY-MM-DD")
    bt_p.add_argument("--days", type=int, default=180, help="lookback if --start omitted")
    bt_p.add_argument("--equity", type=float, default=100_000.0)
    bt_p.add_argument("--seed", type=int, default=7)
    bt_p.add_argument("--source", choices=["alpaca", "synthetic"], default="synthetic",
                       help="'alpaca' pulls real historical stock closes (needs API keys); "
                            "'synthetic' uses a seeded GBM generator (no keys needed, for smoke-testing)")
    bt_p.set_defaults(func=cmd_backtest)

    sub.add_parser("report", help="build the sim-to-real gap report").set_defaults(func=cmd_report)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:  # noqa: BLE001 — CLI boundary: always emit JSON, never a bare traceback
        _print({"status": "error", "error": str(e)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
