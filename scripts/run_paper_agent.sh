#!/usr/bin/env bash
# Cron/CI-friendly entry point. Example crontab (every 15 min, market hours,
# US/Eastern trading hours converted to UTC — adjust for your box's TZ):
#   */15 13-20 * * 1-5 /path/to/run_paper_agent.sh trade >> /path/to/logs/cron.log 2>&1
#
# Usage:
#   ./scripts/run_paper_agent.sh scan          # dry run, no orders
#   ./scripts/run_paper_agent.sh trade         # live pass against the paper account
#   ./scripts/run_paper_agent.sh status
#   ./scripts/run_paper_agent.sh backtest --source synthetic --days 180
#   ./scripts/run_paper_agent.sh report
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

if [ ! -d ".venv" ]; then
  echo "No .venv found — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
fi

PY_BIN=".venv/bin/python"
[ -x "$PY_BIN" ] || PY_BIN="python3"

CMD="${1:-scan}"
shift || true

if [ "$CMD" = "trade" ]; then
  # Skip cleanly when the market is closed so a 15-min cron doesn't fire
  # dozens of no-op cycles overnight. Only gates `trade`; scan/backtest/
  # report/status still run any time. If the CLI isn't available we don't
  # gate (the agent handles a closed market itself, just less efficiently).
  ALPACA_BIN="$(command -v alpaca || true)"
  if [ -n "$ALPACA_BIN" ]; then
    IS_OPEN="$("$ALPACA_BIN" clock 2>/dev/null | grep -o '"is_open":[^,]*' | grep -o 'true\|false' || echo unknown)"
    if [ "$IS_OPEN" = "false" ]; then
      echo "{\"status\":\"skipped\",\"reason\":\"market closed\",\"ts\":\"$(date -u +%FT%TZ)\"}"
      exit 0
    fi
  fi
  exec "$PY_BIN" -m alpaca_options_agent.agent.cli trade --yes "$@"
else
  exec "$PY_BIN" -m alpaca_options_agent.agent.cli "$CMD" "$@"
fi
