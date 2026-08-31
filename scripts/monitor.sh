#!/usr/bin/env bash
# Live monitoring dashboard for the paper agent.
#
#   ./scripts/monitor.sh            # refresh every 60s until Ctrl-C
#   ./scripts/monitor.sh 15         # refresh every 15s
#   ./scripts/monitor.sh --once     # print one snapshot and exit (cron/CI)
#
# Pulls, every tick:
#   - PnL snapshot (total / realized / unrealized / today) via `agent pnl`
#   - open option positions + their unrealized PnL
#   - open orders, straight from the Alpaca CLI (independent of the SDK)
#   - market clock
#   - the last few decision-journal lines (fills, risk rejections, errors)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

PY_BIN=".venv/bin/python"
[ -x "$PY_BIN" ] || PY_BIN="python3"
AGENT="$PY_BIN -m alpaca_options_agent.agent.cli"
JOURNAL="logs/agent_journal.jsonl"
ALPACA_BIN="$(command -v alpaca || true)"

INTERVAL=60
ONCE=0
case "${1:-}" in
  --once) ONCE=1 ;;
  "") ;;
  *) INTERVAL="$1" ;;
esac

hr() { printf '%.0s─' $(seq 1 "${COLUMNS:-72}"); echo; }

snapshot() {
  hr
  echo "  ALPACA OPTIONS AGENT — $(date '+%Y-%m-%d %H:%M:%S %Z')"
  hr

  if [ -n "$ALPACA_BIN" ]; then
    "$ALPACA_BIN" clock 2>/dev/null | jq -r '"  market: " + (if .is_open then "OPEN" else "closed" end) + "   next open: " + .next_open' || true
  fi

  local pnl_json
  pnl_json="$($AGENT pnl 2>/dev/null || echo '{}')"

  echo
  echo "  PnL"
  echo "$pnl_json" | jq -r '
    .pnl_snapshot as $s |
    if $s == null then "    (agent pnl failed — check credentials)" else
    "    equity        $" + ($s.equity|tostring) +
    "\n    total PnL      $" + ($s.pnl.total|tostring) + "  (" + (($s.pnl.total_return_pct // 0)|tostring) + "%)" +
    "\n    realized      $" + ($s.pnl.realized_implied|tostring) +
    "\n    unrealized    $" + ($s.pnl.unrealized|tostring) +
    "\n    today         $" + ($s.pnl.today|tostring) + "  (" + (($s.pnl.today_return_pct // 0)|tostring) + "%)" +
    "\n    premium: " + ($s.premium_journal.n_filled|tostring) + " filled / " + ($s.premium_journal.n_rejected|tostring) + " rejected" +
    "  avg slip " + (($s.premium_journal.avg_slippage_bps // "n/a")|tostring) + " bps"
    end'

  echo
  echo "  Open positions"
  echo "$pnl_json" | jq -r '
    (.pnl_snapshot.open_positions // []) as $p |
    if ($p | length) == 0 then "    (none)"
    else $p[] |
      "    " + .symbol + "  qty " + (.qty|tostring) +
      "  entry " + (.avg_entry_price|tostring) +
      "  mark " + ((.current_price // 0)|tostring) +
      "  uPnL $" + (.unrealized_pl|tostring)
    end'

  echo
  echo "  Open orders (Alpaca CLI)"
  if [ -n "$ALPACA_BIN" ]; then
    "$ALPACA_BIN" order list --status open 2>/dev/null | jq -r '
      if (. | length) == 0 then "    (none)"
      else .[] | "    " + .symbol + "  " + .side + "  " + (.qty|tostring) + "  " + .type + "  " + .status
      end' || echo "    (cli error)"
  else
    echo "    (alpaca CLI not installed)"
  fi

  echo
  echo "  Journal tail"
  if [ -f "$JOURNAL" ]; then
    tail -n 6 "$JOURNAL" | jq -r '"    " + (.ts | strftime("%H:%M:%S")) + "  " + .kind +
      (if .kind == "risk_decision" then "  " + .underlying + " approved=" + (.approved|tostring) + " " + (.reasons|join("; "))
       elif .kind == "fill" then "  filled=" + (.fill.filled|tostring) + " realized=" + ((.fill.realized_credit // "n/a")|tostring) + " slip=" + ((.fill.slippage_bps // "n/a")|tostring) + "bps"
       elif .kind == "error" then "  " + .context + ": " + .message
       elif .kind == "note" then "  " + (.message // "")
       else "" end)' 2>/dev/null || tail -n 6 "$JOURNAL"
  else
    echo "    (no journal yet — run \`agent scan\` or \`agent trade --yes\`)"
  fi
  hr
}

if [ "$ONCE" -eq 1 ]; then
  snapshot
  exit 0
fi

while true; do
  clear 2>/dev/null || true
  snapshot
  echo "  refreshing every ${INTERVAL}s — Ctrl-C to stop"
  sleep "$INTERVAL"
done
