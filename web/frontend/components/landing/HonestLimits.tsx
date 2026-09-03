"use client";
import { Reveal } from "./Reveal";

const LIMITS = [
  "IV rank starts as a proxy. A true IV rank needs about a year of daily implied-volatility history per name and tenor; the agent bootstraps local history from day one and labels every signal until roughly twenty sessions have accumulated.",
  "Paper fills do not model real market impact. A live book would move against a real order in ways this environment does not simulate.",
  "Options quotes come from the indicative feed, not OPRA. Quote quality is lower than a paying subscription would provide.",
  "Everything shown is paper trading in a simulated account. It is not investment advice and it is not a track record.",
];

export function HonestLimits() {
  return (
    <section className="k-section" aria-labelledby="limits-h">
      <Reveal className="k-limits">
        <h3 className="k-h3" id="limits-h">What this is not.</h3>
        <ul>
          {LIMITS.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
        <p className="k-limits__note">
          Live figures are on the dashboard; this page is refreshed manually from
          the agent&rsquo;s journal.
        </p>
      </Reveal>
    </section>
  );
}
