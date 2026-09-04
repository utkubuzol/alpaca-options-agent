"use client";
import { useEffect, useRef } from "react";
import { HeroMedia } from "./HeroMedia";
import { Cta } from "./Cta";
import { GITHUB_URL } from "./styles";
import { useHasMouse, usePrefersReducedMotion } from "./hooks";

export function Hero() {
  const hasMouse = useHasMouse();
  const reduced = usePrefersReducedMotion();
  const mediaRef = useRef<HTMLDivElement | null>(null);
  const copyRef = useRef<HTMLDivElement | null>(null);
  const lightRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const heroRef = useRef<HTMLElement | null>(null);

  // Parallax: media at ~0.3x scroll, headline at ~0.6x. Transform only, rAF.
  useEffect(() => {
    if (reduced) return;
    let raf = 0;
    let ticking = false;
    const apply = () => {
      const y = window.scrollY;
      if (mediaRef.current) mediaRef.current.style.transform = `translate3d(0, ${y * 0.3}px, 0)`;
      if (copyRef.current) copyRef.current.style.transform = `translate3d(0, ${y * 0.18}px, 0)`;
      if (scrollRef.current) scrollRef.current.style.opacity = y > 40 ? "0" : "1";
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) {
        ticking = true;
        raf = requestAnimationFrame(apply);
      }
    };
    apply();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, [reduced]);

  // Cursor light over the hero — soft cyan radial, screen-blended, follows rAF.
  useEffect(() => {
    if (!hasMouse || reduced) return;
    const hero = heroRef.current;
    const light = lightRef.current;
    if (!hero || !light) return;
    const pos = { x: 0, y: 0 };
    let raf = 0;
    let pending = false;
    const draw = () => {
      light.style.setProperty("--mx", `${pos.x}px`);
      light.style.setProperty("--my", `${pos.y}px`);
      pending = false;
    };
    const onMove = (e: MouseEvent) => {
      const r = hero.getBoundingClientRect();
      pos.x = e.clientX - r.left;
      pos.y = e.clientY - r.top;
      light.style.opacity = "1";
      if (!pending) {
        pending = true;
        raf = requestAnimationFrame(draw);
      }
    };
    const onLeave = () => { light.style.opacity = "0"; };
    hero.addEventListener("mousemove", onMove, { passive: true });
    hero.addEventListener("mouseleave", onLeave);
    return () => {
      hero.removeEventListener("mousemove", onMove);
      hero.removeEventListener("mouseleave", onLeave);
      cancelAnimationFrame(raf);
    };
  }, [hasMouse, reduced]);

  return (
    <section className="k-hero" id="top" ref={heroRef as any} aria-label="Kestrel">
      <div ref={mediaRef} className="k-hero__media-wrap" style={{ position: "absolute", inset: 0, zIndex: 0 }}>
        <HeroMedia src="/hero-hourglass.png" />
      </div>
      <div className="k-hero__vignette" />
      <div ref={lightRef} className="k-hero__light" />
      <div className="k-hero__inner">
        <div ref={copyRef} className="k-hero__copy">
          <h1 className="k-h1">
            Waits.<br />Then commits.
          </h1>
          <p className="k-hero__sub">
            An autonomous options agent that sells premium only when volatility
            pays for it — and measures whether the fill was ever real.
          </p>
          <div className="k-hero__ctas">
            <Cta href="/login" variant="primary" dataReticle>Open dashboard</Cta>
            <Cta href={GITHUB_URL} variant="ghost" external>Read the ledger</Cta>
          </div>
        </div>
      </div>
      <div ref={scrollRef} className="k-scroll" aria-hidden="true">
        <span>Scroll</span>
        <span className="k-scroll__rail" />
      </div>
    </section>
  );
}
