import { Inter } from "next/font/google";
import { KestrelLanding } from "@/components/landing/KestrelLanding";
import type { LandingData } from "@/components/landing/types";
import data from "@/components/landing/data.json";

// Inter is loaded here (inside the landing route only) so it never touches the
// dashboard's root layout / typography.
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

// Every figure the page shows comes from this generated JSON, produced by
// `scripts/build_landing_data.py` from the agent's append-only journal. It is
// imported at build time (no runtime data fetching), so `/` stays statically
// prerendered. When a key is null, the matching section degrades honestly —
// see the landing components. Regenerate with:
//   python scripts/build_landing_data.py <path/to/agent_journal.jsonl>
export default function Page() {
  return <KestrelLanding data={data as LandingData} fontClassName={inter.className} />;
}
