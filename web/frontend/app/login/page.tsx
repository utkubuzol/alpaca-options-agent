"use client";

export const dynamic = "force-dynamic";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase-browser";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState(false);

  // Already signed in? Skip the form, go straight to the dashboard. Lets the
  // landing page's "Open dashboard" CTA point here unconditionally.
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) router.replace("/dashboard");
      else setChecked(true);
    });
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      if (mode === "signup") {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setMsg("Account created. If email confirmation is on, check your inbox, then sign in.");
        setMode("signin");
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.replace("/dashboard");
      }
    } catch (err: any) {
      setMsg(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!checked) return <div className="p-8 text-sm opacity-60">Loading…</div>;

  return (
    <div className="min-h-screen grid place-items-center p-6">
      <form onSubmit={submit} className="card p-6 w-full max-w-sm space-y-4">
        <a href="/" className="text-xs opacity-60 hover:opacity-100">← Kestrel</a>
        <h1 className="text-lg font-semibold">Kestrel</h1>
        <p className="text-xs opacity-60">
          {mode === "signin" ? "Sign in to your dashboard" : "Create an account"}
        </p>
        <input
          className="w-full"
          type="email"
          placeholder="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="w-full"
          type="password"
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={6}
        />
        <button
          className="w-full bg-accent text-black font-medium rounded-lg py-2 disabled:opacity-50"
          disabled={busy}
        >
          {busy ? "…" : mode === "signin" ? "Sign in" : "Sign up"}
        </button>
        <button
          type="button"
          className="w-full text-xs opacity-70 underline"
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
        >
          {mode === "signin" ? "Need an account? Sign up" : "Have an account? Sign in"}
        </button>
        {msg && <p className="text-xs text-amber-400">{msg}</p>}
      </form>
    </div>
  );
}
