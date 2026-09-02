#!/usr/bin/env bash
# Autonomous worker guard: probe worker every 60s. On state change, print one
# line (→ a chat notification). On DOWN, try one restart, then report the
# result. Meant to run under the Monitor tool (persistent).
set -u
cd "$(dirname "$0")"

SCRATCH="${WORKER_SCRATCH:-/private/tmp/claude-501/-Users-utku-Downloads-alpaca-options-agent/ae61169c-26d5-4628-8a1d-8ea9eb50d564/scratchpad}"
PID_FILE="$SCRATCH/worker.pid"
LOG_FILE="$SCRATCH/worker.log"
VENV_PY="../../.venv/bin/python"

start_worker() {
  nohup "$VENV_PY" worker.py >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
}

prev="init"
while true; do
  if probe=$(./worker_status.sh 2>&1); then
    state="OK"
  else
    state="DOWN"
  fi

  if [ "$state" = "DOWN" ]; then
    echo "$(date -u +%H:%M:%SZ) worker DOWN — $probe — restarting"
    start_worker
    sleep 12
    if probe2=$(./worker_status.sh 2>&1); then
      echo "$(date -u +%H:%M:%SZ) worker RECOVERED — $probe2"
      prev="OK"
    else
      echo "$(date -u +%H:%M:%SZ) worker RESTART FAILED — $probe2 — check $LOG_FILE"
      prev="DOWN"
    fi
  else
    [ "$prev" != "OK" ] && echo "$(date -u +%H:%M:%SZ) worker OK — $probe"
    prev="OK"
  fi

  sleep 60
done
