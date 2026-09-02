"use client";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Reveal } from "./Reveal";
import { Stat } from "@/components/ui";
import { useIsMobile } from "./hooks";
import type { KestrelData } from "./types";

const ACCENT = "#26D9E4";

function FillTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload as { trade: number; expected: number; realized: number };
  const slip = p.expected - p.realized;
  return (
    <div className="k-tooltip">
      <div className="k-tooltip__row"><span className="k-tooltip__k">Trade</span><span>#{p.trade}</span></div>
      <div className="k-tooltip__row"><span className="k-tooltip__k">Expected</span><span>${p.expected}</span></div>
      <div className="k-tooltip__row"><span className="k-tooltip__k">Realized</span><span>${p.realized}</span></div>
      <div className="k-tooltip__row"><span className="k-tooltip__k">Slippage</span><span>{"\u2212"}${slip}</span></div>
    </div>
  );
}

export function Proof({ data }: { data: KestrelData }) {
  const mobile = useIsMobile();
  const rows = data.fills.map((f) => ({
    ...f,
    gap: Math.max(0, f.expected - f.realized),
  }));
  const s = data.stats;

  return (
    <section className="k-section" id="proof" aria-labelledby="proof-h">
      <Reveal>
        <p className="k-eyebrow">04 / The proof</p>
        <h2 className="k-h2" id="proof-h">The backtest and the paper book run the same code.</h2>
      </Reveal>
      <Reveal delay={80}>
        <p className="k-body">
          When a strategy backtests well, how do you know that is alpha and not a
          backtest that never paid for what it traded?
        </p>
        <p className="k-body">
          Nothing fills at the mid. Kestrel prices every order as a marketable
          limit, submits it, and records{" "}
          <strong>expected credit against realized credit</strong> — on every
          trade, with no exceptions and no smoothing. The same candidate
          generator, the same risk screen, and the same cost model drive both the
          backtest and the live paper agent.
        </p>
      </Reveal>

      <Reveal delay={140} className="k-chart-frame" style={{ marginTop: 40 }} data-reticle>
        <p className="k-sr">
          Chart: expected versus realized credit in dollars per contract across
          {" "}{rows.length} trades. Expected credit is the dashed line, realized
          credit the solid line, and the shaded band between them is the logged
          slippage — realized consistently trails expected because nothing fills
          at the mid.
        </p>
        <div className="k-chart" style={{ height: 300 }} aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 12, right: 16, bottom: 4, left: 8 }}>
              <CartesianGrid stroke="#1C232D" strokeDasharray="2 4" vertical={false} />
              <XAxis
                dataKey="trade"
                tickLine={false}
                axisLine={{ stroke: "#1C232D" }}
                ticks={mobile ? [1, 10, 20] : [1, 5, 10, 15, 20]}
                tickFormatter={(v) => `#${v}`}
              />
              <YAxis
                domain={[40, 110]}
                ticks={mobile ? [50, 100] : [50, 70, 90, 110]}
                tickFormatter={(v) => `$${v}`}
                tickLine={false}
                axisLine={false}
                width={44}
              />
              <Tooltip content={<FillTooltip />} />
              <Area dataKey="realized" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
              <Area dataKey="gap" stackId="band" stroke="none" fill="rgba(38,217,228,0.16)" isAnimationActive={false} />
              <Line
                type="monotone"
                dataKey="expected"
                stroke={ACCENT}
                strokeWidth={1.6}
                strokeDasharray="5 4"
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="realized"
                stroke={ACCENT}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="k-caption">
          Expected (dashed) vs realized (solid) credit, $/contract. The band is logged slippage.
        </p>
      </Reveal>

      <div className="k-stats">
        <Reveal as="div" data-reticle><Stat label="Fills logged" value={String(s.fills)} /></Reveal>
        <Reveal as="div" delay={60} data-reticle><Stat label="Avg slippage" value={`${s.avgSlippageBps} bps`} /></Reveal>
        <Reveal as="div" delay={120} data-reticle><Stat label="Worst slippage" value={`${s.worstSlippageBps} bps`} /></Reveal>
        <Reveal as="div" delay={180} data-reticle><Stat label="Candidates rejected" value={String(s.rejected)} /></Reveal>
      </div>
    </section>
  );
}
