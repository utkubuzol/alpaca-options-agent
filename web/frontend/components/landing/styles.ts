// Kestrel landing — all colour + layout tokens are scoped under `.kestrel`.
// Nothing here touches the dashboard: no `:root` vars, no globals.css, no
// tailwind.config changes. The dashboard keeps its own palette entirely.

export const GITHUB_URL = "https://github.com/utkubuzol/alpaca-options-agent";
export const DEMO_URL = GITHUB_URL;

export const KESTREL_CSS = `
.kestrel {
  --k-bg: #07090D;
  --k-panel: #10151C;
  --k-border: #1C232D;
  --k-fg: #E8EFF6;
  /* spec base is #7D8A9C; lightened to clear 4.5:1 on --k-bg for body copy */
  --k-muted: #9AA7B8;
  --k-axis: #7D8A9C;
  --k-accent: #26D9E4;
  --k-accent-dim: #0E7C86;
  --k-pos: #34D399;
  --k-neg: #F87171;

  background: var(--k-bg);
  color: var(--k-fg);
  width: 100%;
  position: relative;
  overflow-x: hidden;
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  line-height: 1.5;
}

.kestrel *,
.kestrel *::before,
.kestrel *::after { box-sizing: border-box; }

.kestrel a { color: inherit; text-decoration: none; }

/* free-follow reticle hint: no OS cursor change, we draw our own overlay */
.k-num { font-variant-numeric: tabular-nums; }

.k-sr {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0);
  white-space: nowrap; border: 0;
}

/* ---------- typography ---------- */
.k-eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--k-accent-dim);
  font-weight: 500;
  margin: 0 0 22px;
}
.k-h1 {
  font-size: clamp(2.5rem, 7vw, 5.5rem);
  font-weight: 500;
  letter-spacing: -0.03em;
  line-height: 0.95;
  margin: 0;
}
.k-h2 {
  font-size: clamp(1.9rem, 4.4vw, 3.25rem);
  font-weight: 500;
  letter-spacing: -0.03em;
  line-height: 1.02;
  margin: 0 0 28px;
}
.k-h3 {
  font-size: clamp(1.35rem, 2.4vw, 1.75rem);
  font-weight: 500;
  letter-spacing: -0.02em;
  margin: 0 0 20px;
}
.k-body {
  font-size: clamp(1rem, 1.1vw, 1.125rem);
  color: var(--k-muted);
  max-width: 62ch;
  margin: 0 0 18px;
}
.k-body strong { color: var(--k-fg); font-weight: 500; }
.k-caption {
  font-size: 13px;
  color: var(--k-axis);
  margin-top: 14px;
  letter-spacing: 0.01em;
}

/* ---------- layout ---------- */
.k-section {
  position: relative;
  max-width: 1200px;
  margin: 0 auto;
  padding: clamp(80px, 12vh, 150px) clamp(20px, 5vw, 48px);
}
.k-grid-2 {
  display: grid;
  grid-template-columns: 1fr;
  gap: clamp(36px, 5vw, 64px);
  align-items: center;
}
@media (min-width: 900px) {
  .k-grid-2 { grid-template-columns: 1.05fr 1fr; }
}

/* ---------- nav ---------- */
.k-nav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px clamp(20px, 5vw, 48px);
  background: transparent;
  border-bottom: 1px solid transparent;
  transition: background .35s ease, border-color .35s ease, backdrop-filter .35s ease;
}
.k-nav--scrolled {
  background: rgba(7, 9, 13, 0.72);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--k-border);
}
.k-brand { display: flex; align-items: center; gap: 10px; }
.k-wordmark {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.22em;
  color: var(--k-fg);
}
.k-navlinks { display: none; align-items: center; gap: 28px; }
@media (min-width: 760px) { .k-navlinks { display: flex; } }
.k-navlink {
  font-size: 13px;
  color: var(--k-muted);
  transition: color .2s ease;
  letter-spacing: 0.01em;
}
.k-navlink:hover { color: var(--k-fg); }

/* ---------- buttons ---------- */
.k-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.01em;
  padding: 11px 20px;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: pointer;
  will-change: transform;
  transition: background .2s ease, border-color .2s ease, color .2s ease;
}
.k-btn--primary { background: var(--k-accent); color: #05171a; border-color: var(--k-accent); }
.k-btn--primary:hover { background: #4fe4ee; }
.k-btn--ghost { background: transparent; color: var(--k-fg); border-color: var(--k-border); }
.k-btn--ghost:hover { border-color: var(--k-accent-dim); color: var(--k-accent); }
.k-btn--sm { padding: 8px 14px; font-size: 13px; }
.kestrel a:focus-visible,
.kestrel button:focus-visible {
  outline: 2px solid var(--k-accent);
  outline-offset: 3px;
  border-radius: 10px;
}

/* ---------- hero ---------- */
.k-hero {
  position: relative;
  height: 100svh;
  min-height: 640px;
  width: 100%;
  overflow: hidden;
  display: flex;
  align-items: center;
}
.k-hero__media { position: absolute; inset: 0; z-index: 0; }
.k-hero__media img,
.k-hero__media video { width: 100%; height: 100%; object-fit: cover; display: block; }
.k-hero__vignette {
  position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background:
    radial-gradient(120% 90% at 50% 42%, rgba(7,9,13,0) 32%, rgba(7,9,13,0.5) 74%, rgba(7,9,13,0.95) 100%),
    linear-gradient(90deg, rgba(7,9,13,0.94) 0%, rgba(7,9,13,0.74) 22%, rgba(7,9,13,0.34) 43%, rgba(7,9,13,0) 62%),
    linear-gradient(180deg, rgba(7,9,13,0.5) 0%, rgba(7,9,13,0) 22%, rgba(7,9,13,0) 62%, rgba(7,9,13,0.92) 100%);
}
.k-hero__light {
  position: absolute; inset: 0; z-index: 2; pointer-events: none;
  mix-blend-mode: screen;
  opacity: 0;
  background: radial-gradient(260px 260px at var(--mx, 50%) var(--my, 50%), rgba(38,217,228,0.08), rgba(38,217,228,0) 70%);
}
.k-hero__inner {
  position: relative; z-index: 3;
  max-width: 1200px; margin: 0 auto; width: 100%;
  padding: 0 clamp(20px, 5vw, 48px);
}
.k-hero__copy { max-width: 760px; will-change: transform; }
.k-hero__sub {
  font-size: clamp(1.05rem, 1.5vw, 1.35rem);
  color: var(--k-fg);
  opacity: 0.82;
  max-width: 56ch;
  margin: 26px 0 34px;
  line-height: 1.45;
}
.k-hero__ctas { display: flex; flex-wrap: wrap; gap: 14px; }
.k-scroll {
  position: absolute; left: 50%; bottom: 26px; z-index: 3;
  transform: translateX(-50%);
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  color: var(--k-axis); font-size: 10px; letter-spacing: 0.24em; text-transform: uppercase;
  transition: opacity .6s ease;
}
.k-scroll__rail { width: 1px; height: 42px; background: linear-gradient(180deg, var(--k-accent), rgba(38,217,228,0)); }

/* ---------- panels / charts ---------- */
.k-panel {
  background: var(--k-panel);
  border: 1px solid var(--k-border);
  border-radius: 14px;
  padding: clamp(18px, 2.4vw, 26px);
}
.k-chart { width: 100%; }
.k-chart-frame {
  background: linear-gradient(180deg, rgba(16,21,28,0.7), rgba(16,21,28,0.35));
  border: 1px solid var(--k-border);
  border-radius: 14px;
  padding: 18px 16px 12px;
}

/* recharts axis + tooltip theming, scoped */
.kestrel .recharts-cartesian-axis-tick text { fill: var(--k-axis); font-size: 11px; }
.kestrel .recharts-text { fill: var(--k-axis); }
.k-tooltip {
  background: rgba(7,9,13,0.92);
  border: 1px solid var(--k-border);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  color: var(--k-fg);
}
.k-tooltip__row { display: flex; gap: 12px; justify-content: space-between; }
.k-tooltip__k { color: var(--k-axis); }

/* ---------- gates ---------- */
.k-wires { position: relative; width: 100%; }
.k-wires__canvas { display: block; width: 100%; height: 340px; }
.k-wires__labels {
  position: absolute; inset: 0; pointer-events: none;
}
.k-wire-label {
  position: absolute; left: 0;
  transform: translateY(-50%);
  font-size: 12px; color: var(--k-muted); letter-spacing: 0.01em;
  padding-right: 12px;
  pointer-events: auto;
}
.k-wire-label__idx { color: var(--k-accent-dim); margin-right: 8px; font-variant-numeric: tabular-nums; }

/* ---------- table ---------- */
.k-table-wrap { margin-top: 40px; border: 1px solid var(--k-border); border-radius: 12px; overflow: hidden; }
.k-table-title { font-size: 13px; color: var(--k-axis); padding: 14px 16px; border-bottom: 1px solid var(--k-border); background: rgba(16,21,28,0.4); }
.k-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.k-table th {
  text-align: left; font-weight: 500; color: var(--k-axis);
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em;
  padding: 12px 16px; border-bottom: 1px solid var(--k-border);
}
.k-table td { padding: 13px 16px; border-bottom: 1px solid rgba(28,35,45,0.6); color: var(--k-muted); }
.k-table tr:last-child td { border-bottom: none; }
.k-table td.k-mono { color: var(--k-fg); font-variant-numeric: tabular-nums; }
.k-tag {
  display: inline-block; font-size: 11px; padding: 3px 8px; border-radius: 999px;
  border: 1px solid var(--k-border); color: var(--k-accent); background: rgba(38,217,228,0.06);
}
@media (max-width: 640px) {
  .k-hide-sm { display: none; }
}

/* ---------- stats row ---------- */
.k-stats {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; margin-top: 32px;
}
@media (min-width: 760px) { .k-stats { grid-template-columns: repeat(4, 1fr); } }
.k-stat {
  background: var(--k-panel);
  border: 1px solid var(--k-border);
  border-radius: 12px;
  padding: 18px;
}
.k-stat__label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em; color: var(--k-axis); }
.k-stat__value { font-size: clamp(1.5rem, 2.4vw, 2rem); font-weight: 500; margin-top: 8px; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
.k-stat__sub { font-size: 12px; color: var(--k-muted); margin-top: 4px; }

/* ---------- honest limits ---------- */
.k-limits {
  background: var(--k-panel);
  border: 1px solid var(--k-border);
  border-radius: 16px;
  padding: clamp(28px, 4vw, 48px);
}
.k-limits ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 18px; }
.k-limits li { color: var(--k-muted); font-size: 15px; line-height: 1.55; padding-left: 20px; position: relative; max-width: 76ch; }
.k-limits li::before { content: ""; position: absolute; left: 0; top: 10px; width: 6px; height: 1px; background: var(--k-axis); }

/* ---------- footer ---------- */
.k-footer {
  border-top: 1px solid var(--k-border);
  padding: clamp(40px, 6vw, 72px) clamp(20px, 5vw, 48px);
  max-width: 1200px; margin: 0 auto;
  display: flex; flex-direction: column; gap: 20px;
}
.k-footer__line { color: var(--k-axis); font-size: 14px; max-width: 60ch; }
.k-footer__links { display: flex; gap: 24px; flex-wrap: wrap; }
.k-footer__links a { color: var(--k-muted); font-size: 13px; }
.k-footer__links a:hover { color: var(--k-accent); }

/* ---------- reticle ---------- */
.k-reticle {
  position: fixed; top: 0; left: 0; z-index: 60;
  pointer-events: none;
  will-change: transform, width, height;
  mix-blend-mode: screen;
}
.k-reticle__c { position: absolute; width: 12px; height: 12px; border: 0 solid var(--k-accent); }
.k-reticle__c--tl { top: 0; left: 0; border-top-width: 1px; border-left-width: 1px; }
.k-reticle__c--tr { top: 0; right: 0; border-top-width: 1px; border-right-width: 1px; }
.k-reticle__c--bl { bottom: 0; left: 0; border-bottom-width: 1px; border-left-width: 1px; }
.k-reticle__c--br { bottom: 0; right: 0; border-bottom-width: 1px; border-right-width: 1px; }

/* ---------- reveal ---------- */
.k-reveal { opacity: 1; }
.js .k-reveal { opacity: 0; transform: translateY(16px); }
.js .k-reveal.k-reveal--in { opacity: 1; transform: translateY(0); transition: opacity .5s ease-out, transform .5s ease-out; }

@media (prefers-reduced-motion: reduce) {
  .js .k-reveal { opacity: 1 !important; transform: none !important; transition: none !important; }
  .k-reticle { display: none !important; }
  .k-hero__light { display: none !important; }
}
`;
