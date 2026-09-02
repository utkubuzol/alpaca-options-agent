"use client";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  ReferenceLine,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { Reveal } from "./Reveal";
import type { KestrelData } from "./types";

const ACCENT = "#26D9E4";
const DORMANT = "#1C232D";

function IvTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const v = payload[0].payload.v as number;
  return (
    <div className="k-tooltip">
      <div className="k-tooltip__row">
        <span className="k-tooltip__k">IV rank</span>
        <span>{v.toFixed(2)}</span>
      </div>
    </div>
  );
}

export function TheWait({ data }: { data: KestrelData }) {
  const rows = data.ivRank.map((v, i) => ({ i: i + 1, v }));
  const th = data.ivThreshold;

  return (
    <section className="k-section" id="how-it-works" aria-labelledby="wait-h">
      <Reveal>
        <p className="k-eyebrow">01 / The wait</p>
        <h2 className="k-h2" id="wait-h">Most days it does nothing.</h2>
      </Reveal>
      <Reveal delay={80}>
        <p className="k-body">
          A kestrel holds still in mid-air because hovering costs it energy.
          Patience is a position — it is priced, and it is paid for.
        </p>
        <p className="k-body">
          Kestrel scans every optionable name in its universe on a schedule and
          stays out until implied volatility is rich against that name&rsquo;s own
          recent history. <strong>No signal, no trade</strong>, and the reason is
          written to the journal either way.
        </p>
      </Reveal>

      <Reveal delay={140} className="k-chart-frame" style={{ marginTop: 40 }} data-reticle>
        <p className="k-sr">
          Chart: forty daily implied-volatility-rank readings between 0 and 1.
          Bars at or above the {th.toFixed(2)} entry threshold are highlighted in
          cyan; the remaining lower bars are dormant days when the agent stays
          out of the market.
        </p>
        <div className="k-chart" style={{ height: 180 }} aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 4, bottom: 4, left: 4 }} barCategoryGap={2}>
              <XAxis dataKey="i" hide />
              <YAxis domain={[0, 1]} hide />
              <Tooltip cursor={{ fill: "rgba(38,217,228,0.06)" }} content={<IvTooltip />} />
              <ReferenceLine
                y={th}
                stroke={ACCENT}
                strokeDasharray="4 4"
                strokeOpacity={0.7}
              />
              <Bar dataKey="v" radius={[2, 2, 0, 0]} isAnimationActive={false}>
                {rows.map((r) => (
                  <Cell key={r.i} fill={r.v >= th ? ACCENT : DORMANT} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="k-caption">
          Entry threshold at IV rank {th.toFixed(2)}. Below the line, the agent sleeps.
        </p>
      </Reveal>
    </section>
  );
}
