"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen grid place-items-center p-6">
      <div className="card p-6 max-w-lg space-y-3">
        <h1 className="text-lg font-semibold text-rose-400">Client error</h1>
        <pre className="text-xs whitespace-pre-wrap opacity-80 bg-bg border border-border rounded-lg p-3">
          {error?.message || String(error)}
        </pre>
        <p className="text-xs opacity-60">
          If this mentions a Supabase URL / API key: the{" "}
          <code>NEXT_PUBLIC_SUPABASE_*</code> env vars weren&apos;t set at build
          time. Set them in Vercel (Production scope) and redeploy without build
          cache.
        </p>
        <button
          className="text-xs border border-border rounded-lg px-3 py-1.5"
          onClick={reset}
        >
          Retry
        </button>
      </div>
    </div>
  );
}
