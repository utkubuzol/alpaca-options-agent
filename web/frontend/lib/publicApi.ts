// Unauthenticated fetch for the public showcase endpoints. No Supabase token,
// returns null on any failure so callers can fall back cleanly.
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function publicGet<T = any>(path: string): Promise<T | null> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 8000);
    const res = await fetch(`${BASE}${path}`, { signal: ctrl.signal });
    clearTimeout(t);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export type Quote = {
  symbol: string;
  price: number;
  prevClose: number;
  changePct: number;
};
