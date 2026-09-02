export type KestrelData = {
  ivRank: number[];
  ivThreshold: number;
  payoff: { price: number; pnl: number }[];
  rejections: {
    ts: string;
    underlying: string;
    strategy: string;
    gate: string;
    reason: string;
  }[];
  fills: { trade: number; expected: number; realized: number }[];
  stats: {
    fills: number;
    avgSlippageBps: number;
    worstSlippageBps: number;
    rejected: number;
  };
};
