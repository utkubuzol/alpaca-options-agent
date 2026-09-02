"use client";
import { useEffect, useRef } from "react";
import { useFinePointer, usePrefersReducedMotion } from "./hooks";

// Anchor styled as a Kestrel button. Primary variant is magnetic: within a
// 60px radius it eases up to 6px toward the cursor. Transform only, rAF-driven.
export function Cta({
  href,
  children,
  variant = "primary",
  magnetic = variant === "primary",
  size,
  external,
  dataReticle,
}: {
  href: string;
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  magnetic?: boolean;
  size?: "sm";
  external?: boolean;
  dataReticle?: boolean;
}) {
  const fine = useFinePointer();
  const reduced = usePrefersReducedMotion();
  const ref = useRef<HTMLAnchorElement | null>(null);

  useEffect(() => {
    if (!magnetic || !fine || reduced) return;
    const el = ref.current;
    if (!el) return;
    const RADIUS = 60;
    const MAX = 6;
    const cur = { x: 0, y: 0 };
    const target = { x: 0, y: 0 };
    let raf = 0;
    let running = false;

    const loop = () => {
      cur.x += (target.x - cur.x) * 0.18;
      cur.y += (target.y - cur.y) * 0.18;
      el.style.transform = `translate(${cur.x.toFixed(2)}px, ${cur.y.toFixed(2)}px)`;
      if (Math.abs(cur.x - target.x) < 0.1 && Math.abs(cur.y - target.y) < 0.1 && target.x === 0 && target.y === 0) {
        running = false;
        el.style.transform = "translate(0px, 0px)";
        return;
      }
      raf = requestAnimationFrame(loop);
    };
    const ensure = () => {
      if (!running) {
        running = true;
        raf = requestAnimationFrame(loop);
      }
    };
    const onMove = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const dist = Math.hypot(dx, dy);
      if (dist < RADIUS + Math.max(r.width, r.height) / 2) {
        const pull = Math.min(1, (RADIUS - Math.max(0, dist - Math.max(r.width, r.height) / 2)) / RADIUS);
        target.x = (dx / (dist || 1)) * MAX * pull;
        target.y = (dy / (dist || 1)) * MAX * pull;
      } else {
        target.x = 0;
        target.y = 0;
      }
      ensure();
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf);
    };
  }, [magnetic, fine, reduced]);

  return (
    <a
      ref={ref}
      href={href}
      className={`k-btn k-btn--${variant}${size === "sm" ? " k-btn--sm" : ""}`}
      {...(external ? { target: "_blank", rel: "noreferrer noopener" } : {})}
      {...(dataReticle ? { "data-reticle": "" } : {})}
    >
      {children}
    </a>
  );
}
