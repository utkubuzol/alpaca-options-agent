"use client";
import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

let _client: SupabaseClient | null = null;

/** Lazily created so the client is never constructed during the build's
 *  static prerender pass (where NEXT_PUBLIC_* env is absent). */
export function getSupabase(): SupabaseClient {
  if (!_client) {
    _client = createBrowserClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    );
  }
  return _client;
}

/** Back-compat proxy so callers can keep using `supabase.auth.…`. */
export const supabase: SupabaseClient = new Proxy({} as SupabaseClient, {
  get(_t, prop) {
    return (getSupabase() as any)[prop];
  },
});
