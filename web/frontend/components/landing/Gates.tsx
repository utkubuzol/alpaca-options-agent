"use client";
import { useEffect, useRef } from "react";
import { Reveal } from "./Reveal";
import { DataCaption, EmptyNote } from "./Caption";
import { useHasMouse, usePrefersReducedMotion } from "./hooks";
import type { LandingData } from "./types";

const GATES = [
  "Max loss per trade",
  "Single-name concentration",
  "Portfolio delta",
  "Daily drawdown breaker",
  "Open interest floor",
  "Bid-ask spread ceiling",
];

const H = 340;
const PAD = 28;
const N = 42; // points per wire
const ACCENT = [38, 217, 228];
const DIM = [14, 124, 134];

function baselineY(j: number) {
  return PAD + ((j + 0.5) / GATES.length) * (H - 2 * PAD);
}

// Six taut wires on a canvas, each a pinned verlet chain. The cursor bends the
// nearest wire; it oscillates back and settles in ~1s. Capped at 30fps, paused
// off-screen, and rendered flat/static under reduced motion or coarse pointers.
function Wires() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const hasMouse = useHasMouse();
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let W = wrap.clientWidth;
    const state: { y: number; oldY: number; base: number }[][] = [];
    let gutter = 220;

    const build = () => {
      W = wrap.clientWidth;
      gutter = W < 620 ? 132 : 220;
      canvas.width = Math.floor(W * dpr);
      canvas.height = Math.floor(H * dpr);
      canvas.style.width = W + "px";
      canvas.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      state.length = 0;
      const x0 = gutter;
      const x1 = W - 20;
      for (let j = 0; j < GATES.length; j++) {
        const base = baselineY(j);
        const pts = [];
        for (let i = 0; i < N; i++) {
          pts.push({ y: base, oldY: base, base });
        }
        state.push(pts as any);
      }
      (build as any).x0 = x0;
      (build as any).x1 = x1;
    };
    build();

    const px = (i: number) => (build as any).x0 + (((build as any).x1 - (build as any).x0) * i) / (N - 1);

    const mouse = { x: -9999, y: -9999, on: false };
    const onMove = (e: MouseEvent) => {
      const r = canvas.getBoundingClientRect();
      mouse.x = e.clientX - r.left;
      mouse.y = e.clientY - r.top;
      mouse.on = true;
    };
    const onLeave = () => { mouse.on = false; mouse.x = -9999; mouse.y = -9999; };

    const drawStatic = () => {
      ctx.clearRect(0, 0, W, H);
      for (let j = 0; j < GATES.length; j++) {
        const base = baselineY(j);
        ctx.beginPath();
        ctx.moveTo((build as any).x0, base);
        ctx.lineTo((build as any).x1, base);
        ctx.strokeStyle = `rgba(${DIM.join(",")},0.9)`;
        ctx.lineWidth = 1.4;
        ctx.stroke();
      }
    };

    if (reduced || !hasMouse) {
      drawStatic();
      const onResize = () => { build(); drawStatic(); };
      window.addEventListener("resize", onResize);
      return () => window.removeEventListener("resize", onResize);
    }

    const RANGE = 120;
    let running = false;
    let raf = 0;
    let last = 0;
    const STEP = 1000 / 30;

    const simulate = () => {
      const damping = 0.9;
      const spread = 90;
      for (let j = 0; j < GATES.length; j++) {
        const pts = state[j];
        for (let i = 1; i < N - 1; i++) {
          const p = pts[i];
          const v = (p.y - p.oldY) * damping;
          p.oldY = p.y;
          p.y += v;
          p.y += (p.base - p.y) * 0.06;
        }
        if (mouse.on) {
          for (let i = 1; i < N - 1; i++) {
            const p = pts[i];
            const dxp = px(i) - mouse.x;
            const dyBase = p.base - mouse.y;
            if (Math.abs(dyBase) < RANGE) {
              const fall = Math.exp(-(dxp * dxp) / (spread * spread));
              const proximity = 1 - Math.abs(dyBase) / RANGE;
              p.y += (mouse.y - p.y) * 0.35 * fall * proximity;
            }
          }
        }
        for (let k = 0; k < 3; k++) {
          for (let i = 0; i < N - 1; i++) {
            const a = pts[i];
            const b = pts[i + 1];
            const dy = b.y - a.y;
            const corr = dy * 0.5 * 0.5;
            if (i !== 0) a.y += corr;
            if (i + 1 !== N - 1) b.y -= corr;
          }
        }
      }
    };

    const render = () => {
      ctx.clearRect(0, 0, W, H);
      for (let j = 0; j < GATES.length; j++) {
        const pts = state[j];
        let maxD = 0;
        for (let i = 0; i < N; i++) maxD = Math.max(maxD, Math.abs(pts[i].y - pts[i].base));
        const t = Math.min(1, maxD / 26);
        const col = ACCENT.map((c, idx) => Math.round(DIM[idx] + (c - DIM[idx]) * t));
        ctx.beginPath();
        ctx.moveTo(px(0), pts[0].y);
        for (let i = 1; i < N; i++) ctx.lineTo(px(i), pts[i].y);
        ctx.strokeStyle = `rgba(${col.join(",")},${0.85 + t * 0.15})`;
        ctx.lineWidth = 1.4 + t * 0.6;
        ctx.stroke();
      }
    };

    const loop = (ts: number) => {
      if (!running) return;
      raf = requestAnimationFrame(loop);
      if (ts - last < STEP) return;
      last = ts;
      simulate();
      render();
    };
    const start = () => { if (!running) { running = true; last = 0; raf = requestAnimationFrame(loop); } };
    const stop = () => { running = false; cancelAnimationFrame(raf); };

    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) start();
          else stop();
        }
      },
      { threshold: 0.05 }
    );
    io.observe(wrap);

    window.addEventListener("mousemove", onMove, { passive: true });
    canvas.addEventListener("mouseleave", onLeave);
    const onResize = () => build();
    window.addEventListener("resize", onResize);
    render();

    return () => {
      stop();
      io.disconnect();
      window.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("mouseleave", onLeave);
      window.removeEventListener("resize", onResize);
    };
  }, [hasMouse, reduced]);

  return (
    <div className="k-wires" ref={wrapRef}>
      <canvas className="k-wires__canvas" ref={canvasRef} aria-hidden="true" />
      <div className="k-wires__labels">
        {GATES.map((g, j) => (
          <div key={g} className="k-wire-label" style={{ top: baselineY(j) }} data-reticle>
            <span className="k-wire-label__idx">{String(j + 1).padStart(2, "0")}</span>
            {g}
          </div>
        ))}
      </div>
    </div>
  );
}

export function Gates({ data }: { data: LandingData }) {
  const rejections = data.rejections ?? [];
  const hasData = rejections.length > 0;

  return (
    <section className="k-section" aria-labelledby="gates-h">
      <Reveal>
        <p className="k-eyebrow">03 / The gates</p>
        <h2 className="k-h2" id="gates-h">Six gates. None of them can add risk.</h2>
      </Reveal>
      <Reveal delay={80}>
        <p className="k-body">
          Every candidate passes a deterministic screen before it reaches the
          broker. A gate can shrink a position or veto it outright.{" "}
          <strong>No gate can enlarge one.</strong> The model proposes; the code
          disposes.
        </p>
      </Reveal>

      <Reveal delay={120} style={{ marginTop: 24 }}>
        <p className="k-sr">
          Six horizontal wires, one per risk gate: max loss per trade,
          single-name concentration, portfolio delta, daily drawdown breaker,
          open interest floor, and bid-ask spread ceiling.
        </p>
        <Wires />
      </Reveal>

      {hasData ? (
        <Reveal delay={80}>
          <div className="k-table-wrap">
            <div className="k-table-title">Rejections are logged, not silently dropped.</div>
            <table className="k-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Underlying</th>
                  <th className="k-hide-sm">Strategy</th>
                  <th>Gate fired</th>
                  <th className="k-hide-sm">Reason</th>
                </tr>
              </thead>
              <tbody>
                {rejections.map((r) => (
                  <tr key={r.ts + r.underlying} data-reticle>
                    <td className="k-mono">{r.ts}</td>
                    <td className="k-mono">{r.underlying}</td>
                    <td className="k-hide-sm">{r.strategy}</td>
                    <td><span className="k-tag">{r.gate}</span></td>
                    <td className="k-hide-sm">{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <DataCaption data={data} />
        </Reveal>
      ) : (
        <Reveal delay={80}>
          <EmptyNote>
            Real gate rejections — timestamp, underlying, strategy, the gate that
            fired and why — appear here once the agent&rsquo;s journal is connected.
            The dashboard shows current gate activity.
          </EmptyNote>
        </Reveal>
      )}
    </section>
  );
}
