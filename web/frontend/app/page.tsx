"use client";

export const dynamic = "force-dynamic";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase-browser";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      router.replace(data.session ? "/dashboard" : "/login");
    });
  }, [router]);
  return <div className="p-8 text-sm opacity-60">Loading…</div>;
}
