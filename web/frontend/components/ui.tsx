"use client";
import React from "react";

export function Card({
  title,
  children,
  right,
  reticle = true,
}: {
  title?: string;
  children: React.ReactNode;
  right?: React.ReactNode;
  reticle?: boolean;
}) {
  return (
    <div
      className="bg-panel border border-border rounded-2xl p-4"
      {...(reticle ? { "data-reticle": "" } : {})}
    >
      {(title || right) && (
        <div className="flex items-center justify-between mb-3">
          {title && (
            <h2 className="text-[11px] font-medium uppercase tracking-[0.14em] text-axis">
              {title}
            </h2>
          )}
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "pos" | "neg" | "neutral";
}) {
  const color = tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-fg";
  return (
    <div className="bg-panel border border-border rounded-xl p-4" data-reticle>
      <div className="text-[11px] uppercase tracking-[0.14em] text-axis">{label}</div>
      <div className={`text-2xl font-medium mt-2 tabular-nums tracking-tight ${color}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

export function money(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function tone(v: number | null | undefined): "pos" | "neg" | "neutral" {
  if (v == null || v === 0) return "neutral";
  return v > 0 ? "pos" : "neg";
}

export function Btn({
  children,
  onClick,
  variant = "primary",
  disabled,
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const cls =
    variant === "primary"
      ? "bg-accent text-[#05171a] border border-accent hover:bg-[#4fe4ee]"
      : variant === "danger"
        ? "bg-neg/15 text-neg border border-neg/40"
        : "border border-border text-fg hover:border-accentDim hover:text-accent";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`text-xs font-medium rounded-lg px-3 py-1.5 transition-colors disabled:opacity-40 ${cls}`}
    >
      {children}
    </button>
  );
}
