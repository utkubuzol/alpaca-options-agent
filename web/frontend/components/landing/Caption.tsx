import type { LandingData } from "./types";

// Honesty labels (Step 4). Real journal-backed visuals get provenance; charts
// that render on shape alone get an explicit illustrative disclaimer; data-only
// groups that are hidden get a plain note pointing to the live source.

export function DataCaption({ data }: { data: LandingData }) {
  const label = data.mode === "backtest" ? "Backtest journal" : "Live paper account";
  return (
    <p className="k-honesty">
      {label} · as of {data.asOf} · {data.recordCount} records
    </p>
  );
}

export function IllustrativeCaption() {
  return <p className="k-honesty">Illustrative — shape only, not live figures</p>;
}

export function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p className="k-empty">{children}</p>;
}
