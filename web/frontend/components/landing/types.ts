// Shape of components/landing/data.json — produced by scripts/build_landing_data.py
// from the agent's journal. Every data key is nullable: when the journal cannot
// back it, the generator emits null and the page degrades honestly (a section
// either hides its chart or marks it clearly as illustrative — never a fake
// number that reads as real).
export type LandingData = {
  mode: "live" | "backtest" | null;
  source: string | null;
  asOf: string | null; // ISO 8601 of the most recent record used
  recordCount: number;
  ivRank: number[] | null;
  ivThreshold: number | null;
  payoff: { price: number; pnl: number }[] | null;
  rejections: {
    ts: string;
    underlying: string;
    strategy: string;
    gate: string;
    reason: string;
  }[] | null;
  fills: { trade: number; expected: number; realized: number }[] | null;
  stats: {
    fills: number;
    avgSlippageBps: number;
    worstSlippageBps: number;
    rejected: number;
  } | null;
};
