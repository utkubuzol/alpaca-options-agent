#!/usr/bin/env bash
# Push secrets from web/backend/.env into Fly, then deploy.
# Run from the repo root (where fly.toml is). Requires `fly auth login` done once.
#
#   ./web/deploy-fly.sh                 # secrets + deploy
#   ./web/deploy-fly.sh --secrets-only  # just sync secrets
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE="web/backend/.env"
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE"; exit 1; }
command -v fly >/dev/null || { echo "install flyctl: https://fly.io/docs/flyctl/install/"; exit 1; }

# Only these keys go to Fly (skip blanks, skip comments).
KEYS="SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY SUPABASE_JWT_SECRET APP_SECRET_KEY TELEGRAM_BOT_TOKEN FRONTEND_ORIGINS"

args=()
while IFS= read -r line; do
  k="${line%%=*}"
  v="${line#*=}"                     # keep the rest verbatim (Fernet keys end in '=')
  case " $KEYS " in *" $k "*) ;; *) continue ;; esac
  [ -n "$v" ] || continue
  args+=("$k=$v")
done < <(grep -E '^[A-Z_]+=' "$ENV_FILE")

echo "== syncing ${#args[@]} secrets to Fly =="
printf '  %s\n' "${args[@]%%=*}"
fly secrets set "${args[@]}" --stage      # --stage: don't restart yet; deploy will

[ "${1:-}" = "--secrets-only" ] && { fly secrets deploy; exit 0; }

echo "== deploy =="
fly deploy --ha=false                      # single machine per process
echo
echo "API:    https://$(fly status --json | python3 -c 'import sys,json;print(json.load(sys.stdin)["Hostname"])' 2>/dev/null || echo '<app>.fly.dev')"
echo "Next:   set NEXT_PUBLIC_API_URL on Vercel to that URL, and add the Vercel"
echo "        domain to FRONTEND_ORIGINS here, then ./web/deploy-fly.sh --secrets-only"
