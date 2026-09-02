"use client";
import { useEffect, useRef } from "react";
import { useHasMouse, usePrefersReducedMotion } from "./hooks";

type Box = { x: number; y: number; w: number; h: number };

// The kestrel's fixed gaze: a cyan corner-bracket frame that free-follows the
// cursor with lag and snaps to elements marked [data-reticle]. Driven entirely
// by rAF + refs; React state is never touched per frame.
export function Reticle() {
  const hasMouse = useHasMouse();
  const reduced = usePrefersReducedMotion();
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!hasMouse || reduced) return;
    const el = ref.current;
    if (!el) return;

    const FREE = 30; // free-follow bracket size
    const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const cur: Box = { x: mouse.x - FREE / 2, y: mouse.y - FREE / 2, w: FREE, h: FREE };

    let targets: HTMLElement[] = [];
    const refresh = () => {
      targets = Array.from(
        document.querySelectorAll<HTMLElement>("[data-reticle]")
      );
    };
    refresh();
    const refreshTimer = window.setInterval(refresh, 800);

    const onMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };
    window.addEventListener("mousemove", onMove, { passive: true });

    let visible = false;
    const pickTarget = (): Box => {
      let best: { box: Box; area: number } | null = null;
      for (const t of targets) {
        const r = t.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        const pad = 22;
        const inside =
          mouse.x >= r.left - pad &&
          mouse.x <= r.right + pad &&
          mouse.y >= r.top - pad &&
          mouse.y <= r.bottom + pad;
        if (!inside) continue;
        const area = r.width * r.height;
        if (!best || area < best.area) {
          best = {
            area,
            box: { x: r.left - 6, y: r.top - 6, w: r.width + 12, h: r.height + 12 },
          };
        }
      }
      if (best) return best.box;
      return { x: mouse.x - FREE / 2, y: mouse.y - FREE / 2, w: FREE, h: FREE };
    };

    let raf = 0;
    const tick = () => {
      const target = pickTarget();
      const k = 0.15;
      cur.x += (target.x - cur.x) * k;
      cur.y += (target.y - cur.y) * k;
      cur.w += (target.w - cur.w) * k;
      cur.h += (target.h - cur.h) * k;
      el.style.transform = `translate(${cur.x}px, ${cur.y}px)`;
      el.style.width = `${cur.w}px`;
      el.style.height = `${cur.h}px`;
      if (!visible) {
        visible = true;
        el.style.opacity = "1";
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.clearInterval(refreshTimer);
      window.removeEventListener("mousemove", onMove);
    };
  }, [hasMouse, reduced]);

  if (!hasMouse || reduced) return null;
  return (
    <div ref={ref} className="k-reticle" style={{ opacity: 0 }} aria-hidden="true">
      <span className="k-reticle__c k-reticle__c--tl" />
      <span className="k-reticle__c k-reticle__c--tr" />
      <span className="k-reticle__c k-reticle__c--bl" />
      <span className="k-reticle__c k-reticle__c--br" />
    </div>
  );
}
