"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase-browser";

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
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
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

  if (!ready) return <div className="p-8 text-sm opacity-60">Loading…</div>;

  return (
    <div className="min-h-screen grid grid-cols-[200px_1fr]">
      <aside className="border-r border-border p-4 flex flex-col gap-1">
        <div className="font-semibold text-sm mb-4">⚡ Options SaaS</div>
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={`text-sm rounded-lg px-3 py-2 ${
              pathname === n.href ? "bg-panel text-accent" : "opacity-70 hover:opacity-100"
            }`}
          >
            {n.label}
          </Link>
        ))}
        <div className="mt-auto text-xs opacity-50 pt-4 break-all">{email}</div>
        <button
          className="text-xs underline opacity-70 text-left"
          onClick={async () => {
            await supabase.auth.signOut();
            router.replace("/login");
          }}
        >
          Sign out
        </button>
      </aside>
      <main className="p-6 max-w-6xl">{children}</main>
    </div>
  );
}
