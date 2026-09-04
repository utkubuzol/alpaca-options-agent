"use client";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  ReferenceLine,
  ReferenceDot,
  Tooltip,
} from "recharts";
import { Reveal } from "@/components/Reveal";
import { DataCaption, IllustrativeCaption } from "./Caption";
import type { LandingData } from "./types";

const ACCENT = "#26D9E4";
const AXIS = "#7D8A9C";

// Illustrative shape only — the canonical defined-risk payoff (flat floor,
// slope through breakeven, flat plateau). Rendered with NO numeric axes so no
// dollar figure can read as real; used when the journal has no position to plot.
const ILLUSTRATIVE_PAYOFF = [
  { price: 88, pnl: -432 }, { price: 90, pnl: -432 }, { price: 92, pnl: -432 },
  { price: 94, pnl: -432 }, { price: 95, pnl: -432 }, { price: 96, pnl: -332 },
  { price: 97, pnl: -232 }, { price: 98, pnl: -132 }, { price: 99, pnl: -32 },
  { price: 99.32, pnl: 0 }, { price: 100, pnl: 68 }, { price: 101, pnl: 68 },
  { price: 103, pnl: 68 }, { price: 105, pnl: 68 }, { price: 108, pnl: 68 },
];

function PayoffTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload as { price: number; pnl: number };
  return (
    <div className="k-tooltip">
      <div className="k-tooltip__row"><span className="k-tooltip__k">Underlying</span><span>${p.price.toFixed(2)}</span></div>
      <div className="k-tooltip__row">
        <span className="k-tooltip__k">P/L</span>
        <span style={{ color: p.pnl >= 0 ? "#34D399" : "#F87171" }}>
          {p.pnl >= 0 ? "+" : "\u2212"}${Math.abs(p.pnl)}
        </span>
      </div>
    </div>
  );
}

function PayoffChart({ points, live }: { points: { price: number; pnl: number }[]; live: boolean }) {
  const maxProfit = points.reduce((a, b) => (b.pnl > a.pnl ? b : a));
  const maxLoss = points.reduce((a, b) => (b.pnl < a.pnl ? b : a));
  const breakeven = points.reduce((a, b) => (Math.abs(b.pnl) < Math.abs(a.pnl) ? b : a));
  return (
    <div className="k-chart" style={{ height: 300 }} aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 24, right: 20, bottom: 8, left: 8 }}>
          <XAxis
            dataKey="price"
            type="number"
            domain={["dataMin", "dataMax"]}
            hide={!live}
            tickFormatter={(v) => `$${v}`}
            tickLine={false}
            axisLine={{ stroke: "#1C232D" }}
          />
          <YAxis
            hide={!live}
            tickFormatter={(v) => (v === 0 ? "$0" : `${v > 0 ? "+" : "\u2212"}$${Math.abs(v)}`)}
            tickLine={false}
            axisLine={false}
            width={48}
          />
          {live && <Tooltip content={<PayoffTooltip />} />}
          <ReferenceLine y={0} stroke="#1C232D" />
          <Line type="linear" dataKey="pnl" stroke={ACCENT} strokeWidth={2} dot={false} isAnimationActive={false} />
          <ReferenceDot x={maxProfit.price} y={maxProfit.pnl} r={4} fill={ACCENT} stroke="#07090D"
            label={{ value: "Max profit", position: "top", dx: -30, fill: AXIS, fontSize: 11 }} />
          <ReferenceDot x={breakeven.price} y={0} r={4} fill={ACCENT} stroke="#07090D"
            label={{ value: "Breakeven", position: "top", fill: AXIS, fontSize: 11 }} />
          <ReferenceDot x={maxLoss.price} y={maxLoss.pnl} r={4} fill={ACCENT} stroke="#07090D"
            label={{ value: "Max loss — the floor", position: "top", dx: 70, fill: AXIS, fontSize: 11 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TheStrike({ data }: { data: LandingData }) {
  const live = !!data.payoff && data.payoff.length > 1;
  const points = live ? data.payoff! : ILLUSTRATIVE_PAYOFF;

  return (
    <section className="k-section" aria-labelledby="strike-h">
      <Reveal>
        <p className="k-eyebrow">02 / The strike</p>
        <h2 className="k-h2" id="strike-h">One move. Bounded before it is placed.</h2>
      </Reveal>
      <div className="k-grid-2">
        <Reveal delay={80}>
          <p className="k-body">
            When volatility is rich, Kestrel sells a defined-risk structure sized
            to the regime — a cash-secured put in a bullish or neutral tape, a
            call credit spread in a bearish or neutral one, a covered call when
            the account already holds the shares.
          </p>
          <p className="k-body">
            <strong>Maximum loss is known at entry</strong>, not discovered
            afterwards. Time runs, and the agent is paid to hold the other side
            of it.
          </p>
          <p className="k-caption" style={{ marginTop: 20 }}>
            The floor is the point. Loss is capped before the order is sent.
          </p>
        </Reveal>

        <Reveal delay={140} className="k-chart-frame" data-reticle>
          <p className="k-sr">
            {live
              ? "Chart: profit and loss of a defined-risk credit spread at expiry against the underlying price — a flat maximum-loss floor, a slope through breakeven, and a flat maximum-profit plateau."
              : "Illustrative diagram: a defined-risk payoff curve — flat maximum-loss floor on one side, a slope through breakeven, a flat maximum-profit plateau on the other. Shape only — not live figures."}
          </p>
          <PayoffChart points={points} live={live} />
          {live ? <DataCaption data={data} /> : <IllustrativeCaption />}
        </Reveal>
      </div>
    </section>
  );
}
