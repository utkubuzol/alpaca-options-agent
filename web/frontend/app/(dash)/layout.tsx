"use client";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase-browser";
import { Reticle } from "@/components/Reticle";

const NAV = [
  { href: "/dashboard", label: "Overview" },
  { href: "/positions", label: "Positions" },
  { href: "/trades", label: "Trades" },
  { href: "/strategies", label: "Strategies" },
  { href: "/settings", label: "Settings" },
];

export default function DashLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    rootRef.current?.classList.add("js"); // opt into scroll-reveal
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.replace("/login");
        return;
      }
      setEmail(data.session.user.email ?? null);
      setReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) => {
      if (!session) router.replace("/login");
    });
    return () => sub.subscription.unsubscribe();
  }, [router]);

  if (!ready) return <div className="p-8 text-sm text-muted">Loading…</div>;

  return (
    <div ref={rootRef} className="min-h-screen grid grid-cols-[212px_1fr] bg-bg text-fg">
      <Reticle />
      <aside className="border-r border-border bg-panel/40 p-4 flex flex-col gap-1">
        <a
          href="/"
          className="flex items-center gap-2 text-sm font-semibold tracking-[0.22em] mb-5"
        >
          <span className="text-accent">◆</span> KESTREL
        </a>
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            data-reticle
            className={`text-sm rounded-lg px-3 py-2 transition-colors ${
              pathname === n.href
                ? "bg-panel text-accent"
                : "text-muted hover:text-fg"
            }`}
          >
            {n.label}
          </Link>
        ))}
        <div className="mt-auto text-xs text-axis pt-4 break-all">{email}</div>
        <button
          className="text-xs text-muted hover:text-fg underline text-left"
          onClick={async () => {
            await supabase.auth.signOut();
            router.replace("/");
          }}
        >
          Sign out
        </button>
      </aside>
      <main className="p-6 max-w-6xl">{children}</main>
    </div>
  );
}
