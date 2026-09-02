"use client";
import { useEffect, useRef } from "react";
import { KESTREL_CSS } from "./styles";
import { Reticle } from "./Reticle";
import { Nav } from "./Nav";
import { Hero } from "./Hero";
import { TheWait } from "./TheWait";
import { TheStrike } from "./TheStrike";
import { Gates } from "./Gates";
import type { KestrelData } from "./types";

export function KestrelLanding({
  data,
  fontClassName,
}: {
  data: KestrelData;
  fontClassName: string;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  // Mark the tree as JS-enabled only after hydration, so the reveal animations
  // (which start hidden) never hide content when JavaScript is unavailable.
  useEffect(() => {
    rootRef.current?.classList.add("js");
  }, []);

  return (
    <div ref={rootRef} className={`kestrel ${fontClassName}`}>
      <style dangerouslySetInnerHTML={{ __html: KESTREL_CSS }} />
      <Reticle />
      <Nav />
      <main>
        <Hero />
        <TheWait data={data} />
        <TheStrike data={data} />
        <Gates data={data} />
      </main>
    </div>
  );
}
