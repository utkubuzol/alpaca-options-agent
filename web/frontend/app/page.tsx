import { Inter } from "next/font/google";
import { KestrelLanding } from "@/components/landing/KestrelLanding";
import type { KestrelData } from "@/components/landing/types";

// Inter is loaded here (inside the landing route only) so it never touches the
// dashboard's root layout / typography.
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

// PLACEHOLDER DATA — every number the page shows lives here so it can be swapped
// for real journal output from `logs/agent_journal.jsonl` without touching JSX.
// (Not `export`ed: Next.js page files may only export a default + reserved
// fields, so this stays a module-local const at the top of the file.)
const DATA: KestrelData = {
  // ~40 daily IV-rank observations, 0–1. Most days sit below the entry
  // threshold (the agent sleeps); a handful of rich-vol days poke above it.
  ivRank: [
    0.32, 0.28, 0.41, 0.37, 0.44, 0.35, 0.29, 0.52, 0.48, 0.55,
    0.61, 0.58, 0.64, 0.49, 0.4, 0.33, 0.31, 0.45, 0.5, 0.57,
    0.68, 0.72, 0.63, 0.54, 0.47, 0.39, 0.42, 0.36, 0.3, 0.34,
    0.51, 0.6, 0.66, 0.71, 0.59, 0.46, 0.38, 0.43, 0.62, 0.56,
  ],
  ivThreshold: 0.6,
  // Put credit spread P/L at expiry ($/contract): flat max-loss floor on the
  // left, a slope through breakeven, a flat max-profit plateau on the right.
  payoff: [
    { price: 88, pnl: -432 },
    { price: 90, pnl: -432 },
    { price: 92, pnl: -432 },
    { price: 94, pnl: -432 },
    { price: 95, pnl: -432 },
    { price: 96, pnl: -332 },
    { price: 97, pnl: -232 },
    { price: 98, pnl: -132 },
    { price: 99, pnl: -32 },
    { price: 99.32, pnl: 0 },
    { price: 100, pnl: 68 },
    { price: 101, pnl: 68 },
    { price: 103, pnl: 68 },
    { price: 105, pnl: 68 },
    { price: 108, pnl: 68 },
  ],
  rejections: [
    { ts: "2026-08-28 14:32", underlying: "TSLA", strategy: "csp", gate: "Max loss per trade", reason: "defined risk $612 > $500 cap" },
    { ts: "2026-08-28 15:07", underlying: "NVDA", strategy: "credit_spread", gate: "Bid-ask spread ceiling", reason: "spread 8.4% > 5% ceiling" },
    { ts: "2026-08-29 13:55", underlying: "AAPL", strategy: "covered_call", gate: "Single-name concentration", reason: "would reach 27% of book > 20%" },
    { ts: "2026-08-29 18:11", underlying: "AMD", strategy: "credit_spread", gate: "Open interest floor", reason: "OI 143 < 250 minimum" },
    { ts: "2026-08-30 14:02", underlying: "META", strategy: "csp", gate: "Portfolio delta", reason: "net delta +0.42 > +0.35 band" },
  ],
  // Expected vs realized credit ($/contract) across recent trades. Nothing
  // fills at the mid; realized trails expected by real, logged slippage.
  fills: [
    { trade: 1, expected: 72, realized: 69 },
    { trade: 2, expected: 58, realized: 57 },
    { trade: 3, expected: 91, realized: 86 },
    { trade: 4, expected: 64, realized: 62 },
    { trade: 5, expected: 80, realized: 74 },
    { trade: 6, expected: 47, realized: 46 },
    { trade: 7, expected: 103, realized: 97 },
    { trade: 8, expected: 69, realized: 66 },
    { trade: 9, expected: 55, realized: 55 },
    { trade: 10, expected: 88, realized: 82 },
    { trade: 11, expected: 76, realized: 73 },
    { trade: 12, expected: 61, realized: 58 },
    { trade: 13, expected: 94, realized: 90 },
    { trade: 14, expected: 52, realized: 50 },
    { trade: 15, expected: 83, realized: 79 },
    { trade: 16, expected: 67, realized: 65 },
    { trade: 17, expected: 99, realized: 92 },
    { trade: 18, expected: 71, realized: 68 },
    { trade: 19, expected: 60, realized: 59 },
    { trade: 20, expected: 85, realized: 80 },
  ],
  stats: {
    fills: 20,
    avgSlippageBps: 41,
    worstSlippageBps: 88,
    rejected: 37,
  },
};

export default function Page() {
  return <KestrelLanding data={DATA} fontClassName={inter.className} />;
}
