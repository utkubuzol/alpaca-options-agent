# Deploy — 24/7, no laptop

Supabase is already cloud (`alpaca-options-saas`, ref `vcfveqjvsuhgfgtkpkhw`).
Two more pieces:

| piece | host | why |
|---|---|---|
| API + worker (`web/backend/`) | **Fly.io** — one app, two processes | worker is a long-lived loop; Fly runs always-on containers |
| dashboard (`web/frontend/`) | **Vercel** | native Next.js, free, auto-deploy on push |

---

## 1. Fly.io — API + worker

One-time:

```bash
brew install flyctl          # or: curl -L https://fly.io/install.sh | sh
fly auth login
cd <repo root>               # where fly.toml is
fly launch --no-deploy --copy-config --name YOUR-APP-NAME
```

`fly.toml` already defines both processes (`web` = uvicorn, `worker` =
`python worker.py`) off the single `web/backend/Dockerfile`.

Deploy (syncs secrets from `web/backend/.env`, then ships):

```bash
./web/deploy-fly.sh
```

That pushes `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`,
`APP_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `FRONTEND_ORIGINS` as Fly secrets.

API is then at `https://YOUR-APP-NAME.fly.dev` (health: `/health`).

Check the worker:

```bash
fly logs -a YOUR-APP-NAME | grep tick     # heartbeat every 60s
fly status -a YOUR-APP-NAME               # 2 machines: web + worker
```

---

## 2. Vercel — dashboard

1. vercel.com → **Add New Project** → import `utkubuzol/alpaca-options-agent`
2. **Root Directory**: `web/frontend`
3. Framework preset: Next.js (auto)
4. **Environment Variables**:
   - `NEXT_PUBLIC_SUPABASE_URL` = `https://vcfveqjvsuhgfgtkpkhw.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = `sb_publishable_yRGHWe-u1-OOC9TWWS94QQ_4ejnWKgy`
   - `NEXT_PUBLIC_API_URL` = `https://YOUR-APP-NAME.fly.dev`
5. Deploy → `https://YOUR-PROJECT.vercel.app`

---

## 3. Wire CORS

Add the Vercel domain to Fly's `FRONTEND_ORIGINS`, then re-sync:

```bash
# edit web/backend/.env:
# FRONTEND_ORIGINS=http://localhost:3000,https://YOUR-PROJECT.vercel.app
./web/deploy-fly.sh --secrets-only
```

---

## 4. Supabase auth redirect

Supabase dashboard → Authentication → URL Configuration → add
`https://YOUR-PROJECT.vercel.app` to **Redirect URLs** and set **Site URL**.

---

## Done

- Push to `main` → Vercel redeploys the dashboard automatically.
- `./web/deploy-fly.sh` → ships API + worker.
- Worker ticks every 60s on Fly, runs enabled strategies each `interval_minutes`
  while the market is open, submits paper orders in `mode=trade`, pushes fills
  to Telegram. Independent of any laptop.

## Local dev is unchanged

`docker compose up` or the two dev servers — see `web/README.md`.
