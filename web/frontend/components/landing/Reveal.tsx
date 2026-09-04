"use client";
import { useEffect, useRef } from "react";

// Section entrance: opacity + 16px translateY, once, via IntersectionObserver.
// Default (no JS) state is fully visible — the `.js` class on the wrapper is
// what opts an element into the hidden-then-reveal behaviour (see styles.ts),
// so the page is complete and readable with JavaScript disabled.
export function Reveal({
  children,
  className = "",
  as: Tag = "div",
  delay = 0,
  ...rest
}: {
  children: React.ReactNode;
  className?: string;
  as?: keyof JSX.IntrinsicElements;
  delay?: number;
} & React.HTMLAttributes<HTMLElement>) {
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.classList.add("k-reveal--in");
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            if (delay) (e.target as HTMLElement).style.transitionDelay = `${delay}ms`;
            e.target.classList.add("k-reveal--in");
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [delay]);

  const Comp = Tag as any;
  return (
    <Comp ref={ref as any} className={`k-reveal ${className}`} {...rest}>
      {children}
    </Comp>
  );
}
