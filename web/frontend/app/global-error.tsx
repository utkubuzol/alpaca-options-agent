"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          background: "#0b0e14",
          color: "#e6e9ef",
          fontFamily: "system-ui, sans-serif",
          display: "grid",
          placeItems: "center",
          minHeight: "100vh",
          margin: 0,
        }}
      >
        <div style={{ maxWidth: 520, padding: 24 }}>
          <h1 style={{ color: "#fb7185", fontSize: 18 }}>Fatal client error</h1>
          <pre
            style={{
              fontSize: 12,
              whiteSpace: "pre-wrap",
              background: "#141922",
              border: "1px solid #232a36",
              borderRadius: 8,
              padding: 12,
            }}
          >
            {error?.message || String(error)}
          </pre>
          <button onClick={reset} style={{ marginTop: 12, padding: "6px 12px" }}>
            Retry
          </button>
        </div>
      </body>
    </html>
  );
}
