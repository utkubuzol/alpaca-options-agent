"use client";

export const dynamic = "force-dynamic";
import { useEffect, useRef, useState } from "react";
import { apiGet, openTradeStream } from "@/lib/api";
import { Card, Btn } from "@/components/ui";
import { Reveal } from "@/components/Reveal";
import { PageHeader } from "@/components/PageHeader";

const KINDS = ["", "fill", "risk_decision", "candidate", "scan", "error", "note"];

function KindBadge({ kind }: { kind: string }) {
  const map: Record<string, string> = {
    fill: "bg-emerald-500/20 text-emerald-300",
    error: "bg-rose-500/20 text-rose-300",
    risk_decision: "bg-amber-500/20 text-amber-300",
    candidate: "bg-sky-500/20 text-sky-300",
  };
  return (
    <span className={`text-[10px] rounded px-1.5 py-0.5 ${map[kind] || "bg-panel text-muted"}`}>
      {kind}
    </span>
  );
}

export default function TradesPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [kind, setKind] = useState("");
  const [underlying, setUnderlying] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [live, setLive] = useState(true);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    const q = new URLSearchParams();
    if (kind) q.set("kind", kind);
    if (underlying) q.set("underlying", underlying);
    apiGet(`/api/trades?${q}`).then((d) => setEvents(d.events || []));
  }, [kind, underlying]);

  useEffect(() => {
    if (!live) {
      abort.current?.abort();
      return;
    }
    const ac = new AbortController();
    abort.current = ac;
    openTradeStream((row) => {
      setEvents((prev) => {
        if (prev.some((e) => e.id === row.id)) return prev;
        if (kind && row.kind !== kind) return prev;
        if (underlying && row.underlying !== underlying.toUpperCase()) return prev;
        return [row, ...prev].slice(0, 300);
      });
    }, ac.signal).catch(() => {});
    return () => ac.abort();
  }, [live, kind, underlying]);

  return (
    <div className="space-y-4">
      <PageHeader title="Trades" />
      <div className="flex items-center gap-3 flex-wrap">
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k || "all kinds"}
            </option>
          ))}
        </select>
        <input
          placeholder="underlying"
          value={underlying}
          onChange={(e) => setUnderlying(e.target.value.toUpperCase())}
          className="w-32"
        />
        <Btn variant={live ? "primary" : "ghost"} onClick={() => setLive(!live)}>
          {live ? "● live" : "paused"}
        </Btn>
      </div>

      <Reveal><Card>
        <div className="divide-y divide-border">
          {events.map((e) => (
            <div key={e.id} className="py-2">
              <button
                className="w-full flex items-center gap-3 text-left"
                onClick={() => setExpanded(expanded === e.id ? null : e.id)}
              >
                <span className="text-[11px] text-axis w-32 shrink-0">
                  {new Date(e.ts).toLocaleString()}
                </span>
                <KindBadge kind={e.kind} />
                <span className="text-xs font-mono text-muted">{e.underlying || "—"}</span>
                <span className="text-xs text-axis truncate">
                  {summarize(e)}
                </span>
              </button>
              {expanded === e.id && (
                <pre className="mt-2 text-[11px] bg-bg border border-border rounded-lg p-3 overflow-x-auto">
                  {JSON.stringify(e.payload, null, 2)}
                </pre>
              )}
            </div>
          ))}
          {events.length === 0 && (
            <div className="py-4 text-xs text-muted">No events yet. Run a strategy scan.</div>
          )}
        </div>
      </Card></Reveal>
    </div>
  );
}

function summarize(e: any): string {
  const p = e.payload || {};
  if (e.kind === "fill") {
    const f = p.fill || p;
    return `${f.filled ? "filled" : "not filled"} · exp ${f.expected_credit ?? "?"} / real ${f.realized_credit ?? "?"}`;
  }
  if (e.kind === "risk_decision")
    return `${p.approved ? "approved" : "blocked"} · ${(p.reasons || []).join("; ")}`;
  if (e.kind === "candidate")
    return `${p.candidate?.strategy_type ?? ""} score ${p.candidate?.signal_score ?? ""}`;
  if (e.kind === "error") return p.message || "";
  if (e.kind === "note") return p.message || "";
  if (e.kind === "scan")
    return `iv_rank ${p.vol_signal?.iv_rank ?? "?"} · ${p.trend_signal?.regime ?? "?"}`;
  return "";
}
