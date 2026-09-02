# alpaca-options-saas — web layer

Multi-tenant SaaS around the `alpaca_options_agent` package: sign up, store
your own Alpaca **paper** keys, build strategies from a dashboard, watch
trades / PnL live, and get every fill pushed to Telegram (WhatsApp is stubbed
behind the same interface).

```
web/frontend/  Next.js 14 App Router dashboard  (Supabase Auth)
web/backend/   FastAPI API + APScheduler worker  (imports the root package)
supabase/      SQL migrations (schema + RLS)
```

The root Python package is unchanged in behaviour — the CLI still reads
`.env`. The SaaS builds a per-user `AgentConfig` via
`AgentConfig.from_strategy(strategy_row, creds)` and runs the same
`run_cycle()`, only with a Postgres-backed journal (`DBJournal`) that also
fires notifications.

## Architecture

```
Next.js ──Bearer JWT──▶ FastAPI ──service-role──▶ Supabase Postgres (RLS)
                            │
                    AgentConfig.from_strategy + run_cycle(journal=DBJournal)
                            │
                  DBJournal.fill()/error() ─▶ Notifier ─▶ Telegram (live) / WhatsApp (stub)

APScheduler worker ──market-hours gate (broker.get_clock)──▶ same cycle, on a schedule
```

## Supabase project

Already created: **alpaca-options-saas**, ref `vcfveqjvsuhgfgtkpkhw`,
region `us-west-1`. Migrations in `supabase/migrations/` are applied.

- URL: `https://vcfveqjvsuhgfgtkpkhw.supabase.co`
- Publishable (anon) key: `sb_publishable_yRGHWe-u1-OOC9TWWS94QQ_4ejnWKgy`
- **Service-role key** and (if used) **JWT secret**: Dashboard → Project
  Settings → API. Not retrievable via tooling — copy them by hand into
  `web/backend/.env`.

Auth: email + password is enough. For a smoother demo, turn **off** "Confirm
email" in Dashboard → Authentication → Providers → Email.

To re-apply schema from scratch: run the two files in `supabase/migrations/`
in order (SQL editor or `supabase db push`).

## Environment

`web/backend/.env` (see `.env.example`):

| var | what |
|---|---|
| `SUPABASE_URL` | project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | service-role key — RLS bypass, backend only |
| `SUPABASE_JWT_SECRET` | only if the project uses the legacy HS256 secret |
| `APP_SECRET_KEY` | Fernet key — `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
| `TELEGRAM_BOT_TOKEN` | platform bot from @BotFather (users may override per-account) |
| `FRONTEND_ORIGINS` | CORS allow-list, comma-separated |

`web/frontend/.env.local` (see `.env.local.example`): `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`.

## Run locally

Backend:

```bash
cd web/backend
python -m venv .venv && . .venv/bin/activate
pip install -e ../.. -r requirements.txt
cp .env.example .env   # fill it in
uvicorn app.main:app --reload --port 8000
python worker.py       # separate terminal — the scheduler
```

Frontend:

```bash
cd web/frontend
npm install
cp .env.local.example .env.local
npm run dev             # http://localhost:3000
```

Or everything at once:

```bash
export NEXT_PUBLIC_SUPABASE_URL=... NEXT_PUBLIC_SUPABASE_ANON_KEY=... NEXT_PUBLIC_API_URL=http://localhost:8000
docker compose up --build
```

## Onboarding a user

1. Sign up on `/login`.
2. **Settings → Alpaca paper credentials**: paste your paper key id + secret
   (get them at app.alpaca.markets/paper/dashboard/overview), set a baseline
   equity, hit **Test connection**. Keys are Fernet-encrypted at rest.
3. **Settings → Notifications**: DM the platform Telegram bot (or `@userinfobot`)
   to get your numeric chat id, paste it, **Send test**.
4. **Strategies → New strategy**: pick a universe, strategy types
   (`csp` / `covered_call` / `credit_spread`), delta / DTE / profit-target /
   stop / risk caps, and a run interval. **Run scan** for a dry pass, or flip
   **enabled** to let the worker run it every interval during market hours.
5. Watch **Trades** (live SSE) and **Overview** (PnL + equity curve).

Live order submission is locked to **paper**. The `strategies.mode` column can
be `trade` (submits paper orders) but real-money is out of scope.

## Deploy

`render.yaml` at the repo root defines three services (`saas-api`,
`saas-worker`, `saas-web`). `render blueprint launch`, then set the
`sync: false` secrets in the dashboard. Fly.io / Railway equivalents: one
process per Dockerfile (`web/backend/Dockerfile`,
`web/backend/Dockerfile.worker`, `web/frontend/Dockerfile`).

## Tests

```bash
cd web/backend && PYTHONPATH=. pytest      # backend: notifier, DBJournal, routes
cd ../.. && pytest                          # root package incl. from_strategy
```

## Making WhatsApp real

`app/notifier.py::WhatsAppChannel` is a no-op with the same
`send(target, text)` signature as `TelegramChannel`. Two supported paths,
noted in the docstring: Twilio WhatsApp (sandbox, one POST per message) or
Meta WhatsApp Cloud API (approved templates, 24h session window). Wire either
into `send()`; the `Notifier` orchestration, settings, and `notifications_log`
already handle the `whatsapp` channel.
