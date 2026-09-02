import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Alpaca Options SaaS",
  description: "Monitor trades, PnL, and strategies for the Alpaca options agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
