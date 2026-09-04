import { KestrelLanding } from "@/components/landing/KestrelLanding";
import type { LandingData } from "@/components/landing/types";
import data from "@/components/landing/data.json";

// `data.json` is only a build-time seed (usually all-null). The real figures
// come from /api/public/showcase at runtime — see KestrelLanding. Inter is
// loaded app-wide in app/layout.tsx now, so no per-route font here.
// Regenerate the seed: python scripts/build_landing_data.py <agent_journal.jsonl>
export default function Page() {
  return <KestrelLanding data={data as LandingData} fontClassName="" />;
}
