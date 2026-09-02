"use client";

export const dynamic = "force-dynamic";
import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiGet } from "@/lib/api";
import { Card, Stat, money, tone } from "@/components/ui";

export default function DashboardPage() {
  const [pnl, setPnl] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/pnl").then(setPnl).catch((e) => setErr(String(e)));
  }, []);

  if (err)
    return (
      <div className="text-sm text-rose-400">
        {err.includes("no Alpaca credentials")
          ? "Add your Alpaca paper keys in Settings to see PnL."
          : err}
      </div>
    );
  if (!pnl) return <div className="text-sm opacity-60">Loading…</div>;

  const p = pnl.pnl;
  const curve = (pnl.equity_curve || []).map((c: any) => ({
    ts: new Date(c.ts).toLocaleDateString(),
    equity: c.equity,
  }));
  const pj = pnl.premium_journal || {};

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Overview</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Total PnL" value={money(p.total)} sub={`${p.total_return_pct ?? 0}%`} tone={tone(p.total)} />
        <Stat label="Realized" value={money(p.realized_implied)} tone={tone(p.realized_implied)} />
        <Stat label="Unrealized" value={money(p.unrealized)} tone={tone(p.unrealized)} />
        <Stat label="Today" value={money(p.today)} sub={`${p.today_return_pct ?? 0}%`} tone={tone(p.today)} />
      </div>

      <Card title="Equity curve">
        {curve.length < 2 ? (
          <p className="text-xs opacity-50">Not enough snapshots yet — runs populate this.</p>
        ) : (
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={curve}>
                <defs>
                  <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#4f9cf9" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#4f9cf9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="ts" tick={{ fontSize: 11, fill: "#7c8798" }} />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 11, fill: "#7c8798" }}
                  width={70}
                  tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  contentStyle={{ background: "#141922", border: "1px solid #232a36" }}
                  formatter={(v: any) => money(v)}
                />
                <Area type="monotone" dataKey="equity" stroke="#4f9cf9" fill="url(#eq)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <div className="grid md:grid-cols-2 gap-3">
        <Card title="Premium-selling execution">
          <dl className="text-sm grid grid-cols-2 gap-y-1">
            <dt className="opacity-60">Fills logged</dt>
            <dd>{pj.n_fills ?? 0}</dd>
            <dt className="opacity-60">Filled</dt>
            <dd>{pj.n_filled ?? 0}</dd>
            <dt className="opacity-60">Rejected</dt>
            <dd>{pj.n_rejected ?? 0}</dd>
            <dt className="opacity-60">Credit given up / contract</dt>
            <dd>{money(pj.credit_given_up_per_contract)}</dd>
            <dt className="opacity-60">Avg slippage</dt>
            <dd>{pj.avg_slippage_bps != null ? `${pj.avg_slippage_bps} bps` : "—"}</dd>
            <dt className="opacity-60">Worst slippage</dt>
            <dd>{pj.worst_slippage_bps != null ? `${pj.worst_slippage_bps} bps` : "—"}</dd>
          </dl>
        </Card>
        <Card title="Open positions">
          <table className="w-full text-sm">
            <tbody>
              {(pnl.open_positions || []).slice(0, 8).map((pos: any) => (
                <tr key={pos.symbol} className="border-t border-border">
                  <td className="py-1 font-mono text-xs">{pos.symbol}</td>
                  <td className="text-right">{pos.qty}</td>
                  <td className={`text-right ${pos.unrealized_pl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {money(pos.unrealized_pl)}
                  </td>
                </tr>
              ))}
              {(pnl.open_positions || []).length === 0 && (
                <tr>
                  <td className="py-2 text-xs opacity-50">No open positions.</td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
