"use client";
import { useEffect, useRef } from "react";

// Dashboard page title with the landing's cursor-light behind it.
export function PageHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const light = el.querySelector<HTMLElement>(".cursor-light");
    if (!light) return;
    const onMove = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      light.style.setProperty("--mx", `${e.clientX - r.left}px`);
      light.style.setProperty("--my", `${e.clientY - r.top}px`);
      light.style.opacity = "1";
    };
    const onLeave = () => {
      light.style.opacity = "0";
    };
    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  return (
    <div ref={ref} className="relative -mx-2 px-2 py-1 flex items-center justify-between">
      <span className="cursor-light" />
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {right}
    </div>
  );
}
