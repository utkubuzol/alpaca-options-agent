-- alpaca-options-saas — initial schema
-- Multi-tenant: every row is scoped to auth.users.id. The FastAPI backend
-- talks to Postgres with the service-role key (RLS bypassed) and filters by
-- user_id itself; the RLS policies below are the safety net for any direct
-- (frontend / anon-key) access.

-- ------------------------------------------------------------------ --
-- profiles
-- ------------------------------------------------------------------ --
create table if not exists public.profiles (
    id           uuid primary key references auth.users (id) on delete cascade,
    display_name text,
    created_at   timestamptz not null default now()
);
alter table public.profiles enable row level security;

create policy profiles_self_select on public.profiles
    for select using (id = auth.uid());
create policy profiles_self_upsert on public.profiles
    for insert with check (id = auth.uid());
create policy profiles_self_update on public.profiles
    for update using (id = auth.uid());

-- ------------------------------------------------------------------ --
-- broker_credentials  (one row per user; secrets are Fernet-encrypted app-side)
-- ------------------------------------------------------------------ --
create table if not exists public.broker_credentials (
    user_id               uuid primary key references auth.users (id) on delete cascade,
    alpaca_api_key_enc    text not null,
    alpaca_secret_key_enc text not null,
    paper                 boolean not null default true,
    baseline_equity       numeric not null default 100000,
    updated_at            timestamptz not null default now()
);
alter table public.broker_credentials enable row level security;
create policy broker_credentials_self on public.broker_credentials
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ------------------------------------------------------------------ --
-- strategies
-- ------------------------------------------------------------------ --
create table if not exists public.strategies (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null references auth.users (id) on delete cascade,
    name            text not null,
    enabled         boolean not null default false,
    universe        text[] not null default '{}',
    strategy_types  text[] not null default '{csp,covered_call,credit_spread}',
    params          jsonb  not null default '{}'::jsonb,
    risk            jsonb  not null default '{}'::jsonb,
    mode            text   not null default 'scan' check (mode in ('scan', 'trade')),
    interval_minutes int   not null default 15 check (interval_minutes >= 1),
    last_run_at     timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index if not exists strategies_user_idx on public.strategies (user_id);
create index if not exists strategies_due_idx on public.strategies (enabled, last_run_at)
    where enabled;
alter table public.strategies enable row level security;
create policy strategies_self on public.strategies
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ------------------------------------------------------------------ --
-- runs
-- ------------------------------------------------------------------ --
create table if not exists public.runs (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users (id) on delete cascade,
    strategy_id uuid references public.strategies (id) on delete set null,
    mode        text not null,
    status      text not null default 'running' check (status in ('running', 'ok', 'error')),
    started_at  timestamptz not null default now(),
    finished_at timestamptz,
    summary     jsonb
);
create index if not exists runs_user_started_idx on public.runs (user_id, started_at desc);
alter table public.runs enable row level security;
create policy runs_self on public.runs
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ------------------------------------------------------------------ --
-- trade_events  (DB mirror of the JSONL decision journal; powers the feed)
-- ------------------------------------------------------------------ --
create table if not exists public.trade_events (
    id         bigint generated always as identity primary key,
    user_id    uuid not null references auth.users (id) on delete cascade,
    run_id     uuid references public.runs (id) on delete cascade,
    ts         timestamptz not null default now(),
    kind       text not null,
    underlying text,
    payload    jsonb not null default '{}'::jsonb
);
create index if not exists trade_events_user_id_desc_idx on public.trade_events (user_id, id desc);
create index if not exists trade_events_user_kind_idx on public.trade_events (user_id, kind);
alter table public.trade_events enable row level security;
create policy trade_events_self on public.trade_events
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ------------------------------------------------------------------ --
-- positions_snapshots  (equity curve / history)
-- ------------------------------------------------------------------ --
create table if not exists public.positions_snapshots (
    id        bigint generated always as identity primary key,
    user_id   uuid not null references auth.users (id) on delete cascade,
    ts        timestamptz not null default now(),
    equity    numeric,
    cash      numeric,
    pnl       jsonb,
    positions jsonb
);
create index if not exists positions_snapshots_user_ts_idx
    on public.positions_snapshots (user_id, ts desc);
alter table public.positions_snapshots enable row level security;
create policy positions_snapshots_self on public.positions_snapshots
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ------------------------------------------------------------------ --
-- notification_settings
-- ------------------------------------------------------------------ --
create table if not exists public.notification_settings (
    user_id                 uuid primary key references auth.users (id) on delete cascade,
    telegram_chat_id        text,
    telegram_bot_token_enc  text,
    whatsapp_number         text,
    channels                jsonb  not null default '{"telegram": true, "whatsapp": false}'::jsonb,
    event_kinds             text[] not null default '{fill,error}',
    updated_at              timestamptz not null default now()
);
alter table public.notification_settings enable row level security;
create policy notification_settings_self on public.notification_settings
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ------------------------------------------------------------------ --
-- notifications_log
-- ------------------------------------------------------------------ --
create table if not exists public.notifications_log (
    id        bigint generated always as identity primary key,
    user_id   uuid not null references auth.users (id) on delete cascade,
    ts        timestamptz not null default now(),
    channel   text not null,
    event_ref text,
    status    text not null,
    error     text
);
create index if not exists notifications_log_user_ts_idx
    on public.notifications_log (user_id, ts desc);
alter table public.notifications_log enable row level security;
create policy notifications_log_self on public.notifications_log
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ------------------------------------------------------------------ --
-- new-user bootstrap: profile + default notification_settings row
-- ------------------------------------------------------------------ --
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, display_name)
        values (new.id, coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1)))
        on conflict (id) do nothing;
    insert into public.notification_settings (user_id)
        values (new.id)
        on conflict (user_id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();
