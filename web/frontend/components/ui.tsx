"use client";
import React from "react";

export function Card({
  title,
  children,
  right,
}: {
  title?: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <div className="card p-4">
      {(title || right) && (
        <div className="flex items-center justify-between mb-3">
          {title && <h2 className="text-sm font-semibold opacity-80">{title}</h2>}
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
  const color =
    tone === "pos" ? "text-emerald-400" : tone === "neg" ? "text-rose-400" : "";
  return (
    <div className="card p-4">
      <div className="text-xs opacity-60">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${color}`}>{value}</div>
      {sub && <div className="text-xs opacity-50 mt-1">{sub}</div>}
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
      ? "bg-accent text-black"
      : variant === "danger"
        ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
        : "border border-border";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`text-xs font-medium rounded-lg px-3 py-1.5 disabled:opacity-40 ${cls}`}
    >
      {children}
    </button>
  );
}
