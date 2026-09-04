"use client";
import { useEffect, useState } from "react";
import { publicGet, type Quote } from "@/lib/publicApi";

const DEFAULT = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "TSLA"];

// Thin live strip: SYM  price  ▲/▼ d%. Polls /api/public/quotes every 30s.
// Real Alpaca data; renders nothing until the first successful fetch.
export function Ticker({
  symbols = DEFAULT,
  className = "",
}: {
  symbols?: string[];
  className?: string;
}) {
  const [quotes, setQuotes] = useState<Quote[] | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const r = await publicGet<{ quotes: Quote[] }>(
        `/api/public/quotes?symbols=${symbols.join(",")}`,
      );
      if (alive && r?.quotes?.length) setQuotes(r.quotes);
    };
    load();
    const id = setInterval(load, 30_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [symbols]);

  if (!quotes) return null;

  return (
    <div
      className={`flex gap-5 overflow-x-auto whitespace-nowrap border border-border rounded-xl bg-panel/60 px-4 py-2 text-xs ${className}`}
      data-reticle
    >
      {quotes.map((q) => {
        const up = q.changePct >= 0;
        return (
          <span key={q.symbol} className="inline-flex items-center gap-2 tabular-nums">
            <span className="text-muted font-medium">{q.symbol}</span>
            <span className="text-fg">{q.price.toFixed(2)}</span>
            <span className={up ? "text-pos" : "text-neg"}>
              {up ? "▲" : "▼"} {Math.abs(q.changePct).toFixed(2)}%
            </span>
          </span>
        );
      })}
    </div>
  );
}
