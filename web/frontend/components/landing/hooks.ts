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

// "Has a mouse" — true if the device can hover with a fine pointer, OR as soon
// as a genuine non-touch pointer moves. This is more robust than a bare
// `(pointer: fine)` check: some real desktops (VNC / remote sessions / certain
// Linux setups) report a coarse primary pointer even with a mouse attached, and
// we still want the cursor-driven effects there. Touchscreens never fire a
// non-touch pointermove, so the reticle and wire physics stay off for them.
export function useHasMouse(): boolean {
  const [has, setHas] = useState(false);
  useEffect(() => {
    if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
      setHas(true);
      return;
    }
    let done = false;
    const enable = () => {
      if (done) return;
      done = true;
      setHas(true);
      window.removeEventListener("pointermove", onPointer as any);
      window.removeEventListener("mousemove", onMouse);
    };
    const onPointer = (e: PointerEvent) => {
      if (e.pointerType !== "touch") enable();
    };
    const onMouse = () => enable();
    if (typeof window.PointerEvent !== "undefined") {
      window.addEventListener("pointermove", onPointer as any, { passive: true });
    } else {
      window.addEventListener("mousemove", onMouse, { passive: true });
    }
    return () => {
      window.removeEventListener("pointermove", onPointer as any);
      window.removeEventListener("mousemove", onMouse);
    };
  }, []);
  return has;
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
