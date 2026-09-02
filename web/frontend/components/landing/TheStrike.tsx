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
import { Reveal } from "./Reveal";
import { useIsMobile } from "./hooks";
import type { KestrelData } from "./types";

const ACCENT = "#26D9E4";
const AXIS = "#7D8A9C";

function PayoffTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload as { price: number; pnl: number };
  return (
    <div className="k-tooltip">
      <div className="k-tooltip__row">
        <span className="k-tooltip__k">Underlying</span>
        <span>${p.price.toFixed(2)}</span>
      </div>
      <div className="k-tooltip__row">
        <span className="k-tooltip__k">P/L</span>
        <span style={{ color: p.pnl >= 0 ? "#34D399" : "#F87171" }}>
          {p.pnl >= 0 ? "+" : "\u2212"}${Math.abs(p.pnl)}
        </span>
      </div>
    </div>
  );
}

export function TheStrike({ data }: { data: KestrelData }) {
  const mobile = useIsMobile();
  const d = data.payoff;
  const maxProfit = d[d.length - 1];
  const maxLoss = d[0];
  const breakeven = d.find((p) => p.pnl === 0) ?? d[0];

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
            Chart: profit and loss of a put credit spread at expiry against the
            underlying price. A flat maximum-loss floor of ${Math.abs(maxLoss.pnl)} on the
            left, a slope up through breakeven near ${breakeven.price}, and a flat
            maximum-profit plateau of ${maxProfit.pnl} on the right. Loss is capped
            before the order is placed.
          </p>
          <div className="k-chart" style={{ height: 300 }} aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={d} margin={{ top: 24, right: 20, bottom: 8, left: 8 }}>
                <XAxis
                  dataKey="price"
                  type="number"
                  domain={[88, 108]}
                  ticks={mobile ? [90, 100, 108] : [90, 95, 100, 105]}
                  tickFormatter={(v) => `$${v}`}
                  tickLine={false}
                  axisLine={{ stroke: "#1C232D" }}
                />
                <YAxis
                  domain={[-480, 150]}
                  ticks={mobile ? [-400, 0] : [-400, -200, 0, 68]}
                  tickFormatter={(v) => (v === 0 ? "$0" : `${v > 0 ? "+" : "\u2212"}$${Math.abs(v)}`)}
                  tickLine={false}
                  axisLine={false}
                  width={48}
                />
                <Tooltip content={<PayoffTooltip />} />
                <ReferenceLine y={0} stroke="#1C232D" />
                <Line
                  type="linear"
                  dataKey="pnl"
                  stroke={ACCENT}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                <ReferenceDot x={maxProfit.price} y={maxProfit.pnl} r={4} fill={ACCENT} stroke="#07090D"
                  label={{ value: "Max profit", position: "top", dx: -30, fill: AXIS, fontSize: 11 }} />
                <ReferenceDot x={breakeven.price} y={0} r={4} fill={ACCENT} stroke="#07090D"
                  label={{ value: "Breakeven", position: "top", fill: AXIS, fontSize: 11 }} />
                <ReferenceDot x={maxLoss.price} y={maxLoss.pnl} r={4} fill={ACCENT} stroke="#07090D"
                  label={{ value: "Max loss — the floor", position: "top", dx: 70, fill: AXIS, fontSize: 11 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="k-caption">Put credit spread, profit/loss per contract at expiry.</p>
        </Reveal>
      </div>
    </section>
  );
}
