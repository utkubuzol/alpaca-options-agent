#!/usr/bin/env bash
# One-shot Telegram wiring for the demo user.
#   ./tg_setup.sh <BOT_TOKEN>
# Steps:
#   1. validate token via getMe
#   2. wait for you to send /start (or any message) to the bot, capture chat_id
#   3. store bot token in web/backend/.env, store chat_id via the API
#   4. send a test message
set -eu
cd "$(dirname "$0")"

TOKEN="${1:?usage: ./tg_setup.sh <BOT_TOKEN>}"
API="http://localhost:8000"
SUPA_URL="https://vcfveqjvsuhgfgtkpkhw.supabase.co"
ANON="sb_publishable_yRGHWe-u1-OOC9TWWS94QQ_4ejnWKgy"
PY=../../.venv/bin/python

echo "== validate token =="
me=$(curl -s "https://api.telegram.org/bot${TOKEN}/getMe")
echo "$me" | "$PY" -c "import sys,json;d=json.load(sys.stdin);assert d['ok'],d;print('bot:',d['result']['username'])"

echo "== send /start to that bot from your Telegram now; waiting for a message... =="
chat_id=""
for i in $(seq 1 60); do
  upd=$(curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates?offset=-1&timeout=10")
  chat_id=$(echo "$upd" | "$PY" -c "
import sys,json
d=json.load(sys.stdin)
r=d.get('result') or []
print(r[-1]['message']['chat']['id'] if r and 'message' in r[-1] else '')
" 2>/dev/null || true)
  [ -n "$chat_id" ] && break
  sleep 2
done
[ -n "$chat_id" ] || { echo "no message received — send /start to the bot and re-run"; exit 1; }
echo "captured chat_id: $chat_id"

echo "== write TELEGRAM_BOT_TOKEN into .env =="
if grep -q '^TELEGRAM_BOT_TOKEN=' .env 2>/dev/null; then
  "$PY" - "$TOKEN" <<'PY'
import sys,pathlib
tok=sys.argv[1]; p=pathlib.Path(".env")
lines=[("TELEGRAM_BOT_TOKEN="+tok) if l.startswith("TELEGRAM_BOT_TOKEN=") else l for l in p.read_text().splitlines()]
p.write_text("\n".join(lines)+"\n")
PY
else
  echo "TELEGRAM_BOT_TOKEN=$TOKEN" >> .env
fi
echo "   done"

echo "== NOTE: restart API + worker separately so the guard Monitor doesn't"
echo "         race the restart (done by the operator, not this script)."

echo "== store chat_id via API for demo user =="
TOK=$(curl -s -X POST "$SUPA_URL/auth/v1/token?grant_type=password" -H "apikey: $ANON" \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@alpaca-saas.local","password":"demo-pass-12345"}' \
  | "$PY" -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -X PUT "$API/api/notification-settings" -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -d "{\"telegram_chat_id\":\"$chat_id\",\"channels\":{\"telegram\":true,\"whatsapp\":false},\"event_kinds\":[\"fill\",\"error\"]}"
echo

echo "== send test message =="
curl -s -X POST "$API/api/notification-settings/test" -H "Authorization: Bearer $TOK"
echo
echo "DONE — check your Telegram."
