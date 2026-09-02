#!/usr/bin/env bash
# Worker liveness probe. Exit 0 = healthy, 1 = dead/stale.
#   PID file:  $SCRATCH/worker.pid
#   Log file:  $SCRATCH/worker.log
# "healthy" = process alive AND a heartbeat line ("tick HH:MM:SS") logged in
# the last 180s (worker ticks every 60s).
set -u

SCRATCH="${WORKER_SCRATCH:-/private/tmp/claude-501/-Users-utku-Downloads-alpaca-options-agent/ae61169c-26d5-4628-8a1d-8ea9eb50d564/scratchpad}"
PID_FILE="$SCRATCH/worker.pid"
LOG_FILE="$SCRATCH/worker.log"

fail() { echo "WORKER DOWN: $1"; exit 1; }

[ -f "$PID_FILE" ] || fail "no pid file"
PID="$(cat "$PID_FILE")"
kill -0 "$PID" 2>/dev/null || fail "pid $PID not running"

[ -f "$LOG_FILE" ] || fail "no log file"
LAST_TICK_EPOCH=$(
  /usr/bin/python3 - "$LOG_FILE" <<'PY'
import sys, re, datetime
UTC = datetime.timezone.utc
log = open(sys.argv[1], errors="replace").read().splitlines()
now = datetime.datetime.now(UTC)  # worker logs tick time in UTC
last = None
for line in reversed(log):
    m = re.search(r"tick (\d{2}):(\d{2}):(\d{2})", line)
    if m:
        h, mi, s = map(int, m.groups())
        t = now.replace(hour=h, minute=mi, second=s, microsecond=0)
        if t > now + datetime.timedelta(minutes=1):  # crossed midnight
            t -= datetime.timedelta(days=1)
        last = t
        break
print(int(last.timestamp()) if last else 0)
PY
)

[ "$LAST_TICK_EPOCH" -gt 0 ] || fail "no heartbeat line in log yet"
AGE=$(( $(date +%s) - LAST_TICK_EPOCH ))
[ "$AGE" -lt 180 ] || fail "stale heartbeat (${AGE}s old)"

echo "WORKER OK: pid $PID, last tick ${AGE}s ago"
exit 0
