"use client";
import { supabase } from "./supabase-browser";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function api<T = any>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = {
    "Content-Type": "application/json",
    ...(await authHeader()),
    ...(init.headers || {}),
  };
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${path}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export function apiGet<T = any>(path: string) {
  return api<T>(path);
}
export function apiSend<T = any>(path: string, method: string, body?: unknown) {
  return api<T>(path, { method, body: body ? JSON.stringify(body) : undefined });
}

/** EventSource can't set headers — pass the token as a query param the
 *  backend also accepts via the standard Authorization dependency is not
 *  possible, so we open the stream with fetch + ReadableStream instead. */
export async function openTradeStream(
  onEvent: (e: any) => void,
  signal: AbortSignal,
) {
  const headers = await authHeader();
  const res = await fetch(`${BASE}/api/trades/stream`, { headers, signal });
  if (!res.body) return;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const chunks = buf.split("\n\n");
    buf = chunks.pop() || "";
    for (const chunk of chunks) {
      const line = chunk.split("\n").find((l) => l.startsWith("data:"));
      if (line) {
        try {
          onEvent(JSON.parse(line.slice(5).trim()));
        } catch {
          /* ignore keep-alive */
        }
      }
    }
  }
}
