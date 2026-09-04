"use client";
import { useEffect, useRef, useState } from "react";
import { KESTREL_CSS } from "./styles";
import { Reticle } from "@/components/Reticle";
import { Ticker } from "@/components/Ticker";
import { publicGet } from "@/lib/publicApi";
import { Nav } from "./Nav";
import { Hero } from "./Hero";
import { TheWait } from "./TheWait";
import { TheStrike } from "./TheStrike";
import { Gates } from "./Gates";
import { Proof } from "./Proof";
import { HonestLimits } from "./HonestLimits";
import { Footer } from "./Footer";
import type { LandingData } from "./types";

export function KestrelLanding({
  data,
  fontClassName,
}: {
  data: LandingData; // build-time seed from data.json
  fontClassName: string;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  // Start from the build-time seed, then overlay the live journal aggregate
  // from /api/public/showcase. Sections already flip illustrative -> live on
  // their data key being non-null, so nothing else changes.
  const [live, setLive] = useState<LandingData>(data);

  useEffect(() => {
    rootRef.current?.classList.add("js");
    publicGet<LandingData>("/api/public/showcase").then((r) => {
      if (r && r.recordCount > 0) setLive({ ...data, ...r });
    });
  }, [data]);

  return (
    <div ref={rootRef} className={`kestrel ${fontClassName}`}>
      <style dangerouslySetInnerHTML={{ __html: KESTREL_CSS }} />
      <Reticle />
      <Nav />
      <main>
        <Hero />
        <div className="k-section" style={{ paddingTop: 0, paddingBottom: 0 }}>
          <Ticker />
        </div>
        <TheWait data={live} />
        <TheStrike data={live} />
        <Gates data={live} />
        <Proof data={live} />
        <HonestLimits />
      </main>
      <Footer />
    </div>
  );
}
