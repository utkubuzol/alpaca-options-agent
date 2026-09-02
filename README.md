# Options Alpha Agent

An autonomous, premium-selling options trading agent built for Alpaca's paper
trading environment — Trading API for execution, Alpaca's CLI for
cron/CI-friendly status checks, and a strategy/risk/execution stack designed
around one question: **when a strategy "backtests great," how do you know
whether that's alpha or just a backtest that doesn't pay for what it trades?**

Built for the *Alpaca AI Trading Agents Hackathon* — Options Alpha Agents track.

## SaaS dashboard (`web/`)

A multi-tenant web layer wraps this package: FastAPI + Next.js + Supabase.
Users sign up, store their own Alpaca **paper** keys, build strategies from a
dashboard (no `.env` editing), watch trades / PnL / equity curve live, and get
every fill pushed to **Telegram** (WhatsApp wired but stubbed). It reuses the
strategy / risk / execution stack unchanged via
`AgentConfig.from_strategy(strategy_row, creds)` + `run_cycle(journal=DBJournal)`,
and an APScheduler worker replaces cron. See **[`web/README.md`](web/README.md)**.

## What it does

Every cycle, for each underlying in a configured universe, the agent:

1. **Scans** — pulls the live option chain (price, greeks, IV) and computes
   an IV-rank signal and a trend regime from recent price action.
2. **Decides** — if implied volatility is rich relative to its own recent
   history, proposes a premium-selling trade sized to the regime: a
   cash-secured put in a bullish/neutral market, a call credit spread in a
   bearish/neutral market, a covered call if the account already holds
   shares in an uptrend.
3. **Risk-screens** — sizes (or rejects) the trade against buying power,
   concentration, portfolio delta, and a daily drawdown circuit breaker.
4. **Executes** — submits a marketable limit order (single- or multi-leg) to
   Alpaca's paper account and logs the expected vs. realized fill price.
5. **Journals everything** — every scan, every candidate, every risk
   rejection reason, every fill, in a structured, append-only log.

The same strategy/risk/execution-cost code also drives a backtest engine, so
the agent's own historical track record and its live paper track record are
produced by the same logic, not two different codebases that happen to share
a name.

## Hackathon requirements → where they live

| Requirement | Implementation |
|---|---|
| Autonomous agent, Alpaca Trading API | `alpaca_options_agent/broker/client.py` (alpaca-py `TradingClient` + `OptionHistoricalDataClient`), driven by `agent/runner.py` |
| MCP server or CLI | `alpaca_options_agent/broker/cli_bridge.py` shells out to Alpaca's official CLI (`alpacahq/cli`) for account/position status — used as a cron-friendly, independent cross-check against the SDK session on every cycle. (Swapping in Alpaca's MCP server for an LLM-driven front end is a documented extension point — see *Extending* below.) |
| Options trading | Every strategy — cash-secured puts, covered calls, put/call credit spreads (`strategy/premium_selling.py`) |
| Paper trading environment | `config.py` refuses to run unless `ALPACA_PAPER_TRADE=true` |

## Reducing the sim-to-real gap

This was the explicit ask, so it's treated as a first-class deliverable, not
a README claim:

**1. Realistic execution modeling** (`execution/cost_model.py`). Nothing
fills at the mid. Every order is priced as a marketable limit: mid price,
minus (for a credit sale) an edge that widens with quoted spread and thins
with open interest, so a thin, wide-quoted contract genuinely costs more to
trade than a tight, liquid one — not just gets filtered out. The live
engine (`execution/execution_engine.py`) submits that price, polls for a
fill, and logs `expected_credit` vs `realized_credit` on every single trade.

**2. Backtest-to-paper consistency.** The backtest engine
(`backtest/engine.py`) calls the identical `generate_candidates()`,
`RiskManager.screen()`, and `expected_marketable_limit()` functions the live
agent calls. The only backtest-only pieces are clearly isolated: a
Black-Scholes chain generator (`backtest/pricing.py`,
`backtest/synthetic_chain.py`) standing in for real historical OPRA data
(which a paper account doesn't have access to), and a stochastic
`simulate_fill()` standing in for a real order book. `agent report` builds a
side-by-side comparison of backtest-modeled slippage vs. paper-realized
slippage — the actual number that says how good the execution model is,
updated every time the agent trades.

**3. Risk & position management** (`risk/risk_manager.py`). Buying-power and
collateral sizing, single-underlying concentration caps, a portfolio
delta-dollar cap, and a daily-drawdown circuit breaker that blocks *all* new
risk once tripped — applied identically pre-trade in backtest and live, so a
backtest can't "win" by ignoring a constraint the live agent would have hit.

**4. Live monitoring & explainability** (`monitoring/journal.py`). Every
candidate carries a plain-English `rationale` string. Every risk rejection
carries its reasons. Everything is written to an append-only JSONL journal —
so "why didn't it trade AAPL today" is answerable by reading a log line, not
by re-running the code with a debugger attached.

### Honest limitations (stated on purpose)

- **IV rank starts as a proxy.** A true IV-rank needs ~1 year of daily IV
  history for the same underlying/tenor. Alpaca's option chain endpoint
  gives you *today's* IV, not a time series. `strategy/signals.py`
  bootstraps a real local history from day one (`IVHistoryStore`) and uses
  an IV/HV-ratio proxy — clearly labeled `iv_rank_is_proxy=True` in every
  logged signal — until ~20 sessions of real history accumulate. This is
  the same problem any team without a paid historical-IV feed has to solve;
  the code says so instead of quietly faking a percentile.
- **Backtest option prices are modeled, not historical.** See point 2 above
  — this is a deliberate, documented choice, and the gap report is built
  specifically to quantify how much that matters.
- **Options TIF is `day`-only** (an Alpaca platform constraint, not a
  limitation of this code) — so a resting order that doesn't fill expires
  at the close and the next cycle re-evaluates from scratch rather than
  assuming a stale GTC order is still working.
- **Live portfolio delta** in `agent/runner.py` is conservatively reported
  as `0.0` rather than silently wrong: aggregating real-time delta across
  open positions needs a live per-position greeks lookup this cycle
  doesn't yet do (the backtest engine *does* track it correctly — see
  `backtest/engine.py::_current_delta_dollars` — because it already has
  every leg's model price on hand). Wiring the same lookup into
  `broker/client.py::get_positions()` is the natural next step.

## Project layout

```
alpaca_options_agent/
  config.py                  # env-driven config: credentials, risk limits, execution params
  broker/
    client.py                 # alpaca-py wrapper: account, chain+greeks, order submission
    cli_bridge.py              # shells out to Alpaca's official CLI for status cross-checks
  strategy/
    types.py                   # shared dataclasses (OptionQuote, TradeCandidate, Leg, FillResult)
    signals.py                  # IV rank (+ proxy), trend regime
    premium_selling.py           # CSP / covered call / credit spread candidate generation
  execution/
    cost_model.py                # marketable-limit pricing, slippage math, backtest fill simulation
    execution_engine.py           # live: submit, poll, record expected vs. realized
  risk/
    risk_manager.py                # buying power, concentration, delta cap, drawdown breaker
  backtest/
    pricing.py                      # Black-Scholes pricer + greeks
    synthetic_chain.py               # builds a modeled option chain for a given date
    data_loader.py                    # real Alpaca historical closes, or seeded synthetic closes
    engine.py                          # day-by-day backtest loop, reusing strategy/risk/cost code
  monitoring/
    journal.py                        # append-only structured decision log
    report.py                          # backtest-vs-paper sim-to-real gap report
  agent/
    runner.py                          # one live scan-decide-risk-execute cycle
    cli.py                              # `agent scan|trade|status|backtest|report`
scripts/run_paper_agent.sh              # cron/CI entry point
tests/                                   # 20 unit + integration tests, no API keys required
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .          # installs the `agent` console command

cp .env.example .env
# edit .env: paste your PAPER trading keys from
# https://app.alpaca.markets/paper/dashboard/overview
```

Options trading needs to be enabled on the paper account (Level 2 for
single-leg CSPs/covered calls, Level 3 for the multi-leg credit spreads) —
toggle it in the Alpaca dashboard's paper account settings.

The Alpaca CLI is optional but recommended (`brew install alpacahq/tap/cli`
or `go install github.com/alpacahq/cli/cmd/alpaca@latest`) — without it, the
agent runs fine on the SDK alone and simply logs `cli_cross_check_skipped`.

## Usage

```bash
# No network/API keys needed — proves the pipeline end to end:
python -m pytest tests/ -q

# Backtest against a seeded synthetic price path (no keys needed):
agent backtest --universe SPY,QQQ,AAPL --days 240 --source synthetic

# Backtest against real historical Alpaca stock closes (keys needed,
# option prices are still modeled — see "Honest limitations" above):
agent backtest --universe SPY,QQQ,AAPL --days 240 --source alpaca

# Dry run against the live paper chain — generates and risk-screens
# candidates, sends nothing:
agent scan

# Live pass against the paper account — actually submits orders:
agent trade --yes

# Account, positions, open orders (SDK + CLI cross-check):
agent status

# Backtest-vs-paper sim-to-real gap report:
agent report
```

Run `agent trade --yes` repeatedly during market hours (cron, or
`scripts/run_paper_agent.sh` — see the crontab example in that file) rather
than as a long-lived process; each cycle looks at current live positions
before deciding what (if anything) to add.

## Testing

`tests/` covers the Black-Scholes pricer (put-call parity, delta bounds,
zero-DTE intrinsic value), the execution cost model (edge given up on a
credit, wider spreads costing more, fills never beating mid), the strategy
engine (IV-rank gating, correct strike selection by delta, regime-based
strategy choice, liquidity filtering), the risk manager (drawdown breaker,
buying-power sizing, concentration caps), and a full end-to-end backtest
smoke test — all synthetic, all deterministic given a seed, none requiring
API keys or network access.

## Extending: swapping in the MCP server

`broker/client.py` and `broker/cli_bridge.py` are the only modules that talk
to Alpaca directly — everything else works with the normalized dataclasses
in `strategy/types.py`. To front this with Alpaca's MCP server
(`alpacahq/alpaca-mcp-server`) for an LLM-driven interactive mode instead of
(or alongside) the autonomous CLI loop: point an MCP client at the server
with the same `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`, and let the LLM call its
~80 tools directly for exploration/manual trading, while the autonomous
`agent trade` cron loop keeps running independently against the same paper
account. The two don't conflict — they're both just clients of the same
Alpaca account.
