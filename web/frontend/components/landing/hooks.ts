"use client";
import { useEffect, useState } from "react";

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

// Fine pointer = mouse/trackpad. Coarse/none = touch → hide reticle, static wires.
export function useFinePointer(): boolean {
  const [fine, setFine] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(pointer: fine)");
    const on = () => setFine(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return fine;
}

export function useIsMobile(breakpoint = 760): boolean {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const on = () => setMobile(window.innerWidth < breakpoint);
    on();
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, [breakpoint]);
  return mobile;
}
