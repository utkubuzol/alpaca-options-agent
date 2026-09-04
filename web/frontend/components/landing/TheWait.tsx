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
import { DataCaption, IllustrativeCaption } from "./Caption";
import type { LandingData } from "./types";

const ACCENT = "#26D9E4";
const DORMANT = "#1C232D";

// Illustrative shape only — a generic "mostly-dormant, occasionally-rich" IV
// profile with no numeric axes, used when the journal has no IV history to show.
const ILLUSTRATIVE_IV = [
  0.32, 0.28, 0.41, 0.37, 0.44, 0.35, 0.29, 0.52, 0.48, 0.55,
  0.61, 0.58, 0.64, 0.49, 0.4, 0.33, 0.31, 0.45, 0.5, 0.57,
  0.68, 0.72, 0.63, 0.54, 0.47, 0.39, 0.42, 0.36, 0.3, 0.34,
  0.51, 0.6, 0.66, 0.71, 0.59, 0.46, 0.38, 0.43, 0.62, 0.56,
];
const ILLUSTRATIVE_TH = 0.6;

function IvTooltip({ active, payload, live }: any) {
  if (!active || !payload?.length || !live) return null;
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

export function TheWait({ data }: { data: LandingData }) {
  const live = !!data.ivRank && data.ivRank.length > 0;
  const values = live ? data.ivRank! : ILLUSTRATIVE_IV;
  const th = live ? data.ivThreshold : ILLUSTRATIVE_TH;
  const rows = values.map((v, i) => ({ i: i + 1, v }));

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
          {live
            ? `Chart: ${rows.length} daily implied-volatility-rank readings between 0 and 1. Bars at or above the entry threshold are highlighted in cyan; the rest are dormant days.`
            : "Illustrative diagram: a strip of daily implied-volatility-rank bars, most below an entry threshold line (dormant days), a few above it. Shape only — not live figures."}
        </p>
        <div className="k-chart" style={{ height: 180 }} aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 4, bottom: 4, left: 4 }} barCategoryGap={2}>
              <XAxis dataKey="i" hide />
              <YAxis domain={[0, 1]} hide />
              {live && <Tooltip cursor={{ fill: "rgba(38,217,228,0.06)" }} content={<IvTooltip live={live} />} />}
              {th != null && (
                <ReferenceLine y={th} stroke={ACCENT} strokeDasharray="4 4" strokeOpacity={0.7} />
              )}
              <Bar dataKey="v" radius={[2, 2, 0, 0]} isAnimationActive={false}>
                {rows.map((r) => (
                  <Cell key={r.i} fill={th != null && r.v >= th ? ACCENT : DORMANT} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        {live ? <DataCaption data={data} /> : <IllustrativeCaption />}
      </Reveal>
    </section>
  );
}
