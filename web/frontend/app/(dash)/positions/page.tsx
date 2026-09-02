"use client";

export const dynamic = "force-dynamic";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { Card, money } from "@/components/ui";

export default function PositionsPage() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/positions")
      .then((d) => setRows(d.positions))
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Positions</h1>
      {err && <div className="text-sm text-rose-400">{err}</div>}
      <Card>
        <table className="w-full text-sm">
          <thead className="text-xs opacity-60">
            <tr className="text-left">
              <th className="py-2">Symbol</th>
              <th>Class</th>
              <th className="text-right">Qty</th>
              <th className="text-right">Entry</th>
              <th className="text-right">Last</th>
              <th className="text-right">Mkt value</th>
              <th className="text-right">Unrealized</th>
            </tr>
          </thead>
          <tbody>
            {(rows || []).map((p) => (
              <tr key={p.symbol} className="border-t border-border">
                <td className="py-1.5 font-mono text-xs">{p.symbol}</td>
                <td className="text-xs opacity-70">{p.asset_class}</td>
                <td className="text-right">{p.qty}</td>
                <td className="text-right">{money(p.avg_entry_price)}</td>
                <td className="text-right">{money(p.current_price)}</td>
                <td className="text-right">{money(p.market_value)}</td>
                <td className={`text-right ${p.unrealized_pl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {money(p.unrealized_pl)}
                </td>
              </tr>
            ))}
            {rows && rows.length === 0 && (
              <tr>
                <td className="py-3 text-xs opacity-50" colSpan={7}>
                  No open positions.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
